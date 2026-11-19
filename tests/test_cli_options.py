from pathlib import Path

import pytest

from moteur.cli import lire_options


@pytest.mark.spec("CLI-02")
def test_verbeux_avant_ou_apres_la_commande() -> None:
    assert lire_options(["-v", "quotidien"]).verbeux
    assert lire_options(["quotidien", "-v"]).verbeux
    assert not lire_options(["quotidien"]).verbeux


@pytest.mark.spec("CLI-02")
def test_config_par_defaut_et_apres_la_commande() -> None:
    assert lire_options(["collecter"]).config == Path("config.toml")
    assert lire_options(["collecter", "--config", "x.toml"]).config == Path("x.toml")
    options = lire_options(["decisions", "export.json", "-v"])
    assert options.fichier == Path("export.json") and options.verbeux
