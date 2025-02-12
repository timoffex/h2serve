h2serve: A Python HTTP/2 server
===============================

.. note::

   This is an experimental package I wrote for fun. It works, but you should
   probably use `hypercorn <https://github.com/pgjones/hypercorn>`_.

h2serve is a simple, tested HTTP/2 server.

It is built on top of the `h2 <http://python-hyper.org/projects/h2/en/stable/index.html>`_
library and only supports `trio <https://trio.readthedocs.io/en/stable/index.html>`_
as the async backend.

The usage is straightforward:

1. Define an :py:func:`h2serve.AppHandler` function:

   .. code:: python

      async def app(
         req: h2serve.HTTP2Request,
         resp: h2serve.HTTP2Response,
      ) -> None:
         ...

2. Use :py:func:`h2serve.serve` to start the server:

   .. code:: python

      async with trio.open_nursery() as server_nursery:
         server = await h2serve.serve(
            server_nursery,
            app,
            host=...,
            port=...,
            ssl_context=...,
         )

   :py:func:`h2serve.serve` returns a :py:class:`h2serve.Server` which you can
   use to get its :py:attr:`h2serve.Server.addresses` (in case you passed
   `port=0`).

HTTP/2 requires SSL, so you will need an SSL certificate. For local testing,
you can create a `localhost` certificate using `mkcert <https://github.com/FiloSottile/mkcert>`_.
See the documentation on :py:func:`h2serve.serve` for details about the
`ssl_context`, but the basic configuration will look like this:

.. code:: python

   # Having imported the built-in 'ssl' module.
   ssl_context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
   ssl_context.load_cert_chain(CERTIFICATE_FILE)
   ssl_context.set_alpn_protocols(["h2"])

.. toctree::
   :maxdepth: 1

   serverpush
   flowcontrol
   api