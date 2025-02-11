from __future__ import annotations

import functools
import logging
import ssl
from typing import cast

import h2.settings
import trio

from ._app_handler import AppHandler
from ._conn_handler import HTTP2ConnectionHandler
from ._logging import ContextualLogger

_logger = ContextualLogger(logging.getLogger(__name__))


INETSocketAddr = tuple[str, int] | tuple[str, int, int, int]
"""An IPv4 (host, port) or an IPv6 (host, port, flowinfo, scope_id).

See the Python socket module's descriptions of the AF_INET and AF_INET6
socket families.
"""


class Server:
    def __init__(
        self,
        cancel_scope: trio.CancelScope,
        addresses: list[INETSocketAddr],
    ) -> None:
        self._cancel_scope = cancel_scope
        self._addresses = addresses

    @property
    def addresses(self) -> list[INETSocketAddr]:
        """All addresses on which new connections are being accepted."""
        return self._addresses

    @property
    def localhost_port(self) -> int:
        """The port on localhost on which the server accepts connections.

        Raises:
            ValueError: If the server is not running on localhost.
        """
        for host, port, *_ in self.addresses:
            if host in ("localhost", "127.0.0.1"):
                return port

        raise ValueError("The server is not running on localhost.")

    def stop(self) -> None:
        """Close all connections and cancel all handlers.

        After calling this, the server can no longer be used.
        Calling this method again is a no-op.
        """
        self._cancel_scope.cancel()


async def serve(
    nursery: trio.Nursery,
    app: AppHandler,
    *,
    host: str | bytes | None,
    port: int,
    ssl_context: ssl.SSLContext,
    http2_settings: dict[h2.settings.SettingCodes | int, int] | None = None,
) -> Server:
    """Start an HTTP/2 server.

    Args:
        nursery: Parent nursery for the server.
        app: The application logic to run on every request.
        host: The host to pass to `trio.open_ssl_over_tcp_listeners`. For local testing,
            you often want the string "localhost" or "127.0.0.1", or your IP address
            on your local network (e.g. "192.168.0.<X>"). See the `trio` documentation
            for more.
        port: The port to listen on, or 0 to allow the OS to pick a port for you.
        ssl_context: The SSL context to use. It must be a server context (purpose
            set to `ssl.Purpose.CLIENT_AUTH`) with ALPN protocols set to ["h2"].
        http2_settings: Initial settings to use on new connections.
            Unspecified settings use their default values.

    Returns:
        A handle to the server.
    """
    server = await nursery.start(
        functools.partial(
            _serve,
            app,
            host=host,
            port=port,
            ssl_context=ssl_context,
            http2_settings=http2_settings,
        )
    )

    assert isinstance(server, Server)
    return server


async def _serve(
    app: AppHandler,
    host: str | bytes | None,
    port: int,
    ssl_context: ssl.SSLContext,
    http2_settings: dict[h2.settings.SettingCodes | int, int] | None,
    *,
    task_status: trio.TaskStatus[Server] = trio.TASK_STATUS_IGNORED,
) -> None:
    listeners = await trio.open_ssl_over_tcp_listeners(
        port,
        ssl_context,
        host=host,
    )

    addresses: list[INETSocketAddr] = []
    for listener in listeners:
        sockstream = cast(trio.SocketStream, listener.transport_listener)
        addresses.append(sockstream.socket.getsockname())
    _logger.info("Listening on %s", addresses)

    cancel_scope = trio.CancelScope()
    task_status.started(
        Server(
            cancel_scope=cancel_scope,
            addresses=addresses,
        )
    )

    async def handle(stream: trio.SSLStream[trio.SocketStream]) -> None:
        await HTTP2ConnectionHandler(stream, app).handle_no_except(
            initial_settings=http2_settings
        )

    with cancel_scope:
        await trio.serve_listeners(handle, listeners)
