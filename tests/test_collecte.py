from dataclasses import replace
from pathlib import Path

import pytest

from moteur.collecte import (
    collecter,
    detailler,
    entreprises_deja_vues,
    interroger,
    spontanees,
)
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


@pytest.mark.spec("COL-04")
def test_entreprises_deja_vues(tmp_path: Path) -> None:
    fichier = tmp_path / "entreprises_vues.csv"
    fichier.write_text(
        "entreprise;site;statut\nGrand Groupe;;envoyee\nÉté Labs;;refusee\n", encoding="utf-8"
    )
    assert entreprises_deja_vues(fichier) == {"grand-groupe", "ete-labs"}
    assert entreprises_deja_vues(tmp_path / "absent.csv") == set()


@pytest.mark.spec("COL-04")
def test_entreprises_deja_vues_ignore_l_historique(tmp_path: Path) -> None:
    fichier = tmp_path / "entreprises_vues.csv"
    fichier.write_text(
        "entreprise;statut (proposee/refusee);commentaire\n"
        "Ancienne;candidature envoyee (historique);\n"
        "Acme;refusee;\n",
        encoding="utf-8",
    )
    assert entreprises_deja_vues(fichier) == {"acme"}


@pytest.mark.spec("COL-01")
def test_une_source_en_panne_n_arrete_pas_les_autres() -> None:
    offre = Offre("Acme", "Data Scientist")
    assert interroger([SourceFixe("a"), SourceFixe("b", [offre])]) == [offre]


@pytest.mark.spec("COL-03")
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


@pytest.mark.spec("COL-02")
def test_collecter_filtre_puis_ajoute_les_spontanees() -> None:
    source = SourceFixe(
        "a", [Offre("Acme", "Data Scientist", lieu="Paris"), Offre("Acme", "Commercial")]
    )
    cibles = [EntrepriseCible(nom="Libre", spontanee=True)]
    resultat = collecter([source], criteres(), cibles, set(), "Lead AI")
    assert [(o.entreprise, o.type) for o in resultat] == [("Acme", "offre"), ("Libre", "spontanee")]


class SourceDetailleeFixe(SourceFixe):
    def __init__(self, nom: str, en_panne: str = "") -> None:
        super().__init__(nom, [])
        self.ouvertes: list[str] = []
        self._en_panne = en_panne

    def detailler(self, offre: Offre) -> Offre:
        self.ouvertes.append(offre.url)
        if offre.url == self._en_panne:
            raise ErreurSource("HTTP 500")
        return replace(offre, description=f"Texte de {offre.url}")


@pytest.mark.spec("COL-02")
def test_detailler_ne_complete_que_les_offres_sans_texte_de_la_source() -> None:
    source = SourceDetailleeFixe("service_public", en_panne="c")
    offres = [
        Offre("A", "Data scientist", url="a", source="service_public"),
        Offre("B", "Data scientist", url="b", source="service_public", description="Déjà là"),
        Offre("C", "Data scientist", url="c", source="service_public"),
        Offre("D", "Data scientist", url="d", source="ats"),
    ]
    resultat = detailler(offres, [source, SourceFixe("ats", [])])
    assert [o.description for o in resultat] == ["Texte de a", "Déjà là", "", ""]
    assert source.ouvertes == ["a", "c"]
