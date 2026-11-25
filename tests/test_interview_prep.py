"""Interview preparation sheets (specs/interview-prep.md)."""

# ruff: noqa: F811  (the shared `chemins` fixture is imported, then requested by name)

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from moteur.claude_cli import ClaudeCli, ClaudeError, ProcessResult
from moteur.config import Paths
from moteur.decisions import apply
from moteur.exchange import decisions_from, for_the_page
from moteur.generation import folder_name
from moteur.interview_prep import (
    CUT,
    MAX_LENGTH,
    SHEET_FILE,
    TECH_CUT,
    TECH_MAX_LENGTH,
    TECH_SHEET_FILE,
    TECH_SYSTEM,
    WEB_TOOLS,
    allowed_details,
    clean_sheet,
    launch_in_background,
    lock,
    lock_path,
    preparation_prompt,
    prepare,
    prepare_alone,
)
from moteur.local_db import LocalDb
from moteur.mcp_link import decisions as decisions_tool
from moteur.models import JobAd, PrepRequest
from tests.conftest import FakeAssistant
from tests.test_generation import paths  # noqa: F401  (shared fixture)

AD = JobAd("Acme", "Lead AI", location="Paris", url="https://a", description="Texte de l'offre")
SHEET = "# Préparation : Acme — Lead AI\n## À retenir\nTout."
DETAILS = """# Infos pour remplir les formulaires de candidature

## Identité
- Prénom / Nom : Jean Exemple

## Contact
- Téléphone : 06 00 00 00 00

## Situation
- Préavis : 3 mois
- Critère de tri des offres (NE JAMAIS COMMUNIQUER) : plancher 65K€ brut/an
- Habilitation défense : aucune

## Préférences
- Télétravail souhaité : si possible

## Formation
- Diplôme : Master

## Réponses types aux questions fréquentes
- Pourquoi quitter votre poste actuel : nouveau défi
"""


def document(**fields: Any) -> dict[str, Any]:
    """A page document of the application, interview requested."""
    entry = {
        "id": AD.key,
        "statut": "postulee",
        "entreprise": AD.company,
        "poste": AD.title,
        "lieu": AD.location,
        "url": AD.url,
        "texte_offre": AD.description,
        "date_postulee": "2026-11-10",
        "suite": "entretien",
        "notes": "2026-11-18 : appel du recruteur",
        "preparation_demandee_le": "2026-11-19T10:00:00.000Z",
        "pretentions": "70 k€",
        "entretien_infos": "Jeudi 14 h, visio avec le CTO",
        "preparation_consigne": "insiste sur le RAG",
    }
    entry.update(fields)
    return entry


def ask(base: LocalDb, paths: Paths, **fields: Any) -> int:
    return apply(base, decisions_from([document(**fields)]), paths.root).preparations


@pytest.fixture
def base(paths: Paths) -> Any:
    with LocalDb(paths.base) as opened:
        yield opened


@pytest.mark.spec("PREP-01", "BASE-12", "ECH-11")
def test_the_page_request_is_recorded(base: LocalDb, paths: Paths) -> None:
    base.add([AD])
    base.apply_decision(AD.key, "postulee")
    assert ask(base, paths) == 1
    request = base.prep_request(AD.key)
    assert request is not None
    assert request.requested_at == "2026-11-19T10:00:00.000Z"
    assert (request.salary_expectations, request.interview_details, request.instruction) == (
        "70 k€",
        "Jeudi 14 h, visio avec le CTO",
        "insiste sur le RAG",
    )
    assert "Envoyée le : 2026-11-10" in request.context
    assert "appel du recruteur" in request.context
    application = base.find(AD.key)
    assert application is not None
    assert application.status == "close"


@pytest.mark.spec("BASE-12")
def test_an_identical_or_older_request_changes_nothing(base: LocalDb, paths: Paths) -> None:
    base.add([AD])
    assert ask(base, paths) == 1
    assert ask(base, paths) == 0
    assert ask(base, paths, preparation_demandee_le="2026-11-01T00:00:00.000Z") == 0
    assert ask(base, paths, preparation_demandee_le="2026-11-20T00:00:00.000Z") == 1


@pytest.mark.spec("PREP-02")
def test_a_request_is_pending_while_newer_than_the_sheet(base: LocalDb, paths: Paths) -> None:
    base.add([AD])
    assert base.pending_preparations() == []
    ask(base, paths)
    assert base.pending_preparations() == [AD.key]
    base.record_preparation(AD.key, SHEET, "2026-11-19T10:05:00.000Z")
    assert base.pending_preparations() == []
    ask(base, paths, preparation_demandee_le="2026-11-19T11:00:00.000Z")
    assert base.pending_preparations() == [AD.key]


@pytest.mark.spec("PREP-03")
def test_an_unknown_application_is_added_from_the_page(base: LocalDb, paths: Paths) -> None:
    assert ask(base, paths) == 1
    application = base.find(AD.key)
    assert application is not None
    assert application.status == "close"
    assert application.ad.description == "Texte de l'offre"
    assert base.pending_preparations() == [AD.key]


@pytest.mark.spec("PREP-12")
def test_only_allowed_sections_are_sent_never_the_floor() -> None:
    details = allowed_details(DETAILS)
    assert "Préavis : 3 mois" in details
    assert "Télétravail" in details
    assert "nouveau défi" in details
    for absent in ("plancher", "65K", "Critère de tri", "Jean Exemple", "06 00", "Master"):
        assert absent not in details


@pytest.mark.spec("PREP-10", "PREP-11", "PREP-12")
def test_claude_receives_everything_sent(base: LocalDb, paths: Paths) -> None:
    (paths.latex / "commun").mkdir(exist_ok=True)
    (paths.latex / "commun" / "infos-candidature.md").write_text(DETAILS, encoding="utf-8")
    folder = paths.applications / folder_name(AD)
    folder.mkdir(parents=True)
    (folder / "cv.tex").write_text("\\setjob{Lead AI}", encoding="utf-8")
    (folder / "lettre.tex").write_text("Ma lettre promet un POC", encoding="utf-8")
    ask(base, paths)
    application = base.find(AD.key)
    request = base.prep_request(AD.key)
    assert application is not None and request is not None
    prompt = preparation_prompt(application, request, paths, "Mon profil")
    for expected in (
        "Entreprise : Acme",
        "Poste : Lead AI",
        "Lien de l'offre : https://a",
        "Envoyée le : 2026-11-10",
        "Suite : entretien",
        "appel du recruteur",
        "Texte de l'offre",
        "\\setjob{Lead AI}",
        "Ma lettre promet un POC",
        "70 k€",
        "Jeudi 14 h",
        "## Consigne du candidat (prioritaire)\ninsiste sur le RAG",
        "Mon profil",
        "\\newcommand{\\pRAG}{RAG}",
        "Paragraphe.",
        "Préavis : 3 mois",
    ):
        assert expected in prompt
    assert "plancher" not in prompt
    assert "Jean Exemple" not in prompt


@pytest.mark.spec("PREP-20", "CLA-04")
def test_the_call_has_web_tools_only(base: LocalDb, paths: Paths) -> None:
    ask(base, paths)
    assistant = FakeAssistant(SHEET)
    assert prepare(base, assistant, paths, "sonnet", "profil") == (1, [])
    assert assistant.tools == [WEB_TOOLS]
    assert assistant.models == ["sonnet"]
    assert assistant.delays == [900]


@pytest.mark.spec("CLA-04", "CLA-01")
def test_the_claude_command_allows_only_requested_tools() -> None:
    calls: list[tuple[list[str], int]] = []

    def runner(command: Sequence[str], entry: str, delay: int) -> ProcessResult:
        calls.append((list(command), delay))
        return ProcessResult(0, json.dumps({"result": "ok"}))

    claude = ClaudeCli(runner)
    claude.ask("q", system="s", model="haiku")
    claude.ask("q", system="s", model="sonnet", tools=WEB_TOOLS, delay=900)
    (without, delay_without), (with_, delay_with) = calls
    assert without[without.index("--tools") + 1] == ""
    assert "--allowedTools" not in without
    assert with_[with_.index("--tools") + 1] == "WebSearch,WebFetch"
    assert with_[with_.index("--allowedTools") + 1] == "WebSearch,WebFetch"
    assert "mcp__*" in with_ and "--strict-mcp-config" in with_
    assert (delay_without, delay_with) == (600, 900)


@pytest.mark.spec("PREP-21")
def test_a_failed_sheet_stays_pending_and_others_continue(base: LocalDb, paths: Paths) -> None:
    other = JobAd("Beta", "Head of AI")
    ask(base, paths)
    ask(
        base,
        paths,
        id=other.key,
        entreprise="Beta",
        poste="Head of AI",
        preparation_demandee_le="2026-11-19T12:00:00.000Z",
    )

    class Flaky(FakeAssistant):
        def ask(self, prompt: str, **options: Any) -> str:
            if "Acme" in prompt:
                raise ClaudeError("délai dépassé")
            return super().ask(prompt, **options)

    successes, failures = prepare(base, Flaky(SHEET), paths, "sonnet", "")
    assert successes == 1
    assert len(failures) == 1 and "Acme" in failures[0]
    assert base.pending_preparations() == [AD.key]


@pytest.mark.spec("PREP-32", "ECH-03", "CV-21")
def test_the_sheet_is_written_stored_and_sent_to_the_page(base: LocalDb, paths: Paths) -> None:
    ask(base, paths)
    answer = f"Voici la fiche.\n\n{SHEET}"
    prepare(
        base,
        FakeAssistant(answer),
        paths,
        "sonnet",
        "",
        clock=lambda: "2026-11-19T10:05:00.000Z",
    )
    folder = paths.applications / "sent" / folder_name(AD)
    assert (folder / SHEET_FILE).read_text(encoding="utf-8") == SHEET + "\n"
    assert (folder / "offre.md").exists()
    (row,) = for_the_page(base.for_the_page(), paths.root)
    assert row["preparation"] == SHEET + "\n"
    assert row["preparation_le"] == "2026-11-19T10:05:00.000Z"
    # A new request replaces the previous sheet.
    ask(base, paths, preparation_demandee_le="2026-11-20T00:00:00.000Z")
    prepare(
        base,
        FakeAssistant("# Nouvelle"),
        paths,
        "sonnet",
        "",
        clock=lambda: "2026-11-20T00:05:00.000Z",
    )
    assert (folder / SHEET_FILE).read_text(encoding="utf-8") == "# Nouvelle\n"


@pytest.mark.spec("PREP-32")
def test_a_too_long_sheet_is_cut() -> None:
    sheet = clean_sheet("# Fiche\n" + "x" * (MAX_LENGTH * 2))
    assert len(sheet) <= MAX_LENGTH
    assert sheet.endswith(CUT + "\n")
    assert clean_sheet("```markdown\n# Fiche\nTexte\n```") == "# Fiche\nTexte\n"
    with pytest.raises(ClaudeError):
        clean_sheet("   ")


@pytest.mark.spec("PREP-40")
def test_prepare_handles_given_keys_or_all_requests(base: LocalDb, paths: Paths) -> None:
    base.add([AD])
    assert prepare(base, FakeAssistant(SHEET), paths, "sonnet", "") == (0, [])
    assert prepare(base, FakeAssistant(SHEET), paths, "sonnet", "", [AD.key]) == (1, [])
    assert prepare(base, FakeAssistant(SHEET), paths, "sonnet", "", ["inconnue"])[1] == [
        "inconnue: unknown to the local database"
    ]


@pytest.mark.spec("PREP-42")
def test_a_request_arriving_during_the_run_is_handled(base: LocalDb, paths: Paths) -> None:
    other = JobAd("Beta", "Head of AI")
    ask(base, paths)

    class During(FakeAssistant):
        def ask(self, prompt: str, **options: Any) -> str:
            if len(self.prompts) == 0:
                ask(
                    base,
                    paths,
                    id=other.key,
                    company="Beta",
                    title="Head of AI",
                    preparation_demandee_le="2026-11-19T12:00:00.000Z",
                )
            return super().ask(prompt, **options)

    assert prepare_alone(base, During(SHEET), paths, "sonnet", "") == (2, [])
    assert base.pending_preparations() == []
    assert not lock_path(paths).exists()


@pytest.mark.spec("PREP-42")
def test_only_one_preparation_at_a_time(base: LocalDb, paths: Paths) -> None:
    ask(base, paths)
    file = lock_path(paths)
    file.write_text(str(os.getpid()), encoding="utf-8")
    assistant = FakeAssistant(SHEET)
    assert prepare_alone(base, assistant, paths, "sonnet", "") is None
    assert assistant.prompts == []
    # A lock left by a process that no longer exists is ignored.
    file.write_text("999999999", encoding="utf-8")
    assert prepare_alone(base, assistant, paths, "sonnet", "") == (1, [])
    assert not file.exists()


@pytest.mark.spec("PREP-42")
def test_the_lock_is_released_even_after_an_error(tmp_path: Path) -> None:
    file = tmp_path / "v.lock"
    with pytest.raises(RuntimeError), lock(file) as held:
        assert held
        raise RuntimeError
    assert not file.exists()


@pytest.mark.spec("PREP-41", "ECH-26")
def test_decisions_starts_preparation_only_for_a_new_request(
    paths: Paths,
) -> None:
    launches: list[int] = []
    documents = {"candidatures": [document()]}
    outcome = decisions_tool(paths, documents, lambda: launches.append(1))
    assert outcome["preparations"] == 1
    assert launches == [1]
    decisions_tool(paths, documents, lambda: launches.append(1))
    assert launches == [1]
    without = {"candidatures": [document(preparation_demandee_le="")]}
    decisions_tool(paths, without, lambda: launches.append(1))
    assert launches == [1]


@pytest.mark.spec("ECH-26")
def test_a_failed_launch_does_not_change_the_answer(paths: Paths) -> None:
    def broken() -> None:
        raise OSError("pas de python")

    outcome = decisions_tool(paths, {"candidatures": [document()]}, broken)
    assert outcome["preparations"] == 1


@pytest.mark.spec("PREP-41", "PREP-43")
def test_the_launch_is_detached_and_logged(
    paths: Paths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[dict[str, Any]] = []

    def popen(command: list[str], **options: Any) -> None:
        options["stdout"].write("sortie\n")
        started.append({"commande": command, **options})

    monkeypatch.setattr("moteur.interview_prep.subprocess.Popen", popen)
    config = paths.root / "config.toml"
    log = paths.exchange / "preparation.log"
    paths.exchange.mkdir()
    log.write_text("ancienne course\n", encoding="utf-8")
    launch_in_background(config, paths)
    (launched,) = started
    assert launched["commande"][-3:] == ["--config", str(config), "prepare"]
    assert launched["start_new_session"] is True
    assert launched["stdin"] == subprocess.DEVNULL
    assert log.read_text(encoding="utf-8") == "sortie\n"
    # Nothing is started while a run holds the lock.
    lock_path(paths).write_text(str(os.getpid()), encoding="utf-8")
    launch_in_background(config, paths)
    assert len(started) == 1


@pytest.mark.spec("PREP-01")
def test_a_missing_or_empty_request_is_not_read() -> None:
    (without,) = decisions_from([document(preparation_demandee_le="")])
    assert without.preparation is None
    (with_,) = decisions_from([document(pretentions="x" * 5000)])
    assert with_.preparation == PrepRequest(
        "2026-11-19T10:00:00.000Z",
        "x" * 2000,
        "Jeudi 14 h, visio avec le CTO",
        "insiste sur le RAG",
        with_.preparation.context if with_.preparation else "",
    )


TECH_SHEET = "# Préparation technique / manager : Acme — Lead AI\n## À retenir\nTout."
TECHNICAL = {
    "suite": "entretien_technique",
    "preparation_technique_demandee_le": "2026-11-25T09:00:00.000Z",
    "retour_entretien_rh": "La RH a insisté sur l'autonomie",
    "entretien_infos": "Mardi 10 h, sur place avec la manager data",
}


def ask_technical(base: LocalDb, paths: Paths, **fields: Any) -> int:
    return ask(base, paths, **{**TECHNICAL, **fields})


@pytest.mark.spec("PREP-50", "PREP-01", "PREP-02", "BASE-12", "ECH-11")
def test_the_technical_request_is_separate_from_the_hr_one(base: LocalDb, paths: Paths) -> None:
    ask(base, paths)
    base.record_preparation(AD.key, SHEET, "2026-11-19T10:05:00.000Z")
    # The page still sends the served HR request: only the technical one is new.
    assert ask_technical(base, paths) == 1
    assert ask_technical(base, paths) == 0
    assert base.pending_preparations() == []
    assert base.pending_preparations("technique") == [AD.key]
    request = base.prep_request(AD.key, "technique")
    assert request is not None
    assert request.kind == "technique"
    assert request.requested_at == "2026-11-25T09:00:00.000Z"
    assert request.hr_feedback == "La RH a insisté sur l'autonomie"
    assert request.interview_details == "Mardi 10 h, sur place avec la manager data"
    hr_request = base.prep_request(AD.key)
    assert hr_request is not None and hr_request.requested_at == "2026-11-19T10:00:00.000Z"


@pytest.mark.spec("PREP-51")
def test_the_technical_prompt_builds_on_the_hr_sheet(base: LocalDb, paths: Paths) -> None:
    ask(base, paths)
    base.record_preparation(AD.key, SHEET, "2026-11-19T10:05:00.000Z")
    ask_technical(base, paths)
    application = base.find(AD.key)
    request = base.prep_request(AD.key, "technique")
    assert application is not None and request is not None
    prompt = preparation_prompt(application, request, paths, "Mon profil")
    for expected in (
        "Entreprise : Acme",
        "Suite : entretien_technique",
        "Texte de l'offre",
        "Mon profil",
        "\\newcommand{\\pRAG}{RAG}",
        "## Retour des entretiens précédents\nLa RH a insisté sur l'autonomie",
        "## Fiche de l'entretien RH (déjà connue du candidat, à ne pas répéter)\n" + SHEET,
        "## Consigne du candidat (prioritaire)\ninsiste sur le RAG",
    ):
        assert expected in prompt
    hr_request = base.prep_request(AD.key)
    assert hr_request is not None
    hr_prompt = preparation_prompt(application, hr_request, paths, "")
    assert "Retour des entretiens" not in hr_prompt
    assert "Fiche de l'entretien RH" not in hr_prompt


@pytest.mark.spec("PREP-52", "CLA-04")
def test_the_technical_call_uses_its_model_and_web_tools(base: LocalDb, paths: Paths) -> None:
    ask(base, paths)
    ask_technical(base, paths)
    assistant = FakeAssistant(TECH_SHEET)
    assert prepare(base, assistant, paths, "sonnet", "", technical_model="opus") == (2, [])
    assert assistant.models == ["sonnet", "opus"]
    assert assistant.tools == [WEB_TOOLS, WEB_TOOLS]
    assert assistant.delays == [900, 1800]
    assert assistant.systems[1] == TECH_SYSTEM
    assert assistant.systems[0] != TECH_SYSTEM


@pytest.mark.spec("PREP-54", "PREP-02", "ECH-03", "ECH-05")
def test_the_technical_sheet_is_written_apart_and_sent(base: LocalDb, paths: Paths) -> None:
    ask(base, paths)
    prepare(base, FakeAssistant(SHEET), paths, "sonnet", "", clock=lambda: "2026-11-19T10:05Z")
    ask_technical(base, paths)
    prepare(
        base,
        FakeAssistant(f"Voici.\n{TECH_SHEET}"),
        paths,
        "sonnet",
        "",
        clock=lambda: "2026-11-25T09:20:00.000Z",
    )
    folder = paths.applications / "sent" / folder_name(AD)
    assert (folder / TECH_SHEET_FILE).read_text(encoding="utf-8") == TECH_SHEET + "\n"
    assert (folder / SHEET_FILE).read_text(encoding="utf-8") == SHEET + "\n"
    (row,) = for_the_page(base.for_the_page(), paths.root)
    assert row["preparation"] == SHEET + "\n"
    assert row["preparation_technique"] == TECH_SHEET + "\n"
    assert row["preparation_technique_le"] == "2026-11-25T09:20:00.000Z"
    assert row["texte_offre"] == "Texte de l'offre"


@pytest.mark.spec("PREP-54", "ECH-03")
def test_a_technical_sheet_alone_is_sent_and_cut_at_its_own_length(
    base: LocalDb, paths: Paths
) -> None:
    ask_technical(base, paths, preparation_demandee_le="")
    prepare(base, FakeAssistant(TECH_SHEET), paths, "sonnet", "")
    (row,) = for_the_page(base.for_the_page(), paths.root)
    assert "preparation" not in row
    assert row["preparation_technique"] == TECH_SHEET + "\n"
    long_sheet = "# Fiche\n" + "x" * (MAX_LENGTH + 5_000)
    assert len(clean_sheet(long_sheet, TECH_MAX_LENGTH, TECH_CUT)) == len(long_sheet) + 1
    cut = clean_sheet("# Fiche\n" + "x" * TECH_MAX_LENGTH * 2, TECH_MAX_LENGTH, TECH_CUT)
    assert len(cut) <= TECH_MAX_LENGTH and cut.endswith(TECH_CUT + "\n")


@pytest.mark.spec("PREP-55", "PREP-21")
def test_a_failed_technical_sheet_stays_pending_and_keeps_the_hr_one(
    base: LocalDb, paths: Paths
) -> None:
    ask(base, paths)
    prepare(base, FakeAssistant(SHEET), paths, "sonnet", "")
    ask_technical(base, paths)

    class Failing(FakeAssistant):
        def ask(self, prompt: str, **options: Any) -> str:
            raise ClaudeError("délai dépassé")

    successes, failures = prepare(base, Failing(""), paths, "sonnet", "")
    assert successes == 0
    assert len(failures) == 1 and "technique / manager" in failures[0]
    assert base.pending_preparations("technique") == [AD.key]
    application = base.find(AD.key)
    assert application is not None and application.preparation == SHEET + "\n"


@pytest.mark.spec("PREP-40")
def test_prepare_given_keys_can_ask_for_the_technical_sheet(base: LocalDb, paths: Paths) -> None:
    base.add([AD])
    assistant = FakeAssistant(TECH_SHEET)
    assert prepare(base, assistant, paths, "sonnet", "", [AD.key], kind="technique") == (1, [])
    assert assistant.models == ["opus"]
    application = base.find(AD.key)
    assert application is not None
    assert application.technical_preparation == TECH_SHEET + "\n"
    assert application.preparation == ""
