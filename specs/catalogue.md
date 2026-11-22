# Company catalogue and selection

Engine B follows two kinds of companies:

- the **catalogue**, shipped with the tool: public bodies and companies of 500 employees
  or more, useful to almost anyone because they hire for most jobs;
- User's **own companies**: start-ups, small companies, anything else User wants,
  found and added by Claude through engine B (CAT-20 and following) and kept in the
  local database. `config.toml` lists no company (CONF-12).

User does not edit a list by hand: in the page, they untick what does not interest them,
company by company or a whole sector or size at once (PAGE-70 and following), and they
ask Claude to find or add others. Engine B keeps these choices and companies;
`config.toml` is never rewritten.

## The catalogue

- **CAT-01** · The catalogue is the file `catalogue/entreprises.toml` of the repository,
  an array `[[entreprises]]`. It holds only public facts about companies, nothing about a
  candidate (INV-02).
- **CAT-02** · An entry has `nom`, `ats`, `identifiant`, `site` and `linkedin` (CAT-08)
  plus `secteur` (CAT-04, required),
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
  is skipped with a warning naming the company, like CONF-03, and the other entries
  still load: one invalid entry never empties the catalogue.
- **CAT-08** · A company's recruiting tool (`ats`) is empty or one of: greenhouse, lever,
  ashby, workday, smartrecruiters, recruitee, teamtailor, workable, radancy, welcomekit,
  talentsoft, oracle, successfactors, phenom, avature, magnet, sitemap, mckinsey,
  gestmax, sncf, taleez, werecruit;
  when set, `identifiant` is required. Its `site` and `linkedin`, when given, are http(s)
  addresses: they are the company's links of LNK-02. Any other value is rejected with a
  message naming the company and the field, and listing the accepted values.
- **CAT-06** · The companies followed are the catalogue's plus User's own. An own company
  with the same normalised name as a catalogue entry replaces it entirely.
- **CAT-07** · Every company whose tool is searched by keyword (Workday, SmartRecruiters,
  Oracle, SuccessFactors, Phenom, Avature, McKinsey), from the catalogue or User's own, is
  searched with the same terms, `[criteres] recherches` (CONF-11), since the
  catalogue cannot know the job sought. No company has search terms of its own.

## Default selection

- **CAT-10** · Without a choice from User, an own company is searched, from the moment
  it is added (CAT-21); User can untick it like any other (CAT-12). A catalogue
  company is searched if `[criteres] pays` is empty, or if its `pays` is empty, or if they
  share a country; otherwise it is not searched.
- **CAT-11** · Defaults are recomputed at every collection: changing `[criteres] pays`
  moves the companies User has not chosen for, and only them.

## User's choices

- **CAT-12** · User can turn on or off: a company, its unsolicited application, a sector,
  a size and a source (CAT-15). Each choice is kept in the local database (BASE-15) until
  User changes it or goes back to the default.
- **CAT-13** · A company is **searched** when its own state (User's choice, otherwise
  CAT-10) is on **and** neither its sector nor its size is turned off.
- **CAT-14** · An unsolicited application is proposed only for a searched company whose
  unsolicited application is on: User's choice, otherwise off (COL-03).
- **CAT-15** · Sources searched by keyword: France Travail, Choisir le service public and
  Station F. User's choice turns a source on or off; without a choice, it follows
  `actif` in `config.toml` (SRC-10, SRC-20, SRC-70). France Travail is queried only when
  its credentials are set (SRC-10), whatever the choice. Choisir le service public belongs
  to the size `public` and Station F to the size `startup`: turning the size off turns the
  source off too.
- **CAT-16** · A choice about a company or sector that no longer exists (removed from the
  catalogue or from User's own companies) is kept and ignored; it applies again if the company
  comes back.

## Own companies

User never writes an `ats` or an `identifiant`: they tell Claude what they want ("add
Doctolib", "cybersecurity SMEs hiring in Lyon"). Claude finds the companies and their
career pages, and hands them to engine B, which checks each one before keeping it.

- **CAT-20** · An own company has the fields of a catalogue entry (CAT-02: `nom`, `ats`,
  `identifiant`, `site`, `linkedin`, `secteur`, `taille`, `pays`), with any size of
  CAT-03. `ats`, `secteur` and `taille` are required: a company without a supported tool
  cannot be followed (SRC-30), and the sector and size toggles must apply to it. It
  never has `spontanee` (a choice, CAT-12) nor `recherches` (CAT-07). It is kept in the
  local database (BASE-16).
- **CAT-21** · An addition gives either `ats` and `identifiant`, or a career page
  `adresse`, from which the tool and identifier are found as `moteur detect` does
  (CLI-04, CLI-05). An addition with both, or neither, is refused. When `site` is
  missing, it is `adresse`.
- **CAT-22** · Before keeping a company, engine B queries its board once, as the
  collection would (SRC-30 and following; tools searched by keyword, CAT-07, with the
  first term of `[criteres] recherches`). A board that answers is kept with the number of ads it
  returned, zero included (the company may not be hiring right now). A source error
  (SRC-01, SRC-03) refuses the company with that error. Nothing is scored nor stored as
  an application: the next collection finds its ads.
- **CAT-23** · Each company of an addition is handled on its own: one refused company
  does not stop the others. The reasons for a refusal are: an invalid field (CAT-08,
  CAT-20), "unrecognised tool" (CLI-05), a source error (CAT-22) and "already in the
  catalogue" (its key is given, so that Claude can turn it on with `selection`
  instead).
- **CAT-24** · Adding an own company again (same normalised name) replaces its fields,
  after the same check; User's choices about it (BASE-15) are kept.
- **CAT-25** · Only own companies can be removed; catalogue companies are unticked
  (CAT-12). Removing one stops following it; User's choices about it are kept and
  ignored, as CAT-16, and apply again if it is added back.
- **CAT-26** · Moving from an older version: `moteur import-companies` (CLI-10) turns the
  `[[entreprises]]` of `config.toml` into own companies, once, so that none is lost.

## Finding companies with Claude

The skill `skills/trouver-entreprises/SKILL.md` of the repository, installed in the Claude
desktop app, tells Claude how to fill a request from User with the tools of ECH-30 and
following. Its rules guide a conversation, so none of them can be checked by a test.

- **CAT-30** · Claude first reads `entreprises` (ECH-27), so that it neither proposes a
  company already followed nor misses one that is only unticked (it then offers to turn
  it on). *(untested: behaviour of Claude)*
- **CAT-31** · For a description ("start-ups in medical imaging"), Claude searches the
  web and shows User the companies found, each with its size, sector, city and one line
  on why it fits, and adds only those User keeps. A company named by User is added
  without this step. *(untested: behaviour of Claude)*
- **CAT-32** · Claude looks for the company's career page and the recruiting tool behind
  it; when it is unsure of the identifier, it gives the career page as `adresse`
  (CAT-21) and lets engine B find it. A company whose career page uses no supported tool
  (SRC-30) is reported to User as not followable, with its career page, and is not
  added. *(untested: behaviour of Claude)*
- **CAT-33** · After `ajouter_entreprises`, Claude reports to User the companies added
  with their number of ads, and each refusal with its reason; it retries a refused
  company only with new information (another career page, another identifier).
  *(untested: behaviour of Claude)*
- **CAT-34** · The skill holds no personal data (INV-02) and no list of companies: what
  User looks for comes from the conversation and from `entreprises`.
  *(untested: content of a text file)*

## Not covered yet

Editing locations, countries and keywords from the page will come later. The scheduled tasks of engine A ignore these choices: their
targets stay written in their text.
