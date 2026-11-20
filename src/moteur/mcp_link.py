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
from moteur.config import Paths
from moteur.decisions import apply
from moteur.local_db import LocalDb

NAME = "moteur"


def propositions(paths: Paths) -> dict[str, Any]:
    """ECH-21: what `pour-la-page.json` would hold, read from the database right now."""
    with LocalDb(paths.base) as base:
        applications = base.for_the_page()
        links = base.company_links()
    return {"candidatures": exchange.for_the_page(applications, paths.root, links)}


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


def server(paths: Paths, launch_preparation: Launcher = _launch_nothing) -> MCPServer:
    """The two tools of ECH-20, and nothing else."""
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

    return mcp


def launch(paths: Paths, launch_preparation: Launcher = _launch_nothing) -> None:
    """Serves over stdio: stdout belongs to the protocol, nothing else may print there."""
    server(paths, launch_preparation).run("stdio")
