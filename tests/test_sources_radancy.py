import json

import pytest

from moteur.collection import add_details
from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.radancy import SourceRadancy, ads_radancy, complete_radancy
from tests.conftest import FakeClient

PLAN = """﻿<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://careers.exemple.com</loc></url>
<url><loc>https://careers.exemple.com/en/category/data-jobs/49841/9442000/1</loc></url>
<url><loc>https://careers.exemple.com/en/job/new-york/lead-data-scientist/49841/1001</loc></url>
<url><loc>https://careers.exemple.com/en/job/paris/ai-engineer/49841/1002</loc></url>
<url><loc>https://careers.exemple.com/en/job/incomplete/49841</loc></url>
</urlset>"""


@pytest.mark.spec("SRC-50", "SRC-01")
def test_ads_taken_from_the_sitemap() -> None:
    ads = ads_radancy("Exemple", PLAN)
    assert [(o.title, o.location, o.source) for o in ads] == [
        ("Lead Data Scientist", "New York", "radancy"),
        ("Ai Engineer", "Paris", "radancy"),
    ]
    assert ads[1].url == "https://careers.exemple.com/en/job/paris/ai-engineer/49841/1002"
    assert ads_radancy("Exemple", "pas du xml") == []


@pytest.mark.spec("SRC-50")
def test_source_reads_the_sitemap() -> None:
    client = FakeClient({"https://careers.exemple.com/sitemap.xml": PLAN})
    target = TargetCompany(name="Exemple", ats="radancy", identifier="careers.exemple.com")
    source = SourceRadancy(client, target)
    assert len(source.collect()) == 2
    assert source.name == "radancy:Exemple"


def _page(data: object) -> str:
    return f'<html><script type="application/ld+json">{json.dumps(data)}</script></html>'


@pytest.mark.spec("SRC-51", "SRC-02")
def test_the_page_gives_title_text_and_date() -> None:
    ad = JobAd("Exemple", "Ai Engineer", url="u", source="radancy")
    page = _page(
        {
            "@type": "JobPosting",
            "title": "AI Engineer",
            "description": "<p>Construire des mod&egrave;les.</p>",
            "datePosted": "2026-10-19",
        }
    )
    complete = complete_radancy(ad, page)
    assert (complete.title, complete.description, complete.published_on) == (
        "AI Engineer",
        "Construire des modèles.",
        "2026-10-19",
    )
    assert complete_radancy(ad, "<html></html>") == ad


@pytest.mark.spec("SRC-51")
def test_only_retained_ads_are_opened() -> None:
    url = "https://careers.exemple.com/en/job/paris/ai-engineer/49841/1002"
    client = FakeClient({url: _page({"@type": "JobPosting", "description": "Texte"})})
    source = SourceRadancy(client, TargetCompany(name="Exemple", identifier="careers.exemple.com"))
    (ad,) = add_details([JobAd("Exemple", "Ai Engineer", url=url, source="radancy")], [source])
    assert ad.description == "Texte"
    assert [u for u, _ in client.calls] == [url]
