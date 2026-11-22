from pathlib import Path

import pytest

from moteur.config import ConfigError
from moteur.models import JobAd
from moteur.sources.service_public import (
    EMPLOYERS,
    SourceServicePublic,
    address,
    ads_public_service,
    announced_total,
    french_date,
    identifier,
    public_service_description,
)
from tests.conftest import FakeClient, parsed


def _card(
    number: int, employer: str = "Direction Générale de la Sécurité Extérieure (DGSE)"
) -> str:
    return f"""
<li class="fr-col-12 item">
<div class="fr-card fr-card--horizontal fr-card--horizontal-tier fr-card--offer">
  <h3 class="fr-card__title">
    <a href="https://choisirleservicepublic.gouv.fr/offre-emploi/offre-{number}/"
       class="is-same-domain" target="_blank" aria-label="x">
      Ingénieur IA n°{number} H/F
    </a>
  </h3>
  <ul class="fr-card__desc">
    <li class="fr-icon-map-pin-2-line fr-icon--sm">
      <span class="sr-only">Localisation : </span> Paris <strong>(75)</strong></li>
    <li class="fr-icon-file-line fr-icon--sm">
      <span class="sr-only">Fonction publique : </span> Fonction publique de l'État</li>
    <li class="fr-icon-user-line  fr-icon--sm">
      <span class="sr-only">Employeur : </span> {employer}</li>
    <li class="fr-icon-calendar-line  fr-icon--sm">En ligne depuis le 1er novembre 2026</li>
  </ul>
</div></li>"""


def _page(start: int, count: int, total: int) -> str:
    cards = "".join(_card(i) for i in range(start, start + count))
    return f'<p><span class="number">{total}</span> offres</p><ul>{cards}</ul>'


@pytest.mark.spec("SRC-23")
def test_public_service_ads() -> None:
    (ad,) = ads_public_service(_page(7, 1, 1))
    assert ad.title == "Ingénieur IA n°7 H/F"
    assert ad.company == "Direction Générale de la Sécurité Extérieure (DGSE)"
    assert ad.location == "Paris (75)"
    assert ad.url == "https://choisirleservicepublic.gouv.fr/offre-emploi/offre-7/"
    assert (ad.source, ad.published_on) == ("service_public", "2026-11-01")
    assert ads_public_service("<html></html>") == []


@pytest.mark.spec("SRC-21")
def test_adresse_respecte_l_ordre_des_filtres() -> None:
    assert address() == "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/"
    assert address("intelligence artificielle", (3522,), (5, 364), page=2) == (
        "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/"
        "mot-cles/intelligence%20artificielle/domaine/3522/organisme/5-364/page/2/"
    )


@pytest.mark.spec("SRC-23")
def test_date_and_total() -> None:
    assert french_date("En ligne depuis le 16 février 2026") == "2026-02-16"
    assert french_date("En ligne depuis peu") == ""
    assert announced_total('<span class="number">1 274</span>') == 1274
    assert announced_total("") is None


@pytest.mark.spec("CONF-05")
def test_identifier_by_name_or_number() -> None:
    assert identifier("dgse", EMPLOYERS) == 364
    assert identifier("Ministere des Armees", EMPLOYERS) == 5
    assert identifier("12345", EMPLOYERS) == 12345
    assert identifier("Inconnu", EMPLOYERS) is None


@pytest.mark.spec("SRC-20", "SRC-22")
def test_source_pages_then_searches_employers() -> None:
    general = address("ia")
    client = FakeClient(
        {
            general: _page(0, 20, 25),
            address("ia", page=2): _page(20, 5, 25),
            address("ia", employers=(364,)): _page(3, 2, 2),
        }
    )
    source = SourceServicePublic(client, ("ia",), employers=(364,), pages_max=5)
    ads = source.collect()
    assert len(ads) == 25  # the 2 DGSE ads are already seen
    assert sorted(url for url, _ in client.calls) == sorted(
        [general, address("ia", page=2), address("ia", employers=(364,))]
    )
    assert source.name == "service_public"


@pytest.mark.spec("SRC-22")
def test_source_stops_at_pages_max() -> None:
    client = FakeClient({address("ia"): _page(0, 20, 500)})
    SourceServicePublic(client, ("ia",), pages_max=1).collect()
    assert len(client.calls) == 1


@pytest.mark.spec("CONF-05")
def test_public_service_config() -> None:
    data = {
        "service_public": {
            "actif": True,
            "recherches": ["IA"],
            "domaines": ["Numérique", 3525],
            "employeurs": ["DGSE", "DGSI", "14524"],
        }
    }
    service_public = parsed(data, Path()).service_public
    assert service_public.enabled
    assert service_public.domains == (3522, 3525)
    assert service_public.employers == (364, 13502, 14524)
    assert service_public.pages_max == 3
    with pytest.raises(ConfigError):
        parsed({"service_public": {"employeurs": ["Inconnu"]}}, Path())
    with pytest.raises(ConfigError):
        parsed({"service_public": {"pages_max": 0}}, Path())


# Real (shortened) extract of an ad page, taken on 17/11/2026.
AD_PAGE = """<main class="dsfr main-content-single-offer">
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
def test_public_service_description() -> None:
    assert public_service_description(AD_PAGE) == (
        "Vos missions en quelques mots\n"
        "Le pôle data valorise les données du service.\n"
        "Il détecte des phénomènes d’intérêt :\n"
        "• Gestion de projet\n"
        "• Prototypage\n"
        "Profil recherché\n"
        "Bac+5 en data science."
    )
    assert public_service_description("<html>page inattendue</html>") == ""


@pytest.mark.spec("SRC-24")
def test_add_details_opens_the_ad_page() -> None:
    url = "https://choisirleservicepublic.gouv.fr/offre-emploi/tracfin/"
    client = FakeClient({url: AD_PAGE})
    source = SourceServicePublic(client, ["data"])
    ad = source.add_details(JobAd("TRACFIN", "Data scientist", url=url, source="service_public"))
    assert ad.description.startswith("Vos missions en quelques mots")
    assert ad.title == "Data scientist"
    assert client.calls == [(url, {})]
