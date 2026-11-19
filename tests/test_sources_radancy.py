import json

import pytest

from moteur.collecte import detailler
from moteur.config import EntrepriseCible
from moteur.modeles import Offre
from moteur.sources.radancy import SourceRadancy, completer_radancy, offres_radancy
from tests.conftest import FauxClient

PLAN = """﻿<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://careers.exemple.com</loc></url>
<url><loc>https://careers.exemple.com/en/category/data-jobs/49841/9442000/1</loc></url>
<url><loc>https://careers.exemple.com/en/job/new-york/lead-data-scientist/49841/1001</loc></url>
<url><loc>https://careers.exemple.com/en/job/paris/ai-engineer/49841/1002</loc></url>
<url><loc>https://careers.exemple.com/en/job/incomplete/49841</loc></url>
</urlset>"""


@pytest.mark.spec("SRC-50", "SRC-01")
def test_offres_tirees_du_plan_du_site() -> None:
    offres = offres_radancy("Exemple", PLAN)
    assert [(o.poste, o.lieu, o.source) for o in offres] == [
        ("Lead Data Scientist", "New York", "radancy"),
        ("Ai Engineer", "Paris", "radancy"),
    ]
    assert offres[1].url == "https://careers.exemple.com/en/job/paris/ai-engineer/49841/1002"
    assert offres_radancy("Exemple", "pas du xml") == []


@pytest.mark.spec("SRC-50")
def test_source_lit_le_plan_du_site() -> None:
    client = FauxClient({"https://careers.exemple.com/sitemap.xml": PLAN})
    cible = EntrepriseCible(nom="Exemple", ats="radancy", identifiant="careers.exemple.com")
    source = SourceRadancy(client, cible)
    assert len(source.collecter()) == 2
    assert source.nom == "radancy:Exemple"


def _page(donnees: object) -> str:
    return f'<html><script type="application/ld+json">{json.dumps(donnees)}</script></html>'


@pytest.mark.spec("SRC-51", "SRC-02")
def test_la_page_donne_intitule_texte_et_date() -> None:
    offre = Offre("Exemple", "Ai Engineer", url="u", source="radancy")
    page = _page(
        {
            "@type": "JobPosting",
            "title": "AI Engineer",
            "description": "<p>Construire des mod&egrave;les.</p>",
            "datePosted": "2026-10-19",
        }
    )
    complete = completer_radancy(offre, page)
    assert (complete.poste, complete.description, complete.date_publication) == (
        "AI Engineer",
        "Construire des modèles.",
        "2026-10-19",
    )
    assert completer_radancy(offre, "<html></html>") == offre


@pytest.mark.spec("SRC-51")
def test_seules_les_offres_retenues_sont_ouvertes() -> None:
    url = "https://careers.exemple.com/en/job/paris/ai-engineer/49841/1002"
    client = FauxClient({url: _page({"@type": "JobPosting", "description": "Texte"})})
    source = SourceRadancy(
        client, EntrepriseCible(nom="Exemple", identifiant="careers.exemple.com")
    )
    (offre,) = detailler([Offre("Exemple", "Ai Engineer", url=url, source="radancy")], [source])
    assert offre.description == "Texte"
    assert [u for u, _ in client.appels] == [url]
