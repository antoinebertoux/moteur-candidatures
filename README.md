# Moteur local de candidatures

Collecte et trie les offres en code (0 token), puis appelle Claude par `claude -p`
(abonnement, pas de clé API) pour noter les offres et préparer CV et lettre à partir
du dépôt `../latex/`.

## Installation

```bash
uv sync
cp config.exemple.toml config.toml   # puis adapte critères et entreprises
```

Pour France Travail, crée un fichier `.env` (ignoré par Git) à côté de `config.toml` :

```bash
FRANCE_TRAVAIL_ID=...
FRANCE_TRAVAIL_SECRET=...
```

Il est lu automatiquement ; une variable déjà définie dans le shell reste prioritaire.

Choisir le service public (offres de l'État : ministères des Armées et de l'Intérieur,
DGSE, DGSI, DINUM, AMIAD, ANSSI…) ne demande aucun identifiant : règle mots-clés,
domaines et employeurs dans `[service_public]`.

`claude` doit être installé et connecté avec ton abonnement (`claude auth status`).

## Données personnelles

Le dépôt ne contient aucune donnée personnelle. Tout ce qui te concerne reste dans des
fichiers ignorés par Git ou hors du dépôt :

| Fichier | Contenu |
| --- | --- |
| `config.toml` | profil envoyé à Claude, critères, salaire plancher, entreprises suivies |
| `.env` | identifiants France Travail |
| `moteur.sqlite3`, `echange/` | offres vues, notes, décisions |
| `../latex/` | CV, banques de blocs et de paragraphes, `compiler.sh` |
| `../Candidatures/`, `../suivi/` | dossiers générés, entreprises déjà approchées |

Le dossier parent (`racine` dans `[chemins]`, `..` par défaut) doit contenir :

```text
latex/
  compiler.sh                  # compile un dossier ; signale « <nom>.pdf fait N pages »
  cv/modele-cv.tex             # CV de départ, avec \def\latexroot{...}
  cv/banque-fr.tex, banque-en.tex   # macros de blocs autorisées
  lettres/modele-lettre.tex    # squelette de lettre
  lettres/banque-paragraphes.md
suivi/entreprises_vues.csv     # facultatif : colonnes « entreprise;…;statut »
```

## Utilisation

```bash
uv run moteur quotidien          # collecter + noter + exporter
# -> importe echange/pour-la-page.json dans la page de suivi, réponds oui / non
# -> exporte depuis la page, puis :
uv run moteur decisions ~/Downloads/candidatures-export.json
uv run moteur generer            # CV et lettre dans ../Candidatures/<Entreprise - Poste>/
uv run moteur exporter           # -> réimporte : les dossiers passent en « À valider »
uv run moteur servir             # boutons CV / Lettre de la page -> PDF de ton PC
```

La page est sur claude.ai : le navigateur y bloque les liens `file://`. `servir` expose
donc **seulement** `../Candidatures/`, en lecture seule, sur `http://127.0.0.1:8765`
(`--port` pour changer ; la page suppose 8765). Laisse-le tourner pendant la relecture.

Chaque étape existe aussi seule : `collecter`, `noter`, `exporter`. Ajoute `-v` pour le
détail par source.

## Qualité

```bash
uv run ruff format . && uv run ruff check .
uv run mypy
uv run pytest
```

## Organisation

| Module | Rôle | Claude |
| --- | --- | --- |
| `sources/` | France Travail, Choisir le service public, Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Teamtailor, Workday | non |
| `filtre.py` | mots-clés, exclusions, lieux, salaire | non |
| `collecte.py` | assemble les sources, propose les candidatures spontanées | non |
| `base_locale.py` | SQLite : déjà vu, noté, à générer | non |
| `notation.py` | score et résumé, par lots | Haiku |
| `generation.py` | CV et lettre LaTeX, compilation | Sonnet |
| `echange.py` | fichiers échangés avec la page de suivi | non |
| `serveur.py` | sert les PDF de `Candidatures/` à la page | non |

Les identifiants de candidature (`Offre.cle`) sont calculés comme dans la page de suivi :
ne change pas `normaliser` d'un seul côté.
