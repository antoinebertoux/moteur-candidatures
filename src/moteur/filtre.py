"""Tri des offres par règles simples, sans aucun appel à Claude."""

from __future__ import annotations

import re
from collections.abc import Iterable

from moteur.config import Criteres
from moteur.modeles import Offre, contient_expression

_MONTANT = re.compile(r"(\d+(?:[.,]\d+)?)\s*euros", re.IGNORECASE)
_MOIS = re.compile(r"sur\s+(\d+(?:[.,]\d+)?)\s*mois", re.IGNORECASE)


def salaire_annuel_max(libelle: str) -> int | None:
    """Borne haute annuelle d'un libellé France Travail, ou `None` si elle est inconnue.

    Exemples : « Annuel de 45000.0 Euros à 55000.0 Euros sur 12.0 mois »,
    « Mensuel de 3500.0 Euros sur 13.0 mois ».
    """
    montants = [float(m.replace(",", ".")) for m in _MONTANT.findall(libelle)]
    if not montants:
        return None
    debut = libelle.strip().lower()
    if debut.startswith("annuel"):
        return round(max(montants))
    if debut.startswith("mensuel"):
        mois = _MOIS.search(libelle)
        return round(max(montants) * (float(mois.group(1).replace(",", ".")) if mois else 12.0))
    return None


def correspond(offre: Offre, criteres: Criteres) -> bool:
    """Vrai si l'offre passe les critères. Une information absente ne fait jamais rejeter."""
    if criteres.mots_cles and not any(
        contient_expression(offre.poste, mot) for mot in criteres.mots_cles
    ):
        return False
    if any(contient_expression(offre.poste, mot) for mot in criteres.exclusions):
        return False
    if (
        criteres.lieux
        and offre.lieu
        and not any(contient_expression(offre.lieu, lieu) for lieu in criteres.lieux)
    ):
        return False
    if criteres.salaire_plancher:
        maximum = salaire_annuel_max(offre.salaire)
        if maximum is not None and maximum < criteres.salaire_plancher:
            return False
    return True


def filtrer(offres: Iterable[Offre], criteres: Criteres) -> list[Offre]:
    """Garde les offres qui correspondent, sans doublon (même entreprise et même intitulé)."""
    retenues: dict[str, Offre] = {}
    for offre in offres:
        if correspond(offre, criteres):
            retenues.setdefault(offre.cle, offre)
    return list(retenues.values())
