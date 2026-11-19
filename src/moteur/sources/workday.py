"""Pages carrières Workday des grands groupes.

L'identifiant est l'adresse de la page carrières telle qu'elle s'affiche dans le
navigateur, par exemple « https://exemple.wd3.myworkdayjobs.com/fr-FR/Careers ».
Workday ne renvoie pas toutes les offres d'un coup : on interroge sa recherche
avec quelques mots-clés, page par page.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from moteur.config import EntrepriseCible
from moteur.modeles import Offre
from moteur.sources.base import (
    RECHERCHES_EN_PARALLELE,
    ClientHttp,
    chaine,
    en_parallele,
    liste,
    table,
)

RECHERCHES_PAR_DEFAUT = ("machine learning", "intelligence artificielle", "data scientist")
TAILLE_PAGE = 20
PAGES_MAX = 5
_LANGUE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


@dataclass(frozen=True, slots=True)
class SiteWorkday:
    hote: str
    tenant: str
    site: str

    @property
    def api(self) -> str:
        return f"https://{self.hote}/wday/cxs/{self.tenant}/{self.site}/jobs"

    def url_offre(self, chemin: str) -> str:
        return f"https://{self.hote}/{self.site}{chemin}" if chemin else ""


def decouper(adresse: str) -> SiteWorkday:
    """Extrait hôte, tenant et site d'une adresse de page carrières Workday."""
    morceaux = urlsplit(adresse if "://" in adresse else f"https://{adresse}")
    hote = morceaux.netloc
    segments = [s for s in morceaux.path.split("/") if s and not _LANGUE.match(s)]
    if not hote.endswith("myworkdayjobs.com") or not segments:
        raise ValueError(f"adresse Workday inattendue : {adresse}")
    return SiteWorkday(hote=hote, tenant=hote.split(".")[0], site=segments[0])


def offres_workday(entreprise: str, site: SiteWorkday, reponse: object) -> list[Offre]:
    return [
        Offre(
            entreprise=entreprise,
            poste=chaine(poste.get("title")),
            lieu=chaine(poste.get("locationsText")),
            url=site.url_offre(chaine(poste.get("externalPath"))),
            source="workday",
        )
        for poste in map(table, liste(table(reponse).get("jobPostings")))
        if chaine(poste.get("title"))
    ]


class SourceWorkday:
    def __init__(self, client: ClientHttp, entreprise: EntrepriseCible) -> None:
        self._client = client
        self._entreprise = entreprise
        self._site = decouper(entreprise.identifiant)
        self._recherches: Sequence[str] = entreprise.recherches or RECHERCHES_PAR_DEFAUT

    @property
    def nom(self) -> str:
        return f"workday:{self._entreprise.nom}"

    def _rechercher(self, recherche: str) -> list[Offre]:
        """Les offres d'un mot-clé, page après page."""
        trouvees: list[Offre] = []
        total = 0
        for page in range(PAGES_MAX):
            reponse = self._client.post_json(
                self._site.api,
                corps={
                    "appliedFacets": {},
                    "limit": TAILLE_PAGE,
                    "offset": page * TAILLE_PAGE,
                    "searchText": recherche,
                },
                entetes={"Accept": "application/json"},
            )
            offres = offres_workday(self._entreprise.nom, self._site, reponse)
            trouvees.extend(offres)
            # Workday n'indique le total que sur la première page.
            annonce = table(reponse).get("total")
            if isinstance(annonce, int) and annonce > 0:
                total = annonce
            if len(offres) < TAILLE_PAGE or (total and (page + 1) * TAILLE_PAGE >= total):
                break
        return trouvees

    def collecter(self) -> list[Offre]:
        vues: dict[str, Offre] = {}
        for offres in en_parallele(self._rechercher, self._recherches, RECHERCHES_EN_PARALLELE):
            for offre in offres:
                vues.setdefault(offre.url or offre.poste, offre)
        return list(vues.values())
