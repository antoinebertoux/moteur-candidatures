"""Filing of application folders into `sent/` and `hold/` (CV-17 to CV-21)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from moteur.config import Paths
from moteur.cover_letter import generate_letter
from moteur.decisions import apply
from moteur.exchange import decisions_from
from moteur.folders import file_folder, folder_for_writing, locate, place_for
from moteur.generation import folder_name
from moteur.local_db import LocalDb
from moteur.models import Application, JobAd
from tests.conftest import FakeAssistant
from tests.test_cover_letter import compile_fn
from tests.test_generation import TEX, paths  # noqa: F401  (shared fixture)

AD = JobAd("Acme", "Lead AI", url="https://a")
NAME = folder_name(AD)


def document(**fields: Any) -> dict[str, Any]:
    entry = {"id": AD.key, "statut": "postulee", "entreprise": AD.company, "poste": AD.title}
    entry.update(fields)
    return entry


def sync(base: LocalDb, paths: Paths, **fields: Any) -> int:  # noqa: F811
    return apply(base, decisions_from([document(**fields)]), paths.root).folders_filed


def make_folder(paths: Paths, place: str = "", **files: str) -> Path:  # noqa: F811
    folder = paths.applications / place / NAME if place else paths.applications / NAME
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (folder / name.replace("_", ".")).write_text(text, encoding="utf-8")
    return folder


@pytest.fixture
def base(paths: Paths) -> Any:  # noqa: F811
    with LocalDb(paths.base) as opened:
        yield opened


@pytest.mark.spec("CV-17")
def test_where_each_status_is_filed() -> None:
    assert place_for("postulee", "") == "sent"
    assert place_for("postulee", "entretien") == "sent"
    assert place_for("postulee", "refus") == "hold"
    for status in ("a_traiter", "acceptee", "prete", "validee", "refusee"):
        assert place_for(status, "refus") is None


@pytest.mark.spec("CV-18", "ECH-11", "ECH-22")
def test_an_applied_folder_goes_to_sent_then_hold(base: LocalDb, paths: Paths) -> None:  # noqa: F811
    make_folder(paths, cv_tex="cv")
    assert not (paths.applications / "sent").exists()
    assert sync(base, paths) == 1
    assert (paths.applications / "sent" / NAME / "cv.tex").exists()
    assert not (paths.applications / NAME).exists()
    assert sync(base, paths) == 0  # already filed: nothing changes
    assert sync(base, paths, suite="refus") == 1
    assert (paths.applications / "hold" / NAME / "cv.tex").exists()
    assert not (paths.applications / "sent" / NAME).exists()
    assert sync(base, paths, suite="") == 1  # refusal undone
    assert locate(paths.applications, NAME) == paths.applications / "sent" / NAME


@pytest.mark.spec("CV-18", "CV-17")
def test_other_statuses_and_old_are_never_moved(base: LocalDb, paths: Paths) -> None:  # noqa: F811
    make_folder(paths, cv_tex="cv")
    old = paths.applications / "sent" / "old" / NAME
    old.mkdir(parents=True)
    for status in ("validee", "refusee", "acceptee"):
        assert sync(base, paths, statut=status) == 0
    assert (paths.applications / NAME).is_dir()
    assert sync(base, paths) == 1
    assert old.is_dir()  # sent/old is the previous job search
    # Never moved back to the root.
    assert sync(base, paths, statut="validee") == 0
    assert (paths.applications / "sent" / NAME).is_dir()


@pytest.mark.spec("CV-18")
def test_a_document_without_folder_is_skipped(base: LocalDb, paths: Paths) -> None:  # noqa: F811
    assert sync(base, paths) == 0
    assert not (paths.applications / "sent").exists()


@pytest.mark.spec("CV-19")
def test_two_copies_are_merged_without_losing_a_file(paths: Paths) -> None:  # noqa: F811
    root_copy = make_folder(paths, offre_md="same", preparation_md="prep", notes_md="root")
    make_folder(paths, "sent", offre_md="same", cv_tex="cv", notes_md="sent")
    target = file_folder(paths.applications, NAME, "sent")
    assert target == paths.applications / "sent" / NAME
    assert (target / "preparation.md").read_text(encoding="utf-8") == "prep"
    assert (target / "cv.tex").exists()
    assert (target / "notes.md").read_text(encoding="utf-8") == "sent"
    # The different file stays at the root; the identical one is dropped.
    assert sorted(p.name for p in root_copy.iterdir()) == ["notes.md"]
    assert file_folder(paths.applications, NAME, "sent") is None  # nothing more to do
    (root_copy / "notes.md").unlink()
    make_folder(paths, offre_md="same")
    assert file_folder(paths.applications, NAME, "sent") == target
    assert not root_copy.exists()  # a copy left empty is removed


@pytest.mark.spec("CV-20", "ECH-02")
def test_the_pdf_paths_follow_the_folder(base: LocalDb, paths: Paths) -> None:  # noqa: F811
    base.add([AD])
    make_folder(paths, cv_pdf="x", lettre_pdf="y")
    base.mark_generated(AD.key, f"Candidatures/{NAME}/cv.pdf", f"Candidatures/{NAME}/lettre.pdf")
    sync(base, paths)
    found = base.find(AD.key)
    assert found is not None
    assert found.cv_ref == f"Candidatures/sent/{NAME}/cv.pdf"
    assert found.letter_ref == f"Candidatures/sent/{NAME}/lettre.pdf"
    # A folder filed by hand earlier: the paths are fixed at the next sync.
    base.set_refs(AD.key, f"Candidatures/{NAME}/cv.pdf", "")
    sync(base, paths)
    found = base.find(AD.key)
    assert found is not None and found.cv_ref == f"Candidatures/sent/{NAME}/cv.pdf"


@pytest.mark.spec("CV-21")
def test_writers_use_the_folder_where_it_is(paths: Paths) -> None:  # noqa: F811
    assert folder_for_writing(paths.applications, NAME) == paths.applications / NAME
    (paths.applications / NAME).rmdir()
    assert folder_for_writing(paths.applications, NAME, "sent") == (
        paths.applications / "sent" / NAME
    )
    held = make_folder(paths, "hold")
    (paths.applications / "sent" / NAME).rmdir()
    assert folder_for_writing(paths.applications, NAME, "sent") == held


@pytest.mark.spec("CV-21")
def test_a_letter_goes_into_the_filed_folder(base: LocalDb, paths: Paths) -> None:  # noqa: F811
    held = make_folder(paths, "hold", cv_tex="cv")
    _, compiler = compile_fn()
    ref = generate_letter(Application(AD, "generee"), FakeAssistant(TEX), paths, "m", compiler)
    assert ref == f"Candidatures/hold/{NAME}/lettre.pdf"
    assert (held / "lettre.tex").exists()
    assert not (paths.applications / NAME).exists()
