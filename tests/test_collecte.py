from pathlib import Path

from moteur.collecte import collecter, entreprises_deja_vues, interroger, spontanees
from moteur.config import EntrepriseCible
from moteur.modeles import Offre
from moteur.sources.base import ErreurSource
from tests.conftest import criteres


class SourceFixe:
    def __init__(self, nom: str, offres: list[Offre] | None = None) -> None:
        self._nom = nom
        self._offres = offres

    @property
    def nom(self) -> str:
        return self._nom

    def collecter(self) -> list[Offre]:
        if self._offres is None:
            raise ErreurSource("en panne")
        return self._offres


def test_entreprises_deja_vues(tmp_path: Path) -> None:
    fichier = tmp_path / "entreprises_vues.csv"
    fichier.write_text(
        "entreprise;site;statut\nGrand Groupe;;envoyee\nÉté Labs;;refusee\n", encoding="utf-8"
    )
    assert entreprises_deja_vues(fichier) == {"grand-groupe", "ete-labs"}
    assert entreprises_deja_vues(tmp_path / "absent.csv") == set()


def test_entreprises_deja_vues_ignore_l_historique(tmp_path: Path) -> None:
    fichier = tmp_path / "entreprises_vues.csv"
    fichier.write_text(
        "entreprise;statut (proposee/refusee);commentaire\n"
        "Ancienne;candidature envoyee (historique);\n"
        "Acme;refusee;\n",
        encoding="utf-8",
    )
    assert entreprises_deja_vues(fichier) == {"acme"}


def test_une_source_en_panne_n_arrete_pas_les_autres() -> None:
    offre = Offre("Acme", "Data Scientist")
    assert interroger([SourceFixe("a"), SourceFixe("b", [offre])]) == [offre]


def test_spontanees_seulement_pour_les_cibles_sans_offre_et_jamais_vues() -> None:
    cibles = [
        EntrepriseCible(nom="Acme", spontanee=True),
        EntrepriseCible(nom="Déjà Vue", spontanee=True),
        EntrepriseCible(nom="Libre", spontanee=True, site="https://libre.io"),
        EntrepriseCible(nom="Sans Spontanée"),
    ]
    resultat = spontanees(cibles, [Offre("ACME", "Data Scientist")], {"deja-vue"}, "Lead AI")
    assert resultat == [
        Offre("Libre", "Lead AI", type="spontanee", url="https://libre.io", source="cible")
    ]


def test_collecter_filtre_puis_ajoute_les_spontanees() -> None:
    source = SourceFixe(
        "a", [Offre("Acme", "Data Scientist", lieu="Paris"), Offre("Acme", "Commercial")]
    )
    cibles = [EntrepriseCible(nom="Libre", spontanee=True)]
    resultat = collecter([source], criteres(), cibles, set(), "Lead AI")
    assert [(o.entreprise, o.type) for o in resultat] == [("Acme", "offre"), ("Libre", "spontanee")]
