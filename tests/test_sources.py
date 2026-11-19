import httpx
import pytest

from moteur.config import EntrepriseCible
from moteur.sources import france_travail
from moteur.sources.ats import URLS, SourceAts, offres_ashby, offres_greenhouse, offres_lever
from moteur.sources.base import ClientHttpx, ErreurSource, texte_brut
from moteur.sources.france_travail import SourceFranceTravail, offre_depuis_resultat
from tests.conftest import FauxClient

RESULTAT = {
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
def test_texte_brut_retire_le_html_echappe() -> None:
    assert texte_brut("&lt;p&gt;Bonjour &amp;amp; <b>bienvenue</b>&lt;/p&gt;") == (
        "Bonjour & bienvenue"
    )


@pytest.mark.spec("SRC-12")
def test_resultat_france_travail() -> None:
    offre = offre_depuis_resultat(RESULTAT)
    assert offre is not None
    assert (offre.entreprise, offre.poste, offre.lieu) == (
        "Acme",
        "Data Scientist (H/F)",
        "75 - PARIS 14",
    )
    assert offre.url == "https://exemple.fr/offre/123ABC"
    assert offre.date_publication == "2026-11-10"
    assert offre.source == "france_travail"


@pytest.mark.spec("SRC-01", "SRC-12")
def test_resultat_france_travail_incomplet() -> None:
    assert offre_depuis_resultat({"id": "1"}) is None
    offre = offre_depuis_resultat({"id": "9", "intitule": "Ingénieur IA"})
    assert offre is not None
    assert offre.entreprise == "Entreprise non précisée"
    assert offre.url.endswith("/9")


@pytest.mark.spec("SRC-11")
def test_france_travail_demande_un_jeton_puis_cherche() -> None:
    client = FauxClient(
        {
            france_travail.URL_JETON: {"access_token": "jeton"},
            france_travail.URL_RECHERCHE: {"resultats": [RESULTAT, {"id": "sans intitulé"}]},
        }
    )
    source = SourceFranceTravail(client, "id", "secret", ["ia", "data"], ["75", "92"])
    assert len(source.collecter()) == 4
    recherches = [params for url, params in client.appels if url == france_travail.URL_RECHERCHE]
    assert {(p["motsCles"], p["departement"]) for p in recherches} == {
        ("ia", "75"),
        ("ia", "92"),
        ("data", "75"),
        ("data", "92"),
    }


@pytest.mark.spec("SRC-11")
def test_france_travail_sans_resultat_ni_jeton() -> None:
    vide = FauxClient({france_travail.URL_JETON: {"access_token": "jeton"}})
    assert SourceFranceTravail(vide, "id", "secret", ["ia"]).collecter() == []
    with pytest.raises(ErreurSource):
        SourceFranceTravail(FauxClient({}), "id", "secret", ["ia"]).collecter()


@pytest.mark.spec("SRC-31")
def test_greenhouse() -> None:
    reponse = {
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
    (offre,) = offres_greenhouse("Acme", reponse)
    assert (offre.poste, offre.lieu, offre.description) == ("ML Engineer", "Paris", "Build models")
    assert offre.date_publication == "2026-11-01"


@pytest.mark.spec("SRC-31")
def test_lever() -> None:
    reponse = [
        {
            "text": "AI Engineer",
            "hostedUrl": "https://jobs.lever.co/acme/1",
            "categories": {"location": "Paris"},
            "descriptionPlain": "Ship LLM features",
        }
    ]
    (offre,) = offres_lever("Acme", reponse)
    assert (offre.poste, offre.lieu, offre.url) == (
        "AI Engineer",
        "Paris",
        "https://jobs.lever.co/acme/1",
    )


@pytest.mark.spec("SRC-01", "SRC-31")
def test_ashby_et_reponses_inattendues() -> None:
    reponse = {"jobs": [{"title": "Head of AI", "location": "Remote", "jobUrl": "https://a/1"}]}
    (offre,) = offres_ashby("Acme", reponse)
    assert (offre.poste, offre.lieu, offre.source) == ("Head of AI", "Remote", "ashby")
    assert offres_ashby("Acme", None) == []
    assert offres_greenhouse("Acme", ["pas un objet"]) == []
    assert offres_lever("Acme", {"pas": "une liste"}) == []


@pytest.mark.spec("SRC-30")
def test_source_ats_appelle_la_bonne_adresse() -> None:
    url = URLS["lever"].format(id="acme")
    client = FauxClient({url: [{"text": "AI Engineer"}]})
    source = SourceAts(client, EntrepriseCible(nom="Acme", ats="lever", identifiant="acme"))
    assert [o.poste for o in source.collecter()] == ["AI Engineer"]
    assert client.appels == [(url, {"mode": "json"})]
    assert source.nom == "lever:Acme"


@pytest.mark.spec("SRC-30")
def test_source_ats_refuse_une_entreprise_sans_ats() -> None:
    with pytest.raises(ValueError, match="ATS"):
        SourceAts(FauxClient({}), EntrepriseCible(nom="Acme"))


def _client_qui_repond(*statuts: tuple[int, dict[str, str]]) -> tuple[ClientHttpx, list[float]]:
    """Client dont le serveur répond tour à tour les statuts donnés ; renvoie aussi les pauses."""
    reponses = iter(statuts)
    pauses: list[float] = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        statut, entetes = next(reponses)
        return httpx.Response(statut, headers=entetes, json={"ok": statut})

    client = ClientHttpx(transport=httpx.MockTransport(repondre), pause=pauses.append)
    return client, pauses


@pytest.mark.spec("SRC-04")
def test_un_429_est_reessaye_apres_le_delai_demande() -> None:
    client, pauses = _client_qui_repond((429, {"Retry-After": "120"}), (429, {}), (200, {}))
    assert client.post_json("https://exemple.test/jobs", corps={}) == {"ok": 200}
    assert pauses == [30.0, 5.0]


@pytest.mark.spec("SRC-04")
def test_trois_429_de_suite_font_une_erreur_de_source() -> None:
    client, pauses = _client_qui_repond((429, {}), (429, {"Retry-After": "2"}), (429, {}))
    with pytest.raises(ErreurSource, match="HTTP 429"):
        client.get_json("https://exemple.test/jobs")
    assert pauses == [5.0, 2.0]
