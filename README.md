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

Le dépôt ne contient aucune donnée personnelle. Elles restent dans des
fichiers ignorés par Git ou hors du dépôt :

| Fichier | Contenu |
| --- | --- |
| `config.toml` | profil envoyé à Claude, critères, salaire plancher, entreprises suivies |
| `.env` | identifiants France Travail |
| `moteur.sqlite3`, `echange/` | offres vues, notes, décisions |
| `../latex/` | CV, banques de blocs et de paragraphes, `compiler.sh` |
| `../Candidatures/`, `../suivi/` | dossiers générés, entreprises déjà approchées |
| `prive/` | export de la base de la page, texte rempli des tâches planifiées |

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
uv run moteur generer            # CV et lettre dans ../Candidatures/<Entreprise - Poste>/
uv run moteur servir             # à laisser tourner : boutons CV / Lettre -> PDF de ton PC
```

### Direct link with the page (`moteur mcp`)

When the page is open in the Claude desktop app on this PC, it talks to engine B through
an MCP server (rules ECH-20 to ECH-25, PAGE-35 to PAGE-38): it imports the proposals and
ready folders at load and every minute, and sends its decisions a few seconds after each
change. No JSON file to move by hand. The app starts the server itself; declare it once
in `~/.config/Claude/claude_desktop_config.json`, then restart the app:

```json
{
  "mcpServers": {
    "moteur": {
      "command": "/usr/bin/uv",
      "args": ["--directory", "/chemin/vers/moteur", "run", "moteur", "mcp"]
    }
  }
}
```

The "Moteur B" chip in the page header shows whether the link is up.

### Fallback: JSON files

Elsewhere (phone, browser, app closed), exchange by hand:

```bash
uv run moteur exporter           # -> importe echange/pour-la-page.json dans la page
uv run moteur decisions ~/Downloads/candidatures-export.json   # après « Exporter »
```

La page ne peut pas `fetch()` le PC : la plateforme des artefacts bloque tout appel vers
un autre hôte, `127.0.0.1` compris. Seul le serveur MCP passe, par l'app desktop.

La page est sur claude.ai : le navigateur y bloque les liens `file://`. `servir` expose
donc **seulement** `../Candidatures/`, en lecture seule, sur `http://127.0.0.1:8765`
(`--port` pour changer ; la page suppose 8765).

Chaque étape existe aussi seule : `collecter`, `noter`, `exporter`. Ajoute `-v` pour le
détail par source.

## Page de suivi et tâches planifiées

L'outil complet tient en trois morceaux, tous dans ce dépôt :

| Dossier | Contenu |
| --- | --- |
| `src/moteur/` | moteur B, sur le PC (ce README) |
| [`page-suivi/`](page-suivi/README.md) | code de la page de suivi (artefact claude.ai) et schéma de sa base |
| [`taches/`](taches/README.md) | gabarits des tâches planifiées Claude (moteur A) |

Pour tout réinstaller chez quelqu'un d'autre : publier la page, créer les tâches à
partir des gabarits, puis configurer le moteur (Installation ci-dessus).

## Specs

Le comportement attendu est décrit dans [`specs/`](specs/README.md), règle par règle.
Chaque règle du moteur est vérifiée par un test qui la cite
(`@pytest.mark.spec("FILT-03")`) ; `tests/test_specs.py` échoue s'il en manque un.

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
| `decisions.py` | applies the page's decisions (file or direct link) | non |
| `liaison.py` | MCP server `moteur mcp`, direct link with the page | non |
| `serveur.py` | sert les PDF de `Candidatures/` à la page | non |

Les identifiants de candidature (`Offre.cle`) sont calculés comme dans la page de suivi :
ne change pas `normaliser` d'un seul côté.
