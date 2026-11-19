"""Interview preparation sheet: what was sent, the company today, likely questions.

Rules PREP-xx of `specs/interview-prep.md`. The only Claude call given tools: web search
and page fetching, for the company research (CLA-04).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from moteur.base_locale import BaseLocale
from moteur.claude_cli import Assistant, ErreurClaude
from moteur.config import Chemins
from moteur.generation import _ecrire_fiche, nom_dossier
from moteur.modeles import Candidature, DemandePreparation, normaliser

journal = logging.getLogger(__name__)

OUTILS_WEB = ("WebSearch", "WebFetch")
DELAI_SECONDES = 900
LONGUEUR_MAX = 40_000
FICHIER_FICHE = "preparation-entretien.md"
FICHIER_JOURNAL = "preparation.log"
MAX_TEXTE_OFFRE = 8_000
COUPEE = "\n\n*(Fiche coupée : elle dépassait 40 000 caractères.)*"

# Sections of `infos-candidature.md` that may be sent to Claude (PREP-12).
_SECTIONS_PERMISES = ("situation", "preferences", "reponses-types")
# Lines never sent, whatever their section: the salary floor (INV-03).
_LIGNES_INTERDITES = ("critere-de-tri", "plancher")

SYSTEME_PREPARATION = """Tu prépares le candidat à un entretien d'embauche pour une \
candidature qu'il a envoyée. Tu écris une fiche en français, en Markdown, qu'il relira \
juste avant l'entretien.
Règles strictes :
1. Tu n'inventes aucune expérience, aucun chiffre, aucun fait sur le candidat : tout ce \
que tu dis de lui vient du CV, de la lettre, des banques et des informations fournies. Ce \
qui n'y est pas, tu le laisses de côté.
2. Pour l'entreprise, tu cherches sur le web (outils de recherche et de lecture de pages) \
des informations à jour. Chaque chiffre donne sa source et sa date. Ce que tu ne trouves \
pas, tu écris « non trouvé » : jamais de supposition.
3. La consigne du candidat, si elle existe, est prioritaire.
4. Plan, dans cet ordre, avec ces titres :
# Préparation : <entreprise> — <poste>
## À retenir
Quelques lignes : le poste, l'entreprise, la date d'envoi, les infos de l'entretien, le \
salaire annoncé (sinon « non renseigné : à décider avant l'entretien »), le préavis, ce \
que la lettre a promis.
## À relire en priorité
Chaque projet ou affirmation du CV et de la lettre qu'on risque de creuser, avec les \
chiffres et les faits à avoir en tête, tirés des banques.
## L'entreprise
Date de création, effectifs, chiffre d'affaires ou dernière levée de fonds (start-up : \
montant, date, investisseurs), dirigeants, produits, actualité des 12 derniers mois, \
concurrents ; pour un organisme public, sa mission et son rattachement.
## Le poste
Ce que l'offre demande vraiment, les points qui collent, les manques et comment y répondre.
## Questions probables
Une dizaine, chacune avec une réponse suggérée ou une histoire (situation, action, \
résultat) tirée de l'expérience réelle du candidat. Si l'offre est en anglais, les \
réponses sont en anglais.
## Questions à poser
Cinq à huit, propres à l'entreprise et au poste.
Réponds uniquement par la fiche, sans texte avant ni après."""


def maintenant() -> str:
    """Current time in the format of the page's `Date.toISOString()`."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def infos_permises(texte: str) -> str:
    """The parts of `infos-candidature.md` that Claude may read (PREP-12).

    Only the Situation, Préférences and Réponses types sections are kept, without any
    line about the sorting criterion or the salary floor (INV-03).
    """
    gardees: list[str] = []
    permise = False
    for ligne in texte.splitlines():
        if ligne.startswith("#"):
            titre = normaliser(ligne.lstrip("#"))
            permise = ligne.startswith("## ") and titre.startswith(_SECTIONS_PERMISES)
            if permise:
                gardees.append(ligne)
            continue
        if permise and not any(mot in normaliser(ligne) for mot in _LIGNES_INTERDITES):
            gardees.append(ligne)
    return "\n".join(gardees).strip()


def _lire(fichier: Path) -> str:
    try:
        return fichier.read_text(encoding="utf-8")
    except OSError:
        return ""


def prompt_preparation(
    candidature: Candidature, demande: DemandePreparation, chemins: Chemins, profil: str
) -> str:
    """What Claude receives for one sheet (PREP-10 to PREP-12)."""
    offre = candidature.offre
    dossier = chemins.candidatures / nom_dossier(offre)
    lignes = [f"Entreprise : {offre.entreprise}", f"Poste : {offre.poste}"]
    if offre.type == "spontanee":
        lignes.append("Candidature spontanée (pas d'offre publiée).")
    if offre.lieu:
        lignes.append(f"Lieu : {offre.lieu}")
    if offre.url:
        lignes.append(f"Lien de l'offre : {offre.url}")
    if candidature.resume:
        lignes.append(f"Résumé : {candidature.resume}")
    langue = "anglais" if candidature.langue == "en" else "français"
    lignes.append(f"Langue de l'offre : {langue}")
    parties = ["## Candidature\n" + "\n".join(lignes)]
    if demande.contexte:
        parties.append(f"## Suivi dans la page (dates, réponses, notes)\n{demande.contexte}")
    entretien = [
        f"Salaire annoncé par le candidat : {demande.pretentions or 'non renseigné'}",
    ]
    if demande.entretien_infos:
        entretien.append(f"Entretien : {demande.entretien_infos}")
    parties.append("## Entretien\n" + "\n".join(entretien))
    texte_offre = _lire(dossier / "offre.md") or offre.description
    if texte_offre:
        parties.append(f"## Texte de l'offre\n{texte_offre[:MAX_TEXTE_OFFRE]}")
    for nom, titre in (("cv.tex", "CV envoyé"), ("lettre.tex", "Lettre envoyée")):
        contenu = _lire(dossier / nom)
        if contenu:
            parties.append(f"## {titre} (LaTeX)\n```latex\n{contenu}\n```")
    if profil:
        parties.append(f"## Profil du candidat\n{profil}")
    banques = (
        (chemins.latex / "cv" / f"banque-{candidature.langue}.tex", "Banque du CV", "latex"),
        (chemins.latex / "lettres" / "banque-paragraphes.md", "Banque de paragraphes", "md"),
    )
    for fichier, titre, format_ in banques:
        contenu = _lire(fichier)
        if contenu:
            parties.append(f"## {titre}\n```{format_}\n{contenu}\n```")
    infos = infos_permises(_lire(chemins.latex / "commun" / "infos-candidature.md"))
    if infos:
        parties.append(f"## Situation et préférences du candidat\n{infos}")
    if demande.consigne:
        parties.append(f"## Consigne du candidat (prioritaire)\n{demande.consigne}")
    return "\n\n".join(parties)


def nettoyer_fiche(reponse: str) -> str:
    """The sheet in Claude's answer, cut at 40,000 characters (PREP-32)."""
    texte = reponse.strip()
    if texte.startswith("```"):
        texte = texte.split("\n", 1)[1] if "\n" in texte else ""
        if texte.rstrip().endswith("```"):
            texte = texte.rstrip()[:-3]
    lignes = texte.strip().splitlines()
    debut = next((i for i, ligne in enumerate(lignes) if ligne.startswith("# ")), 0)
    texte = "\n".join(lignes[debut:]).strip()
    if not texte:
        raise ErreurClaude("Fiche de préparation vide")
    if len(texte) > LONGUEUR_MAX:
        texte = texte[: LONGUEUR_MAX - len(COUPEE) - 1].rstrip() + COUPEE
    return texte + "\n"


def preparer_fiche(
    candidature: Candidature,
    demande: DemandePreparation,
    assistant: Assistant,
    chemins: Chemins,
    modele: str,
    profil: str,
) -> str:
    """Has Claude write the sheet and saves it in the folder; returns its text."""
    prompt = prompt_preparation(candidature, demande, chemins, profil)
    reponse = assistant.demander(
        prompt,
        systeme=SYSTEME_PREPARATION,
        modele=modele,
        outils=OUTILS_WEB,
        delai=DELAI_SECONDES,
    )
    fiche = nettoyer_fiche(reponse)
    dossier = chemins.candidatures / nom_dossier(candidature.offre)
    dossier.mkdir(parents=True, exist_ok=True)
    _ecrire_fiche(dossier, candidature.offre)
    (dossier / FICHIER_FICHE).write_text(fiche, encoding="utf-8")
    return fiche


def preparer(
    base: BaseLocale,
    assistant: Assistant,
    chemins: Chemins,
    modele: str,
    profil: str,
    cles: list[str] | None = None,
    horloge: Callable[[], str] = maintenant,
    essayees: set[str] | None = None,
) -> tuple[int, list[str]]:
    """Sheets of the given applications, or of every pending request (PREP-40).

    Without identifiers, pending requests are read again before ending, so that a
    request recorded meanwhile is not left behind (PREP-42). A failed sheet stays
    pending and is not retried in the same run (PREP-21).
    """
    reussites, echecs = 0, []
    essayees = set() if essayees is None else essayees
    a_faire = list(cles) if cles else _nouvelles(base, essayees)
    while a_faire:
        for cle in a_faire:
            essayees.add(cle)
            candidature = base.trouver(cle)
            if candidature is None:
                echecs.append(f"{cle} : inconnue de la base locale")
                continue
            offre = candidature.offre
            demande = base.demande_preparation(cle) or DemandePreparation(horloge())
            try:
                fiche = preparer_fiche(candidature, demande, assistant, chemins, modele, profil)
            except (ErreurClaude, OSError) as erreur:
                echecs.append(f"{offre.entreprise} — {offre.poste} : {erreur}")
                continue
            base.enregistrer_preparation(cle, fiche, horloge())
            reussites += 1
        a_faire = [] if cles else _nouvelles(base, essayees)
    return reussites, echecs


def _nouvelles(base: BaseLocale, essayees: set[str]) -> list[str]:
    return [cle for cle in base.preparations_en_attente() if cle not in essayees]


def preparer_seul(
    base: BaseLocale,
    assistant: Assistant,
    chemins: Chemins,
    modele: str,
    profil: str,
    cles: list[str] | None = None,
    horloge: Callable[[], str] = maintenant,
) -> tuple[int, list[str]] | None:
    """`preparer` while holding the lock; None if another run holds it (PREP-42).

    Once the lock is released, pending requests are checked once more: one recorded
    just before the release, whose background start found the lock still held, is not
    left behind.
    """
    reussites, echecs = 0, list[str]()
    essayees: set[str] = set()
    premier = True
    while premier or (not cles and _nouvelles(base, essayees)):
        with verrou(chemin_verrou(chemins)) as tenu:
            if not tenu:
                return None if premier else (reussites, echecs)
            faites, ratees = preparer(
                base, assistant, chemins, modele, profil, cles, horloge, essayees
            )
        reussites, echecs, premier = reussites + faites, echecs + ratees, False
    return reussites, echecs


def chemin_verrou(chemins: Chemins) -> Path:
    return chemins.base.parent / "preparation.lock"


def _processus_vivant(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _pid_du_verrou(fichier: Path) -> int:
    try:
        return int(fichier.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0


def verrou_tenu(fichier: Path) -> bool:
    """True if a living process holds the lock."""
    pid = _pid_du_verrou(fichier)
    return bool(pid) and _processus_vivant(pid)


@contextmanager
def verrou(fichier: Path) -> Iterator[bool]:
    """Yields true if this process holds the lock, false if another run holds it.

    A lock left by a process that no longer exists is taken over (PREP-42).
    """
    for _ in range(2):
        try:
            descripteur = os.open(fichier, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if verrou_tenu(fichier):
                yield False
                return
            fichier.unlink(missing_ok=True)
            continue
        with os.fdopen(descripteur, "w", encoding="utf-8") as sortie:
            sortie.write(str(os.getpid()))
        try:
            yield True
        finally:
            fichier.unlink(missing_ok=True)
        return
    yield False


def lancer_en_arriere_plan(config: Path, chemins: Chemins) -> None:
    """Starts `moteur preparer` detached, output to `echange/preparation.log` (PREP-41/43).

    Returns at once: the caller (the `decisions` tool) never waits for it. Nothing is
    started while a run holds the lock: that run picks up the new request itself.
    """
    if verrou_tenu(chemin_verrou(chemins)):
        return
    chemins.echange.mkdir(parents=True, exist_ok=True)
    with (chemins.echange / FICHIER_JOURNAL).open("w", encoding="utf-8") as sortie:
        subprocess.Popen(
            [sys.executable, "-m", "moteur.cli", "--config", str(config), "preparer"],
            stdin=subprocess.DEVNULL,
            stdout=sortie,
            stderr=subprocess.STDOUT,
            cwd=config.parent,
            start_new_session=True,
        )
    journal.info("moteur preparer lancé en arrière-plan")
