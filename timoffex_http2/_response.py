from __future__ import annotations

from typing import Iterable

from ._state import HTTP2State


class HTTP2Response:
    """An HTTP/2 response writer."""

    def __init__(self, stream_id: int, state: HTTP2State):
        self._id = stream_id
        self._state = state

        self._ended = False

    @property
    def ended(self) -> bool:
        """Whether a frame with END_STREAM was emitted."""
        return self._ended

    async def interim(
        self,
        status_1xx: int,
        headers: Iterable[tuple[bytes, bytes]],
    ) -> None:
        """Send an informational (1xx) status.

        This may be called zero or more times before any other methods.

        Args:
            status_1xx: The 100-level HTTP status code to send.
            headers: Other headers to include.
        """
        if not (100 <= status_1xx < 200):
            raise ValueError(
                f"The interim response must use a 100-level status code;"
                f" received {status_1xx}."
            )

        async with self._state.use(block_on_send=True) as state:
            state.send_headers(
                self._id,
                [
                    (":status", str(status_1xx)),
                    *headers,
                ],
            )

    async def headers(
        self,
        status: int,
        headers: Iterable[tuple[bytes, bytes]],
        *,
        end_stream: bool = False,
    ) -> None:
        """Send response headers.

        This must be called exactly once per response, after any interim responses.

        Args:
            status: The HTTP status code to send.
            headers: Other headers to include.
            end_stream: If true, indicates that there is no response body or trailers.
        """
        async with self._state.use(block_on_send=True) as state:
            state.send_headers(
                self._id,
                [
                    (":status", str(status)),
                    *headers,
                ],
                end_stream=end_stream,
            )

        if end_stream:
            self._ended = True

    async def body(
        self,
        data: bytes,
        *,
        end_stream: bool = False,
    ) -> None:
        """Send the response body.

        This may be called zero or more times after sending response headers
        with end_stream=False.

        This blocks until the response is accepted by the client's flow control
        settings. The data may be broken up across more than one DATA frame
        depending on the client's flow control window.

        Args:
            data: The raw data to send.
            end_stream: If true, there is no more response body and no trailers.
        """
        # Avoid reallocating when slicing.
        data = memoryview(data)

        if not data and end_stream:
            async with self._state.use() as state:
                state.send_data(self._id, b"", end_stream=True)

        while len(data) > 0:
            async with self._state.use(block_on_send=True) as state:
                while (limit := state.local_flow_control_window(self._id)) <= 0:
                    await self._state.wait_for_change()

                state.send_data(
                    self._id,
                    data[:limit],
                    end_stream=end_stream and limit >= len(data),
                )
                data = data[limit:]

        if end_stream:
            self._ended = True

    async def trailers(self, trailers: Iterable[tuple[bytes, bytes]]) -> None:
        """Send response trailers.

        This may be called once after the response headers and body have been sent
        with end_stream=False.

        Calling this always ends the stream.

        Args:
            trailers: Header tuples to send.
        """
        async with self._state.use(block_on_send=True) as state:
            state.send_headers(
                self._id,
                trailers,
                end_stream=True,
            )

        self._ended = True

    async def end(self) -> None:
        """Indicate that the entire response has been emitted.

        This can be used instead of passing the end_stream argument to
        other methods. It may be used after using `trailers`, but is a no-op.
        """
        if not self._ended:
            async with self._state.use(block_on_send=True) as state:
                state.end_stream(self._id)

            self._ended = True
