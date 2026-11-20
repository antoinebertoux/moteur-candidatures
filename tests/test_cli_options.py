import argparse
import subprocess
import sys
from pathlib import Path

import pytest

from moteur.cli import build_parser, read_options

ENGLISH_COMMANDS = {
    "collect",
    "score",
    "export",
    "links",
    "daily",
    "decisions",
    "generate",
    "letter",
    "prepare",
    "mcp",
    "detect",
    "serve",
}


@pytest.mark.spec("CLI-02")
def test_verbose_before_or_after_the_command() -> None:
    assert read_options(["-v", "daily"]).verbose
    assert read_options(["daily", "--verbose"]).verbose
    assert not read_options(["daily"]).verbose


@pytest.mark.spec("CLI-02")
def test_default_config_and_config_after_the_command() -> None:
    assert read_options(["collect"]).config == Path("config.toml")
    assert read_options(["collect", "--config", "x.toml"]).config == Path("x.toml")
    options = read_options(["decisions", "export.json", "-v"])
    assert options.file == Path("export.json") and options.verbose


@pytest.mark.spec("CLI-07")
def test_commands_and_help_are_in_english() -> None:
    parser = build_parser()
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert set(subparsers.choices) == ENGLISH_COMMANDS
    help_text = parser.format_help() + "".join(p.format_help() for p in subparsers.choices.values())
    assert not any(c in help_text for c in "éèàêç")
    assert read_options(["detect", "https://x.io", "--name", "X"]).name == "X"


@pytest.mark.spec("CLI-07")
def test_a_configuration_error_is_reported_in_english(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "moteur.cli", "--config", str(tmp_path / "none.toml"), "score"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stderr.startswith("Error: ")
    assert "Traceback" not in result.stderr


@pytest.mark.spec("CLI-08")
@pytest.mark.parametrize(
    "arguments",
    [["quotidien"], ["collecter"], ["generer"], ["servir"], ["daily", "--verbeux"]],
)
def test_former_french_names_are_rejected(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        read_options(arguments)
    assert stop.value.code == 2
