"""Command line: `moteur <command>`."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from moteur import exchange
from moteur.claude_cli import ClaudeCli, claude_binary
from moteur.collection import collect, companies_already_seen
from moteur.company_links import config_links, look_up
from moteur.config import Config, ConfigError, load_config
from moteur.cover_letter import generate_letters
from moteur.decisions import apply as apply_decisions
from moteur.detection import report as detection_report
from moteur.env import load_env
from moteur.generation import generate, latex_compiler
from moteur.interview_prep import launch_in_background, prepare_alone
from moteur.latex_repository import LatexRepositoryError, init_latex
from moteur.local_db import LocalDb
from moteur.mcp_link import launch as run_mcp_link
from moteur.pdf_server import DEFAULT_PORT, serve
from moteur.scoring import score_ads
from moteur.sources.ats import SourceAts
from moteur.sources.base import HttpClient, HttpxClient, Source
from moteur.sources.france_travail import SourceFranceTravail
from moteur.sources.radancy import SourceRadancy
from moteur.sources.service_public import SourceServicePublic
from moteur.sources.station_f import SourceStationF
from moteur.sources.welcomekit import SourceWelcomeKit
from moteur.sources.workday import SourceWorkday

log = logging.getLogger("moteur")

FILE_FOR_THE_PAGE = "pour-la-page.json"


def build_sources(config: Config, client: HttpClient) -> list[Source]:
    sources: list[Source] = []
    france_travail = config.france_travail
    if france_travail.enabled:
        identifier = os.environ.get("FRANCE_TRAVAIL_ID", "")
        secret = os.environ.get("FRANCE_TRAVAIL_SECRET", "")
        if identifier and secret:
            sources.append(
                SourceFranceTravail(
                    client,
                    identifier,
                    secret,
                    france_travail.searches,
                    france_travail.departments,
                    france_travail.published_since,
                )
            )
        else:
            log.warning("France Travail skipped: set FRANCE_TRAVAIL_ID and FRANCE_TRAVAIL_SECRET")
    service_public = config.service_public
    if service_public.enabled:
        sources.append(
            SourceServicePublic(
                client,
                service_public.searches,
                service_public.domains,
                service_public.employers,
                service_public.pages_max,
            )
        )
    station_f = config.station_f
    if station_f.enabled:
        sources.append(
            SourceStationF(
                client, station_f.searches, station_f.pages_max, station_f.published_since
            )
        )
    for target in config.companies:
        if target.ats == "workday":
            sources.append(SourceWorkday(client, target))
        elif target.ats == "radancy":
            sources.append(SourceRadancy(client, target))
        elif target.ats == "welcomekit":
            sources.append(SourceWelcomeKit(client, target))
        elif target.ats:
            sources.append(SourceAts(client, target))
    return sources


def command_collect(config: Config, base: LocalDb) -> None:
    client = HttpxClient()
    try:
        already_seen = companies_already_seen(config.paths.seen_companies) | base.known_companies()
        ads = collect(
            build_sources(config, client),
            config.criteria,
            config.companies,
            already_seen,
            config.unsolicited_role,
        )
    finally:
        client.close()
    print(f"{len(ads)} kept after filtering, {base.add(ads)} of them new")


def command_score(config: Config, base: LocalDb) -> None:
    scored_count = score_ads(
        base,
        ClaudeCli(binary=claude_binary()),
        profile=config.profile,
        model=config.scoring_model,
        batch_size=config.batch_size,
    )
    print(f"{scored_count} ads scored, {len(base.to_score())} still waiting")


def command_links(config: Config, base: LocalDb) -> None:
    """LNK-10: looks up the missing company links; never stops the daily run (LNK-15)."""
    looked_up_count, found_links = look_up(
        base, ClaudeCli(binary=claude_binary()), model=config.scoring_model
    )
    print(f"{looked_up_count} companies looked up, {found_links} links found")


def command_export(config: Config, base: LocalDb) -> None:
    applications = base.for_the_page()
    config.paths.exchange.mkdir(parents=True, exist_ok=True)
    file = config.paths.exchange / FILE_FOR_THE_PAGE
    file.write_text(
        exchange.serialise(
            applications, config.paths.root, base.company_links(), base.archived_ad_texts()
        ),
        encoding="utf-8",
    )
    print(f"{len(applications)} entries in {file}: to import into the tracking page")


def command_decisions(base: LocalDb, file: Path, root: Path) -> None:
    decisions = exchange.read_decisions(file.read_text(encoding="utf-8"))
    print(apply_decisions(base, decisions, root).sentence())


def command_generate(config: Config, base: LocalDb) -> None:
    successes, failures = generate(
        base,
        ClaudeCli(binary=claude_binary()),
        config.paths,
        config.generation_model,
        latex_compiler(config.paths.latex),
    )
    print(f"{successes} folders generated, {len(failures)} failed")
    for failure in failures:
        print(f"  - {failure}")
    command_letter(config, base, [])


def command_letter(config: Config, base: LocalDb, keys: list[str]) -> None:
    """Letters only: those of the given keys, otherwise all the missing ones."""
    if not keys and not base.missing_letters():
        return
    successes, failures = generate_letters(
        base,
        ClaudeCli(binary=claude_binary()),
        config.paths,
        config.generation_model,
        latex_compiler(config.paths.latex),
        keys,
    )
    print(f"{successes} letters added, {len(failures)} failed")
    for failure in failures:
        print(f"  - {failure}")


def command_init_latex(config: Config) -> None:
    """LTX-03: copies the example to latex/ and says what to adapt."""
    target = config.paths.latex
    to_adapt = init_latex(target)
    print(f"Example copied to {target}. Adapt these files to your own profile:")
    for name in to_adapt:
        print(f"  - {name}")
    print("Optional: put your photo in cv/images/ and set it with \\setphoto in cv/modele-cv.tex")


def command_prepare(config: Config, base: LocalDb, keys: list[str]) -> None:
    """Interview preparation sheets: the given identifiers, or every pending request."""
    result = prepare_alone(
        base,
        ClaudeCli(binary=claude_binary()),
        config.paths,
        config.preparation_model,
        config.profile,
        keys,
    )
    if result is None:
        print("A preparation is already running: it will handle the pending requests")
        return
    successes, failures = result
    print(f"{successes} preparation sheets written, {len(failures)} failed")
    for failure in failures:
        print(f"  - {failure}")


def build_parser() -> argparse.ArgumentParser:
    # Common options, accepted before or after the command (`moteur -v daily` as well as
    # `moteur daily -v`). SUPPRESS keeps the subparser from overwriting the value.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, default=argparse.SUPPRESS)
    common.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help="show details for each source",
    )
    parser = argparse.ArgumentParser(prog="moteur", description=__doc__, parents=[common])
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        return commands.add_parser(name, help=help_text, parents=[common])

    command("collect", "query the sources and filter (0 tokens)")
    command("score", "score the new ads with Claude")
    command("export", "write the file to import into the page")
    command("links", "look up the website and LinkedIn page of companies that lack them")
    command("daily", "collect, score, links, then export")
    command("decisions", "read the page's export").add_argument("file", type=Path)
    command("init-latex", "copy the LaTeX example to latex/, to adapt to your profile")
    command("generate", "prepare the CV and letter of accepted ads")
    command(
        "letter", "add the letter to folders already generated (all the missing ones)"
    ).add_argument("keys", nargs="*", help="specific identifiers (same format as the page)")
    command("prepare", "interview preparation sheets (all pending requests)").add_argument(
        "keys", nargs="*", help="specific identifiers (same format as the page)"
    )
    command("mcp", "direct link with the page, started by the Claude desktop app")
    detect = command("detect", "recognise the recruiting tool of career pages")
    detect.add_argument("addresses", nargs="+", help="career pages or ad addresses")
    detect.add_argument("--name", default="", help="company name (single address only)")
    command("serve", "serve the CVs and letters for the page's links").add_argument(
        "--port", type=int, default=DEFAULT_PORT
    )
    return parser


def read_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parses the command line and fills in the missing common options."""
    options = build_parser().parse_args(arguments)
    if not hasattr(options, "config"):
        options.config = Path("config.toml")
    if not hasattr(options, "verbose"):
        options.verbose = False
    return options


def main(arguments: Sequence[str] | None = None) -> int:
    options = read_options(arguments)
    logging.basicConfig(
        level=logging.INFO if options.verbose else logging.WARNING, format="%(message)s"
    )
    if options.command == "detect":
        # CLI-06: needs no configuration, writes nothing, never calls Claude.
        client = HttpxClient()
        try:
            print(detection_report(options.addresses, client, options.name))
        finally:
            client.close()
        return 0
    try:
        load_env(options.config.resolve().parent / ".env")
        config = load_config(options.config)
        # CONF-09: the tracked companies' links, refreshed at every start.
        with LocalDb(config.paths.base) as base:
            base.set_config_links(
                config_links([(e.name, e.site, e.linkedin) for e in config.companies])
            )
        if options.command == "mcp":
            # ECH-24: the server opens the database for each call, never for its whole life.
            config_file = options.config.resolve()
            run_mcp_link(config.paths, lambda: launch_in_background(config_file, config.paths))
            return 0
        if options.command == "init-latex":
            command_init_latex(config)
            return 0
        with LocalDb(config.paths.base) as base:
            if options.command in ("collect", "daily"):
                command_collect(config, base)
            if options.command in ("score", "daily"):
                command_score(config, base)
            if options.command in ("links", "daily"):
                command_links(config, base)
            if options.command in ("export", "daily"):
                command_export(config, base)
            if options.command == "decisions":
                command_decisions(base, options.file, config.paths.root)
            if options.command == "generate":
                command_generate(config, base)
                command_export(config, base)
            if options.command == "letter":
                command_letter(config, base, options.keys)
                command_export(config, base)
            if options.command == "prepare":
                command_prepare(config, base, options.keys)
                command_export(config, base)
            if options.command == "serve":
                serve(config.paths.applications, options.port)
    except (ConfigError, exchange.ExchangeError, LatexRepositoryError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
