import pytest

from moteur.config import EntrepriseCible
from moteur.sources import france_travail
from moteur.sources.ats import URLS, SourceAts, offres_ashby, offres_greenhouse, offres_lever
from moteur.sources.base import ErreurSource, texte_brut
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


def test_texte_brut_retire_le_html_echappe() -> None:
    assert texte_brut("&lt;p&gt;Bonjour &amp;amp; <b>bienvenue</b>&lt;/p&gt;") == (
        "Bonjour & bienvenue"
    )


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


def test_resultat_france_travail_incomplet() -> None:
    assert offre_depuis_resultat({"id": "1"}) is None
    offre = offre_depuis_resultat({"id": "9", "intitule": "Ingénieur IA"})
    assert offre is not None
    assert offre.entreprise == "Entreprise non précisée"
    assert offre.url.endswith("/9")


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


def test_france_travail_sans_resultat_ni_jeton() -> None:
    vide = FauxClient({france_travail.URL_JETON: {"access_token": "jeton"}})
    assert SourceFranceTravail(vide, "id", "secret", ["ia"]).collecter() == []
    with pytest.raises(ErreurSource):
        SourceFranceTravail(FauxClient({}), "id", "secret", ["ia"]).collecter()


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


def test_ashby_et_reponses_inattendues() -> None:
    reponse = {"jobs": [{"title": "Head of AI", "location": "Remote", "jobUrl": "https://a/1"}]}
    (offre,) = offres_ashby("Acme", reponse)
    assert (offre.poste, offre.lieu, offre.source) == ("Head of AI", "Remote", "ashby")
    assert offres_ashby("Acme", None) == []
    assert offres_greenhouse("Acme", ["pas un objet"]) == []
    assert offres_lever("Acme", {"pas": "une liste"}) == []


def test_source_ats_appelle_la_bonne_adresse() -> None:
    url = URLS["lever"].format(id="acme")
    client = FauxClient({url: [{"text": "AI Engineer"}]})
    source = SourceAts(client, EntrepriseCible(nom="Acme", ats="lever", identifiant="acme"))
    assert [o.poste for o in source.collecter()] == ["AI Engineer"]
    assert client.appels == [(url, {"mode": "json"})]
    assert source.nom == "lever:Acme"


def test_source_ats_refuse_une_entreprise_sans_ats() -> None:
    with pytest.raises(ValueError, match="ATS"):
        SourceAts(FauxClient({}), EntrepriseCible(nom="Acme"))
