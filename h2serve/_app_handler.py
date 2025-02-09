from __future__ import annotations

from typing import Awaitable, Callable

from ._request import HTTP2Request
from ._response import HTTP2Response

AppHandler = Callable[[HTTP2Request, HTTP2Response], Awaitable[None]]
"""An application handler for HTTP/2 requests."""
