from __future__ import annotations

import dataclasses
import math
from typing_extensions import override

import trio


class HTTP2Request:
    """An HTTP/2 request.

    All attributes are read-only and must not be modified.

    Attributes:
        headers: All request headers, in order.
        body: A channel of request body chunks. Reading from it raises EndOfChannel
            after all data has been received. Closing it indicates that the rest of
            the body can be discarded. Every received chunk must be acknowledged by
            setting its `ack` event to emit window updates; failing to do so can result
            in a deadlock if flow control is used.
        trailers: A channel of trailers, closed after the entire request is received.
            This must not be read until the body has been fully read or closed.
            Reading from it raises EndOfChannel after the entire request has been
            received. Closing it indicates that any trailers can be discarded.
    """

    def __init__(
        self,
        headers: list[Header],
        body: trio.abc.ReceiveChannel[DataChunk],
        trailers: trio.abc.ReceiveChannel[Header],
    ):
        self.headers = headers
        self.body = body
        self.trailers = trailers


@dataclasses.dataclass(frozen=True)
class Header:
    name: bytes
    value: bytes


@dataclasses.dataclass(frozen=True)
class DataChunk:
    data: bytes
    ack: trio.Event


def unbuffered_data_chunk_channel() -> tuple[
    trio.MemorySendChannel[DataChunk],
    DataChunkReceiveChannel,
]:
    send, recv = trio.open_memory_channel[DataChunk](math.inf)
    return send, DataChunkReceiveChannel(recv)


class DataChunkReceiveChannel(trio.abc.ReceiveChannel[DataChunk]):
    """Wraps a receive channel to ack all buffered data chunks on close."""

    def __init__(self, chan: trio.MemoryReceiveChannel[DataChunk]) -> None:
        self._chan = chan

    def close(self) -> None:
        self._ack_all()
        self._chan.close()

    @override
    async def aclose(self) -> None:
        self._ack_all()
        await self._chan.aclose()

    @override
    async def receive(self) -> DataChunk:
        return await self._chan.receive()

    def _ack_all(self) -> None:
        """Acknowledge all buffered chunks."""
        while True:
            try:
                chunk = self._chan.receive_nowait()
                chunk.ack.set()
            except (trio.WouldBlock, trio.EndOfChannel):
                return
