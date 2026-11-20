"""Preparing an application folder: tailored LaTeX CV and letter, then compiled.

Relies on the existing `latex/` repository: CV template, block bank, letter skeleton,
paragraph bank and `compiler.sh`.
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

from moteur.claude_cli import Assistant, ClaudeError, ProcessResult, extract_block
from moteur.config import Paths
from moteur.local_db import LocalDb
from moteur.models import Application, JobAd, Language

log = logging.getLogger(__name__)

Compiler = Callable[[Path, str], ProcessResult]
"""Compile un fichier `.tex` d'un dossier de candidature."""

LATEX_ROOT = r"\def\latexroot{../../latex/}"
_ROOT_LINE = re.compile(r"\\def\\latexroot\{[^}]*\}")
_BANK = re.compile(r"cv/banque-(?:fr|en)")
_FORBIDDEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]+')
_SPACES = re.compile(r"\s+")
_TOO_MANY_PAGES = re.compile(r"(\S+)\.pdf fait (\d+) pages")
_CONTACT_LINE = r"\\newcommand\{{\\{}\}}\{{([^}}]*)\}}"
_EUROFINS = re.compile(
    r"(\\datedexperience\{Eurofins\}.*?\\explanationdetail\{%?)(.*?)(\n?\s*\}\s*\n)", re.S
)
_BULLET = re.compile(r"\\p[A-Z]\w*")
_PROJECTS = re.compile(r"(\\section\{\\secProjets\}[^\n]*\n)(.*?)(\n\s*\\section)", re.S)
_PROJECT = re.compile(r"\\proj[A-Z]\w*")
MIN_BULLETS = 5

CV_SYSTEM = """Tu adaptes un CV LaTeX à une offre d'emploi.
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

LETTER_SYSTEM = """Tu rédiges une lettre de motivation LaTeX à partir d'un squelette.
Règles strictes :
1. Tu conserves le préambule, les macros et la structure du squelette ; tu remplaces le \
contenu des \\lettercontent{...} et ENTREPRISE dans \\companyname.
2. Langue : celle indiquée. En anglais, salutation « Dear Hiring Manager, » et formule \
finale anglaise de la banque.
3. Entre la salutation et la formule finale, quatre paragraphes : accroche (le poste \
exact et pourquoi cette entreprise) ; une ou deux réalisations Eurofins qui répondent aux \
exigences précises de l'offre ; ce que le candidat apporte au-delà du technique ; \
pourquoi eux, avec des éléments concrets tirés de l'offre ou du résumé.
4. Tu n'inventes aucun fait sur le candidat : tout vient de la banque de paragraphes, \
dont tu respectes les « points à vérifier ». N'écris jamais que le candidat est certifié \
en IA générative. Aucun salaire, aucune prétention. Géopolitique ou podcast Le Collimateur \
seulement pour un poste axé défense.
5. Candidature spontanée : pas d'offre publiée ; propose le rôle indiqué et appuie-toi \
sur l'angle du résumé.
6. Style direct et concret : pas de formule creuse (« passionné », « dynamique », \
« je me permets »), pas de recopie de l'offre. 250 à 350 mots : la lettre tient sur une \
page. Échappe les caractères spéciaux LaTeX (& % $ # _).
Réponds uniquement par le fichier lettre.tex complet, dans un bloc ```latex."""


class GenerationError(Exception):
    """The folder could not be generated or compiled."""


def folder_name(ad: JobAd) -> str:
    """Stable folder name for an application, without forbidden characters."""
    suffix = "spontanée" if ad.type == "spontanee" else ad.title
    raw = _FORBIDDEN.sub(" ", f"{ad.company} - {suffix}")
    return _SPACES.sub(" ", raw).strip(" .")[:100].strip(" .")


def prepare_template(tex: str, language: Language) -> str:
    """Adapts a repository template so that it compiles from Candidatures/<folder>/."""
    with_root = _ROOT_LINE.sub(lambda _: LATEX_ROOT, tex)
    return _BANK.sub(f"cv/banque-{language}", with_root)


def extract_tex(answer: str) -> str:
    """Complete LaTeX file contained in Claude's answer."""
    tex = extract_block(answer)
    if "\\documentclass" not in tex or "\\end{document}" not in tex:
        raise ClaudeError("The answer does not contain a complete LaTeX file")
    return _ROOT_LINE.sub(lambda _: LATEX_ROOT, tex) + "\n"


def extra_pages(output: str) -> dict[str, int]:
    """Files reported by compiler.sh as longer than one page."""
    return {name: int(pages) for name, pages in _TOO_MANY_PAGES.findall(output)}


def latex_compiler(latex: Path) -> Compiler:
    """Real compiler: runs `latex/compiler.sh <folder> <file>`."""

    def compiler(folder: Path, file: str) -> ProcessResult:
        try:
            result = subprocess.run(
                [str(latex / "compiler.sh"), str(folder), file],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GenerationError(f"compiler.sh could not run: {error}") from error
        return ProcessResult(result.returncode, result.stdout, result.stderr)

    return compiler


def _ad_description(application: Application) -> str:
    ad = application.ad
    rows = [f"Entreprise : {ad.company}", f"Poste : {ad.title}"]
    if ad.location:
        rows.append(f"Lieu : {ad.location}")
    if ad.type == "spontanee":
        rows.append("Candidature spontanée : aucune offre publiée, vise le rôle indiqué.")
    if application.summary:
        rows.append(f"Résumé : {application.summary}")
    if ad.description:
        rows.append(f"Texte de l'offre :\n{ad.description[:6000]}")
    return "\n".join(rows)


def _prompt(application: Application, start_point: str, bank: str, instruction: str) -> str:
    language = "anglais" if application.language == "en" else "français"
    parts = [
        f"## Offre\n{_ad_description(application)}",
        f"## Langue du document\n{language}",
        f"## Fichier de départ\n```latex\n{start_point}\n```",
        f"## Banque\n```\n{bank}\n```",
    ]
    if instruction:
        parts.append(f"## Consigne du candidat (prioritaire)\n{instruction}")
    return "\n\n".join(parts)


def _write_sheet(folder: Path, ad: JobAd) -> None:
    sheet = folder / "offre.md"
    if sheet.exists():
        return
    sheet.write_text(
        f"# {ad.company} — {ad.title}\n- Lien : {ad.url}\n- Source : {ad.source}\n"
        f"\n## Texte de l'offre\n{ad.description}\n",
        encoding="utf-8",
    )


def _compile(folder: Path, file: str, compile_fn: Compiler) -> dict[str, int]:
    result = compile_fn(folder, file)
    if result.code != 0:
        end = (result.output + result.error).strip()[-800:]
        raise GenerationError(f"Compilation failed in {folder.name}:\n{end}")
    return extra_pages(result.output)


def cv_contents(tex: str) -> tuple[list[str], list[str]]:
    """Eurofins bullets and projects of the CV, in the order of relevance chosen by Claude."""
    eurofins = _EUROFINS.search(tex)
    projects = _PROJECTS.search(tex)
    return (
        _BULLET.findall(eurofins.group(2)) if eurofins else [],
        _PROJECT.findall(projects.group(2)) if projects else [],
    )


def with_content(tex: str, bullets: list[str], projects: list[str]) -> str:
    """The CV with only these Eurofins bullets and these projects."""
    tex = _EUROFINS.sub(
        lambda m: m.group(1) + "\n" + " \\\\\n".join(bullets) + m.group(3), tex, count=1
    )
    return _PROJECTS.sub(lambda m: m.group(1) + "\n".join(projects) + m.group(3), tex, count=1)


def reduced_versions(
    bullets: list[str], projects: list[str]
) -> Iterator[tuple[list[str], list[str]]]:
    """From the full CV to the shortest: first the second project, then the last bullets."""
    yield bullets, projects
    while len(projects) > 1:
        projects = projects[:-1]
        yield bullets, projects
    while len(bullets) > MIN_BULLETS:
        bullets = bullets[:-1]
        yield bullets, projects


def fit_cv(cv: Path, compile_fn: Compiler) -> int:
    """Keeps as much content as possible on one page; returns the final page count.

    First removes the second project then the last bullets until it fits on one page,
    then fills the remaining space with the shorter removed items, in order.
    """
    tex = cv.read_text(encoding="utf-8")
    bullets, projects = cv_contents(tex)

    def attempt(p: list[str], pr: list[str]) -> int:
        cv.write_text(with_content(tex, p, pr), encoding="utf-8")
        return _compile(cv.parent, cv.name, compile_fn).get(cv.stem, 1)

    pages, kept_bullets, kept_projects = 1, bullets, projects
    for kept_bullets, kept_projects in reduced_versions(bullets, projects):
        pages = attempt(kept_bullets, kept_projects)
        if pages == 1:
            break
    if pages > 1:
        return pages
    # The first removed item does not fit; the next, shorter ones may.
    candidates = [(x, True) for x in bullets if x not in kept_bullets][1:]
    candidates += [(x, False) for x in projects if x not in kept_projects]
    last_try_fitted = True
    for element, is_bullet in candidates:
        bullets_try = (
            [x for x in bullets if x in kept_bullets or x == element] if is_bullet else kept_bullets
        )
        projects_try = (
            kept_projects
            if is_bullet
            else [x for x in projects if x in kept_projects or x == element]
        )
        last_try_fitted = attempt(bullets_try, projects_try) == 1
        if last_try_fitted:
            kept_bullets, kept_projects = bullets_try, projects_try
    if not last_try_fitted:
        attempt(kept_bullets, kept_projects)
    return 1


def write_letter(
    application: Application,
    letter: Path,
    instruction: str,
    assistant: Assistant,
    paths: Paths,
    model: str,
) -> None:
    """Writes `lettre.tex` (not compiled), shared by the full folder and the letter alone.

    An existing letter is the starting point only when an instruction comes with it;
    otherwise the letter is rewritten from the skeleton.
    """
    if instruction and letter.exists():
        start = letter.read_text(encoding="utf-8")
    else:
        skeleton = (paths.latex / "lettres" / "modele-lettre.tex").read_text(encoding="utf-8")
        start = prepare_template(skeleton, application.language)
    paragraphs = (paths.latex / "lettres" / "banque-paragraphes.md").read_text(encoding="utf-8")
    prompt = _prompt(application, start, paragraphs, instruction)
    letter.write_text(
        extract_tex(assistant.ask(prompt, system=LETTER_SYSTEM, model=model)),
        encoding="utf-8",
    )


def cv_pdf_name(latex: Path) -> str:
    """Name of the compiled CV, from the first and last name in `commun/coordonnees.tex` (CV-16)."""
    try:
        details = (latex / "commun" / "coordonnees.tex").read_text(encoding="utf-8")
    except OSError:
        return "cv.pdf"
    parts = []
    for macro in ("coPrenom", "coNom"):
        found = re.search(_CONTACT_LINE.format(macro), details)
        value = _SPACES.sub("-", _FORBIDDEN.sub("-", found.group(1).strip())) if found else ""
        if not value:
            return "cv.pdf"
        parts.append(value)
    return f"cv_{parts[0]}_{parts[1]}.pdf"


def generate_folder(
    application: Application,
    assistant: Assistant,
    paths: Paths,
    model: str,
    compile_fn: Compiler,
) -> tuple[str, str]:
    """Generates and compiles the folder; returns the CV and letter paths ('' if none)."""
    ad, language = application.ad, application.language
    folder = paths.applications / folder_name(ad)
    folder.mkdir(parents=True, exist_ok=True)
    _write_sheet(folder, ad)

    cv = folder / "cv.tex"
    cv_bank = (paths.latex / "cv" / f"banque-{language}.tex").read_text(encoding="utf-8")
    if application.instruction and cv.exists():
        starting_cv = cv.read_text(encoding="utf-8")
    else:
        cv_template = (paths.latex / "cv" / "modele-cv.tex").read_text(encoding="utf-8")
        starting_cv = prepare_template(cv_template, language)

    cv_prompt_text = _prompt(application, starting_cv, cv_bank, application.instruction)
    cv.write_text(
        extract_tex(assistant.ask(cv_prompt_text, system=CV_SYSTEM, model=model)),
        encoding="utf-8",
    )

    letter = folder / "lettre.tex"
    with_letter = application.letter_requested or ad.type == "spontanee"
    if with_letter:
        write_letter(application, letter, application.instruction, assistant, paths, model)

    pages = {"cv": fit_cv(cv, compile_fn)}
    if with_letter:
        pages.update(_compile(folder, letter.name, compile_fn))
    for name, count in pages.items():
        if count > 1:
            log.warning("%s/%s.pdf has %d pages: to rework", folder.name, name, count)

    def reference(file: Path) -> str:
        return str(file.with_suffix(".pdf").relative_to(paths.root))

    cv_pdf = folder / cv_pdf_name(paths.latex)
    compiled = cv.with_suffix(".pdf")
    if compiled != cv_pdf and compiled.exists():
        compiled.replace(cv_pdf)
    return reference(cv_pdf), reference(letter) if with_letter else ""


def generate(
    base: LocalDb,
    assistant: Assistant,
    paths: Paths,
    model: str,
    compile_fn: Compiler,
) -> tuple[int, list[str]]:
    """Generates every accepted folder. Returns the number of successes and the failures."""
    successes, failures = 0, []
    for application in base.to_generate():
        ad = application.ad
        try:
            cv_ref, letter_ref = generate_folder(application, assistant, paths, model, compile_fn)
        except (ClaudeError, GenerationError, OSError) as error:
            failures.append(f"{ad.company} — {ad.title}: {error}")
            continue
        base.mark_generated(ad.key, cv_ref, letter_ref)
        successes += 1
    return successes, failures
