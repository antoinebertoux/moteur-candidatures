"""Company website and LinkedIn page, shared by every application of a company.

Sources, strongest first (LNK-02): User's correction in the page, the tracked company
in `config.toml`, then a lookup by Claude with web search only (LNK-10 to LNK-15).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from moteur.claude_cli import Assistant, ErreurClaude, extraire_json
from moteur.modeles import Offre, normaliser

if TYPE_CHECKING:
    from moteur.base_locale import BaseLocale

log = logging.getLogger(__name__)

BATCH_SIZE = 10
RETRY_AFTER = timedelta(days=30)
LOOKUP_TOOLS = ("WebSearch",)

_LINKEDIN = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)?linkedin\.com/company/([^/?#\s]+)", re.IGNORECASE
)
# Hosts that are never a company's own website (LNK-03): job boards, recruiting tools,
# social networks, encyclopedias and company registers.
_EXCLUDED_LABELS = frozenset({"linkedin", "indeed", "glassdoor", "wikipedia", "wikidata"})
_EXCLUDED_DOMAINS = (
    "welcometothejungle.com",
    "welcomekit.co",
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "recruitee.com",
    "teamtailor.com",
    "workable.com",
    "tmp.com",
    "francetravail.fr",
    "pole-emploi.fr",
    "choisirleservicepublic.gouv.fr",
    "apec.fr",
    "hellowork.com",
    "jobteaser.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "crunchbase.com",
    "societe.com",
    "pappers.fr",
)


@dataclass(frozen=True, slots=True)
class CompanyLinks:
    site: str = ""
    linkedin: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.site and self.linkedin)

    def over(self, weaker: CompanyLinks) -> CompanyLinks:
        """These links, each missing one taken from a weaker source (LNK-02)."""
        return CompanyLinks(self.site or weaker.site, self.linkedin or weaker.linkedin)


def company_key(name: str) -> str:
    """One record per company, keyed by its normalised name (LNK-01)."""
    return normaliser(name)


def is_web_address(value: str) -> bool:
    return bool(re.match(r"^https?://\S+$", value.strip(), re.IGNORECASE))


def clean_linkedin(value: object) -> str:
    """`https://www.linkedin.com/company/<name>/`, or "" if not a company page (LNK-03)."""
    if not isinstance(value, str):
        return ""
    found = _LINKEDIN.match(value.strip())
    return f"https://www.linkedin.com/company/{found.group(1)}/" if found else ""


def clean_website(value: object) -> str:
    """`https://<host>/`, or "" if not the company's own website (LNK-03)."""
    if not isinstance(value, str) or not is_web_address(value):
        return ""
    host = (urlsplit(value.strip()).hostname or "").lower().rstrip(".")
    if "." not in host:
        return ""
    if _EXCLUDED_LABELS & set(host.split(".")):
        return ""
    if any(host == domain or host.endswith("." + domain) for domain in _EXCLUDED_DOMAINS):
        return ""
    return f"https://{host}/"


_INSTRUCTIONS = """Tu retrouves le site officiel et la page LinkedIn d'entreprises.
Pour chaque entreprise reçue, cherche sur le web et réponds par un objet JSON avec
exactement ces champs :
- "entreprise" : le nom reçu, recopié tel quel ;
- "site" : l'adresse du site officiel de l'entreprise (pas un site d'offres d'emploi,
  pas un réseau social, pas Wikipédia) ;
- "linkedin" : l'adresse de sa page entreprise LinkedIn
  (https://www.linkedin.com/company/...).
L'offre jointe sert seulement à ne pas confondre avec une entreprise homonyme.
Laisse un champ vide ("") si tu n'es pas sûr : ne devine jamais une adresse.
Réponds uniquement par un tableau JSON, sans texte autour."""


def build_prompt(companies: Sequence[Offre]) -> str:
    """Only the company name and one of its ads' title, location and link (LNK-12)."""
    return json.dumps(
        [
            {
                "entreprise": offer.entreprise,
                "offre": {"poste": offer.poste, "lieu": offer.lieu, "lien": offer.url},
            }
            for offer in companies
        ],
        ensure_ascii=False,
    )


def parse_response(text: str, asked: set[str]) -> dict[str, CompanyLinks]:
    """Links found per company key; unknown companies and malformed links are dropped
    (LNK-14). A response that is not an array raises `ErreurClaude`."""
    data = extraire_json(text)
    if not isinstance(data, list):
        raise ErreurClaude("La recherche de liens doit renvoyer un tableau JSON")
    found: dict[str, CompanyLinks] = {}
    for entry in data:
        if not isinstance(entry, dict) or not isinstance(entry.get("entreprise"), str):
            continue
        key = company_key(entry["entreprise"])
        if key not in asked:
            continue
        found[key] = CompanyLinks(
            clean_website(entry.get("site")), clean_linkedin(entry.get("linkedin"))
        )
    return found


def to_look_up(base: BaseLocale, today: date) -> list[Offre]:
    """One ad per company still missing a link and not looked up recently (LNK-10, LNK-11)."""
    links = base.company_links()
    looked_up = base.company_lookups()
    limit = (today - RETRY_AFTER).isoformat()
    chosen: dict[str, Offre] = {}
    for application in base.pour_la_page() + base.a_generer():
        offer = application.offre
        key = company_key(offer.entreprise)
        if not key or key in chosen or links.get(key, CompanyLinks()).complete:
            continue
        if looked_up.get(key, "") > limit:
            continue
        chosen[key] = offer
    return list(chosen.values())


def look_up(
    base: BaseLocale, assistant: Assistant, *, model: str, today: date | None = None
) -> tuple[int, int]:
    """Looks up the missing links, in batches; returns (companies looked up, links found).

    A failed batch records nothing and is retried on the next run (LNK-14).
    """
    today = today or date.today()
    companies = to_look_up(base, today)
    looked_up = found = 0
    for start in range(0, len(companies), BATCH_SIZE):
        batch = companies[start : start + BATCH_SIZE]
        asked = {company_key(offer.entreprise) for offer in batch}
        try:
            answer = assistant.demander(
                build_prompt(batch), systeme=_INSTRUCTIONS, modele=model, outils=LOOKUP_TOOLS
            )
            results = parse_response(answer, asked)
        except ErreurClaude as error:
            log.warning("Liens de %d entreprises non cherchés : %s", len(batch), error)
            continue
        for key in sorted(asked):
            links = results.get(key, CompanyLinks())
            base.record_lookup(key, links, today.isoformat())
            found += bool(links.site) + bool(links.linkedin)
        looked_up += len(batch)
    return looked_up, found


def config_links(companies: Sequence[tuple[str, str, str]]) -> Mapping[str, CompanyLinks]:
    """Links of the tracked companies `(name, site, linkedin)`, by company key (CONF-09)."""
    return {
        company_key(name): CompanyLinks(site.strip(), linkedin.strip())
        for name, site, linkedin in companies
        if site.strip() or linkedin.strip()
    }
