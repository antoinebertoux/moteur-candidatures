"""Interview preparation sheet: what was sent, the company today, likely questions.

Rules PREP-xx of `specs/interview-prep.md`. The only Claude call given tools: web search
and page fetching, for the company research (CLA-04). Two kinds of sheet: the HR
interview and the technical / manager interview (PREP-50).
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

from moteur.claude_cli import Assistant, ClaudeError
from moteur.config import Paths
from moteur.generation import _write_sheet, folder_name
from moteur.local_db import LocalDb
from moteur.models import Application, PrepKind, PrepRequest, normalise

log = logging.getLogger(__name__)

WEB_TOOLS = ("WebSearch", "WebFetch")
DELAY_SECONDS = 900
MAX_LENGTH = 40_000
SHEET_FILE = "preparation-entretien.md"
LOG_FILE = "preparation.log"
MAX_AD_TEXT = 8_000
CUT = "\n\n*(Fiche coupée : elle dépassait 40 000 caractères.)*"
# Technical / manager sheet (PREP-52, PREP-54).
TECH_DELAY_SECONDS = 1_800
TECH_MAX_LENGTH = 60_000
TECH_SHEET_FILE = "preparation-entretien-technique.md"
TECH_CUT = "\n\n*(Fiche coupée : elle dépassait 60 000 caractères.)*"
DEFAULT_TECH_MODEL = "opus"
KINDS: tuple[PrepKind, ...] = ("rh", "technique")

# Sections of `infos-candidature.md` that may be sent to Claude (PREP-12).
_ALLOWED_SECTIONS = ("situation", "preferences", "reponses-types")
# Lines never sent, whatever their section: the salary floor (INV-03).
_FORBIDDEN_LINES = ("critere-de-tri", "plancher")

PREP_SYSTEM = """Tu prépares le candidat à un entretien d'embauche pour une \
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

TECH_SYSTEM = """Tu prépares le candidat à un entretien technique ou avec son futur \
manager, pour une candidature qui a déjà passé un premier entretien (recruteur ou RH). \
Cet entretien porte un peu sur la technique, beaucoup sur ce qu'il a fait et sur ce \
qu'il fera sur place ; ce peut aussi être un test technique ou une étude de cas. Tu \
écris une fiche approfondie en français, en Markdown, qu'il travaillera la veille et \
relira juste avant.
Règles strictes :
1. Tu n'inventes aucune expérience, aucun chiffre, aucun fait sur le candidat : tout ce \
que tu dis de lui vient du CV, de la lettre, des banques, du retour des entretiens \
précédents et des informations fournies. Ce qui n'y est pas, tu le laisses de côté ; si \
un sujet attendu n'est pas couvert par son expérience, tu le dis et tu proposes une \
réponse honnête (ce qu'il connaît d'approchant, comment il s'y mettrait).
2. Tu cherches sur le web (outils de recherche et de lecture de pages), en profondeur : \
site de l'entreprise, blog technique, dépôts publics, conférences, autres offres de \
l'entreprise (elles révèlent la stack et l'organisation), articles de presse, \
publications. Chaque chiffre donne sa source et sa date. Ce que tu ne trouves pas, tu \
écris « non trouvé » : jamais de supposition présentée comme un fait ; une hypothèse est \
écrite comme telle.
3. Interlocuteurs nommés : seulement leur parcours professionnel public (poste, \
parcours, interventions, publications), rien de privé.
4. La fiche RH déjà faite, si elle est fournie, est connue du candidat : ne la répète \
pas, approfondis. La consigne du candidat, si elle existe, est prioritaire.
5. Plan, dans cet ordre, avec ces titres :
# Préparation technique / manager : <entreprise> — <poste>
## À retenir
Le poste, les infos de l'entretien, les interlocuteurs et leur parcours, ce qu'ont dit \
les entretiens précédents, ce qu'il reste à prouver dans celui-ci.
## L'équipe et le contexte technique
L'équipe et sa place dans l'entreprise, les produits et leurs utilisateurs, la stack et \
les pratiques techniques, le contexte des données et le cadre réglementaire, les défis \
probables de l'équipe en ce moment.
## Ce que je ferai sur place
Les missions et livrables probables des premiers mois ; pour chacun, ce que le candidat \
a déjà fait d'approchant ; une proposition de plan 30-60-90 jours à évoquer.
## Mes projets à raconter
Trois à cinq projets du CV choisis pour ce poste. Pour chacun : contexte, rôle exact du \
candidat, choix techniques et compromis, résultats chiffrés, ce qu'il en a appris, puis \
les questions d'approfondissement probables avec une réponse.
## Questions techniques probables
Les notions de l'offre et de la stack susceptibles d'être demandées, chacune avec une \
réponse courte et juste et le lien avec l'expérience du candidat ; l'exercice probable \
(étude de cas, conception de système, code en direct, exercice à la maison) et comment \
l'aborder.
## Questions du manager
Façon de travailler, autonomie, priorités, désaccords, collaboration avec le produit et \
le métier, échec : réponses sous forme d'histoires (situation, action, résultat) tirées \
de l'expérience réelle du candidat.
## Points de vigilance
Les manques que l'interlocuteur risque de creuser et une manière honnête d'y répondre ; \
le salaire s'il revient sur la table.
## Questions à poser
Huit à douze, pour le manager et l'équipe : missions, critères de réussite, équipe, \
stack, feuille de route, prise de décision.
Si l'offre est en anglais, les réponses suggérées sont en anglais.
Réponds uniquement par la fiche, sans texte avant ni après."""


def now() -> str:
    """Current time in the format of the page's `Date.toISOString()`."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def allowed_details(text: str) -> str:
    """The parts of `infos-candidature.md` that Claude may read (PREP-12).

    Only the Situation, Préférences and Réponses types sections are kept, without any
    line about the sorting criterion or the salary floor (INV-03).
    """
    kept_bullets: list[str] = []
    allowed_one = False
    for row in text.splitlines():
        if row.startswith("#"):
            heading = normalise(row.lstrip("#"))
            allowed_one = row.startswith("## ") and heading.startswith(_ALLOWED_SECTIONS)
            if allowed_one:
                kept_bullets.append(row)
            continue
        if allowed_one and not any(word in normalise(row) for word in _FORBIDDEN_LINES):
            kept_bullets.append(row)
    return "\n".join(kept_bullets).strip()


def _read(file: Path) -> str:
    try:
        return file.read_text(encoding="utf-8")
    except OSError:
        return ""


def preparation_prompt(
    application: Application, request: PrepRequest, paths: Paths, profile: str
) -> str:
    """What Claude receives for one sheet (PREP-10 to PREP-12)."""
    ad = application.ad
    folder = paths.applications / folder_name(ad)
    rows = [f"Entreprise : {ad.company}", f"Poste : {ad.title}"]
    if ad.type == "spontanee":
        rows.append("Candidature spontanée (pas d'offre publiée).")
    if ad.location:
        rows.append(f"Lieu : {ad.location}")
    if ad.url:
        rows.append(f"Lien de l'offre : {ad.url}")
    if application.summary:
        rows.append(f"Résumé : {application.summary}")
    language = "anglais" if application.language == "en" else "français"
    rows.append(f"Langue de l'offre : {language}")
    parts = ["## Candidature\n" + "\n".join(rows)]
    if request.context:
        parts.append(f"## Suivi dans la page (dates, réponses, notes)\n{request.context}")
    interview = [
        f"Salaire annoncé par le candidat : {request.salary_expectations or 'non renseigné'}",
    ]
    if request.interview_details:
        interview.append(f"Entretien : {request.interview_details}")
    parts.append("## Entretien\n" + "\n".join(interview))
    ad_text = _read(folder / "offre.md") or ad.description
    if ad_text:
        parts.append(f"## Texte de l'offre\n{ad_text[:MAX_AD_TEXT]}")
    for name, heading in (("cv.tex", "CV envoyé"), ("lettre.tex", "Lettre envoyée")):
        contents = _read(folder / name)
        if contents:
            parts.append(f"## {heading} (LaTeX)\n```latex\n{contents}\n```")
    if profile:
        parts.append(f"## Profil du candidat\n{profile}")
    banks = (
        (paths.latex / "cv" / f"banque-{application.language}.tex", "Banque du CV", "latex"),
        (paths.latex / "lettres" / "banque-paragraphes.md", "Banque de paragraphes", "md"),
    )
    for file, heading, format_ in banks:
        contents = _read(file)
        if contents:
            parts.append(f"## {heading}\n```{format_}\n{contents}\n```")
    details = allowed_details(_read(paths.latex / "commun" / "infos-candidature.md"))
    if details:
        parts.append(f"## Situation et préférences du candidat\n{details}")
    if request.kind == "technique":
        if request.hr_feedback:
            parts.append(f"## Retour des entretiens précédents\n{request.hr_feedback}")
        if application.preparation:
            parts.append(
                "## Fiche de l'entretien RH (déjà connue du candidat, à ne pas répéter)\n"
                + application.preparation
            )
    if request.instruction:
        parts.append(f"## Consigne du candidat (prioritaire)\n{request.instruction}")
    return "\n\n".join(parts)


def clean_sheet(answer: str, max_length: int = MAX_LENGTH, cut: str = CUT) -> str:
    """The sheet in Claude's answer, cut at 40,000 characters (PREP-32), or 60,000 for a
    technical sheet (PREP-54)."""
    text = answer.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    rows = text.strip().splitlines()
    start = next((i for i, row in enumerate(rows) if row.startswith("# ")), 0)
    text = "\n".join(rows[start:]).strip()
    if not text:
        raise ClaudeError("Empty preparation sheet")
    if len(text) > max_length:
        text = text[: max_length - len(cut) - 1].rstrip() + cut
    return text + "\n"


def prepare_sheet(
    application: Application,
    request: PrepRequest,
    assistant: Assistant,
    paths: Paths,
    model: str,
    profile: str,
) -> str:
    """Has Claude write the sheet of the request's kind and saves it in the folder;
    returns its text (PREP-20, PREP-32, PREP-52, PREP-54)."""
    technical = request.kind == "technique"
    prompt = preparation_prompt(application, request, paths, profile)
    answer = assistant.ask(
        prompt,
        system=TECH_SYSTEM if technical else PREP_SYSTEM,
        model=model,
        tools=WEB_TOOLS,
        delay=TECH_DELAY_SECONDS if technical else DELAY_SECONDS,
    )
    sheet = clean_sheet(answer, TECH_MAX_LENGTH, TECH_CUT) if technical else clean_sheet(answer)
    folder = paths.applications / folder_name(application.ad)
    folder.mkdir(parents=True, exist_ok=True)
    _write_sheet(folder, application.ad)
    (folder / (TECH_SHEET_FILE if technical else SHEET_FILE)).write_text(sheet, encoding="utf-8")
    return sheet


def prepare(
    base: LocalDb,
    assistant: Assistant,
    paths: Paths,
    model: str,
    profile: str,
    keys: list[str] | None = None,
    clock: Callable[[], str] = now,
    tried: set[tuple[PrepKind, str]] | None = None,
    *,
    technical_model: str = DEFAULT_TECH_MODEL,
    kind: PrepKind = "rh",
) -> tuple[int, list[str]]:
    """Sheets of the given applications (of `kind`), or of every pending request of both
    kinds (PREP-40).

    Without identifiers, pending requests are read again before ending, so that a
    request recorded meanwhile is not left behind (PREP-42). A failed sheet stays
    pending and is not retried in the same run (PREP-21, PREP-55).
    """
    successes, failures = 0, list[str]()
    tried = set() if tried is None else tried
    to_do = [(kind, key) for key in keys] if keys else _new_ones(base, tried)
    while to_do:
        for job in to_do:
            tried.add(job)
            job_kind, key = job
            application = base.find(key)
            if application is None:
                failures.append(f"{key}: unknown to the local database")
                continue
            ad = application.ad
            request = base.prep_request(key, job_kind) or PrepRequest(clock(), kind=job_kind)
            job_model = technical_model if job_kind == "technique" else model
            try:
                sheet = prepare_sheet(application, request, assistant, paths, job_model, profile)
            except (ClaudeError, OSError) as error:
                label = " (technique / manager)" if job_kind == "technique" else ""
                failures.append(f"{ad.company} — {ad.title}{label}: {error}")
                continue
            base.record_preparation(key, sheet, clock(), job_kind)
            successes += 1
        to_do = [] if keys else _new_ones(base, tried)
    return successes, failures


def _new_ones(base: LocalDb, tried: set[tuple[PrepKind, str]]) -> list[tuple[PrepKind, str]]:
    jobs = [(kind, key) for kind in KINDS for key in base.pending_preparations(kind)]
    return [job for job in jobs if job not in tried]


def prepare_alone(
    base: LocalDb,
    assistant: Assistant,
    paths: Paths,
    model: str,
    profile: str,
    keys: list[str] | None = None,
    clock: Callable[[], str] = now,
    *,
    technical_model: str = DEFAULT_TECH_MODEL,
    kind: PrepKind = "rh",
) -> tuple[int, list[str]] | None:
    """`preparer` while holding the lock; None if another run holds it (PREP-42).

    Once the lock is released, pending requests are checked once more: one recorded
    just before the release, whose background start found the lock still held, is not
    left behind.
    """
    successes, failures = 0, list[str]()
    tried: set[tuple[PrepKind, str]] = set()
    first = True
    while first or (not keys and _new_ones(base, tried)):
        with lock(lock_path(paths)) as held:
            if not held:
                return None if first else (successes, failures)
            done, failed = prepare(
                base,
                assistant,
                paths,
                model,
                profile,
                keys,
                clock,
                tried,
                technical_model=technical_model,
                kind=kind,
            )
        successes, failures, first = successes + done, failures + failed, False
    return successes, failures


def lock_path(paths: Paths) -> Path:
    return paths.base.parent / "preparation.lock"


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_pid(file: Path) -> int:
    try:
        return int(file.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0


def lock_held(file: Path) -> bool:
    """True if a living process holds the lock."""
    pid = _lock_pid(file)
    return bool(pid) and _process_alive(pid)


@contextmanager
def lock(file: Path) -> Iterator[bool]:
    """Yields true if this process holds the lock, false if another run holds it.

    A lock left by a process that no longer exists is taken over (PREP-42).
    """
    for _ in range(2):
        try:
            descriptor = os.open(file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if lock_held(file):
                yield False
                return
            file.unlink(missing_ok=True)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(str(os.getpid()))
        try:
            yield True
        finally:
            file.unlink(missing_ok=True)
        return
    yield False


def launch_in_background(config: Path, paths: Paths) -> None:
    """Starts `moteur prepare` detached, output to `echange/preparation.log` (PREP-41/43).

    Returns at once: the caller (the `decisions` tool) never waits for it. Nothing is
    started while a run holds the lock: that run picks up the new request itself.
    """
    if lock_held(lock_path(paths)):
        return
    paths.exchange.mkdir(parents=True, exist_ok=True)
    with (paths.exchange / LOG_FILE).open("w", encoding="utf-8") as output:
        subprocess.Popen(
            [sys.executable, "-m", "moteur.cli", "--config", str(config), "prepare"],
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=config.parent,
            start_new_session=True,
        )
    log.info("moteur prepare started in the background")
