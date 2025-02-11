import contextlib
import random
from collections.abc import Iterator
from typing import TypeVar

import h2.connection
import h2.settings
import hyperframe.frame
import trio

import h2serve


@contextlib.contextmanager
def _timeout(msg: str) -> Iterator[None]:
    try:
        with trio.fail_after(1):
            yield
    except trio.TooSlowError as e:
        raise AssertionError(msg) from e


_FrameType = TypeVar("_FrameType", bound=hyperframe.frame.Frame)


class HTTP2Tester:
    def __init__(
        self,
        server: h2serve.Server,
        stream: trio.SSLStream,
    ) -> None:
        self._server = server
        self.stream = stream
        self._conn = h2.connection.H2Connection()

    async def expect(self, frame_type: type[_FrameType]) -> _FrameType:
        """Assert that the next HTTP/2 frame has a given type.

        Args:
            frame_type: The hyperframe class representing the expected
                HTTP/2 frame type.

        Returns:
            The parsed frame.

        Raises:
            AssertionError: If the next frame is of the wrong type.
                After this, the tester is in an invalid state and must not be used.
            Exception: Other exceptions are possible due to connection issues
                and data validity issues.
        """
        with _timeout(f"Did not receive frame of type {frame_type}."):
            header = await self._receive_exactly(9)
            frame, body_len = hyperframe.frame.Frame.parse_frame_header(
                memoryview(header),
                strict=True,
            )

            if not isinstance(frame, frame_type):
                raise AssertionError(
                    f"Expected frame of type {frame_type} but got {type(frame)}"
                )

            body = await self._receive_exactly(body_len)
            frame.parse_body(memoryview(body))

            self._conn.receive_data(header + body)
            await self._flush()

            return frame

    async def ping_and_expect_pong(self) -> None:
        """Send a PING and expect a PING as the next incoming frame."""
        opaque = random.randbytes(8)
        await self.ping(opaque)
        pong = await self.expect(hyperframe.frame.PingFrame)
        assert pong.opaque_data == opaque

    async def _receive_exactly(self, n: int) -> bytes:
        chunks: list[bytes | bytearray] = []
        total_read = 0

        while total_read < n:
            data = await self.stream.receive_some(n - total_read)
            if not data:
                raise AssertionError(f"Stream closed before {n} bytes could be read.")

            total_read += len(data)
            chunks.append(data)

        return b"".join(chunks)

    def new_stream_id(self) -> int:
        return self._conn.get_next_available_stream_id()

    async def initiate_connection(self) -> None:
        self._conn.initiate_connection()
        await self._flush()

    async def update_settings(
        self,
        updates: dict[h2.settings.SettingCodes | int, int],
    ) -> None:
        self._conn.update_settings(updates)
        await self._flush()

    async def acknowledge_received_data(
        self,
        acknowledged_size: int,
        stream_id: int,
    ) -> None:
        self._conn.acknowledge_received_data(acknowledged_size, stream_id)
        await self._flush()

    async def start_request(
        self,
        method: str,
        path: str,
        *,
        extra_headers: list[tuple[str, str]] | None = None,
        end_stream: bool,
    ) -> int:
        """Send headers for a standard HTTP request.

        The authority is localhost and the scheme is https.

        Args:
            method: The HTTP :method header.
            path: The :path header.

        Returns:
            Stream ID for the new request.
        """
        stream_id = self.new_stream_id()
        await self.send_headers(
            stream_id,
            headers=[
                (":method", method),
                (":path", path),
                (":authority", "localhost"),
                (":scheme", "https"),
                *(extra_headers or []),
            ],
            end_stream=end_stream,
        )
        return stream_id

    async def send_headers(self, *args, **kwargs) -> None:
        self._conn.send_headers(*args, **kwargs)
        await self._flush()

    async def send_data(self, *args, **kwargs):
        self._conn.send_data(*args, **kwargs)
        await self._flush()

    async def end_stream(self, stream_id: int) -> None:
        self._conn.end_stream(stream_id)
        await self._flush()

    async def reset_stream(self, stream_id: int) -> None:
        self._conn.reset_stream(stream_id)
        await self._flush()

    async def ping(self, *args, **kwargs):
        self._conn.ping(*args, **kwargs)
        await self._flush()

    async def _flush(self):
        with _timeout("Timed out."):
            await self.stream.send_all(self._conn.data_to_send())
