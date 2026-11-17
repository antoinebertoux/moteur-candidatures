"""Collecte : interroge les sources, filtre, et propose les candidatures spontanées."""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable, Sequence
from pathlib import Path

from moteur.config import Criteres, EntrepriseCible
from moteur.filtre import filtrer
from moteur.modeles import Offre, normaliser
from moteur.sources.base import ErreurSource, Source, SourceDetaillee

journal = logging.getLogger(__name__)


def entreprises_deja_vues(chemin: Path) -> set[str]:
    """Noms normalisés du fichier `suivi/entreprises_vues.csv` (vide s'il n'existe pas).

    Les lignes dont le statut mentionne « historique » (candidatures d'une ancienne
    recherche) sont ignorées : on peut de nouveau proposer ces entreprises.
    """
    if not chemin.exists():
        return set()
    with chemin.open(encoding="utf-8", newline="") as fichier:
        return {
            normaliser(ligne["entreprise"])
            for ligne in csv.DictReader(fichier, delimiter=";")
            if ligne.get("entreprise") and "historique" not in _statut(ligne).lower()
        }


def _statut(ligne: dict[str, str]) -> str:
    """Valeur de la colonne de statut, quel que soit le libellé exact de son en-tête."""
    for cle, valeur in ligne.items():
        if cle and cle.strip().lower().startswith("statut"):
            return valeur or ""
    return ""


def interroger(sources: Iterable[Source]) -> list[Offre]:
    """Rassemble les offres de toutes les sources ; une source en panne n'arrête pas les autres."""
    offres: list[Offre] = []
    for source in sources:
        try:
            trouvees = source.collecter()
        except ErreurSource as erreur:
            journal.warning("Source %s ignorée : %s", source.nom, erreur)
            continue
        journal.info("%s : %d offres", source.nom, len(trouvees))
        offres.extend(trouvees)
    return offres


def detailler(offres: Iterable[Offre], sources: Iterable[Source]) -> list[Offre]:
    """Ajoute le texte des offres retenues dont la source ne le donne qu'en ouvrant leur page.

    Fait après le filtrage, pour n'ouvrir que les pages des offres gardées.
    """
    par_nom = {source.nom: source for source in sources if isinstance(source, SourceDetaillee)}
    completees: list[Offre] = []
    for offre in offres:
        source = par_nom.get(offre.source)
        if source is not None and not offre.description:
            try:
                offre = source.detailler(offre)
            except ErreurSource as erreur:
                journal.warning("Texte de l'offre %s non récupéré : %s", offre.url, erreur)
        completees.append(offre)
    return completees


def spontanees(
    cibles: Sequence[EntrepriseCible], retenues: Sequence[Offre], deja_vues: set[str], role: str
) -> list[Offre]:
    """Une candidature spontanée par entreprise cible sans offre retenue et jamais approchée."""
    avec_offre = {normaliser(offre.entreprise) for offre in retenues}
    return [
        Offre(entreprise=cible.nom, poste=role, type="spontanee", url=cible.site, source="cible")
        for cible in cibles
        if cible.spontanee and normaliser(cible.nom) not in avec_offre | deja_vues
    ]


def collecter(
    sources: Sequence[Source],
    criteres: Criteres,
    cibles: Sequence[EntrepriseCible],
    deja_vues: set[str],
    role_spontane: str,
) -> list[Offre]:
    retenues = detailler(filtrer(interroger(sources), criteres), sources)
    return retenues + spontanees(cibles, retenues, deja_vues, role_spontane)
