import hyperframe.frame

from tests.http2tester import HTTP2Tester


async def test_response_before_receiving_full_request(start_test_server) -> None:
    async def app(req, resp):
        await req.body.aclose()
        await req.trailers.aclose()
        await resp.headers(200, headers=[], end_stream=True)

    tester: HTTP2Tester = await start_test_server(app)
    await tester.initiate_connection()
    await tester.expect(hyperframe.frame.SettingsFrame)  # Server settings
    await tester.expect(hyperframe.frame.SettingsFrame)  # Client settings ack

    # STEP 1. Send headers for a request.
    stream_id = tester.new_stream_id()
    await tester.send_headers(
        stream_id,
        [
            (":method", "GET"),
            (":authority", "localhost"),
            (":scheme", "https"),
            (":path", "/"),
        ],
        end_stream=False,
    )

    # The response is received despite the request not being fully sent.
    headers = await tester.expect(hyperframe.frame.HeadersFrame)
    assert "END_STREAM" in headers.flags

    # STEP 2. Finish the request.
    await tester.send_data(stream_id, b"abc", end_stream=False)
    await tester.send_headers(stream_id, [("X_MY_TRAILER", "123")], end_stream=True)

    # Ensure no other frames are generated.
    await tester.ping_and_expect_pong()
