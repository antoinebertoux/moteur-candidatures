"""Choisir le service public : offres de la fonction publique (État, hospitalière, territoriale).

Le site n'a pas d'API de lecture ; on lit ses pages de résultats, dont l'adresse encode
les filtres : `/nos-offres/filtres/mot-cles/<mots>/domaine/<ids>/organisme/<ids>/page/<n>/`.
Les ministères (Armées, Intérieur…), DGSE, DGSI, DINUM, AMIAD, ANSSI (via le SGDSN)
et la plupart des établissements publics y publient leurs postes.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from urllib.parse import quote

from moteur.modeles import Offre, normaliser
from moteur.sources.base import ClientHttp, texte_brut

URL_RECHERCHE = "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/"
OFFRES_PAR_PAGE = 20

# Identifiants des filtres du site (valeurs des cases à cocher « Domaine » et « Employeur »).
DOMAINES = {
    "Défense": 3511,
    "Numérique": 3522,
    "Recherche": 3525,
    "Renseignement": 3527,
    "Sécurité": 3529,
    "Direction et pilotage des politiques publiques": 3512,
    "Organisation, contrôle et évaluation": 3523,
    "Environnement": 3514,
}
EMPLOYEURS = {
    # Défense
    "Ministère des armées": 5,
    "État-major des armées": 13346,
    "DGA": 13262,
    "DGSE": 364,
    "AMIAD": 14524,
    "DIRISI": 11480,
    "SSA": 2040,
    "ONERA": 382,
    # Intérieur
    "Ministère de l'Intérieur": 11,
    "DGSI": 13502,
    "Agence du numérique des forces de sécurité intérieure": 14499,
    "Commandement de la gendarmerie dans le cyberespace": 14542,
    # Premier ministre et interministériel
    "Premier ministre": 3,
    "DINUM": 10668,
    "SGDSN": 300,
    "Ministères économiques et financiers": 9,
    "INSEE": 978,
    "Ministère de l'Enseignement supérieur et de la Recherche": 13399,
    "CNRS": 602,
    "GIP ACYMA": 2554,
}

_CARTE = re.compile(r'class="fr-card fr-card--horizontal[^"]*fr-card--offer"')
_LIEN = re.compile(r'<h3 class="fr-card__title">\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_ELEMENT = re.compile(r'<li class="fr-icon-([a-z0-9-]+)[^"]*"[^>]*>(.*?)</li>', re.S)
_ETIQUETTE = re.compile(r'<span class="sr-only">.*?</span>', re.S)
_TOTAL = re.compile(r'<span class="number">\s*([\d\s]+)')
_DATE = re.compile(r"(\d{1,2})(?:er)?\s+([a-zéû]+)\s+(\d{4})")
_MOIS = {
    m: i
    for i, m in enumerate(
        (
            "janvier",
            "fevrier",
            "mars",
            "avril",
            "mai",
            "juin",
            "juillet",
            "aout",
            "septembre",
            "octobre",
            "novembre",
            "decembre",
        ),
        start=1,
    )
}


def identifiant(nom: str, table: dict[str, int]) -> int | None:
    """Identifiant d'un domaine ou employeur, donné par son nom (accents ignorés) ou en chiffres."""
    if nom.strip().isdigit():
        return int(nom)
    cible = normaliser(nom)
    return next((valeur for cle, valeur in table.items() if normaliser(cle) == cible), None)


def adresse(
    mots: str = "", domaines: Sequence[int] = (), employeurs: Sequence[int] = (), page: int = 1
) -> str:
    """Adresse d'une page de résultats ; l'ordre des filtres est imposé par le site."""
    morceaux = []
    if mots:
        morceaux.append(f"mot-cles/{quote(mots, safe='')}")
    if domaines:
        morceaux.append("domaine/" + "-".join(map(str, domaines)))
    if employeurs:
        morceaux.append("organisme/" + "-".join(map(str, employeurs)))
    if page > 1:
        morceaux.append(f"page/{page}")
    return URL_RECHERCHE + "".join(f"{m}/" for m in morceaux)


def date_francaise(texte: str) -> str:
    """« En ligne depuis le 16 novembre 2026 » -> « 2026-11-16 » (vide si illisible)."""
    trouve = _DATE.search(normaliser(texte).replace("-", " "))
    if not trouve:
        return ""
    jour, mois, annee = trouve.groups()
    numero = _MOIS.get(mois)
    return f"{annee}-{numero:02d}-{int(jour):02d}" if numero else ""


def total_annonce(page: str) -> int | None:
    trouve = _TOTAL.search(page)
    return int(re.sub(r"\s", "", trouve.group(1))) if trouve else None


def offres_service_public(page: str) -> list[Offre]:
    """Extrait les cartes d'offres d'une page de résultats."""
    offres: list[Offre] = []
    debuts = [m.start() for m in _CARTE.finditer(page)]
    for debut, fin in zip(debuts, [*debuts[1:], len(page)], strict=False):
        carte = page[debut:fin]
        lien = _LIEN.search(carte)
        if not lien:
            continue
        poste = texte_brut(lien.group(2))
        if not poste:
            continue
        champs = {
            icone: texte_brut(_ETIQUETTE.sub(" ", contenu))
            for icone, contenu in _ELEMENT.findall(carte)
        }
        offres.append(
            Offre(
                entreprise=champs.get("user-line") or "Fonction publique",
                poste=poste,
                lieu=champs.get("map-pin-2-line", ""),
                url=lien.group(1),
                source="service_public",
                date_publication=date_francaise(champs.get("calendar-line", "")),
            )
        )
    return offres


class SourceServicePublic:
    """Une recherche par mot-clé sur tout le site, puis la même chez les employeurs suivis.

    Les résultats sont triés par pertinence : la seconde passe rattrape les offres des
    employeurs suivis qui seraient au-delà des premières pages de la recherche générale.
    """

    def __init__(
        self,
        client: ClientHttp,
        recherches: Sequence[str],
        domaines: Sequence[int] = (),
        employeurs: Sequence[int] = (),
        pages_max: int = 3,
    ) -> None:
        self._client = client
        self._recherches = recherches
        self._domaines = domaines
        self._employeurs = employeurs
        self._pages_max = pages_max

    @property
    def nom(self) -> str:
        return "service_public"

    def _parcourir(self, mots: str, employeurs: Sequence[int], vues: dict[str, Offre]) -> None:
        for page in range(1, self._pages_max + 1):
            contenu = self._client.get_texte(adresse(mots, self._domaines, employeurs, page))
            offres = offres_service_public(contenu)
            for offre in offres:
                vues.setdefault(offre.url, offre)
            total = total_annonce(contenu)
            if len(offres) < OFFRES_PAR_PAGE or (
                total is not None and page * OFFRES_PAR_PAGE >= total
            ):
                break

    def collecter(self) -> list[Offre]:
        vues: dict[str, Offre] = {}
        for mots in self._recherches or ("",):
            self._parcourir(mots, (), vues)
            if self._employeurs:
                self._parcourir(mots, self._employeurs, vues)
        return list(vues.values())
