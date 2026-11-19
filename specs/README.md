# Specs de l'outil de candidatures

Ces fichiers décrivent **ce que fait** l'outil, pas comment il est codé. Ils font foi :
quand le code et une spec divergent, l'un des deux est faux et doit être corrigé.

## Comment s'en servir

- **Une règle = un identifiant stable** (`FILT-03`). Il ne change jamais et n'est pas
  réutilisé : une règle supprimée est barrée, pas renumérotée.
- **Chaque règle du moteur est vérifiée par au moins un test**, qui la cite :
  `@pytest.mark.spec("FILT-03")`. `tests/test_specs.py` échoue si une règle n'a pas de
  test ou si un test cite une règle inconnue.
- Une règle marquée *(non testé)* est assumée sans test automatique (consigne donnée à
  Claude, comportement réseau…). Les règles de la page et des tâches planifiées ne sont
  pas dans ce dépôt : elles sont vérifiées à la main.
- **Ordre de travail** : on modifie d'abord la spec, Antoine la valide, puis on code et on
  teste. Le commit contient les trois.

## Vue d'ensemble

```text
            ┌──────────────── Moteur A : tâches planifiées dans Claude ───────────────┐
            │  cherchent les offres sur le web et écrivent directement dans la base   │
            └────────────────────────────────────┬───────────────────────────────────┘
                                                 ▼
 Moteur B (ce dépôt, sur le PC)          Page « Suivi des candidatures »
 collecter → noter → exporter ──JSON──▶  (artefact claude.ai + sa base)
                                          Antoine trie : oui / non, lettre, retouches
 decisions ◀───────────────JSON───────── Exporter
 generer / lettre  → PDF dans ../Candidatures/
 exporter ─────────────────JSON──────▶  Importer : les dossiers passent « À valider »
 servir  ◀── liens CV / Lettre ─────────  Antoine relit, valide, postule lui-même
```

Claude n'est appelé que pour **noter** (Haiku) et **rédiger** (Sonnet), par `claude -p`
avec l'abonnement, sans clé API. Tout le reste est du code, à 0 token.

## Statuts

| Page (champ `statut`) | Étape affichée | Base locale du moteur B |
| --- | --- | --- |
| — | — | `a_noter` : collectée, pas encore notée |
| `a_traiter` | À traiter | `notee` : proposée à la page |
| `acceptee` | À préparer | `acceptee` : CV (et lettre) à générer |
| `prete` | À valider | `generee` : PDF prêts |
| `validee` | À envoyer | `generee` |
| `postulee` | Postulée | `close` |
| `refusee` | Refusée | `refusee` |

## Fichiers

| Fichier | Préfixe | Sujet |
| --- | --- | --- |
| [identifiants.md](identifiants.md) | `ID` | identifiant d'une candidature, règles partagées avec la page |
| [config.md](config.md) | `CONF` | `config.toml` et `.env` |
| [sources.md](sources.md) | `SRC` | sites interrogés |
| [collecte.md](collecte.md) | `COL`, `FILT` | assemblage des sources, filtre, candidatures spontanées |
| [base-locale.md](base-locale.md) | `BASE` | ce que le moteur B retient et ses transitions |
| [notation.md](notation.md) | `NOT`, `CLA` | notation par Claude, appel à `claude -p` |
| [generation.md](generation.md) | `CV`, `LET`, `GEN` | CV et lettre LaTeX |
| [echange.md](echange.md) | `ECH` | fichiers échangés avec la page |
| [cli.md](cli.md) | `CLI`, `SRV` | commandes et serveur local des PDF |
| [page-suivi.md](page-suivi.md) | `PAGE` | page de suivi (artefact claude.ai) |
| [taches-claude.md](taches-claude.md) | `TACHE` | moteur A : tâches planifiées |
| ce fichier | `INV` | invariants de tout l'outil |

## Invariants

- **INV-01** · Rien n'est jamais envoyé à un employeur sans qu'Antoine ait validé : ni le
  moteur B ni le moteur A ne postulent ni n'envoient de message. *(non testé)*
- **INV-02** · Le dépôt ne contient aucune donnée personnelle : `config.toml`, `.env`,
  `moteur.sqlite3` et `echange/` sont ignorés par Git ; CV, lettres et candidatures
  restent hors du dépôt. *(non testé)*
- **INV-03** · Le plancher salarial n'est jamais transmis à Claude ni écrit dans la base de
  la page. *(non testé)*
- **INV-04** · Les anciennes candidatures (avant novembre 2026) ne sont pas reprises dans
  le suivi. *(non testé)*
