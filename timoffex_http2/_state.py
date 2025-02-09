from __future__ import annotations

import contextlib
from typing import AsyncIterator

import h2.config
import h2.connection
import trio

from ._notifying_channel import NotifyingSendChannel


class HTTP2State:
    """A concurrency-aware wrapper around the HTTP/2 state.

    This provides the `use` context manager for locking and accessing
    the state value, after which any new data is flushed to an output channel.
    The `wait_for_change` method allows temporarily releasing the lock and
    blocking until another task calls `use`.

    Usable as a context manager to close the output channel's send side.
    """

    def __init__(
        self,
        out: NotifyingSendChannel,
    ):
        """Initiate the state.

        Args:
            out: The channel to which to push data to write. If the channel is blocking,
                the receiver must implement timeouts and promptly close the channel
                on any timeout or write error. This is important because a part of `use`
                shields itself from cancellation.
        """
        self._outfifo = trio.StrictFIFOLock()
        self._out = out

        config = h2.config.H2Configuration(client_side=False)
        self._h2_state = h2.connection.H2Connection(config)
        self._h2_state_cond = trio.Condition()

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type, exc, tb) -> None:
        self._out.close()

    @contextlib.asynccontextmanager
    async def use(
        self,
        block_on_send: bool = False,
    ) -> AsyncIterator[h2.connection.H2Connection]:
        """Read or mutate the connection state.

        Any new data to send is put on the out-channel at the end.
        If `block_on_send` is True, this blocks until the data is read
        from the channel, which creates backpressure.

        Raises:
            trio.ClosedResourceError: If we are unable to flush data, meaning that
                the connection has been closed.
        """
        async with self._h2_state_cond:
            yield self._h2_state
            send_event = trio.Event() if block_on_send else None

            self._h2_state_cond.notify_all()
            data = self._h2_state.data_to_send()

        if data:
            # Cancelling would discard frames and put us in an invalid state,
            # so we shield. We expect the _out channel receiver to implement
            # timeouts and close itself if it is blocked too long.
            with trio.CancelScope(shield=True):
                async with self._outfifo:
                    await self._out.send(data, send_event)

            if send_event:
                await send_event.wait()

    async def wait_for_change(self) -> None:
        """Wait for the connection state to change.

        This can only be used inside the `use()` context manager.
        """
        await self._h2_state_cond.wait()
