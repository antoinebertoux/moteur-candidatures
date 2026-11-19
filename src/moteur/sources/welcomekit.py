"""Career sites hosted by Welcome Kit (Welcome to the Jungle), e.g. ``jobs.zama.org``.

The home page lists each job as a ``/jobs/<slug>`` link with its title; the slug ends
with the city. The page of each retained ad gives the exact title, location and text.
The Welcome to the Jungle site itself refuses automated requests and is not used.
"""

from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urlsplit

from moteur.config import EntrepriseCible
from moteur.modeles import Offre
from moteur.sources.base import ClientHttp, texte_brut

_LIEN = re.compile(
    r"<a[^>]*href=[\"'](/jobs/[^\"'?#]+)[\"'][^>]*>\s*<h3[^>]*jobs-list-item-title[^>]*>(.*?)</h3>",
    re.DOTALL | re.IGNORECASE,
)
_SPONTANEE = "candidatures-spontanees"
_TITRE = re.compile(r"<h1[^>]*main-header-title[^>]*>(.*?)</h1>", re.DOTALL | re.IGNORECASE)
_LIEU = re.compile(r"icon-location[^>]*>\s*</i>([^<]*)<", re.IGNORECASE)
_BLOC = re.compile(
    r"<div class=[\"']block block-job-text block-job-(about|description|profile|more)[\"']>",
    re.IGNORECASE,
)
_FIN = re.compile(r"<div class=[\"'](?:main-content|block block-job-text)", re.IGNORECASE)


def _lisible(segment: str) -> str:
    """« saint-malo » → « Saint Malo »."""
    return " ".join(mot.capitalize() for mot in segment.split("-") if mot)


def offres_welcomekit(entreprise: str, hote: str, page: str) -> list[Offre]:
    """The jobs listed on the career site's home page; the spontaneous link is ignored."""
    offres: list[Offre] = []
    vues: set[str] = set()
    for chemin, titre_html in _LIEN.findall(page):
        slug = chemin.rstrip("/").rsplit("/", 1)[-1]
        titre = texte_brut(titre_html)
        if not titre or slug == _SPONTANEE or chemin in vues:
            continue
        vues.add(chemin)
        ville = slug.rsplit("_", 1)[1] if "_" in slug else ""
        offres.append(
            Offre(
                entreprise=entreprise,
                poste=titre,
                lieu=_lisible(ville),
                url=f"https://{hote}{chemin}",
                source="welcomekit",
            )
        )
    return offres


def completer_welcomekit(offre: Offre, page: str) -> Offre:
    """Exact title, location and text from the ad's page; unchanged without text blocks."""
    debuts = [m.end() for m in _BLOC.finditer(page)]
    if not debuts:
        return offre
    morceaux = []
    for debut in debuts:
        fin = _FIN.search(page, debut)
        morceaux.append(texte_brut(page[debut : fin.start() if fin else len(page)]))
    titre = _TITRE.search(page)
    lieu = _LIEU.search(page)
    return replace(
        offre,
        poste=(texte_brut(titre.group(1)) if titre else "") or offre.poste,
        lieu=(texte_brut(lieu.group(1)) if lieu else "") or offre.lieu,
        description=" ".join(m for m in morceaux if m),
    )


class SourceWelcomeKit:
    def __init__(self, client: ClientHttp, entreprise: EntrepriseCible) -> None:
        self._client = client
        self._entreprise = entreprise
        hote = entreprise.identifiant.strip()
        self._hote = urlsplit(hote).netloc if "://" in hote else hote.strip("/")

    @property
    def nom(self) -> str:
        return f"welcomekit:{self._entreprise.nom}"

    def collecter(self) -> list[Offre]:
        page = self._client.get_texte(f"https://{self._hote}/")
        return offres_welcomekit(self._entreprise.nom, self._hote, page)

    def detailler(self, offre: Offre) -> Offre:
        return completer_welcomekit(offre, self._client.get_texte(offre.url))
