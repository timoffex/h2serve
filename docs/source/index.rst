h2serve: A Python HTTP/2 server
===============================

.. note::

   This package is not ready for use but will be eventually. If you're looking
   for a stable Python HTTP server, consider one of the existing ones like
   uvicorn for now.

h2serve is an HTTP/2 server designed for *low-level control*.
It is built on top of the `h2 <http://python-hyper.org/projects/h2/en/stable/index.html>`_
library and only supports `trio <https://trio.readthedocs.io/en/stable/index.html>`_
as the async backend.


.. toctree::
   :maxdepth: 1

   flowcontrol
   api