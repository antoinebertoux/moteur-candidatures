"""Contracts shared by the sources, and the HTTP client."""

from __future__ import annotations

import html
import re
import time
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol, TypeVar, runtime_checkable

import httpx

from moteur.models import JobAd

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
            headers={"User-Agent": "moteur-candidatures/0.1 (usage personnel)"},
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
            # The body often explains the error (e.g. OAuth: invalid_scope, invalid_client).
            detail = " ".join(error.response.text.split())[:300]
            message = f"{url}: HTTP {error.response.status_code}"
            raise SourceError(f"{message}: {detail}" if detail else message) from error
        except (httpx.HTTPError, ValueError) as error:
            raise SourceError(f"{url}: {error}") from error


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
