# Configuration

`config.toml` (ignored by Git) is created by copying `config.exemple.toml`. It holds the
profile sent to Claude, the sorting criteria, the sources and the tracked companies.

- **CONF-01** · If `config.toml` is missing, the engine stops and says to copy
  `config.exemple.toml`; if it is malformed, it stops and quotes the TOML error.
- **CONF-02** · Defaults: 8 ads per scoring batch, models `haiku` for scoring and
  `sonnet` for writing, France Travail and Choisir le service public disabled, no salary
  floor, root folder `..` (the parent of `moteur/`).
- **CONF-03** · A value of the wrong type is rejected with a message naming the key;
  `taille_lot` and `pages_max` must be at least 1.
- **CONF-04** · Every tracked company has a name. Its recruiting tool (`ats`) is empty
  or one of: greenhouse, lever, ashby, workday, smartrecruiters, recruitee, teamtailor;
  when set, `identifiant` is required. A Workday company may have its own search
  keywords.
- **CONF-05** · Choisir le service public domains and employers are given by name
  ("DGSE", "Numérique", accents and case ignored) or by their numeric id on the site; an
  unknown name is rejected with the list of known names.
- **CONF-06** · `config.exemple.toml` is always a valid configuration.
- **CONF-07** · Paths derive from the location of `config.toml`: the `moteur.sqlite3`
  database and the `echange/` folder next to it; `latex/`, `Candidatures/` and
  `suivi/entreprises_vues.csv` under the root folder.
- **CONF-08** · The `.env` file next to `config.toml` is read at startup (`KEY=value`,
  blank lines and `#` comments ignored, `export` prefix and quotes accepted). A variable
  already set in the shell is not overwritten. A missing `.env` is not an error.
