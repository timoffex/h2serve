from __future__ import annotations

import logging

import h2.config
import h2.connection
import h2.events
import h2.exceptions
import trio
from h2.errors import ErrorCodes

from ._app_handler import AppHandler
from ._notifying_channel import notifying_channel
from ._state import HTTP2State
from ._stream_handler import HTTP2StreamHandler
from ._logging import ContextualLogger, peer_ctx, stream_id_ctx
from . import _events, events

_logger = ContextualLogger(logging.getLogger(__name__))


# Allow up to 100 outgoing data chunks to accumulate (likely <=100 frames)
# before blocking.
#
# Try to send data for up to 5 minutes before giving up.
_OUTGOING_BUFFER = 100
_OUTGOING_TIMEOUT = 60 * 5


class HTTP2ConnectionHandler:
    """Runs an HTTP/2 server over a TLS stream."""

    def __init__(
        self,
        conn: trio.SSLStream[trio.SocketStream],
        app: AppHandler,
    ) -> None:
        self._conn_scope = trio.CancelScope()

        self._conn = conn
        self._app = app

        self._peer = conn.transport_stream.socket.getpeername()
        peer_ctx.set(self._peer)

        outgoing_data_in, outgoing_data_out = notifying_channel(_OUTGOING_BUFFER)
        self._outgoing_data = outgoing_data_out
        self._state = HTTP2State(outgoing_data_in)

        self._streams: dict[int, HTTP2StreamHandler] = dict()

    async def handle_no_except(self) -> None:
        """Process the stream.

        This returns when the stream is closed, for example if the connection is
        closed by us or the peer. Exceptions are logged and do not bubble up.
        """
        try:
            await self._handle()

        except Exception as e:
            _logger.exception("Encountered error.", exc_info=e)
            await _events.log_event(events.ConnectionError(peer=self._peer, exc=e))

        else:
            _logger.info("Reached end.")

    async def _handle(self) -> None:
        try:
            _logger.info("New connection.")

            await self._conn.do_handshake()
            _logger.info("Handshake succeeded.")

            await self._validate_http2_connection()
            _logger.info("Valid HTTP/2 setup.")

            with self._conn_scope:
                async with trio.open_nursery() as write_scope:
                    with self._state:
                        write_scope.start_soon(self._loop_write)

                        async with self._state.use() as state:
                            state.initiate_connection()

                        async with trio.open_nursery() as handler_nursery:
                            await self._loop_read(handler_nursery)

        finally:
            _logger.info("Trying to gracefully close TCP connection...")
            await self._conn.aclose()
            _logger.info("Closed gracefully.")

    async def _validate_http2_connection(self) -> None:
        """Validate that a connection is ready for HTTP/2.

        Raises an error if the connection is not valid.
        """
        # _stream forwards ssl.SSLObject methods.
        tls_version = self._conn.version()
        if tls_version not in ("TLSv1.2", "TLSv1.3"):
            raise ValueError(
                f"Unrecognized TLS version: {tls_version}. HTTP/2 requires TLS 1.2+."
            )

        alpn = self._conn.selected_alpn_protocol()

        if not alpn:
            raise ValueError("No ALPN protocol negotiated.")
        if alpn != "h2":
            raise ValueError(f"Invalid protocol selected: {alpn}")

    async def _loop_write(self) -> None:
        # NOTE: The contract of HTTP2State requires we close _outgoing_data
        #   on any failure to send data.
        async with self._outgoing_data:
            async for data in self._outgoing_data:
                with trio.fail_after(_OUTGOING_TIMEOUT):
                    await self._conn.send_all(data)

    async def _loop_read(
        self,
        handler_nursery: trio.Nursery,
    ) -> None:
        while True:
            data = await self._conn.receive_some()
            if not data:
                _logger.info("Reached end of TCP connection.")
                return

            async with self._state.use() as state:
                try:
                    events = state.receive_data(data)

                except h2.exceptions.ProtocolError as e:
                    _logger.exception("Protocol error.", exc_info=e)

                    # TODO: Is this necessary, or is it automatic?
                    state.close_connection(e.error_code)

                    return

            for event in events:
                if isinstance(event, h2.events.ConnectionTerminated):
                    self._conn_scope.cancel()
                    return

                else:
                    self._process_event(event, handler_nursery)

    def _process_event(
        self,
        event: h2.events.Event,
        handler_nursery: trio.Nursery,
    ) -> None:
        if isinstance(event, h2.events.RequestReceived):
            stream = HTTP2StreamHandler(
                self._state,
                event.stream_id,
                event.headers,
            )

            # We expect h2 to raise an error if the stream already exists.
            self._streams[event.stream_id] = stream
            handler_nursery.start_soon(self._run_stream_handler, stream)

        elif isinstance(event, h2.events.DataReceived):
            # NOTE: We can receive data after we have sent a full response.
            if event.stream_id in self._streams:
                stream = self._streams[event.stream_id]
                stream.push_data(event.data, event.flow_controlled_length)

        elif isinstance(event, h2.events.TrailersReceived):
            # NOTE: We can receive trailers after we have sent a full response.
            if event.stream_id in self._streams:
                stream = self._streams[event.stream_id]
                stream.push_trailers(event.headers)

        elif isinstance(event, h2.events.StreamEnded):
            if event.stream_id in self._streams:
                self._streams[event.stream_id].mark_complete()

        elif isinstance(event, h2.events.StreamReset):
            if event.stream_id in self._streams:
                self._streams[event.stream_id].cancel()

    async def _run_stream_handler(self, stream: HTTP2StreamHandler) -> None:
        stream_id_ctx.set(stream.id)

        try:
            await stream.run(self._app)

        except Exception as e:
            _logger.exception("Stream ended due to exception.", exc_info=e)

            await _events.log_event(
                events.StreamError(
                    peer=self._peer,
                    stream_id=stream.id,
                    exc=e,
                )
            )

            # NOTE: If the stream ended because the connection is dead, this will
            #   also error out, cancelling all stream handlers in the nursery.
            async with self._state.use() as state:
                state.reset_stream(
                    stream.id,
                    error_code=ErrorCodes.INTERNAL_ERROR,
                )

        finally:
            del self._streams[stream.id]
