from pathlib import Path

import pytest

from moteur.config import ErreurConfig, analyser
from moteur.sources.service_public import (
    EMPLOYEURS,
    SourceServicePublic,
    adresse,
    date_francaise,
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


def test_offres_service_public() -> None:
    (offre,) = offres_service_public(_page(7, 1, 1))
    assert offre.poste == "Ingénieur IA n°7 H/F"
    assert offre.entreprise == "Direction Générale de la Sécurité Extérieure (DGSE)"
    assert offre.lieu == "Paris (75)"
    assert offre.url == "https://choisirleservicepublic.gouv.fr/offre-emploi/offre-7/"
    assert (offre.source, offre.date_publication) == ("service_public", "2026-11-01")
    assert offres_service_public("<html></html>") == []


def test_adresse_respecte_l_ordre_des_filtres() -> None:
    assert adresse() == "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/"
    assert adresse("intelligence artificielle", (3522,), (5, 364), page=2) == (
        "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/"
        "mot-cles/intelligence%20artificielle/domaine/3522/organisme/5-364/page/2/"
    )


def test_date_et_total() -> None:
    assert date_francaise("En ligne depuis le 16 février 2026") == "2026-02-16"
    assert date_francaise("En ligne depuis peu") == ""
    assert total_annonce('<span class="number">1 274</span>') == 1274
    assert total_annonce("") is None


def test_identifiant_par_nom_ou_nombre() -> None:
    assert identifiant("dgse", EMPLOYEURS) == 364
    assert identifiant("Ministere des Armees", EMPLOYEURS) == 5
    assert identifiant("12345", EMPLOYEURS) == 12345
    assert identifiant("Inconnu", EMPLOYEURS) is None


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


def test_source_s_arrete_a_pages_max() -> None:
    client = FauxClient({adresse("ia"): _page(0, 20, 500)})
    SourceServicePublic(client, ("ia",), pages_max=1).collecter()
    assert len(client.appels) == 1


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
