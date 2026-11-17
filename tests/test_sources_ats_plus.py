import pytest

from moteur.config import EntrepriseCible
from moteur.sources.ats import (
    URLS,
    SourceAts,
    offres_recruitee,
    offres_smartrecruiters,
    offres_teamtailor,
)
from moteur.sources.workday import SourceWorkday, decouper, offres_workday
from tests.conftest import FauxClient

EXEMPLE = "https://exemple.wd3.myworkdayjobs.com/fr-FR/Careers"


def test_decouper_une_adresse_workday() -> None:
    site = decouper(EXEMPLE)
    assert (site.hote, site.tenant, site.site) == (
        "exemple.wd3.myworkdayjobs.com",
        "exemple",
        "Careers",
    )
    assert site.api == "https://exemple.wd3.myworkdayjobs.com/wday/cxs/exemple/Careers/jobs"
    assert decouper("groupe.wd3.myworkdayjobs.com/Groupe").site == "Groupe"
    with pytest.raises(ValueError):
        decouper("https://exemple.fr/carrieres")


def test_offres_workday() -> None:
    reponse = {
        "total": 1,
        "jobPostings": [
            {
                "title": "Ingénieur IA F/H",
                "externalPath": "/job/Velizy/Ingenieur-IA_R001",
                "locationsText": "Vélizy-Villacoublay",
            },
            {"title": ""},
        ],
    }
    (offre,) = offres_workday("Exemple", decouper(EXEMPLE), reponse)
    assert (offre.poste, offre.lieu, offre.source) == (
        "Ingénieur IA F/H",
        "Vélizy-Villacoublay",
        "workday",
    )
    assert offre.url == "https://exemple.wd3.myworkdayjobs.com/Careers/job/Velizy/Ingenieur-IA_R001"
    assert offres_workday("Exemple", decouper(EXEMPLE), None) == []


def _page(debut: int, nombre: int, total: int) -> dict[str, object]:
    return {
        "total": total,
        "jobPostings": [
            {"title": f"Poste {i}", "externalPath": f"/job/{i}"}
            for i in range(debut, debut + nombre)
        ],
    }


def test_workday_pagine_et_dedoublonne() -> None:
    api = decouper(EXEMPLE).api
    # Total annoncé sur la première page seulement, comme le fait Workday.
    pages = [_page(0, 20, 25), _page(20, 5, 0), _page(0, 3, 3)]
    client = FauxClient({api: pages})
    cible = EntrepriseCible(
        nom="Exemple", ats="workday", identifiant=EXEMPLE, recherches=("ia", "data")
    )
    source = SourceWorkday(client, cible)
    offres = source.collecter()
    assert len(offres) == 25  # les 3 offres de « data » sont déjà vues
    assert [(c["searchText"], c["offset"]) for _, c in client.appels] == [
        ("ia", 0),
        ("ia", 20),
        ("data", 0),
    ]
    assert source.nom == "workday:Exemple"


def test_smartrecruiters() -> None:
    reponse = {
        "content": [
            {
                "id": "744",
                "name": "Data Scientist",
                "releasedDate": "2026-11-02T09:00:00.000Z",
                "location": {"city": "Paris", "country": "fr"},
            },
            {"name": ""},
        ]
    }
    (offre,) = offres_smartrecruiters("Acme", "Acme1", reponse)
    assert (offre.poste, offre.lieu, offre.date_publication) == (
        "Data Scientist",
        "Paris, FR",
        "2026-11-02",
    )
    assert offre.url == "https://jobs.smartrecruiters.com/Acme1/744"


def test_recruitee() -> None:
    reponse = {
        "offers": [
            {
                "title": "Lead AI",
                "location": "Paris, France",
                "careers_url": "https://acme.recruitee.com/o/lead-ai",
                "description": "<p>Diriger l’IA</p>",
                "published_at": "2026-11-05 10:00:00 UTC",
            }
        ]
    }
    (offre,) = offres_recruitee("Acme", reponse)
    assert (offre.poste, offre.description, offre.date_publication) == (
        "Lead AI",
        "Diriger l’IA",
        "2026-11-05",
    )


FLUX = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:tt="https://teamtailor.com/locations">
  <channel>
    <item>
      <title>AI Engineer</title>
      <link>https://acme.teamtailor.com/jobs/1-ai-engineer</link>
      <description>&lt;p&gt;Agents LLM&lt;/p&gt;</description>
      <pubDate>Tue, 10 Nov 2026 08:00:00 +0100</pubDate>
      <tt:locations><tt:location><tt:city>Paris</tt:city></tt:location></tt:locations>
    </item>
    <item><title></title></item>
  </channel>
</rss>"""


def test_teamtailor() -> None:
    (offre,) = offres_teamtailor("Acme", FLUX)
    assert (offre.poste, offre.lieu, offre.url) == (
        "AI Engineer",
        "Paris",
        "https://acme.teamtailor.com/jobs/1-ai-engineer",
    )
    assert (offre.description, offre.date_publication) == ("Agents LLM", "2026-11-10")
    assert offres_teamtailor("Acme", "pas du xml") == []


def test_source_ats_teamtailor_lit_le_flux_rss() -> None:
    url = URLS["teamtailor"].format(id="acme")
    client = FauxClient({url: FLUX})
    cible = EntrepriseCible(nom="Acme", ats="teamtailor", identifiant="acme")
    assert [o.poste for o in SourceAts(client, cible).collecter()] == ["AI Engineer"]
    assert client.appels == [(url, {})]


def test_source_ats_smartrecruiters_appelle_la_bonne_adresse() -> None:
    url = URLS["smartrecruiters"].format(id="Acme1")
    client = FauxClient({url: {"content": [{"id": "1", "name": "ML Engineer"}]}})
    cible = EntrepriseCible(nom="Acme", ats="smartrecruiters", identifiant="Acme1")
    assert [o.poste for o in SourceAts(client, cible).collecter()] == ["ML Engineer"]
    assert client.appels == [(url, {"limit": "100"})]
