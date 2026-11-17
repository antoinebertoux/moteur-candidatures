"""Lettre de motivation seule, pour un dossier dont le CV existe déjà.

Sert à ajouter une lettre après coup (interrupteur « Lettre » activé dans la page, ou
`moteur lettre <id>`) sans régénérer ni modifier le CV.
"""

from __future__ import annotations

from moteur.base_locale import BaseLocale
from moteur.claude_cli import Assistant, ErreurClaude
from moteur.config import Chemins
from moteur.generation import (
    SYSTEME_LETTRE,
    Compilateur,
    ErreurGeneration,
    _compiler,
    _ecrire_fiche,
    _prompt,
    extraire_tex,
    nom_dossier,
    preparer_modele,
)
from moteur.modeles import Candidature


def generer_lettre(
    candidature: Candidature,
    assistant: Assistant,
    chemins: Chemins,
    modele: str,
    compilateur: Compilateur,
) -> str:
    """Écrit et compile `lettre.tex` du dossier ; renvoie la référence du PDF.

    Une lettre existante sert de point de départ seulement si une consigne de lettre
    l'accompagne ; sinon elle est réécrite depuis le squelette.
    """
    dossier = chemins.candidatures / nom_dossier(candidature.offre)
    dossier.mkdir(parents=True, exist_ok=True)
    _ecrire_fiche(dossier, candidature.offre)
    lettre = dossier / "lettre.tex"
    consigne = candidature.consigne_lettre
    if consigne and lettre.exists():
        depart = lettre.read_text(encoding="utf-8")
    else:
        squelette = (chemins.latex / "lettres" / "modele-lettre.tex").read_text(encoding="utf-8")
        depart = preparer_modele(squelette, candidature.langue)
    paragraphes = (chemins.latex / "lettres" / "banque-paragraphes.md").read_text(encoding="utf-8")
    prompt = _prompt(candidature, depart, paragraphes, consigne)
    lettre.write_text(
        extraire_tex(assistant.demander(prompt, systeme=SYSTEME_LETTRE, modele=modele)),
        encoding="utf-8",
    )
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
