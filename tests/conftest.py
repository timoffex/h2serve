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
        http2_settings: Initial server HTTP/2 setting overrides.

    Returns:
        An HTTP2Tester instance.
    """

    async def fn(
        app,
        *,
        initiated=False,
        http2_settings=None,
        ssl_server=None,
        ssl_client=None,
    ) -> http2tester.HTTP2Tester:
        if not ssl_server:
            ssl_server = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
            ssl_server.load_cert_chain("localhost.pem")
            ssl_server.set_alpn_protocols(["h2"])

        server = await h2serve.serve(
            nursery,
            app,
            host="localhost",
            port=0,
            ssl_context=ssl_server,
            http2_settings=http2_settings,
        )

        if not ssl_client:
            ssl_client = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
            ssl_client.load_verify_locations("localhost.pem")
            ssl_client.set_alpn_protocols(["h2"])

        stream = await trio.open_ssl_over_tcp_stream(
            "localhost",
            server.localhost_port,
            ssl_context=ssl_client,
        )

        tester = http2tester.HTTP2Tester(server, stream)

        if initiated:
            await tester.initiate_connection()
            await tester.expect(hyperframe.frame.SettingsFrame)  # Server
            await tester.expect(hyperframe.frame.SettingsFrame)  # Client ack

        return tester

    return fn
