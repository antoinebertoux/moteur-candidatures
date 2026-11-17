import json
from collections.abc import Sequence

import pytest

from moteur.claude_cli import (
    ClaudeCli,
    ErreurClaude,
    ResultatProcessus,
    extraire_bloc,
    extraire_json,
)


def cli(
    resultat: ResultatProcessus, appels: list[tuple[list[str], str]] | None = None
) -> ClaudeCli:
    def executeur(commande: Sequence[str], entree: str) -> ResultatProcessus:
        if appels is not None:
            appels.append((list(commande), entree))
        return resultat

    return ClaudeCli(executeur)


def test_demander_passe_le_prompt_sur_l_entree_et_coupe_les_outils() -> None:
    appels: list[tuple[list[str], str]] = []
    sortie = json.dumps({"result": "Bonjour", "is_error": False})
    reponse = cli(ResultatProcessus(0, sortie), appels).demander(
        "question", systeme="consignes", modele="haiku"
    )
    assert reponse == "Bonjour"
    ((commande, entree),) = appels
    assert entree == "question"
    assert commande[:2] == ["claude", "-p"]
    assert commande[commande.index("--model") + 1] == "haiku"
    assert commande[commande.index("--system-prompt") + 1] == "consignes"
    assert commande[commande.index("--tools") + 1] == ""
    assert "--no-session-persistence" in commande


@pytest.mark.parametrize(
    "resultat",
    [
        ResultatProcessus(1, "", "non connecté"),
        ResultatProcessus(0, "pas du json"),
        ResultatProcessus(0, json.dumps({"result": "x", "is_error": True})),
        ResultatProcessus(0, json.dumps({"result": "  "})),
        ResultatProcessus(0, json.dumps(["liste"])),
    ],
)
def test_demander_signale_les_echecs(resultat: ResultatProcessus) -> None:
    with pytest.raises(ErreurClaude):
        cli(resultat).demander("q", systeme="s", modele="haiku")


def test_extraire_bloc() -> None:
    assert extraire_bloc("Voici :\n```latex\n\\documentclass{a}\n```\nFin") == "\\documentclass{a}"
    assert extraire_bloc("  sans bloc ") == "sans bloc"


def test_extraire_json() -> None:
    assert extraire_json('Résultat :\n```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert extraire_json('texte {"a": [1, 2]} texte') == {"a": [1, 2]}
    for invalide in ("rien", "[1, 2", "] ["):
        with pytest.raises(ErreurClaude):
            extraire_json(invalide)
