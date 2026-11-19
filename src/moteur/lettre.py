"""Lettre de motivation seule, pour un dossier dont le CV existe déjà.

Sert à ajouter une lettre après coup (interrupteur « Lettre » activé dans la page, ou
`moteur lettre <id>`) sans régénérer ni modifier le CV.
"""

from __future__ import annotations

from moteur.base_locale import BaseLocale
from moteur.claude_cli import Assistant, ErreurClaude
from moteur.config import Chemins
from moteur.generation import (
    Compilateur,
    ErreurGeneration,
    _compiler,
    _ecrire_fiche,
    nom_dossier,
    write_letter,
)
from moteur.modeles import Candidature


def generer_lettre(
    candidature: Candidature,
    assistant: Assistant,
    chemins: Chemins,
    modele: str,
    compilateur: Compilateur,
) -> str:
    """Writes and compiles the folder's `lettre.tex`; returns the PDF reference."""
    dossier = chemins.candidatures / nom_dossier(candidature.offre)
    dossier.mkdir(parents=True, exist_ok=True)
    _ecrire_fiche(dossier, candidature.offre)
    lettre = dossier / "lettre.tex"
    write_letter(candidature, lettre, candidature.consigne_lettre, assistant, chemins, modele)
    pages = _compiler(dossier, lettre.name, compilateur).get(lettre.stem, 1)
    if pages > 1:
        raise ErreurGeneration(f"{dossier.name}/lettre.pdf fait {pages} pages : à reprendre")
    return str(lettre.with_suffix(".pdf").relative_to(chemins.racine))


def generer_lettres(
    base: BaseLocale,
    assistant: Assistant,
    chemins: Chemins,
    modele: str,
    compilateur: Compilateur,
    cles: list[str] | None = None,
) -> tuple[int, list[str]]:
    """Lettres des clés données, ou à défaut de tous les dossiers où elle manque."""
    if cles:
        candidatures, echecs = [], []
        for cle in cles:
            trouvee = base.trouver(cle)
            if trouvee is None:
                echecs.append(f"{cle} : inconnue de la base locale")
            else:
                candidatures.append(trouvee)
    else:
        candidatures, echecs = base.lettres_manquantes(), []
    reussites = 0
    for candidature in candidatures:
        offre = candidature.offre
        try:
            ref = generer_lettre(candidature, assistant, chemins, modele, compilateur)
        except (ErreurClaude, ErreurGeneration, OSError) as erreur:
            echecs.append(f"{offre.entreprise} — {offre.poste} : {erreur}")
            continue
        base.marquer_lettre(offre.cle, ref)
        reussites += 1
    return reussites, echecs
