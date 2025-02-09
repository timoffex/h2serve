from __future__ import annotations

import logging
import math
from typing import Iterable

import hpack
import trio

from ._app_handler import AppHandler
from ._request import DataChunk, Header, HTTP2Request, unbuffered_data_chunk_channel
from ._response import HTTP2Response
from ._state import HTTP2State
from ._logging import ContextualLogger

_logger = ContextualLogger(logging.getLogger(__name__))


class HTTP2StreamHandler:
    """A handler for a single stream in an HTTP/2 connection."""

    def __init__(
        self,
        state: HTTP2State,
        stream_id: int,
        headers: Iterable[hpack.HeaderTuple],
    ) -> None:
        self._state = state
        self.id = stream_id
        self._headers = [Header(name, value) for (name, value) in headers]

        self._nursery: trio.Nursery | None = None

        # We use HTTP/2 flow control to bound the memory usage of request data.
        # The h2 package raises errors if the client sends more data than it's allowed.
        body_in, body_out = unbuffered_data_chunk_channel()
        self._req_body_in = body_in
        self._req_body_out = body_out
        self._req_body_fifo = trio.StrictFIFOLock()

        # We also allow infinite-buffering of trailers.
        # TODO: Does anything bound this memory usage?
        trailers_in, trailers_out = trio.open_memory_channel[Header](math.inf)
        self._trailers_in = trailers_in
        self._trailers_out = trailers_out

    async def run(self, app: AppHandler) -> None:
        """Run application logic to respond to a request.

        Raises:
            Exception: Any error from the application handler. The stream is not
                automatically reset when this happens.
        """
        async with trio.open_nursery() as self._nursery:
            req = HTTP2Request(
                self._headers,
                self._req_body_out,
                self._trailers_out,
            )

            resp = HTTP2Response(
                self.id,
                self._state,
            )

            await app(req, resp)

            # In case the client fails to end the stream, make sure we do it.
            if not resp.ended:
                _logger.warn(
                    "Application did not properly end stream."
                    " Sending an empty DATA frame with the END_STREAM flag."
                )
                async with self._state.use() as state:
                    state.end_stream(self.id)

    def cancel(self) -> None:
        """Cancel the application logic for the stream."""
        if not self._nursery:
            return

        self._nursery.cancel_scope.cancel()

    def push_data(self, data: bytes, flow_controlled_length: int) -> None:
        """Push a request body chunk to the app."""
        assert self._nursery

        ack_event = trio.Event()

        async def handle_ack():
            await ack_event.wait()
            async with self._state.use() as state:
                state.acknowledge_received_data(
                    flow_controlled_length,
                    self.id,
                )

        self._nursery.start_soon(handle_ack)

        try:
            self._req_body_in.send_nowait(DataChunk(data, ack_event))
        except trio.ClosedResourceError:
            # This means the handler will not read the rest of the body,
            # so we can simply ack the data.
            ack_event.set()
            return

    def push_trailers(self, trailers: Iterable[hpack.HeaderTuple]) -> None:
        """Push request trailers to the app."""
        try:
            for name, value in trailers:
                self._trailers_in.send_nowait(Header(name, value))
        except trio.ClosedResourceError:
            # This means the handler will not read the rest of the trailers.
            return

    def mark_complete(self) -> None:
        """Indicate that the request has been fully received."""
        self._req_body_in.close()
        self._trailers_in.close()
