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

from moteur import echange
from moteur.base_locale import BaseLocale
from moteur.config import Chemins
from moteur.decisions import appliquer

NOM = "moteur"


def propositions(chemins: Chemins) -> dict[str, Any]:
    """ECH-21: what `pour-la-page.json` would hold, read from the database right now."""
    with BaseLocale(chemins.base) as base:
        candidatures = base.pour_la_page()
    return {"candidatures": echange.pour_la_page(candidatures, chemins.racine)}


Lanceur = Callable[[], None]
"""Starts `moteur preparer` in the background (PREP-41)."""


def _ne_rien_lancer() -> None:
    return None


def decisions(
    chemins: Chemins, documents: object, lancer_preparation: Lanceur = _ne_rien_lancer
) -> dict[str, int]:
    """ECH-22: applies the page's documents like `moteur decisions` and returns the counts.

    Raises `ErreurEchange` (ECH-23) before touching the database if the input is invalid.
    A new preparation request starts `moteur preparer` in the background (ECH-26).
    """
    lues = echange.decisions_depuis(documents)
    with BaseLocale(chemins.base) as base:
        bilan = appliquer(base, lues, chemins.racine)
    if bilan.preparations:
        # The answer never depends on the background start (ECH-26).
        with suppress(OSError):
            lancer_preparation()
    return bilan.en_dict()


def serveur(chemins: Chemins, lancer_preparation: Lanceur = _ne_rien_lancer) -> MCPServer:
    """The two tools of ECH-20, and nothing else."""
    mcp: MCPServer = MCPServer(NOM, instructions="Local engine B of the tracking page.")

    @mcp.tool(
        name="propositions",
        description="Engine B entries for the page: scored proposals and ready folders.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def outil_propositions() -> dict[str, Any]:
        return propositions(chemins)

    @mcp.tool(
        name="decisions",
        description="Records the page decisions (all its documents) in engine B.",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
    )
    def outil_decisions(candidatures: list[Any]) -> dict[str, int]:
        try:
            return decisions(chemins, {"candidatures": candidatures}, lancer_preparation)
        except echange.ErreurEchange as erreur:
            raise ToolError(str(erreur)) from erreur

    return mcp


def lancer(chemins: Chemins, lancer_preparation: Lanceur = _ne_rien_lancer) -> None:
    """Serves over stdio: stdout belongs to the protocol, nothing else may print there."""
    serveur(chemins, lancer_preparation).run("stdio")
