from __future__ import annotations

import ssl

import pytest
import trio

import timoffex_http2

from tests import http2tester


@pytest.fixture
def start_test_server(nursery: trio.Nursery):
    """Start a server for the duration of the test.

    Args:
        app: The handler to run on the server.

    Returns:
        An HTTP2Tester instance.
    """

    async def fn(app, *, server_events=None) -> http2tester.HTTP2Tester:
        server = await timoffex_http2.serve(
            nursery,
            app,
            host="localhost",
            port=0,
            server_events=server_events,
        )

        ssl_ctx = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cafile="localhost.pem",
        )
        ssl_ctx.set_alpn_protocols(["h2"])

        stream = await trio.open_ssl_over_tcp_stream(
            "localhost",
            server.localhost_port,
            ssl_context=ssl_ctx,
        )

        return http2tester.HTTP2Tester(server, stream)

    return fn
