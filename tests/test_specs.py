"""Chaque règle de `specs/` est vérifiée par un test, et chaque test cite des règles réelles.

Une règle s'écrit `- **FILT-03** · …` ; un test la cite avec
`@pytest.mark.spec("FILT-03")`. Sont dispensées de test : les règles marquées
« (non testé » et celles de la page et des tâches planifiées, hors de ce dépôt.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SPECS = RACINE / "specs"
HORS_DEPOT = {"page-suivi.md", "taches-claude.md"}
_REGLE = re.compile(r"^- \*\*([A-Z]+-\d{2})\*\*")


def blocs(texte: str) -> list[tuple[str, str]]:
    """(identifiant, texte complet) de chaque règle, lignes de continuation comprises."""
    trouves: list[tuple[str, list[str]]] = []
    for ligne in texte.splitlines():
        debut = _REGLE.match(ligne)
        if debut:
            trouves.append((debut.group(1), [ligne]))
        elif not ligne.strip() or ligne.startswith(("#", "|", "- ")):
            trouves.append(("", []))
        elif trouves and trouves[-1][0]:
            trouves[-1][1].append(ligne)
    return [(regle, " ".join(lignes)) for regle, lignes in trouves if regle]


def regles() -> dict[str, bool]:
    """Identifiant de chaque règle -> vrai si elle doit avoir un test."""
    trouvees: dict[str, bool] = {}
    for fichier in sorted(SPECS.glob("*.md")):
        for regle, texte in blocs(fichier.read_text(encoding="utf-8")):
            assert regle not in trouvees, f"{regle} défini deux fois"
            trouvees[regle] = fichier.name not in HORS_DEPOT and "(non testé" not in texte
    return trouvees


def citations() -> dict[str, set[str]]:
    """Règle -> tests qui la citent par `@pytest.mark.spec(...)`."""
    citees: dict[str, set[str]] = {}
    for fichier in sorted((RACINE / "tests").glob("test_*.py")):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if not isinstance(noeud, ast.FunctionDef):
                continue
            for decorateur in noeud.decorator_list:
                if (
                    isinstance(decorateur, ast.Call)
                    and ast.unparse(decorateur.func) == "pytest.mark.spec"
                ):
                    for argument in decorateur.args:
                        assert isinstance(argument, ast.Constant), noeud.name
                        citees.setdefault(str(argument.value), set()).add(noeud.name)
    return citees


def test_chaque_regle_du_moteur_a_un_test() -> None:
    sans_test = sorted(r for r, a_tester in regles().items() if a_tester and r not in citations())
    assert sans_test == [], f"Règles sans test : {', '.join(sans_test)}"


def test_les_tests_citent_des_regles_existantes() -> None:
    inconnues = sorted(set(citations()) - set(regles()))
    assert inconnues == [], f"Règles citées mais absentes de specs/ : {', '.join(inconnues)}"


def test_les_regles_sont_trouvees() -> None:
    toutes = regles()
    assert {"ID-02", "FILT-04", "PAGE-30", "TACHE-05"} <= set(toutes)
    assert not toutes["PAGE-30"]
    assert not toutes["CV-12"]
    assert toutes["FILT-04"]
