import pytest

from moteur.collection import add_details
from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.ats import URLS, SourceAts, ads_workable
from moteur.sources.welcomekit import (
    SourceWelcomeKit,
    ads_welcomekit,
    complete_welcomekit,
)
from tests.conftest import FakeClient

HOME_PAGE = """<html><ul class='jobs-list'>
<li class='jobs-list-item'>
<a class="jobs-list-item-link" href="/jobs/ml-engineer_saint-malo"><h3 class='jobs-list-item-title'>
ML Engineer
</h3></a></li>
<li class='jobs-list-item'>
<a class="jobs-list-item-link" href="/jobs/ml-engineer_saint-malo"><h3 class='jobs-list-item-title'>
ML Engineer
</h3></a></li>
<li class='jobs-list-item'>
<a class="jobs-list-item-link" href="/jobs/research-scientist"><h3 class='jobs-list-item-title'>
Research &amp; Scientist</h3></a></li>
<li class='jobs-list-item'>
<a class="jobs-list-item-link" href="/jobs/candidatures-spontanees">
<h3 class='jobs-list-item-title'>
Candidature spontanée</h3></a></li>
<li class='jobs-list-item'>
<a class="jobs-list-item-link" href="/jobs/sans-titre">
<h3 class='jobs-list-item-title'> </h3></a></li>
</ul></html>"""

PAGE = """<html>
<li class='sticky-header-details'><ul><li>
<i class='icon-secondary icon-location'></i>
Paris
</li></ul></li>
<h1 class='main-header-title'>
Senior ML Engineer
</h1>
<div class='main-content job-content text-formated'>
<div class='block block-job-text block-job-about'>
<h2 class='block-title'>About</h2>
<div class='block-content'><p>Chiffrement homomorphe.</p></div>
</div></div>
<div class='main-content job-content text-formated'>
<div class='block block-job-text block-job-description'>
<h2 class='block-title'>Job Description</h2>
<div class='block-content'><p>Construire des mod&egrave;les.</p></div>
</div></div>
<div class='main-content job-content'>
<div class='block block-job-text block-job-apply'>
<h3 class='block-title'>Postuler</h3>
</div></div>
</html>"""


@pytest.mark.spec("SRC-60", "SRC-01", "SRC-02")
def test_ads_from_the_home_page() -> None:
    ads = ads_welcomekit("Exemple", "jobs.exemple.org", HOME_PAGE)
    assert [(o.title, o.location, o.url, o.source) for o in ads] == [
        (
            "ML Engineer",
            "Saint Malo",
            "https://jobs.exemple.org/jobs/ml-engineer_saint-malo",
            "welcomekit",
        ),
        (
            "Research & Scientist",
            "",
            "https://jobs.exemple.org/jobs/research-scientist",
            "welcomekit",
        ),
    ]
    assert ads_welcomekit("Exemple", "jobs.exemple.org", "pas du html") == []


@pytest.mark.spec("SRC-60")
def test_source_reads_the_home_page() -> None:
    client = FakeClient({"https://jobs.exemple.org/": HOME_PAGE})
    target = TargetCompany(name="Exemple", ats="welcomekit", identifier="https://jobs.exemple.org/")
    source = SourceWelcomeKit(client, target)
    assert len(source.collect()) == 2
    assert source.name == "welcomekit:Exemple"


@pytest.mark.spec("SRC-61", "SRC-02")
def test_the_page_gives_title_location_and_text() -> None:
    ad = JobAd("Exemple", "ML Engineer", location="Saint Malo", url="u", source="welcomekit")
    complete = complete_welcomekit(ad, PAGE)
    assert (complete.title, complete.location) == ("Senior ML Engineer", "Paris")
    assert complete.description == (
        "About Chiffrement homomorphe. Job Description Construire des modèles."
    )
    assert complete_welcomekit(ad, "<html></html>") == ad


@pytest.mark.spec("SRC-61")
def test_only_retained_ads_are_opened() -> None:
    url = "https://jobs.exemple.org/jobs/ml-engineer_paris"
    client = FakeClient({url: PAGE})
    source = SourceWelcomeKit(client, TargetCompany(name="Exemple", identifier="jobs.exemple.org"))
    (ad,) = add_details([JobAd("Exemple", "ML Engineer", url=url, source="welcomekit")], [source])
    assert ad.title == "Senior ML Engineer"
    assert [u for u, _ in client.calls] == [url]


WORKABLE_RESPONSE = {
    "name": "Exemple",
    "jobs": [
        {
            "title": "AI Researcher",
            "url": "https://apply.workable.com/j/ABC",
            "city": "",
            "country": "",
            "telecommuting": True,
            "published_on": "2026-11-02",
            "description": "<p>Tester des agents &amp; mod&egrave;les.</p>",
            "locations": [{"city": "Paris", "country": "France"}],
        },
        {"title": "Office Manager", "city": "Lyon", "country": "France", "telecommuting": False},
        {"title": "", "url": "x"},
        "pas un objet",
    ],
}


@pytest.mark.spec("SRC-32", "SRC-31", "SRC-01", "SRC-02")
def test_workable_ads() -> None:
    ads = ads_workable("Exemple", WORKABLE_RESPONSE)
    assert [(o.title, o.location, o.source) for o in ads] == [
        ("AI Researcher", "Paris, France, Remote", "workable"),
        ("Office Manager", "Lyon, France", "workable"),
    ]
    assert ads[0].url == "https://apply.workable.com/j/ABC"
    assert ads[0].description == "Tester des agents & modèles."
    assert ads[0].published_on == "2026-11-02"
    assert ads_workable("Exemple", None) == []


@pytest.mark.spec("SRC-30")
def test_workable_source_queries_the_widget() -> None:
    url = URLS["workable"].format(id="exemple")
    client = FakeClient({url: WORKABLE_RESPONSE})
    source = SourceAts(client, TargetCompany(name="Exemple", ats="workable", identifier="exemple"))
    assert len(source.collect()) == 2
    assert client.calls == [(url, {"details": "true"})]
