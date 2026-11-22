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
from moteur.config import Config, ConfigError, Paths, with_criteria
from moteur.decisions import apply
from moteur.local_db import LocalDb
from moteur.own_companies import OwnCompanyError, add_companies, remove_companies
from moteur.selection import SelectionError, selection_from, summary
from moteur.sources.base import HttpClient, HttpxClient

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
"""Reads `config.toml` and the own companies again, so that the tools see the current ones."""

ClientFactory = Callable[[], HttpClient]
"""HTTP client for the board check of `ajouter_entreprises` (CAT-22)."""


def _no_config() -> Config:
    raise ConfigError("no configuration given to the server")


def companies(config: Config, paths: Paths) -> dict[str, Any]:
    """ECH-27: the companies followed and User's choices, read right now."""
    with LocalDb(paths.base) as base:
        return summary(with_criteria(config, base.criteria()), base.choices())


def record_selection(config: Config, paths: Paths, entry: object) -> dict[str, Any]:
    """ECH-28: records the choices and answers like `entreprises`.

    Raises `SelectionError` (ECH-29) before touching the database if one choice is invalid.
    """
    selection = selection_from(entry, config)
    with LocalDb(paths.base) as base:
        base.record_choices(selection.choices)
        base.record_criteria(selection.criteria)
        # The criteria just recorded change the defaults of the companies (CAT-11).
        return summary(with_criteria(config, base.criteria()), base.choices())


def add_own_companies(
    config: Config, paths: Paths, entry: object, client: HttpClient
) -> dict[str, Any]:
    """ECH-30: checks and keeps the companies; raises `OwnCompanyError` (ECH-31)."""
    with LocalDb(paths.base) as base:
        return add_companies(entry, config, base, client)


def remove_own_companies(load_config: ConfigLoader, paths: Paths, entry: object) -> dict[str, Any]:
    """ECH-32: removes own companies, then answers like `entreprises`."""
    with LocalDb(paths.base) as base:
        remove_companies(entry, base)
    return companies(load_config(), paths)


def _real_client() -> HttpClient:
    return HttpxClient()


def server(
    paths: Paths,
    launch_preparation: Launcher = _launch_nothing,
    load_config: ConfigLoader = _no_config,
    new_client: ClientFactory = _real_client,
) -> MCPServer:
    """The six tools of ECH-20, and nothing else."""
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
        description=(
            "Turns companies, sectors, sizes or sources on or off for engine B, and replaces "
            "its search criteria (mots_cles, exclusions, lieux, pays, recherches)."
        ),
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
    )
    # The parameter name is the tool's input key, sent by the page: it stays French.
    def selection_tool(choix: list[Any]) -> dict[str, Any]:
        try:
            return record_selection(load_config(), paths, {"choix": choix})
        except (ConfigError, SelectionError) as error:
            raise ToolError(str(error)) from error

    @mcp.tool(
        name="ajouter_entreprises",
        description=(
            "Adds User's own companies to engine B (1 to 20). Each needs nom, secteur, taille "
            "and either ats + identifiant or adresse (career page); optional site, linkedin, "
            "pays. Engine B queries each board before keeping it and says why it refuses one."
        ),
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
    )
    # The parameter name is the tool's input key: it stays French, like the others.
    def add_tool(entreprises: list[Any]) -> dict[str, Any]:
        client = new_client()
        try:
            return add_own_companies(load_config(), paths, {"entreprises": entreprises}, client)
        except (ConfigError, OwnCompanyError) as error:
            raise ToolError(str(error)) from error
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    @mcp.tool(
        name="retirer_entreprises",
        description="Stops following some of User's own companies, given by their key (cle).",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True),
    )
    def remove_tool(cles: list[Any]) -> dict[str, Any]:
        try:
            return remove_own_companies(load_config, paths, {"cles": cles})
        except (ConfigError, OwnCompanyError) as error:
            raise ToolError(str(error)) from error

    return mcp


def launch(
    paths: Paths,
    launch_preparation: Launcher = _launch_nothing,
    load_config: ConfigLoader = _no_config,
) -> None:
    """Serves over stdio: stdout belongs to the protocol, nothing else may print there."""
    server(paths, launch_preparation, load_config).run("stdio")
