import hyperframe.frame
from h2.settings import SettingCodes

from .http2tester import HTTP2Tester


async def test_sends_initial_settings(start_test_server) -> None:
    async def app(req, resp):
        await resp.headers(200, headers=[], end_stream=True)

    tester: HTTP2Tester = await start_test_server(
        app,
        http2_settings={
            SettingCodes.MAX_CONCURRENT_STREAMS: 123,
        },
    )
    await tester.initiate_connection()

    await tester.expect(hyperframe.frame.SettingsFrame)
    custom_settings = await tester.expect(hyperframe.frame.SettingsFrame)
    assert custom_settings.settings[SettingCodes.MAX_CONCURRENT_STREAMS] == 123


async def test_respects_flow_control(start_test_server) -> None:
    async def app(req, resp):
        await resp.headers(200, headers=[], end_stream=False)
        await resp.body(b"1234567890", end_stream=True)

    tester: HTTP2Tester = await start_test_server(app, initiated=True)
    await tester.update_settings({SettingCodes.INITIAL_WINDOW_SIZE: 5})
    await tester.start_request("GET", "/", end_stream=True)

    await tester.expect(hyperframe.frame.SettingsFrame)  # settings ack
    await tester.expect(hyperframe.frame.HeadersFrame)  # response start

    # First chunk.
    body1 = await tester.expect(hyperframe.frame.DataFrame)
    assert body1.flow_controlled_length == 5
    assert body1.data == b"12345"

    # Send a window update to allow 2 more bytes.
    await tester.acknowledge_received_data(2, body1.stream_id)
    body2 = await tester.expect(hyperframe.frame.DataFrame)
    assert body2.flow_controlled_length == 2
    assert body2.data == b"67"

    # Send a window update to allow remaining 3 bytes.
    await tester.acknowledge_received_data(3, body1.stream_id)
    body3 = await tester.expect(hyperframe.frame.DataFrame)
    assert body3.data == b"890"
    assert "END_STREAM" in body3.flags
