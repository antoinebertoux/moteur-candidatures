"""Notation des offres par lots : un seul appel court à Claude pour plusieurs offres."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

from moteur.base_locale import BaseLocale
from moteur.claude_cli import Assistant, ErreurClaude, extraire_json
from moteur.modeles import Note, Offre

journal = logging.getLogger(__name__)

LONGUEUR_DESCRIPTION = 1500
LONGUEUR_RESUME = 400

_CONSIGNES = """Tu tries des offres d'emploi pour le candidat décrit ci-dessous.
Pour chaque offre reçue, réponds par un objet JSON avec exactement ces champs :
- "cle" : la clé reçue, recopiée telle quelle ;
- "score" : entier de 0 à 100, adéquation entre l'offre et ce que cherche le candidat ;
- "resume" : deux phrases en français, ce qu'est le poste puis le point fort ou le point bloquant ;
- "lettre_demandee" : true seulement si l'offre demande une lettre de motivation ;
- "langue" : "en" si l'offre est rédigée en anglais, sinon "fr".
Réponds uniquement par un tableau JSON, sans texte autour.

Candidat :
"""


def systeme(profil: str) -> str:
    return _CONSIGNES + profil


def construire_prompt(offres: Sequence[Offre]) -> str:
    return json.dumps(
        [
            {
                "cle": offre.cle,
                "entreprise": offre.entreprise,
                "poste": offre.poste,
                "lieu": offre.lieu,
                "salaire": offre.salaire,
                "description": offre.description[:LONGUEUR_DESCRIPTION],
            }
            for offre in offres
        ],
        ensure_ascii=False,
    )


def analyser_reponse(texte: str, cles_attendues: set[str]) -> dict[str, Note]:
    """Extrait les notes valides ; ignore les entrées inconnues ou mal formées."""
    donnees = extraire_json(texte)
    if not isinstance(donnees, list):
        raise ErreurClaude("La notation doit être un tableau JSON")
    notes: dict[str, Note] = {}
    for entree in donnees:
        if not isinstance(entree, dict):
            continue
        cle = entree.get("cle")
        score = entree.get("score")
        if (
            cle not in cles_attendues
            or isinstance(score, bool)
            or not isinstance(score, int | float)
        ):
            continue
        notes[cle] = Note(
            score=max(0, min(100, round(score))),
            resume=str(entree.get("resume", ""))[:LONGUEUR_RESUME],
            lettre_demandee=entree.get("lettre_demandee") is True,
            langue="en" if entree.get("langue") == "en" else "fr",
        )
    return notes


def noter(
    base: BaseLocale, assistant: Assistant, *, profil: str, modele: str, taille_lot: int
) -> int:
    """Note toutes les offres en attente. Un lot en échec reste à noter au prochain passage."""
    offres = base.a_noter()
    notees = 0
    for debut in range(0, len(offres), taille_lot):
        lot = offres[debut : debut + taille_lot]
        try:
            reponse = assistant.demander(
                construire_prompt(lot), systeme=systeme(profil), modele=modele
            )
            notes = analyser_reponse(reponse, {offre.cle for offre in lot})
        except ErreurClaude as erreur:
            journal.warning("Lot de %d offres non noté : %s", len(lot), erreur)
            continue
        for cle, note in notes.items():
            base.enregistrer_note(cle, note)
        notees += len(notes)
    return notees
