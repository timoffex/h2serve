# Getting started

Make sure `python` is installed.

Install [uv](https://github.com/astral-sh/uv):

```
pip install uv
```

Create a virtual environment:

```
uv venv
```

Activate it as described by the command.

# Cheatsheet

Install development requirements:

```
uv pip install -r requirements.txt
```

Update development requirements:

1. Update `requirements.in`
2. `uv pip compile requirements.in -o requirements.txt`

---

Run tests:

```
pytest
```

NOTE: The tests require a `localhost.pem` certificate file in the repo root.

Measure and view code coverage from tests:

```
coverage -m pytest
coverage html
# Then open the generated file, likely htmlcov/index.html.
```

---

Generate a self-signed certificate for local testing:

```
openssl \
  req -new -x509 \
  -days 365 -nodes \
  -out localhost.pem \
  -keyout localhost.pem
```

Make sure to enter "localhost" for the common name.

---

Generate documentation:

```
cd docs
make html
```