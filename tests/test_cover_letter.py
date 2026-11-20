import json
from pathlib import Path

import pytest

from moteur.claude_cli import ProcessResult
from moteur.config import Paths
from moteur.cover_letter import generate_letter, generate_letters
from moteur.exchange import Decision, file_date, for_the_page, read_decisions
from moteur.generation import Compiler
from moteur.local_db import LocalDb
from moteur.models import Application, JobAd, default_letter
from tests.conftest import FakeAssistant
from tests.test_generation import TEX, paths  # noqa: F401  (shared fixture)

AD = JobAd("Banque de France", "AI/ML Engineer", description="Texte")


def compile_fn(output: str = "") -> tuple[list[str], Compiler]:
    files: list[str] = []

    def compiler(folder: Path, file: str) -> ProcessResult:
        files.append(file)
        return ProcessResult(0, output)

    return files, compiler


@pytest.mark.parametrize(
    ("ad", "expected"),
    [
        (JobAd("Direction générale de la sécurité intérieure", "DS"), True),
        (JobAd("Secrétariat Général", "AI Engineer", source="service_public"), True),
        (JobAd("Rothschild & Co", "DS"), True),
        (JobAd("Société Générale", "DS"), True),
        (JobAd("Qevlar AI", "Lead AI", type="spontanee"), True),
        (JobAd("Mistral AI", "Applied AI"), False),
        (JobAd("Publicis", "DS"), False),
    ],
)
@pytest.mark.spec("ID-04")
def test_default_letter(ad: JobAd, expected: bool) -> None:
    assert default_letter(ad) is expected


@pytest.mark.spec("LET-02", "ECH-11")
def test_the_page_toggle_beats_the_rule() -> None:
    (bank_without,) = read_decisions(
        json.dumps(
            [
                {
                    "id": "x",
                    "statut": "acceptee",
                    "entreprise": "BNP Paribas",
                    "poste": "DS",
                    "lettre": "non",
                }
            ]
        )
    )
    (startup_with,) = read_decisions(
        json.dumps(
            [
                {
                    "id": "y",
                    "statut": "acceptee",
                    "entreprise": "Mistral AI",
                    "poste": "DS",
                    "lettre": "oui",
                }
            ]
        )
    )
    (startup_default,) = read_decisions(
        json.dumps([{"id": "z", "statut": "acceptee", "entreprise": "Mistral AI", "poste": "DS"}])
    )
    assert bank_without.with_letter is False
    assert startup_with.with_letter is True
    assert startup_default.with_letter is False


@pytest.mark.spec("BASE-08")
def test_set_letter_and_missing_letters(tmp_path: Path) -> None:
    with LocalDb(tmp_path / "b.sqlite3") as base:
        base.add([AD])
        base.complete_from_the_page(AD.key, AD, False)
        base.apply_decision(AD.key, "acceptee")
        base.mark_generated(AD.key, "Candidatures/x/cv.pdf", "")
        assert base.missing_letters() == []
        assert base.set_letter(AD.key, True)
        assert not base.set_letter(AD.key, True)
        assert [c.ad.key for c in base.missing_letters()] == [AD.key]
        base.mark_letter(AD.key, "Candidatures/x/lettre.pdf")
        assert base.missing_letters() == []


@pytest.mark.spec("LET-04")
def test_generate_letter_leaves_the_cv_alone(paths: Paths) -> None:  # noqa: F811
    folder = paths.applications / "Banque de France - AI ML Engineer"
    folder.mkdir(parents=True)
    (folder / "cv.tex").write_text("CV intact", encoding="utf-8")
    files, compiler = compile_fn()
    ref = generate_letter(Application(AD, "generee"), FakeAssistant(TEX), paths, "m", compiler)
    assert files == ["lettre.tex"]
    assert (folder / "cv.tex").read_text(encoding="utf-8") == "CV intact"
    assert (folder / "lettre.tex").exists()
    assert ref.endswith("lettre.pdf")


@pytest.mark.spec("LET-06")
def test_generate_letters_reports_too_long_letter_and_unknown_key(
    paths: Paths,  # noqa: F811
) -> None:
    _, compiler = compile_fn("⚠️  lettre.pdf fait 2 pages")
    with LocalDb(paths.base) as base:
        base.add([AD])
        successes, failures = generate_letters(
            base, FakeAssistant(TEX), paths, "m", compiler, [AD.key, "inconnue"]
        )
        assert successes == 0
        assert len(failures) == 2
        assert "2 pages" in failures[1]
        assert base.find(AD.key) is not None
        assert base.find(AD.key).letter_ref == ""  # type: ignore[union-attr]


@pytest.mark.spec("LET-07")
def test_regenerate_letter_only_if_request_is_newer(tmp_path: Path) -> None:
    from moteur.decisions import letters_to_redo

    letter = tmp_path / "Candidatures" / "x" / "lettre.pdf"
    letter.parent.mkdir(parents=True)
    letter.write_bytes(b"%PDF")
    made_at = file_date(letter)
    assert made_at is not None
    with LocalDb(tmp_path / "b.sqlite3") as base:
        base.add([AD])
        base.apply_decision(AD.key, "acceptee")
        base.mark_generated(AD.key, "Candidatures/x/cv.pdf", "Candidatures/x/lettre.pdf")
        old = Decision(AD.key, "prete", letter_redo_at="2000-01-01T00:00:00.000Z")
        assert letters_to_redo([old], base, tmp_path) == 0
        request = Decision(
            AD.key,
            "prete",
            letter_redo_at="2999-01-01T00:00:00.000Z",
            letter_instruction_page="Plus court",
        )
        assert letters_to_redo([request], base, tmp_path) == 1
        (missing,) = base.missing_letters()
        assert missing.letter_instruction == "Plus court"
        base.mark_letter(AD.key, "Candidatures/x/lettre.pdf")
        assert base.find(AD.key).letter_instruction == ""  # type: ignore[union-attr]


@pytest.mark.spec("LET-05")
def test_letter_instruction_starts_from_existing_letter(paths: Paths) -> None:  # noqa: F811
    folder = paths.applications / "Banque de France - AI ML Engineer"
    folder.mkdir(parents=True)
    (folder / "lettre.tex").write_text("ANCIENNE LETTRE", encoding="utf-8")
    assistant = FakeAssistant(TEX)
    _, compiler = compile_fn()
    application = Application(AD, "generee", letter_instruction="Plus court")
    generate_letter(application, assistant, paths, "m", compiler)
    assert "ANCIENNE LETTRE" in assistant.prompts[0]
    assert "Plus court" in assistant.prompts[0]


@pytest.mark.spec("ECH-02")
def test_export_gives_the_letter_date(tmp_path: Path) -> None:
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "lettre.pdf").write_bytes(b"%PDF")
    application = Application(AD, "generee", cv_ref="x/cv.pdf", letter_ref="x/lettre.pdf")
    (row,) = for_the_page([application], tmp_path)
    assert row["lettre_generee_le"].endswith("Z")


@pytest.mark.spec("BASE-10")
def test_ancienne_base_sans_colonne_consigne_lettre(tmp_path: Path) -> None:
    import sqlite3

    path = tmp_path / "vieille.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE candidatures (cle TEXT PRIMARY KEY, type TEXT NOT NULL,"
        " entreprise TEXT NOT NULL, poste TEXT NOT NULL, lieu TEXT NOT NULL DEFAULT '',"
        " url TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',"
        " description TEXT NOT NULL DEFAULT '', salaire TEXT NOT NULL DEFAULT '',"
        " date_publication TEXT NOT NULL DEFAULT '', statut TEXT NOT NULL, score INTEGER,"
        " resume TEXT NOT NULL DEFAULT '', lettre_demandee INTEGER NOT NULL DEFAULT 0,"
        " langue TEXT NOT NULL DEFAULT 'fr', consigne TEXT NOT NULL DEFAULT '',"
        " cv_ref TEXT NOT NULL DEFAULT '', lettre_ref TEXT NOT NULL DEFAULT '',"
        " date_ajout TEXT NOT NULL)"
    )
    connection.commit()
    connection.close()
    with LocalDb(path) as base:
        base.add([AD])
        assert base.find(AD.key) is not None
