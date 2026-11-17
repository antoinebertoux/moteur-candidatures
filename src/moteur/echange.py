"""Fichiers échangés avec la page de suivi : propositions à importer, décisions à relire."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from moteur.modeles import Candidature


class ErreurEchange(ValueError):
    """Le fichier exporté par la page est illisible."""


@dataclass(frozen=True, slots=True)
class Decision:
    cle: str
    statut: str
    consigne: str = ""


def pour_la_page(candidatures: Iterable[Candidature]) -> list[dict[str, Any]]:
    """Format lu par le bouton « Importer » de la page.

    La page recalcule elle-même l'identifiant à partir du type, de l'entreprise et du
    poste : il ne faut donc pas le lui envoyer.
    """
    lignes: list[dict[str, Any]] = []
    for candidature in candidatures:
        offre = candidature.offre
        ligne: dict[str, Any] = {
            "type": offre.type,
            "entreprise": offre.entreprise,
            "poste": offre.poste,
            "lieu": offre.lieu,
            "url": offre.url,
            "source": offre.source,
            "moteur": "B",
            "resume": candidature.resume,
            "lettre_demandee": candidature.lettre_demandee,
        }
        if candidature.score is not None:
            ligne["score"] = candidature.score
        if candidature.cv_ref:
            ligne["cv_ref"] = candidature.cv_ref
        if candidature.lettre_ref:
            ligne["lettre_ref"] = candidature.lettre_ref
        lignes.append(ligne)
    return lignes


def serialiser(candidatures: Iterable[Candidature]) -> str:
    return json.dumps(pour_la_page(candidatures), ensure_ascii=False, indent=2)


def lire_decisions(texte: str) -> list[Decision]:
    """Lit l'export de la page (`{"candidatures": [...]}` ou directement le tableau)."""
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError as erreur:
        raise ErreurEchange("Export illisible : ce n'est pas du JSON") from erreur
    if isinstance(donnees, dict):
        donnees = donnees.get("candidatures")
    if not isinstance(donnees, list):
        raise ErreurEchange("Export illisible : tableau « candidatures » introuvable")
    decisions: list[Decision] = []
    for entree in donnees:
        if not isinstance(entree, dict):
            continue
        cle, statut = entree.get("id"), entree.get("statut")
        if isinstance(cle, str) and isinstance(statut, str):
            consigne = entree.get("consigne")
            decisions.append(Decision(cle, statut, consigne if isinstance(consigne, str) else ""))
    return decisions
