"""Contracts shared by the sources, and the HTTP client."""

from __future__ import annotations

import html
import http.client
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from email.message import Message
from typing import Any, Protocol, TypeVar, runtime_checkable
from urllib.parse import urlencode

import httpx

from moteur.models import JobAd

# How every HTTP call identifies itself (SRC-03).
USER_AGENT = "moteur-candidatures/0.1 (usage personnel)"
_TAG = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")

# "Too many requests" (429): retries, default and maximum wait.
TRIES_ON_429 = 2
WAIT_429 = 5.0
WAIT_429_MAX = 30.0
# Server error (5xx): one retry, after this wait.
WAIT_5XX = 2.0
# Searches of one source run at the same time (they target the same site).
SEARCHES_IN_PARALLEL = 4

_E = TypeVar("_E")
_R = TypeVar("_R")


def in_parallel(function: Callable[[_E], _R], elements: Iterable[_E], maximum: int) -> list[_R]:
    """Applies `function` to each item, `maximum` at a time; keeps the order of the items."""
    with ThreadPoolExecutor(max_workers=maximum) as runner:
        return list(runner.map(function, elements))


class SourceError(Exception):
    """A source could not be queried; the others carry on."""


class HttpClient(Protocol):
    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any: ...

    def post_form(
        self, url: str, *, data: Mapping[str, str], params: Mapping[str, str] | None = None
    ) -> Any: ...

    def post_json(
        self, url: str, *, body: Mapping[str, Any], headers: Mapping[str, str] | None = None
    ) -> Any: ...

    def get_text(self, url: str, *, params: Mapping[str, str] | None = None) -> str: ...


class Source(Protocol):
    @property
    def name(self) -> str: ...

    def collect(self) -> list[JobAd]: ...


@runtime_checkable
class DetailedSource(Protocol):
    """Source whose results lack the ad text: its page has to be opened."""

    @property
    def name(self) -> str: ...

    def add_details(self, ad: JobAd) -> JobAd: ...


class HttpxClient:
    """Real HTTP client. An empty response (204) gives `None`."""

    def __init__(
        self,
        delay: float = 20.0,
        *,
        transport: httpx.BaseTransport | None = None,
        pause: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(
            timeout=delay,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )
        self._pause = pause

    def _send(self, call: Callable[[], httpx.Response]) -> httpx.Response:
        """Sends the request; retries once on a server error, and on a 429 after the
        requested delay."""
        answer = call()
        if answer.is_server_error:
            self._pause(WAIT_5XX)
            answer = call()
        for _ in range(TRIES_ON_429):
            if answer.status_code != httpx.codes.TOO_MANY_REQUESTS:
                break
            self._pause(_wait(answer.headers.get("Retry-After")))
            answer = call()
        return answer

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return self._json(lambda: self._client.get(url, params=params, headers=headers), url)

    def post_form(
        self, url: str, *, data: Mapping[str, str], params: Mapping[str, str] | None = None
    ) -> Any:
        return self._json(lambda: self._client.post(url, data=data, params=params), url)

    def post_json(
        self, url: str, *, body: Mapping[str, Any], headers: Mapping[str, str] | None = None
    ) -> Any:
        return self._json(lambda: self._client.post(url, json=dict(body), headers=headers), url)

    def get_text(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
        try:
            answer = self._send(lambda: self._client.get(url, params=params))
            answer.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise SourceError(f"{url}: HTTP {error.response.status_code}") from error
        except httpx.HTTPError as error:
            raise SourceError(f"{url}: {error}") from error
        return answer.text

    def close(self) -> None:
        self._client.close()

    def _json(self, call: Callable[[], httpx.Response], url: str) -> Any:
        try:
            answer = self._send(call)
            answer.raise_for_status()
            if answer.status_code == httpx.codes.NO_CONTENT or not answer.content:
                return None
            return answer.json()
        except httpx.HTTPStatusError as error:
            response = error.response
            raise SourceError(
                _error_message(
                    url,
                    response.status_code,
                    response.headers.get("Content-Type", ""),
                    response.text,
                )
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise SourceError(f"{url}: {error}") from error


@dataclass(frozen=True, slots=True)
class _Answer:
    """A response read by `UrllibClient`; header names in lowercase."""

    status: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def text(self) -> str:
        message = Message()
        message["Content-Type"] = self.headers.get("content-type", "")
        return self.body.decode(message.get_content_charset() or "utf-8", errors="replace")


class UrllibClient:
    """HTTP client of Python's standard library, for the sites refusing the usual one
    (SRC-110). Same identification, limit, retries and errors as `HttpxClient`."""

    def __init__(
        self,
        delay: float = 20.0,
        *,
        opener: Callable[..., Any] | None = None,
        pause: Callable[[float], None] = time.sleep,
    ) -> None:
        self._delay = delay
        # The default opener follows redirects.
        self._open = opener or urllib.request.build_opener().open
        self._pause = pause

    def _call(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        data: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> _Answer:
        address = f"{url}{'&' if '?' in url else '?'}{urlencode(params)}" if params else url
        request = urllib.request.Request(
            address,
            data=data,
            headers={"User-Agent": USER_AGENT, **(headers or {})},
            method="GET" if data is None else "POST",
        )
        try:
            with self._open(request, timeout=self._delay) as response:
                return _Answer(response.status, _lowercase(response.headers), response.read())
        except urllib.error.HTTPError as error:
            return _Answer(error.code, _lowercase(error.headers), error.read())
        except urllib.error.URLError as error:
            raise SourceError(f"{url}: {error.reason}") from error
        except (OSError, http.client.HTTPException) as error:
            raise SourceError(f"{url}: {error}") from error

    def _send(self, call: Callable[[], _Answer]) -> _Answer:
        """As `HttpxClient._send`: one retry on a server error, two on a 429 (SRC-04, SRC-06)."""
        answer = call()
        if 500 <= answer.status < 600:
            self._pause(WAIT_5XX)
            answer = call()
        for _ in range(TRIES_ON_429):
            if answer.status != httpx.codes.TOO_MANY_REQUESTS:
                break
            self._pause(_wait(answer.headers.get("retry-after")))
            answer = call()
        return answer

    def _json(self, call: Callable[[], _Answer], url: str) -> Any:
        answer = self._send(call)
        if answer.status >= 400:
            raise SourceError(
                _error_message(
                    url, answer.status, answer.headers.get("content-type", ""), answer.text
                )
            )
        if answer.status == httpx.codes.NO_CONTENT or not answer.body:
            return None
        try:
            return json.loads(answer.body)
        except ValueError as error:
            raise SourceError(f"{url}: {error}") from error

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return self._json(lambda: self._call(url, params=params, headers=headers), url)

    def post_form(
        self, url: str, *, data: Mapping[str, str], params: Mapping[str, str] | None = None
    ) -> Any:
        encoded = urlencode(data).encode()
        form = {"Content-Type": "application/x-www-form-urlencoded"}
        return self._json(lambda: self._call(url, params=params, data=encoded, headers=form), url)

    def post_json(
        self, url: str, *, body: Mapping[str, Any], headers: Mapping[str, str] | None = None
    ) -> Any:
        encoded = json.dumps(dict(body)).encode()
        typed = {"Content-Type": "application/json", **(headers or {})}
        return self._json(lambda: self._call(url, data=encoded, headers=typed), url)

    def get_text(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
        answer = self._send(lambda: self._call(url, params=params))
        if answer.status >= 400:
            raise SourceError(f"{url}: HTTP {answer.status}")
        return answer.text


def _lowercase(headers: Message | None) -> dict[str, str]:
    return {name.lower(): value for name, value in (headers or Message()).items()}


def _error_message(url: str, status: int, content_type: str, text: str) -> str:
    """Source error of an HTTP error. The body often explains it (e.g. OAuth: invalid_scope,
    invalid_client), unless it is a site's HTML error page (SRC-109)."""
    message = f"{url}: HTTP {status}"
    if _is_html(content_type, text):
        return message
    detail = " ".join(text.split())[:300]
    return f"{message}: {detail}" if detail else message


def _is_html(content_type: str, text: str) -> bool:
    """True if a response is an HTML page, by its type or by its first characters."""
    if "html" in content_type.lower():
        return True
    return text.lstrip()[:15].lower().startswith(("<!doctype html", "<html"))


def _wait(value: str | None) -> float:
    """Delay of a Retry-After header in seconds, bounded; 5 s if missing or unreadable."""
    try:
        return min(max(float(value or ""), 0.0), WAIT_429_MAX)
    except ValueError:
        return WAIT_429


def plain_text(contents: str) -> str:
    """Removes HTML tags (possibly escaped) and collapses spaces."""
    without_tags = _TAG.sub(" ", html.unescape(contents))
    return _SPACES.sub(" ", html.unescape(without_tags)).strip()


def string(value: object) -> str:
    """Turns an uncertain JSON value into a clean string."""
    return value.strip() if isinstance(value, str) else ""


def table(value: object) -> dict[str, Any]:
    """Returns the value if it is a JSON object, otherwise an empty object."""
    return value if isinstance(value, dict) else {}


def items(value: object) -> list[Any]:
    """Returns the value if it is a JSON array, otherwise an empty array."""
    return value if isinstance(value, list) else []
