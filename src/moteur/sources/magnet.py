"""Magnet by Hellowork career sites (formerly CVCatcher), e.g. ``jobs.fivesgroup.com``.

The page reads its ads from ``api.magnet.work`` with a short-lived anonymous token, which
every visitor's browser gets by sending the site's public key (published in the page)
and the current time. The source does the same (SRC-75 to SRC-77).
"""

from __future__ import annotations

import base64
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, SourceError, items, plain_text, string, table
from moteur.sources.talentsoft import host_of

API = "https://api.magnet.work"
PAGE_SIZE = 100
PAGES_MAX = 20
_PUBLIC_KEY = re.compile(r'"publicKey"\s*:\s*"([^"]+)"')
# Filters the search requires, all empty: the site lists every ad (SRC-76).
_NO_FILTER: dict[str, Any] = {
    key: []
    for key in (
        "skills",
        "jobs",
        "cities",
        "departments",
        "regions",
        "countries",
        "contracts",
        "hobbies",
    )
}


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def public_key(page: str) -> str:
    """The site's public key, as published in its page (empty if missing)."""
    found = _PUBLIC_KEY.search(page)
    return found.group(1) if found else ""


def login_body(key: str, now: datetime) -> dict[str, str]:
    """What the page sends to get its anonymous token: key and time, in base64."""
    moment = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    return {"usr": _b64(key), "pass": _b64(moment)}


def ads_magnet(company: str, host: str, answer: object) -> list[JobAd]:
    ads: list[JobAd] = []
    for offer in map(table, items(table(table(answer).get("data")).get("list"))):
        title, offer_id = string(offer.get("title")), string(offer.get("id"))
        if not title or not offer_id:
            continue
        place = table(next(iter(items(offer.get("localities"))), {}))
        location = ", ".join(
            part for part in (string(place.get("city_label")), string(place.get("country"))) if part
        )
        language = string(offer.get("language")) or "fr"
        ads.append(
            JobAd(
                company=company,
                title=title,
                location=location,
                url=f"https://{host}/{language}/offer/{offer_id}",
                source="magnet",
                description=plain_text(string(offer.get("description"))),
                published_on=string(offer.get("publication_date"))[:10],
            )
        )
    return ads


def _total(answer: object) -> int:
    total = table(table(answer).get("data")).get("total")
    return total if isinstance(total, int) else 0


class SourceMagnet:
    def __init__(
        self,
        client: HttpClient,
        company: TargetCompany,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = client
        self._company = company
        self._host = host_of(company.identifier)
        self._clock = clock

    @property
    def name(self) -> str:
        return f"magnet:{self._company.name}"

    def _token(self, session: str) -> str:
        key = public_key(self._client.get_text(f"https://{self._host}/"))
        if not key:
            raise SourceError(f"{self._host}: no Magnet public key in the page")
        answer = self._client.post_json(
            f"{API}/v2/security/login",
            body=login_body(key, self._clock()),
            headers={"x-session-id": session},
        )
        token = string(table(table(answer).get("data")).get("token"))
        if not token:
            raise SourceError(f"{self._host}: no Magnet token")
        return token

    def collect(self) -> list[JobAd]:
        session = str(uuid.uuid4())
        headers = {
            "Authorization": f"Bearer {self._token(session)}",
            "x-session-id": session,
            "x-language": "fr",
        }
        ads: list[JobAd] = []
        for page in range(PAGES_MAX):
            answer = self._client.post_json(
                f"{API}/v2/job-offers",
                body={**_NO_FILTER, "offset": page * PAGE_SIZE, "limit": PAGE_SIZE},
                headers=headers,
            )
            found = ads_magnet(self._company.name, self._host, answer)
            ads.extend(found)
            total = _total(answer)
            if len(found) < PAGE_SIZE or (total and (page + 1) * PAGE_SIZE >= total):
                break
        return ads
