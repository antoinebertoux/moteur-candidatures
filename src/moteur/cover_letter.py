"""Cover letter alone, for a folder whose CV already exists.

Used to add a letter afterwards ("Letter" toggle switched on in the page, or
`moteur letter <id>`) without regenerating or changing the CV.
"""

from __future__ import annotations

from moteur.claude_cli import Assistant, ClaudeError
from moteur.config import Paths
from moteur.generation import (
    Compiler,
    GenerationError,
    _compile,
    _write_sheet,
    folder_name,
    write_letter,
)
from moteur.latex_repository import check
from moteur.local_db import LocalDb
from moteur.models import Application


def generate_letter(
    application: Application,
    assistant: Assistant,
    paths: Paths,
    model: str,
    compile_fn: Compiler,
) -> str:
    """Writes and compiles the folder's `lettre.tex`; returns the PDF reference."""
    folder = paths.applications / folder_name(application.ad)
    folder.mkdir(parents=True, exist_ok=True)
    _write_sheet(folder, application.ad)
    letter = folder / "lettre.tex"
    write_letter(application, letter, application.letter_instruction, assistant, paths, model)
    pages = _compile(folder, letter.name, compile_fn).get(letter.stem, 1)
    if pages > 1:
        raise GenerationError(f"{folder.name}/lettre.pdf has {pages} pages: to rework")
    return str(letter.with_suffix(".pdf").relative_to(paths.root))


def generate_letters(
    base: LocalDb,
    assistant: Assistant,
    paths: Paths,
    model: str,
    compile_fn: Compiler,
    keys: list[str] | None = None,
) -> tuple[int, list[str]]:
    """Letters of the given keys, or otherwise of every folder where it is missing.

    Raises `LatexRepositoryError` before any letter if a required file is missing (LTX-10).
    """
    if keys:
        applications, failures = [], []
        for key in keys:
            found_it = base.find(key)
            if found_it is None:
                failures.append(f"{key}: unknown to the local database")
            else:
                applications.append(found_it)
    else:
        applications, failures = base.missing_letters(), []
    if applications:
        check(paths.latex)
    successes = 0
    for application in applications:
        ad = application.ad
        try:
            ref = generate_letter(application, assistant, paths, model, compile_fn)
        except (ClaudeError, GenerationError, OSError) as error:
            failures.append(f"{ad.company} — {ad.title}: {error}")
            continue
        base.mark_letter(ad.key, ref)
        successes += 1
    return successes, failures
