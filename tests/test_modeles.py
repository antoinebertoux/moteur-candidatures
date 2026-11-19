import pytest

from moteur.modeles import LONGUEUR_MAX_CLE, Offre, contient_expression, normaliser


@pytest.mark.spec("ID-01")
def test_normaliser_retire_accents_et_ponctuation() -> None:
    assert normaliser("  Ingénieur·e IA (H/F) — Défense ") == "ingenieur-e-ia-h-f-defense"


@pytest.mark.spec("ID-02")
def test_cle_identique_a_celle_de_la_page_de_suivi() -> None:
    offre = Offre(entreprise="ÉTÉ (Études Techniques Européennes)", poste="Chef de projet IA")
    assert offre.cle == "offre_ete-etudes-techniques-europeennes_chef-de-projet-ia"


@pytest.mark.spec("ID-02")
def test_cle_distingue_offre_et_spontanee() -> None:
    offre = Offre(entreprise="Acme", poste="Lead AI")
    spontanee = Offre(entreprise="Acme", poste="Lead AI", type="spontanee")
    assert offre.cle != spontanee.cle
    assert spontanee.cle.startswith("spontanee_")


@pytest.mark.spec("ID-02")
def test_cle_tronquee() -> None:
    assert len(Offre(entreprise="x" * 200, poste="y").cle) == LONGUEUR_MAX_CLE


@pytest.mark.spec("ID-03")
def test_expression_en_mots_entiers() -> None:
    assert contient_expression("Ingénieur IA senior", "ia")
    assert contient_expression("Head of AI (F/H)", "head of ai")
    assert not contient_expression("Commercial terrain", "ia")
    assert not contient_expression("Data Scientist", "")
