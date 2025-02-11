import ssl

from .http2tester import HTTP2Tester


async def test_fails_no_alpn_protocol(
    start_test_server,
    caplog,
    expect_soon,
) -> None:
    async def app(req, resp):
        pass

    ssl_server = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    ssl_server.load_cert_chain("localhost.pem")
    ssl_server.set_alpn_protocols(["h2"])

    ssl_client = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ssl_client.load_verify_locations("localhost.pem")
    ssl_client.set_alpn_protocols(["http/1.1"])

    tester: HTTP2Tester = await start_test_server(
        app,
        ssl_server=ssl_server,
        ssl_client=ssl_client,
    )

    # Perform the handshake.
    await tester.stream.do_handshake()

    # Check that the server closes the connection and logs an error.
    assert not await tester.stream.receive_some()

    def assert_message():
        assert "No ALPN protocol negotiated." in caplog.text

    await expect_soon(assert_message)


async def test_fails_invalid_alpn_protocol(
    start_test_server,
    caplog,
    expect_soon,
) -> None:
    async def app(req, resp):
        pass

    ssl_server = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    ssl_server.load_cert_chain("localhost.pem")
    ssl_server.set_alpn_protocols(["http/1.1"])

    ssl_client = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ssl_client.load_verify_locations("localhost.pem")
    ssl_client.set_alpn_protocols(["http/1.1"])

    tester: HTTP2Tester = await start_test_server(
        app,
        ssl_server=ssl_server,
        ssl_client=ssl_client,
    )

    # Perform the handshake.
    await tester.stream.do_handshake()

    # Check that the server closes the connection and logs an error.
    assert not await tester.stream.receive_some()

    def assert_message():
        assert "Invalid protocol selected: http/1.1" in caplog.text

    await expect_soon(assert_message)
