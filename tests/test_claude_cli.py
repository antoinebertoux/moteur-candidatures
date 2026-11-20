import json
from collections.abc import Sequence

import pytest

from moteur.claude_cli import (
    ClaudeCli,
    ClaudeError,
    ProcessResult,
    extract_block,
    extract_json,
)


def cli(result: ProcessResult, calls: list[tuple[list[str], str]] | None = None) -> ClaudeCli:
    def runner(command: Sequence[str], entry: str, delay: int) -> ProcessResult:
        if calls is not None:
            calls.append((list(command), entry))
        return result

    return ClaudeCli(runner)


@pytest.mark.spec("CLA-01")
def test_ask_sends_prompt_on_stdin_and_disables_tools() -> None:
    calls: list[tuple[list[str], str]] = []
    output = json.dumps({"result": "Bonjour", "is_error": False})
    answer = cli(ProcessResult(0, output), calls).ask("question", system="consignes", model="haiku")
    assert answer == "Bonjour"
    ((command, entry),) = calls
    assert entry == "question"
    assert command[:2] == ["claude", "-p"]
    assert command[command.index("--model") + 1] == "haiku"
    assert command[command.index("--system-prompt") + 1] == "consignes"
    assert command[command.index("--tools") + 1] == ""
    assert "--no-session-persistence" in command


@pytest.mark.parametrize(
    "result",
    [
        ProcessResult(1, "", "non connecté"),
        ProcessResult(0, "pas du json"),
        ProcessResult(0, json.dumps({"result": "x", "is_error": True})),
        ProcessResult(0, json.dumps({"result": "  "})),
        ProcessResult(0, json.dumps(["liste"])),
    ],
)
@pytest.mark.spec("CLA-02")
def test_ask_reports_failures(result: ProcessResult) -> None:
    with pytest.raises(ClaudeError):
        cli(result).ask("q", system="s", model="haiku")


@pytest.mark.spec("CLA-03")
def test_extract_block() -> None:
    assert extract_block("Voici :\n```latex\n\\documentclass{a}\n```\nFin") == "\\documentclass{a}"
    assert extract_block("  sans bloc ") == "sans bloc"


@pytest.mark.spec("CLA-03")
def test_extract_json() -> None:
    assert extract_json('Résultat :\n```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert extract_json('texte {"a": [1, 2]} texte') == {"a": [1, 2]}
    for invalid in ("rien", "[1, 2", "] ["):
        with pytest.raises(ClaudeError):
            extract_json(invalid)
