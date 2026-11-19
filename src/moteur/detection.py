"""`moteur detecter`: recognises the recruiting tool of career pages (CLI-04 to CLI-06)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from moteur.sources.base import ClientHttp, ErreurSource

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

    def block(self, name: str = "") -> str:
        """The `[[entreprises]]` block to paste into config.toml (CLI-06)."""
        source = self.address if self.ats == "workday" else self.identifier.removeprefix("eu:")
        nom = name or _name_from(source)
        return (
            "[[entreprises]]\n"
            f'nom = "{nom}"\n'
            f'ats = "{self.ats}"\n'
            f'identifiant = "{self.identifier}"\n'
            f'site = "{self.address}"\n'
        )


def _name_from(identifier: str) -> str:
    base = re.sub(r"^https?://", "", identifier).split(".")[0]
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", base) if part)


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


def detect(address: str, client: ClientHttp) -> Detection:
    address = address.strip()
    direct = find_tool(address)
    if direct:
        return Detection(address, *direct)
    url = address if "://" in address else f"https://{address}"
    try:
        page = client.get_texte(url)
    except ErreurSource as error:
        return Detection(address, error=str(error))
    in_page = find_tool(page)
    if in_page is None:
        return Detection(address, error="outil non reconnu")
    return Detection(address, *in_page)


def report(addresses: Sequence[str], client: ClientHttp, name: str = "") -> str:
    """Text printed by `moteur detecter`: one block per recognised address."""
    single_name = name if len(addresses) == 1 else ""
    parts: list[str] = []
    for address in addresses:
        detection = detect(address, client)
        if detection.error:
            parts.append(f"# {address} : {detection.error}\n")
        else:
            parts.append(detection.block(single_name))
    return "\n".join(parts)
