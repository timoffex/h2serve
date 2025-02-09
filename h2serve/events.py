from __future__ import annotations

import dataclasses


class ServerEvent:
    """An event of interest on the server."""


INETSocketAddr = tuple[str, int] | tuple[str, int, int, int]


@dataclasses.dataclass(frozen=True)
class ConnectionError(ServerEvent):
    """A connection was closed due to an error."""

    peer: INETSocketAddr
    exc: Exception


@dataclasses.dataclass(frozen=True)
class StreamError(ServerEvent):
    """A stream was closed due to an error."""

    peer: INETSocketAddr
    stream_id: int
    exc: Exception
