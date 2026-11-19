"""Sites carrières Radancy (TalentBrew), par exemple celui de Moody's.

Leur recherche est interdite aux robots par `robots.txt` ; le plan du site
(`sitemap.xml`) et les pages des offres sont autorisés. Le plan donne l'adresse de
chaque offre, `…/job/<ville>/<intitulé>/<organisation>/<numéro>`, d'où l'on tire un
intitulé et un lieu provisoires ; la page des offres retenues donne le reste.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from typing import Any
from urllib.parse import urlsplit

from moteur.config import EntrepriseCible
from moteur.modeles import Offre
from moteur.sources.base import ClientHttp, chaine, table, texte_brut

_DONNEES = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE
)


def _lisible(segment: str) -> str:
    """« new-york » → « New York »."""
    return " ".join(mot.capitalize() for mot in segment.split("-") if mot)


def offres_radancy(entreprise: str, plan: str) -> list[Offre]:
    """Les offres listées dans le plan du site ; les autres adresses sont ignorées."""
    try:
        racine = ET.fromstring(plan.lstrip("﻿"))
    except ET.ParseError:
        return []
    offres: list[Offre] = []
    for element in racine.iter():
        if element.tag.rsplit("}", 1)[-1] != "loc" or not element.text:
            continue
        adresse = element.text.strip()
        segments = [s for s in urlsplit(adresse).path.split("/") if s]
        if "job" not in segments:
            continue
        suite = segments[segments.index("job") + 1 :]
        if len(suite) != 4 or not suite[1]:
            continue
        ville, intitule = suite[0], suite[1]
        offres.append(
            Offre(
                entreprise=entreprise,
                poste=_lisible(intitule),
                lieu=_lisible(ville),
                url=adresse,
                source="radancy",
            )
        )
    return offres


def _offre_d_emploi(page: str) -> dict[str, Any]:
    """Les données `JobPosting` de la page, ou un objet vide."""
    for bloc in _DONNEES.findall(page):
        try:
            donnees = json.loads(bloc)
        except ValueError:
            continue
        for candidat in donnees if isinstance(donnees, list) else [donnees]:
            if table(candidat).get("@type") == "JobPosting":
                return table(candidat)
    return {}


def completer_radancy(offre: Offre, page: str) -> Offre:
    donnees = _offre_d_emploi(page)
    if not donnees:
        return offre
    return replace(
        offre,
        poste=chaine(donnees.get("title")) or offre.poste,
        description=texte_brut(chaine(donnees.get("description"))),
        date_publication=chaine(donnees.get("datePosted"))[:10],
    )


class SourceRadancy:
    def __init__(self, client: ClientHttp, entreprise: EntrepriseCible) -> None:
        self._client = client
        self._entreprise = entreprise
        hote = entreprise.identifiant.strip()
        self._hote = urlsplit(hote).netloc if "://" in hote else hote.strip("/")

    @property
    def nom(self) -> str:
        return f"radancy:{self._entreprise.nom}"

    def collecter(self) -> list[Offre]:
        plan = self._client.get_texte(f"https://{self._hote}/sitemap.xml")
        return offres_radancy(self._entreprise.nom, plan)

    def detailler(self, offre: Offre) -> Offre:
        return completer_radancy(offre, self._client.get_texte(offre.url))
