import pytest

from moteur.collecte import detailler
from moteur.config import EntrepriseCible
from moteur.modeles import Offre
from moteur.sources.ats import URLS, SourceAts, offres_workable
from moteur.sources.welcomekit import (
    SourceWelcomeKit,
    completer_welcomekit,
    offres_welcomekit,
)
from tests.conftest import FauxClient

ACCUEIL = """<html><ul class='jobs-list'>
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
def test_offres_de_la_page_d_accueil() -> None:
    offres = offres_welcomekit("Exemple", "jobs.exemple.org", ACCUEIL)
    assert [(o.poste, o.lieu, o.url, o.source) for o in offres] == [
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
    assert offres_welcomekit("Exemple", "jobs.exemple.org", "pas du html") == []


@pytest.mark.spec("SRC-60")
def test_source_lit_la_page_d_accueil() -> None:
    client = FauxClient({"https://jobs.exemple.org/": ACCUEIL})
    cible = EntrepriseCible(
        nom="Exemple", ats="welcomekit", identifiant="https://jobs.exemple.org/"
    )
    source = SourceWelcomeKit(client, cible)
    assert len(source.collecter()) == 2
    assert source.nom == "welcomekit:Exemple"


@pytest.mark.spec("SRC-61", "SRC-02")
def test_la_page_donne_intitule_lieu_et_texte() -> None:
    offre = Offre("Exemple", "ML Engineer", lieu="Saint Malo", url="u", source="welcomekit")
    complete = completer_welcomekit(offre, PAGE)
    assert (complete.poste, complete.lieu) == ("Senior ML Engineer", "Paris")
    assert complete.description == (
        "About Chiffrement homomorphe. Job Description Construire des modèles."
    )
    assert completer_welcomekit(offre, "<html></html>") == offre


@pytest.mark.spec("SRC-61")
def test_seules_les_offres_retenues_sont_ouvertes() -> None:
    url = "https://jobs.exemple.org/jobs/ml-engineer_paris"
    client = FauxClient({url: PAGE})
    source = SourceWelcomeKit(
        client, EntrepriseCible(nom="Exemple", identifiant="jobs.exemple.org")
    )
    (offre,) = detailler([Offre("Exemple", "ML Engineer", url=url, source="welcomekit")], [source])
    assert offre.poste == "Senior ML Engineer"
    assert [u for u, _ in client.appels] == [url]


REPONSE_WORKABLE = {
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
def test_offres_workable() -> None:
    offres = offres_workable("Exemple", REPONSE_WORKABLE)
    assert [(o.poste, o.lieu, o.source) for o in offres] == [
        ("AI Researcher", "Paris, France, Remote", "workable"),
        ("Office Manager", "Lyon, France", "workable"),
    ]
    assert offres[0].url == "https://apply.workable.com/j/ABC"
    assert offres[0].description == "Tester des agents & modèles."
    assert offres[0].date_publication == "2026-11-02"
    assert offres_workable("Exemple", None) == []


@pytest.mark.spec("SRC-30")
def test_source_workable_interroge_le_widget() -> None:
    url = URLS["workable"].format(id="exemple")
    client = FauxClient({url: REPONSE_WORKABLE})
    source = SourceAts(
        client, EntrepriseCible(nom="Exemple", ats="workable", identifiant="exemple")
    )
    assert len(source.collecter()) == 2
    assert client.appels == [(url, {"details": "true"})]
