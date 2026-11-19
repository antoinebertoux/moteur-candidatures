import threading
from collections.abc import Mapping
from typing import Any

import pytest

from moteur.config import EntrepriseCible
from moteur.sources.ats import (
    URLS,
    SourceAts,
    offres_recruitee,
    offres_smartrecruiters,
    offres_teamtailor,
)
from moteur.sources.workday import SourceWorkday, decouper, offres_workday, workday_description
from tests.conftest import FauxClient

EXEMPLE = "https://exemple.wd3.myworkdayjobs.com/fr-FR/Careers"


@pytest.mark.spec("SRC-40")
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


@pytest.mark.spec("SRC-41")
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


class ClientWorkday(FauxClient):
    """Répond selon le mot-clé et la position, quel que soit l'ordre des appels."""

    def __init__(
        self,
        pages: dict[tuple[str, int], dict[str, object]],
        barrage: threading.Barrier | None = None,
    ) -> None:
        super().__init__({})
        self.pages = pages
        self.barrage = barrage

    def post_json(
        self, url: str, *, corps: Mapping[str, Any], entetes: Mapping[str, str] | None = None
    ) -> Any:
        self.appels.append((url, dict(corps)))
        if self.barrage is not None and corps["offset"] == 0:
            self.barrage.wait()  # échoue si les mots-clés passent l'un après l'autre
        return self.pages.get((corps["searchText"], corps["offset"]))


@pytest.mark.spec("SRC-41")
def test_workday_pagine_et_dedoublonne() -> None:
    # Total annoncé sur la première page seulement, comme le fait Workday.
    client = ClientWorkday(
        {("ia", 0): _page(0, 20, 25), ("ia", 20): _page(20, 5, 0), ("data", 0): _page(0, 3, 3)}
    )
    cible = EntrepriseCible(
        nom="Exemple", ats="workday", identifiant=EXEMPLE, recherches=("ia", "data")
    )
    source = SourceWorkday(client, cible)
    offres = source.collecter()
    assert len(offres) == 25  # les 3 offres de « data » sont déjà vues
    assert sorted((c["searchText"], c["offset"]) for _, c in client.appels) == [
        ("data", 0),
        ("ia", 0),
        ("ia", 20),
    ]
    assert source.nom == "workday:Exemple"


@pytest.mark.spec("SRC-05")
def test_workday_lance_les_mots_cles_en_parallele_et_garde_leur_ordre() -> None:
    client = ClientWorkday(
        {("ia", 0): _page(0, 2, 2), ("data", 0): _page(1, 2, 2)}, threading.Barrier(2, timeout=5)
    )
    cible = EntrepriseCible(
        nom="Exemple", ats="workday", identifiant=EXEMPLE, recherches=("ia", "data")
    )
    offres = SourceWorkday(client, cible).collecter()
    assert [o.poste for o in offres] == ["Poste 0", "Poste 1", "Poste 2"]


@pytest.mark.spec("SRC-42")
def test_workday_opens_the_detail_page_of_a_retained_ad() -> None:
    detail = "https://exemple.wd3.myworkdayjobs.com/wday/cxs/exemple/Careers/job/Paris/IA_R001"
    client = FauxClient(
        {detail: {"jobPostingInfo": {"jobDescription": "<p>Missions &amp; profil</p>"}}}
    )
    cible = EntrepriseCible(nom="Exemple", ats="workday", identifiant=EXEMPLE)
    (offre,) = offres_workday(
        "Exemple",
        decouper(EXEMPLE),
        {"jobPostings": [{"title": "IA", "externalPath": "/job/Paris/IA_R001"}]},
    )
    detaillee = SourceWorkday(client, cible).detailler(offre)
    assert detaillee.description == "Missions & profil"
    assert client.appels[0][0] == detail


@pytest.mark.spec("SRC-42")
def test_workday_unreadable_or_foreign_detail_leaves_no_text() -> None:
    assert workday_description(None) == ""
    assert workday_description({"jobPostingInfo": "?"}) == ""
    client = FauxClient({})
    cible = EntrepriseCible(nom="Exemple", ats="workday", identifiant=EXEMPLE)
    source = SourceWorkday(client, cible)
    (offre,) = offres_workday(
        "Exemple", decouper(EXEMPLE), {"jobPostings": [{"title": "IA", "externalPath": "/job/1"}]}
    )
    assert source.detailler(offre).description == ""
    from dataclasses import replace

    etrangere = replace(offre, url="https://ailleurs.fr/offre/1")
    assert source.detailler(etrangere) is etrangere
    assert len(client.appels) == 1


@pytest.mark.spec("SRC-31")
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


@pytest.mark.spec("SRC-31")
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


@pytest.mark.spec("SRC-31")
def test_teamtailor() -> None:
    (offre,) = offres_teamtailor("Acme", FLUX)
    assert (offre.poste, offre.lieu, offre.url) == (
        "AI Engineer",
        "Paris",
        "https://acme.teamtailor.com/jobs/1-ai-engineer",
    )
    assert (offre.description, offre.date_publication) == ("Agents LLM", "2026-11-10")
    assert offres_teamtailor("Acme", "pas du xml") == []


@pytest.mark.spec("SRC-30")
def test_source_ats_teamtailor_lit_le_flux_rss() -> None:
    url = URLS["teamtailor"].format(id="acme")
    client = FauxClient({url: FLUX})
    cible = EntrepriseCible(nom="Acme", ats="teamtailor", identifiant="acme")
    assert [o.poste for o in SourceAts(client, cible).collecter()] == ["AI Engineer"]
    assert client.appels == [(url, {})]


@pytest.mark.spec("SRC-30")
def test_source_ats_smartrecruiters_appelle_la_bonne_adresse() -> None:
    url = URLS["smartrecruiters"].format(id="Acme1")
    client = FauxClient({url: {"content": [{"id": "1", "name": "ML Engineer"}]}})
    cible = EntrepriseCible(nom="Acme", ats="smartrecruiters", identifiant="Acme1")
    assert [o.poste for o in SourceAts(client, cible).collecter()] == ["ML Engineer"]
    assert client.appels == [(url, {"limit": "100"})]
