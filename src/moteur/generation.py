"""Préparation d'un dossier de candidature : CV et lettre LaTeX adaptés, puis compilés.

S'appuie sur le dépôt `latex/` existant : modèle de CV, banque de blocs, squelette de
lettre, banque de paragraphes et `compiler.sh`.
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

from moteur.base_locale import BaseLocale
from moteur.claude_cli import Assistant, ErreurClaude, ResultatProcessus, extraire_bloc
from moteur.config import Chemins
from moteur.modeles import Candidature, Langue, Offre

journal = logging.getLogger(__name__)

Compilateur = Callable[[Path, str], ResultatProcessus]
"""Compile un fichier `.tex` d'un dossier de candidature."""

RACINE_LATEX = r"\def\latexroot{../../latex/}"
_LIGNE_RACINE = re.compile(r"\\def\\latexroot\{[^}]*\}")
_BANQUE = re.compile(r"cv/banque-(?:fr|en)")
_INTERDITS = re.compile(r'[/\\:*?"<>|\x00-\x1f]+')
_ESPACES = re.compile(r"\s+")
_TROP_DE_PAGES = re.compile(r"(\S+)\.pdf fait (\d+) pages")
_EUROFINS = re.compile(
    r"(\\datedexperience\{Eurofins\}.*?\\explanationdetail\{%?)(.*?)(\n?\s*\}\s*\n)", re.S
)
_PUCE = re.compile(r"\\p[A-Z]\w*")
_PROJETS = re.compile(r"(\\section\{\\secProjets\}[^\n]*\n)(.*?)(\n\s*\\section)", re.S)
_PROJET = re.compile(r"\\proj[A-Z]\w*")
MIN_PUCES = 5

SYSTEME_CV = """Tu adaptes un CV LaTeX à une offre d'emploi.
Règles strictes :
1. Tu ne changes que le choix des macros : titre (\\setjob), accroche (\\setjobsearch), \
compétences, puces d'expérience, projets, centres d'intérêt.
2. Tu n'utilises que des macros définies dans la banque fournie. Tu n'écris aucun texte \
libre, tu n'inventes aucune expérience et aucune macro.
3. Accroche : une seule, celle de la banque dont le commentaire « Usage » correspond le \
mieux à l'offre.
4. Expérience Eurofins : pars de toutes les puces \\p... de la banque, retire celles qui \
sont vraiment sans rapport avec l'offre (garde-en au moins 7), puis range les autres, \
séparées par \\\\, de la plus pertinente à la moins pertinente. Le programme retire \
ensuite les dernières jusqu'à ce que le CV remplisse exactement une page : l'ordre est \
décisif.
5. Projets académiques : mets les deux projets de la banque, le plus pertinent en premier.
6. Centres d'intérêt : \\extraEscalade et \\extraJeux. \\extraGeoPo seulement si le poste \
est axé défense (DGSE, ministère des Armées, DGA, AID, CND, industriel de défense) ; \
jamais ailleurs, ni dans le reste du secteur public (justice, intérieur, finances, \
régulateurs, etc.).
7. Tu conserves le préambule et la structure du fichier de départ.
Réponds uniquement par le fichier cv.tex complet, dans un bloc ```latex."""

SYSTEME_LETTRE = """Tu rédiges une lettre de motivation LaTeX à partir d'un squelette.
Règles strictes :
1. Tu conserves le préambule, les macros et la structure du squelette ; tu remplaces le \
contenu des \\lettercontent{...} et le nom de l'entreprise.
2. Tu pars des paragraphes de la banque fournie et tu les adaptes à l'entreprise et au poste.
3. Tu n'inventes aucun fait sur le candidat : tout vient de la banque de paragraphes.
4. La lettre tient sur une page, sans formule creuse. Échappe les caractères spéciaux LaTeX.
Réponds uniquement par le fichier lettre.tex complet, dans un bloc ```latex."""


class ErreurGeneration(Exception):
    """Le dossier n'a pas pu être généré ou compilé."""


def nom_dossier(offre: Offre) -> str:
    """Nom de dossier stable pour une candidature, sans caractère interdit."""
    suffixe = "spontanée" if offre.type == "spontanee" else offre.poste
    brut = _INTERDITS.sub(" ", f"{offre.entreprise} - {suffixe}")
    return _ESPACES.sub(" ", brut).strip(" .")[:100].strip(" .")


def preparer_modele(tex: str, langue: Langue) -> str:
    """Adapte un modèle du dépôt pour qu'il compile depuis Candidatures/<dossier>/."""
    avec_racine = _LIGNE_RACINE.sub(lambda _: RACINE_LATEX, tex)
    return _BANQUE.sub(f"cv/banque-{langue}", avec_racine)


def extraire_tex(reponse: str) -> str:
    """Fichier LaTeX complet contenu dans la réponse de Claude."""
    tex = extraire_bloc(reponse)
    if "\\documentclass" not in tex or "\\end{document}" not in tex:
        raise ErreurClaude("La réponse ne contient pas un fichier LaTeX complet")
    return _LIGNE_RACINE.sub(lambda _: RACINE_LATEX, tex) + "\n"


def pages_en_trop(sortie: str) -> dict[str, int]:
    """Fichiers signalés par compiler.sh comme dépassant une page."""
    return {nom: int(pages) for nom, pages in _TROP_DE_PAGES.findall(sortie)}


def compilateur_latex(latex: Path) -> Compilateur:
    """Compilateur réel : lance `latex/compiler.sh <dossier> <fichier>`."""

    def compiler(dossier: Path, fichier: str) -> ResultatProcessus:
        try:
            resultat = subprocess.run(
                [str(latex / "compiler.sh"), str(dossier), fichier],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as erreur:
            raise ErreurGeneration(f"compiler.sh n'a pas pu s'exécuter : {erreur}") from erreur
        return ResultatProcessus(resultat.returncode, resultat.stdout, resultat.stderr)

    return compiler


def _description_offre(candidature: Candidature) -> str:
    offre = candidature.offre
    lignes = [f"Entreprise : {offre.entreprise}", f"Poste : {offre.poste}"]
    if offre.lieu:
        lignes.append(f"Lieu : {offre.lieu}")
    if offre.type == "spontanee":
        lignes.append("Candidature spontanée : aucune offre publiée, vise le rôle indiqué.")
    if candidature.resume:
        lignes.append(f"Résumé : {candidature.resume}")
    if offre.description:
        lignes.append(f"Texte de l'offre :\n{offre.description[:6000]}")
    return "\n".join(lignes)


def _prompt(candidature: Candidature, depart: str, banque: str, consigne: str) -> str:
    langue = "anglais" if candidature.langue == "en" else "français"
    parties = [
        f"## Offre\n{_description_offre(candidature)}",
        f"## Langue du document\n{langue}",
        f"## Fichier de départ\n```latex\n{depart}\n```",
        f"## Banque\n```\n{banque}\n```",
    ]
    if consigne:
        parties.append(f"## Consigne du candidat (prioritaire)\n{consigne}")
    return "\n\n".join(parties)


def _ecrire_fiche(dossier: Path, offre: Offre) -> None:
    fiche = dossier / "offre.md"
    if fiche.exists():
        return
    fiche.write_text(
        f"# {offre.entreprise} — {offre.poste}\n- Lien : {offre.url}\n- Source : {offre.source}\n"
        f"\n## Texte de l'offre\n{offre.description}\n",
        encoding="utf-8",
    )


def _compiler(dossier: Path, fichier: str, compilateur: Compilateur) -> dict[str, int]:
    resultat = compilateur(dossier, fichier)
    if resultat.code != 0:
        fin = (resultat.sortie + resultat.erreur).strip()[-800:]
        raise ErreurGeneration(f"La compilation a échoué dans {dossier.name} :\n{fin}")
    return pages_en_trop(resultat.sortie)


def contenu_cv(tex: str) -> tuple[list[str], list[str]]:
    """Puces Eurofins et projets du CV, dans l'ordre de pertinence choisi par Claude."""
    eurofins = _EUROFINS.search(tex)
    projets = _PROJETS.search(tex)
    return (
        _PUCE.findall(eurofins.group(2)) if eurofins else [],
        _PROJET.findall(projets.group(2)) if projets else [],
    )


def avec_contenu(tex: str, puces: list[str], projets: list[str]) -> str:
    """Le CV avec seulement ces puces Eurofins et ces projets."""
    tex = _EUROFINS.sub(
        lambda m: m.group(1) + "\n" + " \\\\\n".join(puces) + m.group(3), tex, count=1
    )
    return _PROJETS.sub(lambda m: m.group(1) + "\n".join(projets) + m.group(3), tex, count=1)


def versions_reduites(
    puces: list[str], projets: list[str]
) -> Iterator[tuple[list[str], list[str]]]:
    """Du CV complet au plus court : d'abord le second projet, puis les dernières puces."""
    yield puces, projets
    while len(projets) > 1:
        projets = projets[:-1]
        yield puces, projets
    while len(puces) > MIN_PUCES:
        puces = puces[:-1]
        yield puces, projets


def ajuster_cv(cv: Path, compilateur: Compilateur) -> int:
    """Garde le plus de contenu possible sur une page ; renvoie le nombre de pages final."""
    tex = cv.read_text(encoding="utf-8")
    puces, projets = contenu_cv(tex)
    pages = 1
    for puces_gardees, projets_gardes in versions_reduites(puces, projets):
        cv.write_text(avec_contenu(tex, puces_gardees, projets_gardes), encoding="utf-8")
        pages = _compiler(cv.parent, cv.name, compilateur).get(cv.stem, 1)
        if pages == 1:
            break
    return pages


def generer_dossier(
    candidature: Candidature,
    assistant: Assistant,
    chemins: Chemins,
    modele: str,
    compilateur: Compilateur,
) -> tuple[str, str]:
    """Génère et compile le dossier ; renvoie les chemins du CV et de la lettre ('' si aucune)."""
    offre, langue = candidature.offre, candidature.langue
    dossier = chemins.candidatures / nom_dossier(offre)
    dossier.mkdir(parents=True, exist_ok=True)
    _ecrire_fiche(dossier, offre)

    cv = dossier / "cv.tex"
    banque_cv = (chemins.latex / "cv" / f"banque-{langue}.tex").read_text(encoding="utf-8")
    if candidature.consigne and cv.exists():
        depart_cv = cv.read_text(encoding="utf-8")
    else:
        modele_cv = (chemins.latex / "cv" / "modele-cv.tex").read_text(encoding="utf-8")
        depart_cv = preparer_modele(modele_cv, langue)

    prompt_cv = _prompt(candidature, depart_cv, banque_cv, candidature.consigne)
    cv.write_text(
        extraire_tex(assistant.demander(prompt_cv, systeme=SYSTEME_CV, modele=modele)),
        encoding="utf-8",
    )

    lettre = dossier / "lettre.tex"
    avec_lettre = candidature.lettre_demandee or offre.type == "spontanee"
    if avec_lettre:
        if candidature.consigne and lettre.exists():
            depart_lettre = lettre.read_text(encoding="utf-8")
        else:
            squelette = (chemins.latex / "lettres" / "modele-lettre.tex").read_text(
                encoding="utf-8"
            )
            depart_lettre = preparer_modele(squelette, langue)
        paragraphes = (chemins.latex / "lettres" / "banque-paragraphes.md").read_text(
            encoding="utf-8"
        )
        prompt = _prompt(candidature, depart_lettre, paragraphes, candidature.consigne)
        lettre.write_text(
            extraire_tex(assistant.demander(prompt, systeme=SYSTEME_LETTRE, modele=modele)),
            encoding="utf-8",
        )

    pages = {"cv": ajuster_cv(cv, compilateur)}
    if avec_lettre:
        pages.update(_compiler(dossier, lettre.name, compilateur))
    for nom, nb in pages.items():
        if nb > 1:
            journal.warning("%s/%s.pdf fait %d pages : à reprendre", dossier.name, nom, nb)

    def reference(fichier: Path) -> str:
        return str(fichier.with_suffix(".pdf").relative_to(chemins.racine))

    return reference(cv), reference(lettre) if avec_lettre else ""


def generer(
    base: BaseLocale,
    assistant: Assistant,
    chemins: Chemins,
    modele: str,
    compilateur: Compilateur,
) -> tuple[int, list[str]]:
    """Génère tous les dossiers acceptés. Renvoie le nombre de réussites et les échecs."""
    reussites, echecs = 0, []
    for candidature in base.a_generer():
        offre = candidature.offre
        try:
            cv_ref, lettre_ref = generer_dossier(
                candidature, assistant, chemins, modele, compilateur
            )
        except (ErreurClaude, ErreurGeneration, OSError) as erreur:
            echecs.append(f"{offre.entreprise} — {offre.poste} : {erreur}")
            continue
        base.marquer_generee(offre.cle, cv_ref, lettre_ref)
        reussites += 1
    return reussites, echecs
