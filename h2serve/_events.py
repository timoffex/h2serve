from contextvars import ContextVar
import logging

import trio

from . import events
from ._logging import ContextualLogger


_logger = ContextualLogger(logging.getLogger(__name__))


server_events: ContextVar[trio.abc.SendChannel[events.ServerEvent] | None] = ContextVar(
    "server_events",
    default=None,
)


async def log_event(event: events.ServerEvent) -> None:
    if not (chan := server_events.get()):
        return

    try:
        await chan.send(event)

    except trio.ClosedResourceError:
        # If the receiver side is closed, we stop sending.
        server_events.set(None)
        _logger.info("Server event channel is closed, won't sent more events.")

    except Exception as e:
        # On any other error, also stop sending, but log it as an exception.
        server_events.set(None)
        _logger.exception("Error logging server event.", exc_info=e)
