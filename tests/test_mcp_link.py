"""Direct link with the page: the `moteur mcp` server and its two tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client import Client

from moteur.config import Paths
from moteur.exchange import ExchangeError, for_the_page
from moteur.local_db import LocalDb
from moteur.mcp_link import decisions, propositions, server
from moteur.models import JobAd, Rating

AD = JobAd("Acme", "Data Scientist", location="Paris", url="https://a")
NOTE = Rating(score=82, summary="Bon poste.", letter_requested=False, language="fr")


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    paths = Paths(root=tmp_path, base=tmp_path / "moteur.sqlite3", exchange=tmp_path / "e")
    with LocalDb(paths.base) as base:
        base.add([AD])
        base.record_score(AD.key, NOTE)
    return paths


def status(paths: Paths) -> str:
    with LocalDb(paths.base) as base:
        application = base.find(AD.key)
    assert application is not None
    return application.status


def page(page_status: str) -> dict[str, Any]:
    """A document as the page stores it."""
    return {"id": AD.key, "statut": page_status, "entreprise": "Acme", "poste": AD.title}


def invoke(paths: Paths, tool: str, entry: dict[str, Any]) -> Any:
    async def scenario() -> Any:
        async with Client(server(paths)) as client:
            return await client.call_tool(tool, entry)

    return anyio.run(scenario)


@pytest.mark.spec("ECH-20")
def test_the_server_exposes_only_two_tools(paths: Paths) -> None:
    async def scenario() -> Any:
        async with Client(server(paths)) as client:
            return (await client.list_tools()).tools

    tools = {tool.name: tool for tool in anyio.run(scenario)}
    assert set(tools) == {"propositions", "decisions"}
    reading = tools["propositions"].annotations
    assert reading is not None
    assert reading.read_only_hint is True


@pytest.mark.spec("ECH-21")
def test_propositions_reads_the_database_without_writing_a_file(paths: Paths) -> None:
    with LocalDb(paths.base) as base:
        expected = for_the_page(base.for_the_page(), paths.root)
    assert propositions(paths) == {"candidatures": expected}
    assert expected[0]["entreprise"] == "Acme"
    assert expected[0]["score"] == 82
    assert not paths.exchange.exists()


@pytest.mark.spec("ECH-21")
def test_propositions_over_the_protocol(paths: Paths) -> None:
    result = invoke(paths, "propositions", {})
    assert not result.is_error
    assert '"Acme"' in result.content[0].text


@pytest.mark.spec("ECH-22")
def test_decisions_applies_like_the_command(paths: Paths) -> None:
    outcome = decisions(paths, {"candidatures": [page("acceptee")]})
    assert outcome["decisions"] == 1
    assert outcome["to_generate"] == 1
    assert set(outcome) == {
        "decisions",
        "completed",
        "letters",
        "to_generate",
        "letters_to_add",
        "preparations",
    }
    assert status(paths) == "acceptee"


@pytest.mark.spec("ECH-22")
def test_same_decisions_change_nothing_the_second_time(paths: Paths) -> None:
    documents = {"candidatures": [page("refusee")]}
    assert decisions(paths, documents)["decisions"] == 1
    second = decisions(paths, documents)
    assert (second["decisions"], second["completed"], second["letters"]) == (0, 0, 0)
    assert status(paths) == "refusee"


@pytest.mark.spec("ECH-22")
def test_decisions_over_the_protocol(paths: Paths) -> None:
    result = invoke(paths, "decisions", {"candidatures": [page("acceptee")]})
    assert not result.is_error
    assert status(paths) == "acceptee"


@pytest.mark.spec("ECH-23")
def test_an_invalid_input_changes_nothing(paths: Paths) -> None:
    with pytest.raises(ExchangeError, match="candidatures"):
        decisions(paths, {"autre": []})
    result = invoke(paths, "decisions", {"candidatures": "pas un tableau"})
    assert result.is_error
    assert status(paths) == "notee"


@pytest.mark.spec("ECH-24")
def test_the_database_stays_free_between_calls(paths: Paths) -> None:
    propositions(paths)
    decisions(paths, {"candidatures": [page("acceptee")]})
    # A terminal command can write right after: no lock is left behind.
    with LocalDb(paths.base) as base:
        assert base.apply_decision(AD.key, "refusee")


@pytest.mark.spec("ECH-25")
def test_the_tools_never_call_claude(paths: Paths, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_: object, **__: object) -> None:
        raise AssertionError("Claude must not be called")

    monkeypatch.setattr("moteur.claude_cli.ClaudeCli.ask", forbidden)
    monkeypatch.setattr("moteur.generation.generate", forbidden)
    propositions(paths)
    decisions(paths, {"candidatures": [page("acceptee")]})
    assert status(paths) == "acceptee"
