from __future__ import annotations

import ssl

import hyperframe.frame
import pytest
import trio

import h2serve
from . import http2tester


@pytest.fixture
def start_test_server(nursery: trio.Nursery):
    """Start a server for the duration of the test.

    Args:
        app: The handler to run on the server.
        initiated: Whether to initiate the connection and handle the initial
            frames. Defaults to False.

    Returns:
        An HTTP2Tester instance.
    """

    async def fn(
        app,
        *,
        server_events=None,
        initiated=False,
    ) -> http2tester.HTTP2Tester:
        server = await h2serve.serve(
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

        tester = http2tester.HTTP2Tester(server, stream)

        if initiated:
            await tester.initiate_connection()
            await tester.expect(hyperframe.frame.SettingsFrame)  # Server
            await tester.expect(hyperframe.frame.SettingsFrame)  # Client ack

        return tester

    return fn
