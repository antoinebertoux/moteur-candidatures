"""Public career pages: Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Teamtailor,
Workable."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from typing import Any

from moteur.config import EntrepriseCible
from moteur.modeles import Offre
from moteur.sources.base import ClientHttp, chaine, liste, table, texte_brut

URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{id}/jobs",
    "lever": "https://api.lever.co/v0/postings/{id}",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{id}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{id}/postings",
    "recruitee": "https://{id}.recruitee.com/api/offers/",
    "teamtailor": "https://{id}.teamtailor.com/jobs.rss",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{id}",
}
PARAMETRES: dict[str, dict[str, str]] = {
    "greenhouse": {"content": "true"},
    "lever": {"mode": "json"},
    "smartrecruiters": {"limit": "100"},
    "workable": {"details": "true"},
}
URL_SMARTRECRUITERS = "https://jobs.smartrecruiters.com/{id}/{offre}"
GREENHOUSE_EU = "https://boards-api.eu.greenhouse.io/v1/boards/{id}/jobs"
TEAMTAILOR_OWN_DOMAIN = "https://{id}/jobs.rss"
EU_PREFIX = "eu:"


def ats_url(ats: str, identifier: str) -> str:
    """Address of a company's ads (SRC-30), with the EU and own-domain variants."""
    if ats == "greenhouse" and identifier.startswith(EU_PREFIX):
        return GREENHOUSE_EU.format(id=identifier.removeprefix(EU_PREFIX))
    if ats == "teamtailor" and "." in identifier:
        return TEAMTAILOR_OWN_DOMAIN.format(id=identifier)
    return URLS[ats].format(id=identifier)


def offres_greenhouse(entreprise: str, reponse: object) -> list[Offre]:
    return [
        Offre(
            entreprise=entreprise,
            poste=chaine(poste.get("title")),
            lieu=chaine(table(poste.get("location")).get("name")),
            url=chaine(poste.get("absolute_url")),
            source="greenhouse",
            description=texte_brut(chaine(poste.get("content"))),
            date_publication=chaine(poste.get("updated_at"))[:10],
        )
        for poste in map(table, liste(table(reponse).get("jobs")))
        if chaine(poste.get("title"))
    ]


def offres_lever(entreprise: str, reponse: object) -> list[Offre]:
    return [
        Offre(
            entreprise=entreprise,
            poste=chaine(poste.get("text")),
            lieu=chaine(table(poste.get("categories")).get("location")),
            url=chaine(poste.get("hostedUrl")),
            source="lever",
            description=chaine(poste.get("descriptionPlain")),
        )
        for poste in map(table, liste(reponse))
        if chaine(poste.get("text"))
    ]


def offres_ashby(entreprise: str, reponse: object) -> list[Offre]:
    return [
        Offre(
            entreprise=entreprise,
            poste=chaine(poste.get("title")),
            lieu=chaine(poste.get("location")),
            url=chaine(poste.get("jobUrl")),
            source="ashby",
            description=chaine(poste.get("descriptionPlain")),
            date_publication=chaine(poste.get("publishedAt"))[:10],
        )
        for poste in map(table, liste(table(reponse).get("jobs")))
        if chaine(poste.get("title"))
    ]


def offres_smartrecruiters(entreprise: str, identifiant: str, reponse: object) -> list[Offre]:
    offres: list[Offre] = []
    for poste in map(table, liste(table(reponse).get("content"))):
        titre = chaine(poste.get("name"))
        if not titre:
            continue
        lieu = table(poste.get("location"))
        ville = chaine(lieu.get("city"))
        pays = chaine(lieu.get("country")).upper()
        offre_id = chaine(poste.get("id"))
        offres.append(
            Offre(
                entreprise=entreprise,
                poste=titre,
                lieu=", ".join(x for x in (ville, pays) if x),
                url=URL_SMARTRECRUITERS.format(id=identifiant, offre=offre_id) if offre_id else "",
                source="smartrecruiters",
                date_publication=chaine(poste.get("releasedDate"))[:10],
            )
        )
    return offres


def offres_recruitee(entreprise: str, reponse: object) -> list[Offre]:
    return [
        Offre(
            entreprise=entreprise,
            poste=chaine(poste.get("title")),
            lieu=chaine(poste.get("location")),
            url=chaine(poste.get("careers_url")),
            source="recruitee",
            description=texte_brut(chaine(poste.get("description"))),
            date_publication=chaine(poste.get("published_at"))[:10],
        )
        for poste in map(table, liste(table(reponse).get("offers")))
        if chaine(poste.get("title"))
    ]


def offres_workable(entreprise: str, reponse: object) -> list[Offre]:
    offres: list[Offre] = []
    for poste in map(table, liste(table(reponse).get("jobs"))):
        titre = chaine(poste.get("title"))
        if not titre:
            continue
        premier = table(next(iter(liste(poste.get("locations"))), None))
        ville = chaine(poste.get("city")) or chaine(premier.get("city"))
        pays = chaine(poste.get("country")) or chaine(premier.get("country"))
        morceaux = [x for x in (ville, pays) if x]
        if poste.get("telecommuting") is True:
            morceaux.append("Remote")
        offres.append(
            Offre(
                entreprise=entreprise,
                poste=titre,
                lieu=", ".join(morceaux),
                url=chaine(poste.get("url")),
                source="workable",
                description=texte_brut(chaine(poste.get("description"))),
                date_publication=chaine(poste.get("published_on"))[:10],
            )
        )
    return offres


def _texte(element: ET.Element, suffixe: str) -> str:
    """Texte du premier descendant de balise `suffixe`, espaces de noms ignorés."""
    for enfant in element.iter():
        if enfant.tag.rsplit("}", 1)[-1] == suffixe and enfant.text:
            return enfant.text.strip()
    return ""


def _date_rss(valeur: str) -> str:
    try:
        return parsedate_to_datetime(valeur).date().isoformat() if valeur else ""
    except (TypeError, ValueError):
        return ""


def offres_teamtailor(entreprise: str, flux: str) -> list[Offre]:
    """Lit le flux RSS public d'une page carrières Teamtailor."""
    try:
        racine = ET.fromstring(flux)
    except ET.ParseError:
        return []
    offres: list[Offre] = []
    for item in racine.iter("item"):
        titre = _texte(item, "title")
        if not titre:
            continue
        offres.append(
            Offre(
                entreprise=entreprise,
                poste=titre,
                lieu=_texte(item, "city") or _texte(item, "location"),
                url=_texte(item, "link"),
                source="teamtailor",
                description=texte_brut(_texte(item, "description")),
                date_publication=_date_rss(_texte(item, "pubDate")),
            )
        )
    return offres


_ANALYSEURS: dict[str, Callable[[str, Any], list[Offre]]] = {
    "greenhouse": offres_greenhouse,
    "lever": offres_lever,
    "ashby": offres_ashby,
    "recruitee": offres_recruitee,
    "workable": offres_workable,
}
_PRIS_EN_CHARGE = {*_ANALYSEURS, "smartrecruiters", "teamtailor"}


class SourceAts:
    """Les offres publiées par une entreprise sur son outil de recrutement."""

    def __init__(self, client: ClientHttp, entreprise: EntrepriseCible) -> None:
        if entreprise.ats not in _PRIS_EN_CHARGE:
            raise ValueError(f"{entreprise.nom} n'a pas d'ATS pris en charge")
        self._client = client
        self._entreprise = entreprise

    @property
    def nom(self) -> str:
        return f"{self._entreprise.ats}:{self._entreprise.nom}"

    def collecter(self) -> list[Offre]:
        ats = self._entreprise.ats
        identifiant = self._entreprise.identifiant
        url = ats_url(ats, identifiant)
        if ats == "teamtailor":
            return offres_teamtailor(self._entreprise.nom, self._client.get_texte(url))
        reponse = self._client.get_json(url, params=PARAMETRES.get(ats, {}))
        if ats == "smartrecruiters":
            return offres_smartrecruiters(self._entreprise.nom, identifiant, reponse)
        return _ANALYSEURS[ats](self._entreprise.nom, reponse)
