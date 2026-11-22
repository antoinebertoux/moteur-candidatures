# Company catalogue and selection

Engine B follows two kinds of companies:

- the **catalogue**, shipped with the tool: public bodies and companies of 500 employees
  or more, useful to almost anyone because they hire for most jobs;
- User's **own companies**, the `[[entreprises]]` of `config.toml`: start-ups, small
  companies, anything User found themselves.

User does not edit a list by hand: in the page, they untick what does not interest them,
company by company or a whole sector or size at once (PAGE-70 and following). Engine B
keeps these choices; `config.toml` is never rewritten.

## The catalogue

- **CAT-01** · The catalogue is the file `catalogue/entreprises.toml` of the repository,
  an array `[[entreprises]]`. It holds only public facts about companies, nothing about a
  candidate (INV-02).
- **CAT-02** · An entry has the fields of an own company (CONF-04, CONF-09: `nom`, `ats`,
  `identifiant`, `site`, `linkedin`) plus `secteur` (CAT-04, required),
  `taille` (CAT-03, required) and `pays` (two-letter ISO codes of the countries where it
  hires, as in CONF-10; may be empty). It never has `spontanee`, which is a personal
  choice (CAT-14), nor `recherches`, which depend on the job sought (CAT-07). An entry
  with either is rejected (CAT-05).
- **CAT-03** · Sizes: `public` (the State, local authorities, public bodies and public
  research), `grand-groupe` (500 employees or more, state-owned companies
  included), `pme` (fewer than 500 employees) and `startup`. The catalogue only
  holds `public` and `grand-groupe`; the two others are for own companies.
- **CAT-04** · Sectors, a fixed list: `administration`, `defense`,
  `aeronautique-spatial`, `naval-maritime`, `cybersecurite`, `energie`, `environnement`
  (water, waste, climate), `sante` (care, hospitals), `pharmacie-biotech` (medicines,
  biotech, medical devices), `banque`, `assurance`, `industrie`, `automobile`,
  `chimie-materiaux`, `electronique-semiconducteurs`, `transport-logistique`,
  `numerique` (software, internet), `telecommunications`, `jeux-video`,
  `commerce-distribution`, `luxe-mode`, `medias-culture`, `tourisme-hotellerie`,
  `recherche-enseignement`, `conseil`, `esn` (IT services), `interim-rh`,
  `btp-immobilier`, `agroalimentaire`, `economie-sociale` (associations, NGOs, social
  economy). The page shows them with a translated label (PAGE-66).
- **CAT-05** · The catalogue shipped is always valid: every entry follows CAT-02 to
  CAT-04, and two entries never have the same normalised name (ID-01). An invalid entry
  is rejected with a message naming the company, like CONF-03.
- **CAT-06** · The companies followed are the catalogue's plus User's own. An own company
  with the same normalised name as a catalogue entry replaces it entirely.
- **CAT-07** · Every Workday or SmartRecruiters company, from the catalogue or User's
  own, is searched with the same terms, `[criteres] recherches` (CONF-11), since the
  catalogue cannot know the job sought. No company has search terms of its own
  (CONF-04).

## Default selection

- **CAT-10** · Without a choice from User, an own company is searched, from the moment
  it is added to `config.toml`; User can untick it like any other (CAT-12). A catalogue
  company is searched if `[criteres] pays` is empty, or if its `pays` is empty, or if they
  share a country; otherwise it is not searched.
- **CAT-11** · Defaults are recomputed at every collection: changing `[criteres] pays`
  moves the companies User has not chosen for, and only them.

## User's choices

- **CAT-12** · User can turn on or off: a company, its unsolicited application, a sector,
  a size and a source (CAT-15). Each choice is kept in the local database (BASE-15) until
  User changes it or goes back to the default.
- **CAT-13** · A company is **searched** when its own state (User's choice, otherwise
  CAT-10) is on **and** neither its sector nor its size is turned off. An own company
  without `secteur` or `taille` is only affected by the toggles it has.
- **CAT-14** · An unsolicited application is proposed only for a searched company whose
  unsolicited application is on: User's choice, otherwise `spontanee` in `config.toml`
  for an own company, otherwise off for a catalogue company (COL-03).
- **CAT-15** · Sources searched by keyword: France Travail, Choisir le service public and
  Station F are queried only if `actif = true` in `config.toml` (SRC-10…) **and** User
  has not turned them off. Turning a source on in the page never enables one that is off
  in `config.toml` (credentials may be missing). Choisir le service public belongs to
  the size `public` and Station F to the size `startup`: turning the size off turns the
  source off too.
- **CAT-16** · A choice about a company or sector that no longer exists (removed from the
  catalogue or from `config.toml`) is kept and ignored; it applies again if the company
  comes back.

## Not covered yet

Editing locations, countries and keywords from the page, and finding new companies with
Claude, will come later. The scheduled tasks of engine A ignore these choices: their
targets stay written in their text.
