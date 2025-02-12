# h2serve

[![Documentation Status](https://readthedocs.org/projects/h2serve/badge/?version=latest)](https://h2serve.readthedocs.io/en/latest/?badge=latest)

A Python HTTP/2 server.

**EXPERIMENTAL**. I'm playing around with this in my free time. I started this
because I wanted to read and implement the HTTP/2 spec.

All the code is typed and thoroughly documented. See the Sphinx documentation
by clicking the badge above.

The tests start up a server, send HTTP/2 frames to it using `h2`, and make
assertions about the HTTP/2 frames it sends back by parsing them with
`hyperframe`. The test coverage is 92% (measuring branches by passing `--branch`
to `coverage`) as of the last time I ran them. It was interesting to think
about how to test this, considering how most of the implementation effort is
spent on edge cases. Simply being able to connect to the server with a browser
does not build a lot of confidence in its correctness!
