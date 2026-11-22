"""Test doubles shared by the tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from moteur.config import Config, Criteria, TargetCompany, company_fields, parse

SEARCHES = ["ia"]


def parsed(
    data: Mapping[str, Any], folder: Path = Path(), catalogue: tuple[TargetCompany, ...] = ()
) -> Config:
    """`parse`, with the required `[criteres] recherches` (CONF-11) added when missing.

    An `entreprises` list stands for User's own companies, which really come from the
    database (CAT-20): only their fields are checked (CAT-08), to keep the tests short.
    """
    complete = dict(data)
    own = tuple(
        replace(company_fields(entry), origin="perso") for entry in complete.pop("entreprises", [])
    )
    criteria = complete.get("criteres", {})
    if isinstance(criteria, dict) and "recherches" not in criteria:
        complete["criteres"] = {**criteria, "recherches": SEARCHES}
    return parse(complete, folder, catalogue, own)


class FakeClient:
    """HTTP client that returns prepared answers and records the calls."""

    def __init__(self, answers: Mapping[str, Any]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        self.calls.append((url, dict(params or {})))
        return self.answers.get(url)

    def post_form(
        self, url: str, *, data: Mapping[str, str], params: Mapping[str, str] | None = None
    ) -> Any:
        self.calls.append((url, dict(data)))
        return self.answers.get(url)

    def post_json(
        self, url: str, *, body: Mapping[str, Any], headers: Mapping[str, str] | None = None
    ) -> Any:
        self.calls.append((url, dict(body)))
        answer = self.answers.get(url)
        # A list of answers is served page by page.
        if isinstance(answer, list):
            return answer.pop(0) if answer else None
        return answer

    def get_text(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
        self.calls.append((url, dict(params or {})))
        answer = self.answers.get(url)
        return answer if isinstance(answer, str) else ""


class FakeAssistant:
    """Assistant that returns answers in order and records the prompts."""

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.models: list[str] = []
        self.systems: list[str] = []
        self.tools: list[tuple[str, ...]] = []
        self.delays: list[int] = []

    def ask(
        self,
        prompt: str,
        *,
        system: str,
        model: str,
        tools: tuple[str, ...] = (),
        delay: int = 600,
    ) -> str:
        self.prompts.append(prompt)
        self.models.append(model)
        self.systems.append(system)
        self.tools.append(tools)
        self.delays.append(delay)
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def criteria(
    keywords: tuple[str, ...] = ("data scientist", "ia"),
    exclusions: tuple[str, ...] = ("stage",),
    locations: tuple[str, ...] = ("paris",),
    salary_floor: int = 0,
) -> Criteria:
    return Criteria(keywords, exclusions, locations, salary_floor)
