"""Direct link with the tracking page: MCP server started by the Claude desktop app.

The page cannot `fetch()` the PC, but it can call this server as `host:moteur` (artifact
`mcp` capability). It carries the same content as the JSON files of `echange.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from moteur import exchange
from moteur.config import Config, ConfigError, Paths
from moteur.decisions import apply
from moteur.local_db import LocalDb
from moteur.selection import SelectionError, choices_from, summary

NAME = "moteur"


def propositions(paths: Paths) -> dict[str, Any]:
    """ECH-21: what `pour-la-page.json` would hold, read from the database right now."""
    with LocalDb(paths.base) as base:
        applications = base.for_the_page()
        links = base.company_links()
        archived = base.archived_ad_texts()
    rows = exchange.for_the_page(applications, paths.root, links, archived)
    return {"candidatures": rows}


Launcher = Callable[[], None]
"""Starts `moteur preparer` in the background (PREP-41)."""


def _launch_nothing() -> None:
    return None


def decisions(
    paths: Paths, documents: object, launch_preparation: Launcher = _launch_nothing
) -> dict[str, int]:
    """ECH-22: applies the page's documents like `moteur decisions` and returns the counts.

    Raises `ErreurEchange` (ECH-23) before touching the database if the input is invalid.
    A new preparation request starts `moteur preparer` in the background (ECH-26).
    """
    read_ones = exchange.decisions_from(documents)
    with LocalDb(paths.base) as base:
        outcome = apply(base, read_ones, paths.root)
    if outcome.preparations:
        # The answer never depends on the background start (ECH-26).
        with suppress(OSError):
            launch_preparation()
    return outcome.as_dict()


ConfigLoader = Callable[[], Config]
"""Reads `config.toml` again, so that the tools see its current companies."""


def _no_config() -> Config:
    raise ConfigError("no configuration given to the server")


def companies(config: Config, paths: Paths) -> dict[str, Any]:
    """ECH-27: the companies followed and User's choices, read right now."""
    with LocalDb(paths.base) as base:
        return summary(config, base.choices())


def record_selection(config: Config, paths: Paths, entry: object) -> dict[str, Any]:
    """ECH-28: records the choices and answers like `entreprises`.

    Raises `SelectionError` (ECH-29) before touching the database if one choice is invalid.
    """
    choices = choices_from(entry, config)
    with LocalDb(paths.base) as base:
        base.record_choices(choices)
        return summary(config, base.choices())


def server(
    paths: Paths,
    launch_preparation: Launcher = _launch_nothing,
    load_config: ConfigLoader = _no_config,
) -> MCPServer:
    """The four tools of ECH-20, and nothing else."""
    mcp: MCPServer = MCPServer(NAME, instructions="Local engine B of the tracking page.")

    @mcp.tool(
        name="propositions",
        description="Engine B entries for the page: scored proposals and ready folders.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def propositions_tool() -> dict[str, Any]:
        return propositions(paths)

    @mcp.tool(
        name="decisions",
        description="Records the page decisions (all its documents) in engine B.",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
    )
    # The parameter name is the tool's input key, sent by the page: it stays French.
    def decisions_tool(candidatures: list[Any]) -> dict[str, int]:
        try:
            return decisions(paths, {"candidatures": candidatures}, launch_preparation)
        except exchange.ExchangeError as error:
            raise ToolError(str(error)) from error

    @mcp.tool(
        name="entreprises",
        description="Companies followed by engine B and User's choice of what is searched.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def companies_tool() -> dict[str, Any]:
        try:
            return companies(load_config(), paths)
        except ConfigError as error:
            raise ToolError(str(error)) from error

    @mcp.tool(
        name="selection",
        description="Turns companies, sectors, sizes or sources on or off for engine B.",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
    )
    # The parameter name is the tool's input key, sent by the page: it stays French.
    def selection_tool(choix: list[Any]) -> dict[str, Any]:
        try:
            return record_selection(load_config(), paths, {"choix": choix})
        except (ConfigError, SelectionError) as error:
            raise ToolError(str(error)) from error

    return mcp


def launch(
    paths: Paths,
    launch_preparation: Launcher = _launch_nothing,
    load_config: ConfigLoader = _no_config,
) -> None:
    """Serves over stdio: stdout belongs to the protocol, nothing else may print there."""
    server(paths, launch_preparation, load_config).run("stdio")
