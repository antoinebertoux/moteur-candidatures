# Configuration

`config.toml` (ignored by Git) is created by copying `config.exemple.toml`. It holds the
profile sent to Claude, the sorting criteria and the sources. It lists no company: the
catalogue is shipped with the tool and User's own companies are in the local database
([catalogue.md](catalogue.md)).

- **CONF-01** · If `config.toml` is missing, the engine stops and says to copy
  `config.exemple.toml`; if it is malformed, it stops and quotes the TOML error.
- **CONF-02** · Defaults: 8 ads per scoring batch, models `haiku` for scoring and
  `sonnet` for writing and for interview preparation, France Travail, Choisir le
  service public and Station F disabled; Station F reads 3 pages per search and keeps ads
  published in the last 21 days; no salary floor, root folder `..` (the parent of `moteur/`).
- **CONF-03** · A value of the wrong type is rejected with a message naming the key;
  `taille_lot`, `pages_max` and Station F's `publiee_depuis` must be at least 1.
- ~~**CONF-04**~~ · *Removed: `config.toml` lists no company (CONF-12); a company's
  fields are checked by CAT-08 and CAT-20.*
- **CONF-05** · Choisir le service public domains and employers are given by name
  ("Ministère des Armées", "Numérique", accents and case ignored) or by their numeric id on the site; an
  unknown name is rejected with the list of known names.
- ~~**CONF-09**~~ · *Removed: moved to CAT-08.*
- **CONF-10** · `[criteres] pays` lists the countries where ads are searched, as
  two-letter ISO 3166-1 codes (`"fr"`, `"gb"`…, case ignored); empty or missing = every
  country. Any other value is rejected with a message quoting it. The engine holds no
  list of countries of its own: only sources that can search by country use it
  (SmartRecruiters, SRC-35); the others rely on `lieux`.
- **CONF-11** · `[criteres] recherches` is the one list of search terms, shared by every
  company and source: the words typed in the search box of the sites that cannot list
  all their ads (Workday SRC-41, SmartRecruiters SRC-35, France Travail SRC-11, Choisir
  le service public SRC-20, Station F SRC-71). Broad terms ("machine learning") rather
  than titles: every ad found still has to pass `mots_cles` (FILT-01), and each term
  costs one search per company, so a short list keeps the number of requests low.
  The engine holds no default terms, since they depend on the job sought: the list is
  required, and a missing or empty list is rejected with a message saying to fill it
  (`config.exemple.toml` gives an example). A source's own `recherches` (`[france_travail]`, `[service_public]`,
  `[station_f]`), when given, replaces it for that source only.
- **CONF-12** · `config.toml` lists no company: a `[[entreprises]]` array stops the
  engine with a message saying to run `moteur import-companies` (CLI-10), then to delete
  it from `config.toml`.
- **CONF-06** · `config.exemple.toml` is always a valid configuration.
- **CONF-07** · Paths derive from the location of `config.toml`: the `moteur.sqlite3`
  database and the `echange/` folder next to it; `latex/`, `Candidatures/` and
  `suivi/entreprises_vues.csv` under the root folder.
- **CONF-08** · The `.env` file next to `config.toml` is read at startup (`KEY=value`,
  blank lines and `#` comments ignored, `export` prefix and quotes accepted). A variable
  already set in the shell is not overwritten. A missing `.env` is not an error.
