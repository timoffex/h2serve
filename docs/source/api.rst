API Reference
=============

.. automodule:: h2serve
   :members:
   :member-order: bysource
   :show-inheritance:

   .. py:type:: AppHandler
      :canonical: Callable[[HTTP2Request, HTTP2Response], Awaitable[None]]

      An application handler for HTTP/2 requests.

      This processes a single HTTP/2 request (a.k.a. a stream). Here's an
      example handler that responds with HTTP 200 to any request and streams
      the request body as the response body:

      .. code:: python

         async def echo_app(
            req: h2serve.HTTP2Request,
            resp: h2serve.HTTP2Response,
         ) -> None:
            # Indicate we won't use trailers so that h2serve can discard
            # any it receives.
            await req.trailers.aclose()

            await resp.headers(200, headers=[])

            async for chunk in req.body:
               await resp.body(chunk.data)
               chunk.ack.set()
            
            await resp.end()
      
      The `chunk.ack.set()` line is for HTTP/2 flow control\: it tells
      the peer that we've accepted a chunk of data and that more may be sent.
      See :doc:`flowcontrol`.
      
      See the docs for :py:class:`HTTP2Request` and :py:class:`HTTP2Response`.
