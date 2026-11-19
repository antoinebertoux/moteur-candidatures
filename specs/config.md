# Configuration

`config.toml` (ignoré par Git) est créé en copiant `config.exemple.toml`. Il contient le
profil envoyé à Claude, les critères de tri, les sources et les entreprises suivies.

- **CONF-01** · Si `config.toml` est absent, le moteur s'arrête en disant de copier
  `config.exemple.toml` ; s'il est mal formé, il s'arrête en citant l'erreur TOML.
- **CONF-02** · Valeurs par défaut : 8 offres par lot de notation, modèles `haiku` pour
  noter et `sonnet` pour rédiger, France Travail et Choisir le service public désactivés,
  aucun plancher salarial, dossier racine `..` (le dossier parent de `moteur/`).
- **CONF-03** · Une valeur du mauvais type est refusée avec un message qui nomme la clé ;
  `taille_lot` et `pages_max` doivent valoir au moins 1.
- **CONF-04** · Chaque entreprise suivie a un nom. Son outil de recrutement (`ats`) est
  vide ou l'un de : greenhouse, lever, ashby, workday, smartrecruiters, recruitee,
  teamtailor ; s'il est renseigné, `identifiant` est obligatoire. Une entreprise Workday
  peut avoir ses propres mots-clés de recherche.
- **CONF-05** · Les domaines et employeurs de Choisir le service public se donnent par
  leur nom (« DGSE », « Numérique », accents et casse ignorés) ou par leur identifiant
  numérique sur le site ; un nom inconnu est refusé avec la liste des noms reconnus.
- **CONF-06** · `config.exemple.toml` est toujours une configuration valide.
- **CONF-07** · Les chemins se déduisent de l'emplacement de `config.toml` : la base
  `moteur.sqlite3` et le dossier `echange/` à côté de lui ; `latex/`, `Candidatures/` et
  `suivi/entreprises_vues.csv` sous le dossier racine.
- **CONF-08** · Le fichier `.env` placé à côté de `config.toml` est lu au démarrage
  (`CLE=valeur`, lignes vides et commentaires `#` ignorés, préfixe `export` et
  guillemets acceptés). Une variable déjà définie dans le shell n'est pas écrasée. Un
  `.env` absent n'est pas une erreur.
