"""Files exchanged with the tracking page: proposals to import, decisions to read back."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from moteur.company_links import CompanyLinks, company_key, is_web_address
from moteur.models import Application, JobAd, PrepRequest, default_letter
from moteur.refusal import normalise_detail, normalise_reason


class ExchangeError(ValueError):
    """The file exported by the page is unreadable."""


@dataclass(frozen=True, slots=True)
class Decision:
    """One row of the page's export.

    `ad` describes the application as the page knows it: it is used to add to the local
    database the ones that do not come from it (manual entry, engine A).
    """

    key: str
    status: str
    instruction: str = ""
    ad: JobAd | None = None
    letter_requested: bool = False
    letter: bool | None = None
    """Choice made with the page's toggle (field `lettre`: `oui` or `non`)."""
    letter_redo_at: str = ""
    """Time "Regenerate the letter" was clicked (`toISOString()` format)."""
    letter_instruction_page: str = ""
    refusal_reason: str = ""
    """Refusal reason code chosen in the page (PAGE-10), `autre` if unknown."""
    reason_detail: str = ""
    preparation: PrepRequest | None = None
    """Interview preparation request (PREP-01), None if the page made none."""
    links: CompanyLinks | None = None
    """User's correction of the company links (PAGE-42), None if there is none."""

    @property
    def with_letter(self) -> bool:
        """The page's choice if there is one, otherwise the default rule."""
        if self.letter is not None:
            return self.letter
        return self.letter_requested or (self.ad is not None and default_letter(self.ad))


def _text(entry: dict[str, Any], field: str) -> str:
    value = entry.get(field)
    return value.strip() if isinstance(value, str) else ""


def _ad(entry: dict[str, Any]) -> JobAd | None:
    company, title = _text(entry, "entreprise"), _text(entry, "poste")
    if not company or not title:
        return None
    return JobAd(
        company=company,
        title=title,
        type="spontanee" if entry.get("type") == "spontanee" else "offre",
        location=_text(entry, "lieu"),
        url=_text(entry, "url"),
        source=_text(entry, "source"),
        description=_text(entry, "texte_offre"),
    )


_CONTEXT = (
    ("date_postulee", "Envoyée le"),
    ("suite", "Suite"),
    ("contact", "Contact"),
    ("notes", "Notes"),
)
MAX_PREP_FIELD = 2_000


def _preparation(entry: dict[str, Any]) -> PrepRequest | None:
    """The page's preparation request, with what it knows of the follow-up (PREP-10)."""
    requested_at = _text(entry, "preparation_demandee_le")
    if not requested_at:
        return None
    context = [
        f"{label} : {_text(entry, field)}" for field, label in _CONTEXT if _text(entry, field)
    ]
    return PrepRequest(
        requested_at,
        _text(entry, "pretentions")[:MAX_PREP_FIELD],
        _text(entry, "entretien_infos")[:MAX_PREP_FIELD],
        _text(entry, "preparation_consigne")[:MAX_PREP_FIELD],
        "\n".join(context)[:10_000],
    )


def _links(entry: dict[str, Any]) -> CompanyLinks | None:
    """The company links User typed in the page, kept only when `liens_manuels`."""
    if entry.get("liens_manuels") is not True:
        return None
    site, linkedin = _text(entry, "site_entreprise"), _text(entry, "linkedin_entreprise")
    return CompanyLinks(
        site if is_web_address(site) else "", linkedin if is_web_address(linkedin) else ""
    )


def file_date(file: Path) -> str | None:
    """Modification time in the page's `Date.toISOString()` format, or None."""
    try:
        moment = datetime.fromtimestamp(file.stat().st_mtime, UTC)
    except OSError:
        return None
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def for_the_page(
    applications: Iterable[Application],
    root: Path | None = None,
    links: Mapping[str, CompanyLinks] | None = None,
) -> list[dict[str, Any]]:
    """Format read by the page's "Import" button.

    The page computes the identifier itself from the type, the company and the title,
    so it must not be sent.
    """
    rows: list[dict[str, Any]] = []
    for application in applications:
        ad = application.ad
        row: dict[str, Any] = {
            "type": ad.type,
            "entreprise": ad.company,
            "poste": ad.title,
            "lieu": ad.location,
            "url": ad.url,
            "source": ad.source,
            "moteur": "B",
            "resume": application.summary,
            "lettre_demandee": application.letter_requested,
        }
        if application.score is not None:
            row["score"] = application.score
        # ECH-04: the company's links, whatever their source.
        found_links = (links or {}).get(company_key(ad.company), CompanyLinks())
        if found_links.site:
            row["site_entreprise"] = found_links.site
        if found_links.linkedin:
            row["linkedin_entreprise"] = found_links.linkedin
        if application.cv_ref:
            row["cv_ref"] = application.cv_ref
            # The page only moves a folder back to "To validate" if it was generated after
            # the last edit instruction: an old export does not overwrite it.
            generated_at = file_date(root / application.cv_ref) if root else None
            if generated_at:
                row["genere_le"] = generated_at
        if application.letter_ref:
            row["lettre_ref"] = application.letter_ref
            # Lets the page clear its regeneration request once served.
            letter_at = file_date(root / application.letter_ref) if root else None
            if letter_at:
                row["lettre_generee_le"] = letter_at
        if application.preparation:
            row["preparation"] = application.preparation
            row["preparation_le"] = application.preparation_le
        rows.append(row)
    return rows


def serialise(
    applications: Iterable[Application],
    root: Path | None = None,
    links: Mapping[str, CompanyLinks] | None = None,
) -> str:
    return json.dumps(for_the_page(applications, root, links), ensure_ascii=False, indent=2)


def _letter_choice(value: object) -> bool | None:
    if value in ("oui", True):
        return True
    if value in ("non", False):
        return False
    return None


def read_decisions(text: str) -> list[Decision]:
    """Reads the page's export (`{"candidatures": [...]}` or the array itself)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ExchangeError("Unreadable export: it is not JSON") from error
    return decisions_from(data)


def decisions_from(data: object) -> list[Decision]:
    """Decisions from already decoded page documents (file export or direct link)."""
    if isinstance(data, dict):
        data = data.get("candidatures")
    if not isinstance(data, list):
        raise ExchangeError('Unreadable export: no "candidatures" array')
    decisions: list[Decision] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        key, status = entry.get("id"), entry.get("statut")
        if isinstance(key, str) and isinstance(status, str):
            decisions.append(
                Decision(
                    key,
                    status,
                    _text(entry, "consigne"),
                    _ad(entry),
                    entry.get("lettre_demandee") is True,
                    _letter_choice(entry.get("lettre")),
                    _text(entry, "lettre_refaire_le"),
                    _text(entry, "lettre_consigne"),
                    normalise_reason(entry.get("motif_refus")),
                    normalise_detail(entry.get("motif_detail")),
                    _preparation(entry),
                    _links(entry),
                )
            )
    return decisions
