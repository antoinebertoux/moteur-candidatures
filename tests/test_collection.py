import threading
from dataclasses import replace
from pathlib import Path

import pytest

from moteur.collection import (
    add_details,
    collect,
    companies_already_seen,
    query_sources,
    unsolicited_ones,
)
from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import SourceError
from tests.conftest import criteria


class FixedSource:
    def __init__(self, name: str, ads: list[JobAd] | None = None) -> None:
        self._name = name
        self._ads = ads

    @property
    def name(self) -> str:
        return self._name

    def collect(self) -> list[JobAd]:
        if self._ads is None:
            raise SourceError("en panne")
        return self._ads


@pytest.mark.spec("COL-04")
def test_companies_already_seen(tmp_path: Path) -> None:
    file = tmp_path / "entreprises_vues.csv"
    file.write_text(
        "entreprise;site;statut\nGrand Groupe;;envoyee\nÉté Labs;;refusee\n", encoding="utf-8"
    )
    assert companies_already_seen(file) == {"grand-groupe", "ete-labs"}
    assert companies_already_seen(tmp_path / "absent.csv") == set()


@pytest.mark.spec("COL-04")
def test_companies_already_seen_ignore_history(tmp_path: Path) -> None:
    file = tmp_path / "entreprises_vues.csv"
    file.write_text(
        "entreprise;statut (proposee/refusee);commentaire\n"
        "Ancienne;candidature envoyee (historique);\n"
        "Acme;refusee;\n",
        encoding="utf-8",
    )
    assert companies_already_seen(file) == {"acme"}


@pytest.mark.spec("COL-01")
def test_a_broken_source_does_not_stop_the_others() -> None:
    ad = JobAd("Acme", "Data Scientist")
    assert query_sources([FixedSource("a"), FixedSource("b", [ad])]) == [ad]


@pytest.mark.spec("COL-03")
def test_unsolicited_only_for_targets_without_ad_and_never_seen() -> None:
    targets = [
        TargetCompany(name="Acme", unsolicited=True),
        TargetCompany(name="Déjà Vue", unsolicited=True),
        TargetCompany(name="Libre", unsolicited=True, site="https://libre.io"),
        TargetCompany(name="Sans Spontanée"),
    ]
    result = unsolicited_ones(targets, [JobAd("ACME", "Data Scientist")], {"deja-vue"}, "Lead AI")
    assert result == [
        JobAd("Libre", "Lead AI", type="spontanee", url="https://libre.io", source="cible")
    ]


@pytest.mark.spec("COL-02")
def test_collect_filters_then_adds_unsolicited() -> None:
    source = FixedSource(
        "a", [JobAd("Acme", "Data Scientist", location="Paris"), JobAd("Acme", "Commercial")]
    )
    targets = [TargetCompany(name="Libre", unsolicited=True)]
    result = collect([source], criteria(), targets, set(), "Lead AI")
    assert [(o.company, o.type) for o in result] == [("Acme", "offre"), ("Libre", "spontanee")]


class FixedDetailedSource(FixedSource):
    def __init__(self, name: str, broken: str = "") -> None:
        super().__init__(name, [])
        self.opened_ones: list[str] = []
        self._broken = broken

    def add_details(self, ad: JobAd) -> JobAd:
        self.opened_ones.append(ad.url)
        if ad.url == self._broken:
            raise SourceError("HTTP 500")
        return replace(ad, description=f"Texte de {ad.url}")


@pytest.mark.spec("COL-02")
def test_add_details_only_completes_ads_without_source_text() -> None:
    source = FixedDetailedSource("service_public", broken="c")
    ads = [
        JobAd("A", "Data scientist", url="a", source="service_public"),
        JobAd("B", "Data scientist", url="b", source="service_public", description="Déjà là"),
        JobAd("C", "Data scientist", url="c", source="service_public"),
        JobAd("D", "Data scientist", url="d", source="ats"),
    ]
    result = add_details(ads, [source, FixedSource("ats", [])])
    assert [o.description for o in result] == ["Texte de a", "Déjà là", "", ""]
    assert sorted(source.opened_ones) == ["a", "c"]


class WaitingSource(FixedSource):
    """Only answers once every source of the same gate is being queried."""

    def __init__(self, name: str, ads: list[JobAd], gate: threading.Barrier) -> None:
        super().__init__(name, ads)
        self._gate = gate

    def collect(self) -> list[JobAd]:
        self._gate.wait()  # BrokenBarrierError if the sources run one after the other
        return super().collect()


@pytest.mark.spec("COL-07")
def test_query_in_parallel_keeps_source_order() -> None:
    gate = threading.Barrier(3, timeout=5)
    sources = [
        WaitingSource(name, [JobAd(name, "Data Scientist")], gate) for name in ("a", "b", "c")
    ]
    assert [o.company for o in query_sources(sources)] == ["a", "b", "c"]


@pytest.mark.spec("COL-08")
def test_add_details_opens_pages_in_parallel_keeping_order() -> None:
    gate = threading.Barrier(4, timeout=5)

    class Slow(FixedDetailedSource):
        def add_details(self, ad: JobAd) -> JobAd:
            gate.wait()
            return super().add_details(ad)

    ads = [JobAd(x, "Data scientist", url=x, source="service_public") for x in "abcd"]
    result = add_details(ads, [Slow("service_public")])
    assert [o.description for o in result] == [f"Texte de {x}" for x in "abcd"]
