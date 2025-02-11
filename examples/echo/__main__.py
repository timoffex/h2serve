"""An HTTP/2 server that echoes back the request body.

Expects a localhost.pem file in the workspace root.

After starting it up, try sending it data using:

  curl --insecure https://localhost:<port> -d "<data>"

The --insecure option is needed because the localhost certificate is
self-signed. You can find the selected <port> in this program's stderr
output.
"""

import logging
import ssl

import trio

import h2serve


async def app(
    req: h2serve.HTTP2Request,
    resp: h2serve.HTTP2Response,
) -> None:
    # Discard any trailers that come in after the body.
    await req.trailers.aclose()

    await resp.headers(200, [])

    async for chunk in req.body:
        await resp.body(chunk.data)
        chunk.ack.set()

    # Not strictly necessary, but h2serve will emit a warning otherwise.
    await resp.end()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    ssl_context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain("localhost.pem")
    ssl_context.set_alpn_protocols(["h2"])

    async with trio.open_nursery() as nursery:
        await h2serve.serve(
            nursery,
            app,
            host="localhost",
            port=0,
            ssl_context=ssl_context,
        )


if __name__ == "__main__":
    trio.run(main)
