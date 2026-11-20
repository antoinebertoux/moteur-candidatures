import httpx
import pytest

from moteur.config import TargetCompany
from moteur.sources import france_travail
from moteur.sources.ats import URLS, SourceAts, ads_ashby, ads_greenhouse, ads_lever
from moteur.sources.base import HttpxClient, SourceError, plain_text
from moteur.sources.france_travail import SourceFranceTravail, ad_from_result
from tests.conftest import FakeClient

RESULT = {
    "id": "123ABC",
    "intitule": "Data Scientist (H/F)",
    "description": "Vous concevez des modèles.",
    "dateCreation": "2026-11-10T08:00:00.000Z",
    "lieuTravail": {"libelle": "75 - PARIS 14"},
    "entreprise": {"nom": "Acme"},
    "salaire": {"libelle": "Annuel de 60000.0 Euros à 70000.0 Euros sur 12.0 mois"},
    "origineOffre": {"urlOrigine": "https://exemple.fr/offre/123ABC"},
}


@pytest.mark.spec("SRC-02")
def test_plain_text_removes_escaped_html() -> None:
    assert plain_text("&lt;p&gt;Bonjour &amp;amp; <b>bienvenue</b>&lt;/p&gt;") == (
        "Bonjour & bienvenue"
    )


@pytest.mark.spec("SRC-12")
def test_france_travail_result() -> None:
    ad = ad_from_result(RESULT)
    assert ad is not None
    assert (ad.company, ad.title, ad.location) == (
        "Acme",
        "Data Scientist (H/F)",
        "75 - PARIS 14",
    )
    assert ad.url == "https://exemple.fr/offre/123ABC"
    assert ad.published_on == "2026-11-10"
    assert ad.source == "france_travail"


@pytest.mark.spec("SRC-01", "SRC-12")
def test_incomplete_france_travail_result() -> None:
    assert ad_from_result({"id": "1"}) is None
    ad = ad_from_result({"id": "9", "intitule": "Ingénieur IA"})
    assert ad is not None
    assert ad.company == "Entreprise non précisée"
    assert ad.url.endswith("/9")


@pytest.mark.spec("SRC-11")
def test_france_travail_gets_a_token_then_searches() -> None:
    client = FakeClient(
        {
            france_travail.TOKEN_URL: {"access_token": "jeton"},
            france_travail.SEARCH_URL: {"resultats": [RESULT, {"id": "sans intitulé"}]},
        }
    )
    source = SourceFranceTravail(client, "id", "secret", ["ia", "data"], ["75", "92"])
    assert len(source.collect()) == 4
    searches = [params for url, params in client.calls if url == france_travail.SEARCH_URL]
    assert {(p["motsCles"], p["departement"]) for p in searches} == {
        ("ia", "75"),
        ("ia", "92"),
        ("data", "75"),
        ("data", "92"),
    }


@pytest.mark.spec("SRC-11")
def test_france_travail_without_result_or_token() -> None:
    empty = FakeClient({france_travail.TOKEN_URL: {"access_token": "jeton"}})
    assert SourceFranceTravail(empty, "id", "secret", ["ia"]).collect() == []
    with pytest.raises(SourceError):
        SourceFranceTravail(FakeClient({}), "id", "secret", ["ia"]).collect()


@pytest.mark.spec("SRC-31")
def test_greenhouse() -> None:
    answer = {
        "jobs": [
            {
                "title": "ML Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                "location": {"name": "Paris"},
                "content": "&lt;p&gt;Build models&lt;/p&gt;",
                "updated_at": "2026-11-01T10:00:00-04:00",
            },
            {"title": ""},
        ]
    }
    (ad,) = ads_greenhouse("Acme", answer)
    assert (ad.title, ad.location, ad.description) == ("ML Engineer", "Paris", "Build models")
    assert ad.published_on == "2026-11-01"


@pytest.mark.spec("SRC-31")
def test_lever() -> None:
    answer = [
        {
            "text": "AI Engineer",
            "hostedUrl": "https://jobs.lever.co/acme/1",
            "categories": {"location": "Paris"},
            "descriptionPlain": "Ship LLM features",
        }
    ]
    (ad,) = ads_lever("Acme", answer)
    assert (ad.title, ad.location, ad.url) == (
        "AI Engineer",
        "Paris",
        "https://jobs.lever.co/acme/1",
    )


@pytest.mark.spec("SRC-01", "SRC-31")
def test_ashby_et_reponses_inattendues() -> None:
    answer = {"jobs": [{"title": "Head of AI", "location": "Remote", "jobUrl": "https://a/1"}]}
    (ad,) = ads_ashby("Acme", answer)
    assert (ad.title, ad.location, ad.source) == ("Head of AI", "Remote", "ashby")
    assert ads_ashby("Acme", None) == []
    assert ads_greenhouse("Acme", ["pas un objet"]) == []
    assert ads_lever("Acme", {"pas": "une liste"}) == []


@pytest.mark.spec("SRC-30")
def test_ats_source_calls_the_right_address() -> None:
    url = URLS["lever"].format(id="acme")
    client = FakeClient({url: [{"text": "AI Engineer"}]})
    source = SourceAts(client, TargetCompany(name="Acme", ats="lever", identifier="acme"))
    assert [o.title for o in source.collect()] == ["AI Engineer"]
    assert client.calls == [(url, {"mode": "json"})]
    assert source.name == "lever:Acme"


@pytest.mark.spec("SRC-30")
def test_ats_source_rejects_company_without_ats() -> None:
    with pytest.raises(ValueError, match="ATS"):
        SourceAts(FakeClient({}), TargetCompany(name="Acme"))


def _answering_client(*statuses: tuple[int, dict[str, str]]) -> tuple[HttpxClient, list[float]]:
    """Client whose server answers the given statuses in turn; also returns the pauses."""
    answers = iter(statuses)
    pauses: list[float] = []

    def answer_with(query: httpx.Request) -> httpx.Response:
        status, headers = next(answers)
        return httpx.Response(status, headers=headers, json={"ok": status})

    client = HttpxClient(transport=httpx.MockTransport(answer_with), pause=pauses.append)
    return client, pauses


@pytest.mark.spec("SRC-04")
def test_a_429_is_retried_after_the_requested_delay() -> None:
    client, pauses = _answering_client((429, {"Retry-After": "120"}), (429, {}), (200, {}))
    assert client.post_json("https://exemple.test/jobs", body={}) == {"ok": 200}
    assert pauses == [30.0, 5.0]


@pytest.mark.spec("SRC-04")
def test_three_429_in_a_row_make_a_source_error() -> None:
    client, pauses = _answering_client((429, {}), (429, {"Retry-After": "2"}), (429, {}))
    with pytest.raises(SourceError, match="HTTP 429"):
        client.get_json("https://exemple.test/jobs")
    assert pauses == [5.0, 2.0]


@pytest.mark.spec("SRC-06")
def test_a_server_error_is_retried_once() -> None:
    client, pauses = _answering_client((500, {}), (200, {}))
    assert client.post_json("https://exemple.test/jobs", body={}) == {"ok": 200}
    assert pauses == [2.0]


@pytest.mark.spec("SRC-06")
def test_two_server_errors_make_a_source_error() -> None:
    client, pauses = _answering_client((502, {}), (503, {}))
    with pytest.raises(SourceError, match="HTTP 503"):
        client.get_text("https://exemple.test/page")
    assert pauses == [2.0]


@pytest.mark.spec("SRC-33")
def test_greenhouse_board_hosted_in_europe() -> None:
    url = "https://boards-api.eu.greenhouse.io/v1/boards/sifflet/jobs"
    client = FakeClient({url: {"jobs": [{"title": "ML Engineer", "absolute_url": "https://x"}]}})
    target = TargetCompany(name="Sifflet", ats="greenhouse", identifier="eu:sifflet")
    assert [o.title for o in SourceAts(client, target).collect()] == ["ML Engineer"]
    assert client.calls == [(url, {"content": "true"})]


@pytest.mark.spec("SRC-34")
def test_teamtailor_site_on_the_company_domain() -> None:
    url = "https://careers.pruna.ai/jobs.rss"
    feed = "<rss><channel><item><title>ML Engineer</title><link>https://y</link></item></channel></rss>"
    client = FakeClient({url: feed})
    target = TargetCompany(name="Pruna AI", ats="teamtailor", identifier="careers.pruna.ai")
    assert [o.title for o in SourceAts(client, target).collect()] == ["ML Engineer"]
    assert client.calls[0][0] == url
    plain = TargetCompany(name="Qevlar", ats="teamtailor", identifier="qevlar")
    SourceAts(client, plain).collect()
    assert client.calls[1][0] == "https://qevlar.teamtailor.com/jobs.rss"
