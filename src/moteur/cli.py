"""Ligne de commande : `moteur <commande>`."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from moteur import echange
from moteur.base_locale import BaseLocale
from moteur.claude_cli import ClaudeCli
from moteur.collecte import collecter, entreprises_deja_vues
from moteur.config import Config, ErreurConfig, charger
from moteur.decisions import appliquer as appliquer_decisions
from moteur.detection import report as detection_report
from moteur.env import charger_env
from moteur.generation import compilateur_latex, generer
from moteur.lettre import generer_lettres
from moteur.liaison import lancer as lancer_liaison
from moteur.notation import noter
from moteur.serveur import PORT_PAR_DEFAUT, servir
from moteur.sources.ats import SourceAts
from moteur.sources.base import ClientHttp, ClientHttpx, Source
from moteur.sources.france_travail import SourceFranceTravail
from moteur.sources.radancy import SourceRadancy
from moteur.sources.service_public import SourceServicePublic
from moteur.sources.welcomekit import SourceWelcomeKit
from moteur.sources.workday import SourceWorkday

journal = logging.getLogger("moteur")

FICHIER_POUR_LA_PAGE = "pour-la-page.json"


def construire_sources(config: Config, client: ClientHttp) -> list[Source]:
    sources: list[Source] = []
    france_travail = config.france_travail
    if france_travail.actif:
        identifiant = os.environ.get("FRANCE_TRAVAIL_ID", "")
        secret = os.environ.get("FRANCE_TRAVAIL_SECRET", "")
        if identifiant and secret:
            sources.append(
                SourceFranceTravail(
                    client,
                    identifiant,
                    secret,
                    france_travail.recherches,
                    france_travail.departements,
                    france_travail.publiee_depuis,
                )
            )
        else:
            journal.warning(
                "France Travail ignoré : définis FRANCE_TRAVAIL_ID et FRANCE_TRAVAIL_SECRET"
            )
    service_public = config.service_public
    if service_public.actif:
        sources.append(
            SourceServicePublic(
                client,
                service_public.recherches,
                service_public.domaines,
                service_public.employeurs,
                service_public.pages_max,
            )
        )
    for cible in config.entreprises:
        if cible.ats == "workday":
            sources.append(SourceWorkday(client, cible))
        elif cible.ats == "radancy":
            sources.append(SourceRadancy(client, cible))
        elif cible.ats == "welcomekit":
            sources.append(SourceWelcomeKit(client, cible))
        elif cible.ats:
            sources.append(SourceAts(client, cible))
    return sources


def commande_collecter(config: Config, base: BaseLocale) -> None:
    client = ClientHttpx()
    try:
        deja_vues = (
            entreprises_deja_vues(config.chemins.entreprises_vues) | base.entreprises_connues()
        )
        offres = collecter(
            construire_sources(config, client),
            config.criteres,
            config.entreprises,
            deja_vues,
            config.role_spontane,
        )
    finally:
        client.fermer()
    print(f"{len(offres)} retenues après filtrage, dont {base.ajouter(offres)} nouvelles")


def commande_noter(config: Config, base: BaseLocale) -> None:
    notees = noter(
        base,
        ClaudeCli(),
        profil=config.profil,
        modele=config.modele_notation,
        taille_lot=config.taille_lot,
    )
    print(f"{notees} offres notées, {len(base.a_noter())} encore en attente")


def commande_exporter(config: Config, base: BaseLocale) -> None:
    candidatures = base.pour_la_page()
    config.chemins.echange.mkdir(parents=True, exist_ok=True)
    fichier = config.chemins.echange / FICHIER_POUR_LA_PAGE
    fichier.write_text(echange.serialiser(candidatures, config.chemins.racine), encoding="utf-8")
    print(f"{len(candidatures)} entrées dans {fichier} : à importer dans la page de suivi")


def commande_decisions(base: BaseLocale, fichier: Path, racine: Path) -> None:
    decisions = echange.lire_decisions(fichier.read_text(encoding="utf-8"))
    print(appliquer_decisions(base, decisions, racine).phrase())


def commande_generer(config: Config, base: BaseLocale) -> None:
    reussites, echecs = generer(
        base,
        ClaudeCli(),
        config.chemins,
        config.modele_generation,
        compilateur_latex(config.chemins.latex),
    )
    print(f"{reussites} dossiers générés, {len(echecs)} en échec")
    for echec in echecs:
        print(f"  - {echec}")
    commande_lettre(config, base, [])


def commande_lettre(config: Config, base: BaseLocale, cles: list[str]) -> None:
    """Lettres seules : celles des clés données, sinon toutes celles qui manquent."""
    if not cles and not base.lettres_manquantes():
        return
    reussites, echecs = generer_lettres(
        base,
        ClaudeCli(),
        config.chemins,
        config.modele_generation,
        compilateur_latex(config.chemins.latex),
        cles,
    )
    print(f"{reussites} lettres ajoutées, {len(echecs)} en échec")
    for echec in echecs:
        print(f"  - {echec}")


def analyseur() -> argparse.ArgumentParser:
    # Options communes, acceptées avant ou après la commande (`moteur -v quotidien`
    # comme `moteur quotidien -v`). SUPPRESS évite que le sous-parseur écrase la valeur.
    communes = argparse.ArgumentParser(add_help=False)
    communes.add_argument("--config", type=Path, default=argparse.SUPPRESS)
    communes.add_argument(
        "-v",
        "--verbeux",
        action="store_true",
        default=argparse.SUPPRESS,
        help="détaille chaque source",
    )
    parseur = argparse.ArgumentParser(prog="moteur", description=__doc__, parents=[communes])
    commandes = parseur.add_subparsers(dest="commande", required=True)

    def commande(nom: str, aide: str) -> argparse.ArgumentParser:
        return commandes.add_parser(nom, help=aide, parents=[communes])

    commande("collecter", "interroge les sources et filtre (0 token)")
    commande("noter", "note les nouvelles offres avec Claude")
    commande("exporter", "écrit le fichier à importer dans la page")
    commande("quotidien", "collecter, noter puis exporter")
    commande("decisions", "relit l'export de la page").add_argument("fichier", type=Path)
    commande("generer", "prépare CV et lettre des offres acceptées")
    commande(
        "lettre", "ajoute la lettre aux dossiers déjà générés (toutes celles qui manquent)"
    ).add_argument("cles", nargs="*", help="identifiants précis (même format que la page)")
    commande("mcp", "liaison directe avec la page, lancée par l'app Claude desktop")
    detecter = commande("detecter", "reconnaît l'outil de recrutement de pages carrières")
    detecter.add_argument("adresses", nargs="+", help="pages carrières ou adresses d'offres")
    detecter.add_argument("--nom", default="", help="nom de l'entreprise (une seule adresse)")
    commande("servir", "sert les CV et lettres pour les liens de la page").add_argument(
        "--port", type=int, default=PORT_PAR_DEFAUT
    )
    return parseur


def lire_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Analyse la ligne de commande et complète les options communes absentes."""
    options = analyseur().parse_args(arguments)
    if not hasattr(options, "config"):
        options.config = Path("config.toml")
    if not hasattr(options, "verbeux"):
        options.verbeux = False
    return options


def main(arguments: Sequence[str] | None = None) -> int:
    options = lire_options(arguments)
    logging.basicConfig(
        level=logging.INFO if options.verbeux else logging.WARNING, format="%(message)s"
    )
    if options.commande == "detecter":
        # CLI-06: needs no configuration, writes nothing, never calls Claude.
        client = ClientHttpx()
        try:
            print(detection_report(options.adresses, client, options.nom))
        finally:
            client.fermer()
        return 0
    try:
        charger_env(options.config.resolve().parent / ".env")
        config = charger(options.config)
        if options.commande == "mcp":
            # ECH-24: the server opens the database for each call, never for its whole life.
            lancer_liaison(config.chemins)
            return 0
        with BaseLocale(config.chemins.base) as base:
            if options.commande in ("collecter", "quotidien"):
                commande_collecter(config, base)
            if options.commande in ("noter", "quotidien"):
                commande_noter(config, base)
            if options.commande in ("exporter", "quotidien"):
                commande_exporter(config, base)
            if options.commande == "decisions":
                commande_decisions(base, options.fichier, config.chemins.racine)
            if options.commande == "generer":
                commande_generer(config, base)
                commande_exporter(config, base)
            if options.commande == "lettre":
                commande_lettre(config, base, options.cles)
                commande_exporter(config, base)
            if options.commande == "servir":
                servir(config.chemins.candidatures, options.port)
    except (ErreurConfig, echange.ErreurEchange, OSError) as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
