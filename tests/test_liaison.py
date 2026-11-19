"""Direct link with the page: the `moteur mcp` server and its two tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client import Client

from moteur.base_locale import BaseLocale
from moteur.config import Chemins
from moteur.echange import ErreurEchange, pour_la_page
from moteur.liaison import decisions, propositions, serveur
from moteur.modeles import Note, Offre

OFFRE = Offre("Acme", "Data Scientist", lieu="Paris", url="https://a")
NOTE = Note(score=82, resume="Bon poste.", lettre_demandee=False, langue="fr")


@pytest.fixture
def chemins(tmp_path: Path) -> Chemins:
    chemins = Chemins(racine=tmp_path, base=tmp_path / "moteur.sqlite3", echange=tmp_path / "e")
    with BaseLocale(chemins.base) as base:
        base.ajouter([OFFRE])
        base.enregistrer_note(OFFRE.cle, NOTE)
    return chemins


def statut(chemins: Chemins) -> str:
    with BaseLocale(chemins.base) as base:
        candidature = base.trouver(OFFRE.cle)
    assert candidature is not None
    return candidature.statut


def page(statut_page: str) -> dict[str, Any]:
    """A document as the page stores it."""
    return {"id": OFFRE.cle, "statut": statut_page, "entreprise": "Acme", "poste": OFFRE.poste}


def appeler(chemins: Chemins, outil: str, entree: dict[str, Any]) -> Any:
    async def scenario() -> Any:
        async with Client(serveur(chemins)) as client:
            return await client.call_tool(outil, entree)

    return anyio.run(scenario)


@pytest.mark.spec("ECH-20")
def test_le_serveur_n_expose_que_deux_outils(chemins: Chemins) -> None:
    async def scenario() -> Any:
        async with Client(serveur(chemins)) as client:
            return (await client.list_tools()).tools

    outils = {outil.name: outil for outil in anyio.run(scenario)}
    assert set(outils) == {"propositions", "decisions"}
    lecture = outils["propositions"].annotations
    assert lecture is not None
    assert lecture.read_only_hint is True


@pytest.mark.spec("ECH-21")
def test_propositions_lit_la_base_sans_ecrire_de_fichier(chemins: Chemins) -> None:
    with BaseLocale(chemins.base) as base:
        attendu = pour_la_page(base.pour_la_page(), chemins.racine)
    assert propositions(chemins) == {"candidatures": attendu}
    assert attendu[0]["entreprise"] == "Acme"
    assert attendu[0]["score"] == 82
    assert not chemins.echange.exists()


@pytest.mark.spec("ECH-21")
def test_propositions_par_le_protocole(chemins: Chemins) -> None:
    resultat = appeler(chemins, "propositions", {})
    assert not resultat.is_error
    assert '"Acme"' in resultat.content[0].text


@pytest.mark.spec("ECH-22")
def test_decisions_applique_comme_la_commande(chemins: Chemins) -> None:
    bilan = decisions(chemins, {"candidatures": [page("acceptee")]})
    assert bilan["decisions"] == 1
    assert bilan["a_generer"] == 1
    assert set(bilan) == {
        "decisions",
        "completees",
        "lettres",
        "a_generer",
        "lettres_a_ajouter",
        "preparations",
    }
    assert statut(chemins) == "acceptee"


@pytest.mark.spec("ECH-22")
def test_les_memes_decisions_ne_changent_rien_la_seconde_fois(chemins: Chemins) -> None:
    documents = {"candidatures": [page("refusee")]}
    assert decisions(chemins, documents)["decisions"] == 1
    second = decisions(chemins, documents)
    assert (second["decisions"], second["completees"], second["lettres"]) == (0, 0, 0)
    assert statut(chemins) == "refusee"


@pytest.mark.spec("ECH-22")
def test_decisions_par_le_protocole(chemins: Chemins) -> None:
    resultat = appeler(chemins, "decisions", {"candidatures": [page("acceptee")]})
    assert not resultat.is_error
    assert statut(chemins) == "acceptee"


@pytest.mark.spec("ECH-23")
def test_une_entree_invalide_ne_change_rien(chemins: Chemins) -> None:
    with pytest.raises(ErreurEchange, match="candidatures"):
        decisions(chemins, {"autre": []})
    resultat = appeler(chemins, "decisions", {"candidatures": "pas un tableau"})
    assert resultat.is_error
    assert statut(chemins) == "notee"


@pytest.mark.spec("ECH-24")
def test_la_base_reste_libre_entre_deux_appels(chemins: Chemins) -> None:
    propositions(chemins)
    decisions(chemins, {"candidatures": [page("acceptee")]})
    # A terminal command can write right after: no lock is left behind.
    with BaseLocale(chemins.base) as base:
        assert base.appliquer_decision(OFFRE.cle, "refusee")


@pytest.mark.spec("ECH-25")
def test_les_outils_n_appellent_jamais_claude(
    chemins: Chemins, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interdit(*_: object, **__: object) -> None:
        raise AssertionError("Claude must not be called")

    monkeypatch.setattr("moteur.claude_cli.ClaudeCli.demander", interdit)
    monkeypatch.setattr("moteur.generation.generer", interdit)
    propositions(chemins)
    decisions(chemins, {"candidatures": [page("acceptee")]})
    assert statut(chemins) == "acceptee"
