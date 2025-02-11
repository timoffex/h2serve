# Getting started

Install [uv](https://github.com/astral-sh/uv). If you already have Python
installed, you can install `uv` using `pip install uv`. I recommend doing
this globally rather than in a venv; consider it a `pip` replacement.

1. Create a virtual environment:

  ```
  uv venv
  ```

2. Activate it as described by the command.

  Install development requirements:

  ```
  uv pip install -r requirements.txt
  ```

Then use `tox` for other tasks. Try running `tox list`.

* `tox run` will by default run tests in all supported Python versions
* `tox run -e coverage,coverage-html` can be used to collect code coverage
  and output a nice HTML file visualizing it

# Tests prerequisite: localhost.pem

Tests spin up a server on localhost (it's very lightweight!), for which they
need an SSL certificate. They expect a self-signed certificate called
"localhost.pem" that's valid for "localhost".

Generate a self-signed certificate for local testing:

```
openssl \
  req -new -x509 \
  -days 365 -nodes \
  -out localhost.pem \
  -keyout localhost.pem
```

Make sure to enter "localhost" for the common name.
