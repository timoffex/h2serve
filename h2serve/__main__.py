import logging
import sys

import trio

from . import HTTP2Request, HTTP2Response, serve


async def echo(req: HTTP2Request, resp: HTTP2Response) -> None:
    await resp.headers(200, [])

    await resp.body(b"---HEADERS---\n")
    for header in req.headers:
        name = header.name.decode()
        value = header.value.decode()
        await resp.body(f"\t{name}={value}\n".encode())

    await resp.body(b"---BODY---\n")
    async with req.body:
        async for chunk in req.body:
            await resp.body(chunk.data)
            chunk.ack.set()

    await resp.body(b"\n---TRAILERS---\n")
    async with req.trailers:
        async for trailer in req.trailers:
            name = trailer.name.decode()
            value = trailer.value.decode()
            await resp.body(f"\t{name}={value}\n".encode())

    await resp.end()


async def main() -> None:
    await serve(echo, "192.168.0.113", 0)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    trio.run(main)
