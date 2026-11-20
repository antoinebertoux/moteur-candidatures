import pytest

from moteur.filtering import filter_ads, matches, max_annual_salary
from moteur.models import JobAd
from tests.conftest import criteria


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Annuel de 45000.0 Euros à 55000.0 Euros sur 12.0 mois", 55000),
        ("Annuel de 70000,00 Euros", 70000),
        ("Mensuel de 3500.0 Euros sur 13.0 mois", 45500),
        ("Mensuel de 4000 Euros à 5000 Euros", 60000),
        ("Horaire de 15.0 Euros", None),
        ("Selon profil", None),
        ("", None),
    ],
)
@pytest.mark.spec("FILT-04")
def test_max_annual_salary(label: str, expected: int | None) -> None:
    assert max_annual_salary(label) == expected


@pytest.mark.spec("FILT-01")
def test_keeps_a_matching_ad() -> None:
    assert matches(JobAd("Acme", "Data Scientist senior", location="75 - PARIS 14"), criteria())


@pytest.mark.spec("FILT-01")
def test_rejects_without_keyword() -> None:
    assert not matches(JobAd("Acme", "Commercial", location="Paris"), criteria())


@pytest.mark.spec("FILT-02")
def test_rejects_an_exclusion() -> None:
    assert not matches(JobAd("Acme", "Stage Data Scientist", location="Paris"), criteria())


@pytest.mark.spec("FILT-03")
def test_rejects_another_location_but_keeps_unknown_location() -> None:
    assert not matches(JobAd("Acme", "Data Scientist", location="Marseille"), criteria())
    assert matches(JobAd("Acme", "Data Scientist"), criteria())


@pytest.mark.spec("FILT-04")
def test_salary_rejects_only_if_shown_maximum_too_low() -> None:
    rules = criteria(salary_floor=55000)
    low = JobAd("Acme", "Data Scientist", salary="Annuel de 40000 Euros à 50000 Euros")
    high = JobAd("Acme", "Data Scientist", salary="Annuel de 60000 Euros à 75000 Euros")
    inconnu = JobAd("Acme", "Data Scientist", salary="Selon profil")
    assert [matches(o, rules) for o in (low, high, inconnu)] == [False, True, True]


@pytest.mark.spec("FILT-05")
def test_filter_removes_duplicates() -> None:
    ads = [
        JobAd("Acme", "Data Scientist", url="a"),
        JobAd("ACME", "data scientist", url="b"),
        JobAd("Acme", "Commercial"),
    ]
    assert [o.url for o in filter_ads(ads, criteria())] == ["a"]
