"""`moteur detect`: recognises the recruiting tool of career pages (CLI-04 to CLI-06)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from moteur.sources.base import HttpClient, SourceError

# (tool, pattern): the identifier is the first group; Workday keeps the whole address.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "greenhouse-eu",
        re.compile(r"(?:job-)?boards(?:-api)?\.eu\.greenhouse\.io/(?:v1/boards/)?([\w-]+)"),
    ),
    ("greenhouse", re.compile(r"(?:job-)?boards(?:-api)?\.greenhouse\.io/(?:v1/boards/)?([\w-]+)")),
    ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([\w.-]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([\w.%-]+)")),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)")),
    ("recruitee", re.compile(r"([\w-]+)\.recruitee\.com")),
    ("teamtailor", re.compile(r"([\w-]+)\.teamtailor\.com")),
    ("workable", re.compile(r"apply\.workable\.com/([\w-]+)")),
    (
        "workday",
        re.compile(r"(https?://[\w-]+\.wd\d+\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?[\w-]+)"),
    ),
)
# Path segments that are not a board identifier (embed scripts, API words).
_NOT_IDENTIFIERS = {"embed", "api", "v1", "js", "static", "www", "careers", "jobs", "widget"}


@dataclass(frozen=True, slots=True)
class Detection:
    address: str
    ats: str = ""
    identifier: str = ""
    error: str = ""

    def line(self) -> str:
        """What `moteur detect` prints for a recognised address (CLI-06)."""
        return f"{self.address}: ats = {self.ats}, identifiant = {self.identifier}"


def find_tool(text: str) -> tuple[str, str] | None:
    """First recruiting-tool address found in an address or a page (CLI-04, CLI-05)."""
    found: list[tuple[int, str, str]] = []
    for ats, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            identifier = match.group(1)
            if identifier.lower() in _NOT_IDENTIFIERS:
                continue
            found.append((match.start(), ats, identifier))
            break
    if not found:
        return None
    _, ats, identifier = min(found)
    if ats == "greenhouse-eu":
        return "greenhouse", f"eu:{identifier}"
    return ats, identifier


def detect(address: str, client: HttpClient) -> Detection:
    address = address.strip()
    direct = find_tool(address)
    if direct:
        return Detection(address, *direct)
    url = address if "://" in address else f"https://{address}"
    try:
        page = client.get_text(url)
    except SourceError as error:
        return Detection(address, error=str(error))
    in_page = find_tool(page)
    if in_page is None:
        return Detection(address, error="unrecognised tool")
    return Detection(address, *in_page)


def report(addresses: Sequence[str], client: HttpClient) -> str:
    """Text printed by `moteur detect`: one line per address (CLI-05, CLI-06)."""
    lines: list[str] = []
    for address in addresses:
        detection = detect(address, client)
        lines.append(f"{address}: {detection.error}" if detection.error else detection.line())
    return "\n".join(lines)
