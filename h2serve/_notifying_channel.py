from __future__ import annotations

import trio
from typing_extensions import override


def notifying_channel(
    buffer: int | float,
) -> tuple[NotifyingSendChannel, NotifyingReceiveChannel]:
    """A channel that notifies when values are read from it.

    Unlike a regular buffered channel which blocks all sends when the buffer
    is full, this one allows treating some sends differently. This is important
    for HTTP/2, where we want to have backpressure for DATA frames but don't want
    to block the read loop. When sending a DATA frame on a stream, we pass an
    event and wait on it, blocking that stream from generating more data.
    """
    send, recv = trio.open_memory_channel[tuple[bytes, trio.Event | None]](buffer)
    return (
        NotifyingSendChannel(send),
        NotifyingReceiveChannel(recv),
    )


class NotifyingSendChannel:
    """The sender side of a notifying channel of bytes."""

    def __init__(
        self,
        chan: trio.MemorySendChannel[tuple[bytes, trio.Event | None]],
    ) -> None:
        self._chan = chan

    async def send(self, data: bytes, event: trio.Event | None) -> None:
        """Send data on the channel.

        Args:
            data: The data to send.
            event: An event that is signalled when that data is received.
        """
        await self._chan.send((data, event))

    def close(self) -> None:
        """Close the underlying channel, making future send operations fail.

        The receiving end of the channel will raise an EndOfChannel exception
        after it is drained.
        """
        self._chan.close()


class NotifyingReceiveChannel(trio.abc.ReceiveChannel[bytes]):
    """A readable channel of bytes."""

    def __init__(
        self,
        chan: trio.MemoryReceiveChannel[tuple[bytes, trio.Event | None]],
    ) -> None:
        self._chan = chan

    @override
    async def receive(self) -> bytes:
        data, event = await self._chan.receive()

        if event:
            event.set()

        return data

    @override
    async def aclose(self) -> None:
        await self._chan.aclose()

    def close(self) -> None:
        """Close the underlying channel, making future receive operations fail."""
        self._chan.close()
