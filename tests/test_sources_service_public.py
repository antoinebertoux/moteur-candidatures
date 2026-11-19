from pathlib import Path

import pytest

from moteur.config import ErreurConfig, analyser
from moteur.modeles import Offre
from moteur.sources.service_public import (
    EMPLOYEURS,
    SourceServicePublic,
    adresse,
    date_francaise,
    description_service_public,
    identifiant,
    offres_service_public,
    total_annonce,
)
from tests.conftest import FauxClient


def _carte(
    numero: int, employeur: str = "Direction Générale de la Sécurité Extérieure (DGSE)"
) -> str:
    return f"""
<li class="fr-col-12 item">
<div class="fr-card fr-card--horizontal fr-card--horizontal-tier fr-card--offer">
  <h3 class="fr-card__title">
    <a href="https://choisirleservicepublic.gouv.fr/offre-emploi/offre-{numero}/"
       class="is-same-domain" target="_blank" aria-label="x">
      Ingénieur IA n°{numero} H/F
    </a>
  </h3>
  <ul class="fr-card__desc">
    <li class="fr-icon-map-pin-2-line fr-icon--sm">
      <span class="sr-only">Localisation : </span> Paris <strong>(75)</strong></li>
    <li class="fr-icon-file-line fr-icon--sm">
      <span class="sr-only">Fonction publique : </span> Fonction publique de l'État</li>
    <li class="fr-icon-user-line  fr-icon--sm">
      <span class="sr-only">Employeur : </span> {employeur}</li>
    <li class="fr-icon-calendar-line  fr-icon--sm">En ligne depuis le 1er novembre 2026</li>
  </ul>
</div></li>"""


def _page(debut: int, nombre: int, total: int) -> str:
    cartes = "".join(_carte(i) for i in range(debut, debut + nombre))
    return f'<p><span class="number">{total}</span> offres</p><ul>{cartes}</ul>'


@pytest.mark.spec("SRC-23")
def test_offres_service_public() -> None:
    (offre,) = offres_service_public(_page(7, 1, 1))
    assert offre.poste == "Ingénieur IA n°7 H/F"
    assert offre.entreprise == "Direction Générale de la Sécurité Extérieure (DGSE)"
    assert offre.lieu == "Paris (75)"
    assert offre.url == "https://choisirleservicepublic.gouv.fr/offre-emploi/offre-7/"
    assert (offre.source, offre.date_publication) == ("service_public", "2026-11-01")
    assert offres_service_public("<html></html>") == []


@pytest.mark.spec("SRC-21")
def test_adresse_respecte_l_ordre_des_filtres() -> None:
    assert adresse() == "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/"
    assert adresse("intelligence artificielle", (3522,), (5, 364), page=2) == (
        "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/"
        "mot-cles/intelligence%20artificielle/domaine/3522/organisme/5-364/page/2/"
    )


@pytest.mark.spec("SRC-23")
def test_date_et_total() -> None:
    assert date_francaise("En ligne depuis le 16 février 2026") == "2026-02-16"
    assert date_francaise("En ligne depuis peu") == ""
    assert total_annonce('<span class="number">1 274</span>') == 1274
    assert total_annonce("") is None


@pytest.mark.spec("CONF-05")
def test_identifiant_par_nom_ou_nombre() -> None:
    assert identifiant("dgse", EMPLOYEURS) == 364
    assert identifiant("Ministere des Armees", EMPLOYEURS) == 5
    assert identifiant("12345", EMPLOYEURS) == 12345
    assert identifiant("Inconnu", EMPLOYEURS) is None


@pytest.mark.spec("SRC-20", "SRC-22")
def test_source_pagine_puis_cherche_chez_les_employeurs() -> None:
    general = adresse("ia")
    client = FauxClient(
        {
            general: _page(0, 20, 25),
            adresse("ia", page=2): _page(20, 5, 25),
            adresse("ia", employeurs=(364,)): _page(3, 2, 2),
        }
    )
    source = SourceServicePublic(client, ("ia",), employeurs=(364,), pages_max=5)
    offres = source.collecter()
    assert len(offres) == 25  # les 2 offres de la DGSE sont déjà vues
    assert [url for url, _ in client.appels] == [
        general,
        adresse("ia", page=2),
        adresse("ia", employeurs=(364,)),
    ]
    assert source.nom == "service_public"


@pytest.mark.spec("SRC-22")
def test_source_s_arrete_a_pages_max() -> None:
    client = FauxClient({adresse("ia"): _page(0, 20, 500)})
    SourceServicePublic(client, ("ia",), pages_max=1).collecter()
    assert len(client.appels) == 1


@pytest.mark.spec("CONF-05")
def test_config_service_public() -> None:
    donnees = {
        "service_public": {
            "actif": True,
            "recherches": ["IA"],
            "domaines": ["Numérique", 3525],
            "employeurs": ["DGSE", "DGSI", "14524"],
        }
    }
    service_public = analyser(donnees, Path()).service_public
    assert service_public.actif
    assert service_public.domaines == (3522, 3525)
    assert service_public.employeurs == (364, 13502, 14524)
    assert service_public.pages_max == 3
    with pytest.raises(ErreurConfig):
        analyser({"service_public": {"employeurs": ["Inconnu"]}}, Path())
    with pytest.raises(ErreurConfig):
        analyser({"service_public": {"pages_max": 0}}, Path())


# Extrait réel (raccourci) d'une page d'offre, relevé le 17/11/2026.
PAGE_OFFRE = """<main class="dsfr main-content-single-offer">
<div class="strate-hero-offer"><h1>TRACFIN - Data scientist H/F</h1></div>
<div class="strate-two-columns fr-pt-3w bg-color--white"><div class="fr-container">
<div class="fr-grid-row fr-grid-row--gutters">
<div class="fr-col-12 fr-col-md-12 fr-col-lg-6 fr-col-offset-lg-2  col-left rte">
  <h2>Vos missions en quelques mots</h2>
  <div data-module="components/clamp">
    <div class="text-clamp--text fr-mb-3w"><p>Le pôle data valorise les données du service.<br>
    Il détecte des phénomènes d&rsquo;intérêt&nbsp;:</p></div>
    <button class="text-clamp--cta btnlink fr-link">Afficher la suite</button>
    <div class="text-clamp--hiddentext" hidden=""><p><br> • Gestion de projet <br> • Prototypage</p>
    </div>
  </div>
  <h2 class="fr-mt-8w">Profil recherché</h2>
  <div data-module="components/clamp">
    <div class="text-clamp--text"><p>Bac+5 en data science.</p></div>
  </div>
  <div class="block-table"><h3>Niveau d'études minimum requis</h3><ul><li>Niveau 7</li></ul></div>
  <div class="block-cards"><h2 class="fr-mb-5w">Éléments de candidature</h2></div>
</div></div></div></div>
<div class="strate-two-columns about-agency">
<div class="fr-grid-row rte"><p>Qui sommes-nous</p></div></div>
</main>"""


@pytest.mark.spec("SRC-24")
def test_description_service_public() -> None:
    assert description_service_public(PAGE_OFFRE) == (
        "Vos missions en quelques mots\n"
        "Le pôle data valorise les données du service.\n"
        "Il détecte des phénomènes d’intérêt :\n"
        "• Gestion de projet\n"
        "• Prototypage\n"
        "Profil recherché\n"
        "Bac+5 en data science."
    )
    assert description_service_public("<html>page inattendue</html>") == ""


@pytest.mark.spec("SRC-24")
def test_detailler_ouvre_la_page_de_l_offre() -> None:
    url = "https://choisirleservicepublic.gouv.fr/offre-emploi/tracfin/"
    client = FauxClient({url: PAGE_OFFRE})
    source = SourceServicePublic(client, ["data"])
    offre = source.detailler(Offre("TRACFIN", "Data scientist", url=url, source="service_public"))
    assert offre.description.startswith("Vos missions en quelques mots")
    assert offre.poste == "Data scientist"
    assert client.appels == [(url, {})]
