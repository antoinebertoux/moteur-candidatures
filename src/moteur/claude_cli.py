"""Calls to Claude through `claude -p`, so with the subscription and no API key.

Every call runs without MCP servers and with a short system prompt, which keeps quota
use to a minimum. Only two calls are given tools (CLA-04): the interview preparation
(web search and page fetching) and the company link lookup (web search).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

DELAY_SECONDS = 600
_BLOCK = re.compile(r"```[a-zA-Z]*\s*\n(.*?)```", re.DOTALL)


class ClaudeError(Exception):
    """The call to Claude failed or its answer cannot be used."""


@dataclass(frozen=True, slots=True)
class ProcessResult:
    code: int
    output: str
    error: str = ""


Runner = Callable[[Sequence[str], str, int], ProcessResult]
"""Runs a command with the given standard input and a time limit in seconds."""


class Assistant(Protocol):
    def ask(
        self,
        prompt: str,
        *,
        system: str,
        model: str,
        tools: tuple[str, ...] = (),
        delay: int = DELAY_SECONDS,
    ) -> str: ...


def execute(command: Sequence[str], entry: str, delay: int) -> ProcessResult:
    """Runs a command, passing `entry` on its standard input."""
    try:
        result = subprocess.run(
            list(command),
            input=entry,
            capture_output=True,
            text=True,
            timeout=delay,
            check=False,
        )
    except FileNotFoundError as error:
        raise ClaudeError(f"Command not found: {command[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise ClaudeError(f"{command[0]} did not answer within {delay} s") from error
    return ProcessResult(result.returncode, result.stdout, result.stderr)


def claude_binary() -> str:
    """`claude` from the PATH, or its usual install place when the PATH lacks it.

    A process started by the desktop app (PREP-41) may not have `~/.local/bin` in its PATH.
    """
    found_one = shutil.which("claude")
    if found_one:
        return found_one
    installed = Path.home() / ".local" / "bin" / "claude"
    return str(installed) if installed.exists() else "claude"


class ClaudeCli:
    def __init__(self, runner: Runner = execute, binary: str = "claude") -> None:
        self._runner = runner
        self._binary = binary

    def command(self, *, system: str, model: str, tools: tuple[str, ...] = ()) -> list[str]:
        # CLA-01: no tools at all, except the web tools allowed by CLA-04.
        allowed = ["--allowedTools", ",".join(tools)] if tools else []
        return [
            self._binary,
            "-p",
            "--model",
            model,
            "--output-format",
            "json",
            "--system-prompt",
            system,
            "--tools",
            ",".join(tools),
            *allowed,
            "--disallowedTools",
            "mcp__*",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]

    def ask(
        self,
        prompt: str,
        *,
        system: str,
        model: str,
        tools: tuple[str, ...] = (),
        delay: int = DELAY_SECONDS,
    ) -> str:
        command = self.command(system=system, model=model, tools=tools)
        result = self._runner(command, prompt, delay)
        if result.code != 0:
            detail = (result.error or result.output).strip()[:500]
            raise ClaudeError(f"claude failed (code {result.code}): {detail}")
        try:
            answer = json.loads(result.output)
        except json.JSONDecodeError as error:
            raise ClaudeError("Unreadable claude output (JSON expected)") from error
        if not isinstance(answer, dict) or answer.get("is_error"):
            raise ClaudeError(f"claude returned an error: {str(answer)[:500]}")
        text = answer.get("result")
        if not isinstance(text, str) or not text.strip():
            raise ClaudeError("Empty answer from claude")
        return text


def extract_block(text: str) -> str:
    """Contents of the first ``` block of the answer, or the whole answer if there is none."""
    block = _BLOCK.search(text)
    return (block.group(1) if block else text).strip()


def extract_json(text: str) -> Any:
    """Decodes the JSON of an answer, even surrounded by text or a ``` block."""
    candidate = extract_block(text)
    starts = [i for i in (candidate.find("["), candidate.find("{")) if i >= 0]
    end = max(candidate.rfind("]"), candidate.rfind("}"))
    if not starts or end < min(starts):
        raise ClaudeError("No JSON in the answer from claude")
    try:
        return json.loads(candidate[min(starts) : end + 1])
    except json.JSONDecodeError as error:
        raise ClaudeError("Invalid JSON in the answer from claude") from error
