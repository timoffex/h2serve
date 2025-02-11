import hyperframe.frame
import trio

import h2serve

from .http2tester import HTTP2Tester


class _TestError(Exception):
    """An expected error in a test."""


async def test_passes_request_to_app(start_test_server) -> None:
    received_req_headers: list[h2serve.Header] = []
    received_req_body: bytes = b""
    received_req_trailers: list[h2serve.Header] = []

    async def app(req, resp):
        nonlocal received_req_headers, received_req_body, received_req_trailers
        received_req_headers = req.headers

        async for chunk in req.body:
            received_req_body += chunk.data
            chunk.ack.set()

        async for trailer in req.trailers:
            received_req_trailers.append(trailer)

        await resp.headers(200, headers=[], end_stream=True)

    tester: HTTP2Tester = await start_test_server(app, initiated=True)

    stream_id = await tester.start_request(
        "GET",
        "/",
        extra_headers=[("X_TEST_HEADER", "123")],
        end_stream=False,
    )
    await tester.send_data(stream_id, b"testing", end_stream=False)
    await tester.send_headers(
        stream_id,
        headers=[("X_TEST_TRAILER", "321")],
        end_stream=True,
    )

    await tester.expect(hyperframe.frame.HeadersFrame)

    assert (b"x_test_header", b"123") in received_req_headers
    assert (b":path", b"/") in received_req_headers
    assert (b":method", b"GET") in received_req_headers
    assert received_req_body == b"testing"
    assert received_req_trailers == [(b"x_test_trailer", b"321")]


async def test_response_before_receiving_full_request(start_test_server) -> None:
    async def app(req, resp):
        await req.body.aclose()
        await req.trailers.aclose()
        await resp.headers(200, headers=[], end_stream=True)

    tester: HTTP2Tester = await start_test_server(app, initiated=True)

    # STEP 1. Send headers for a request.
    stream_id = tester.new_stream_id()
    await tester.start_request("POST", "/", end_stream=False)

    # The response is received despite the request not being fully sent.
    headers = await tester.expect(hyperframe.frame.HeadersFrame)
    assert "END_STREAM" in headers.flags

    # STEP 2. Finish the request.
    await tester.send_data(stream_id, b"abc", end_stream=False)
    await tester.send_headers(stream_id, [("X_MY_TRAILER", "123")], end_stream=True)

    # Ensure no other frames are generated.
    await tester.ping_and_expect_pong()


async def test_ends_stream_if_app_forgets(start_test_server) -> None:
    async def app(req, resp):
        await req.body.aclose()
        await req.trailers.aclose()
        await resp.headers(200, headers=[], end_stream=False)

    tester: HTTP2Tester = await start_test_server(app, initiated=True)

    await tester.start_request("GET", "/", end_stream=True)

    await tester.expect(hyperframe.frame.HeadersFrame)  # From app
    data = await tester.expect(hyperframe.frame.DataFrame)  # Automatic
    assert "END_STREAM" in data.flags
    assert data.data == b""


async def test_cancels_app_on_stream_reset(start_test_server) -> None:
    cancelled = trio.Event()

    async def app(req, resp):
        await resp.headers(200, headers=[], end_stream=False)

        try:
            await trio.sleep(10)
        except trio.Cancelled:
            cancelled.set()
            raise

    tester: HTTP2Tester = await start_test_server(app, initiated=True)

    stream_id = await tester.start_request("GET", "/", end_stream=False)
    await tester.expect(hyperframe.frame.HeadersFrame)
    await tester.reset_stream(stream_id)

    with trio.fail_after(1):
        await cancelled.wait()


async def test_resets_stream_on_app_exception(
    start_test_server,
    expect_soon,
    caplog,
) -> None:
    async def app(req, resp):
        raise _TestError()

    tester: HTTP2Tester = await start_test_server(app, initiated=True)

    stream_id = await tester.start_request("GET", "/", end_stream=False)
    await tester.send_data(stream_id, b"123", end_stream=True)

    # Expect an RST_STREAM immediately, in response to the headers.
    frame = await tester.expect(hyperframe.frame.RstStreamFrame)
    assert frame.stream_id == stream_id

    def assert_message():
        assert "Stream ended due to exception." in caplog.text
        assert "_TestError" in caplog.text

    await expect_soon(assert_message)

    # Expect we can still use the connection.
    await tester.ping_and_expect_pong()
