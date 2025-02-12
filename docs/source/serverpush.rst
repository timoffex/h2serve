HTTP/2 Server Push
==================

When I first read the `IETF RFC 9113 <https://datatracker.ietf.org/doc/html/rfc9113>`_
defining HTTP/2, I didn't know anything about HTTP/2 other than that it is
HTTP and it is newer than HTTP/1.1. So when I read the Server Push section,
I was excited about the possibilities.

It turns out I am late to the party, as Chrome removed support for HTTP/2 push
back in 2021. You can read this `summary <https://developer.chrome.com/blog/removing-push>`_
or this `long Google Groups thread <https://groups.google.com/a/chromium.org/g/blink-dev/c/K3rYLvmQUBY/m/vOWBKZGoAQAJ>`_
about it, but the TL;DR is that servers didn't implement it fast enough and
the maintenance burden was too much for Chrome.

`hypercorn <https://github.com/pgjones/hypercorn>`_ supports server push,
and `quart <https://github.com/pallets/quart>`_ (which can run on top of
`hypercorn`) has `some documentation <https://quart.palletsprojects.com/en/latest/how_to_guides/using_http2.html>`_
on how to use it, with a note that browsers are deprecating support for it.

Though it would be easy to add, I have not implemented it in `h2serve`.
It could be useful if you control the client, but it is likely a waste of time
if you're building a web server.
