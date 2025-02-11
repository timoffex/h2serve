from __future__ import annotations

import logging
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

peer_ctx: ContextVar[str | None] = ContextVar("peer", default=None)
"""Peer information (address and port) in the context of a connection."""

stream_id_ctx: ContextVar[int | None] = ContextVar("stream_id", default=None)
"""ID of the HTTP/2 stream being processed."""


class ContextualLogger(logging.LoggerAdapter):
    """Logger adapter for the entire package."""

    def __init__(self, logger: logging.Logger) -> None:
        # extra=None is required in Python 3.9.
        super().__init__(logger, extra=None)

    def process(
        self,
        msg: str,
        kwargs: MutableMapping[str, Any],
    ) -> tuple[str, MutableMapping[str, Any]]:
        ctx: dict[str, str] = {}

        if peer := peer_ctx.get():
            ctx["peer"] = peer
        if stream_id := stream_id_ctx.get():
            ctx["stream"] = str(stream_id)

        if not ctx:
            return msg, kwargs

        ctx_str = " ".join(f"{name}={value}" for name, value in ctx.items())
        return f"[{ctx_str}] {msg}", kwargs
