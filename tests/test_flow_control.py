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
