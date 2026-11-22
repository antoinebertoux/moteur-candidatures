# Files exchanged with the page

The page is a claude.ai artifact: it cannot `fetch()` the PC (the platform blocks every
request to another host, `127.0.0.1` included). It can however call an MCP server running
on the PC, through the Claude desktop app (`host:` servers of the artifact `mcp`
capability). Engine B therefore offers two channels carrying the same content:

- the **direct link** (`moteur mcp`, rules ECH-20 and following), used whenever the page
  is open in the Claude desktop app on the PC;
- the **JSON files** below, kept as a fallback (phone, browser, engine stopped).

## Engine B → page: `echange/pour-la-page.json`

- **ECH-01** · Array of entries with: `type`, `entreprise`, `poste`, `lieu`, `url`,
  `source`, `moteur` = `B`, `resume`, `lettre_demandee`, and `score` if the ad is scored.
  **No identifier**: the page recomputes it (ID-02).
- **ECH-02** · A generated folder adds `cv_ref` and `genere_le` (modification date of the
  CV PDF), and if it has a letter `lettre_ref` and `lettre_generee_le`. Dates use the
  format `2026-11-17T21:45:48.123Z`, comparable with the page's.

- **ECH-03** · An application with a preparation sheet (PREP-32) adds `preparation`
  (the Markdown text) and `preparation_le` (date of the sheet, same format), whatever its
  status in engine B.

- **ECH-04** · Every entry adds `site_entreprise` and `linkedin_entreprise` when its
  company has them (LNK-02), whatever the source.

- **ECH-05** · Ad text (BASE-14): a generated folder (ECH-02) and an application sent for
  its preparation sheet (ECH-03) add `texte_offre`, the stored ad text, cut to 20,000
  characters, when they have one. Proposals (`notee`) do not
  carry it, to keep the exchange light.
- **ECH-06** · Every other `close` application (Applied) with an ad text is also sent, with
  only `type`, `entreprise`, `poste`, `moteur` = `B`, `texte_offre` (cut as in ECH-05)
  and `archive` = true. Such an entry only fills in a missing text in the page
  (PAGE-31); it never creates a document.

## Page → engine B: `candidatures-export.json`

- **ECH-10** · Accepted as `{"candidatures": [...]}` or directly as the array. A file that
  is not JSON or has no array is rejected with a message. Entries without `id` or
  `statut` are ignored.
- **ECH-11** · Fields read: `id`, `statut`, `consigne`, `lettre_demandee`, `lettre`
  (`oui` / `non` or boolean; missing = no choice), `lettre_refaire_le`,
  `lettre_consigne`, `motif_refus`, `motif_detail`, `preparation_demandee_le`,
  `pretentions`, `entretien_infos`, `preparation_consigne`, `site_entreprise`,
  `linkedin_entreprise` and `liens_manuels` (PAGE-42), and enough to rebuild the ad if `entreprise` and `poste` are
  present (`type`, `lieu`, `url`, `source`, `texte_offre`). The page sends `texte_offre` whenever it has one, whatever the
  status (BASE-14).
- **ECH-12** · `moteur decisions <file>` applies, in this order: adding unknown accepted
  applications (BASE-07); letter choice of accepted, ready or approved applications
  (BASE-08); status decisions (BASE-05, BASE-06); letter regenerations (LET-07); preparation
  requests (BASE-12). It then
  prints the summary and what is left to generate. *(untested)*

## Direct link: MCP server `moteur mcp`

- **ECH-20** · `moteur mcp` runs an MCP server over stdio, named `moteur`, started by the
  Claude desktop app (`mcpServers` of `claude_desktop_config.json`). It exposes exactly the
  four tools below and nothing else: no access to files, the configuration or `.env`.
- **ECH-21** · Tool `propositions` (annotated read-only, no input): returns
  `{"candidatures": [...]}`, the same entries as `pour-la-page.json` (ECH-01, ECH-02),
  read straight from the local database at call time. No file is written.
- **ECH-22** · Tool `decisions` (input: `{"candidatures": [...]}`, the page's documents,
  same format as ECH-10 and ECH-11): applies them exactly like `moteur decisions`
  (ECH-12) and returns the counts: decisions applied, applications added or completed,
  letter choices or regenerations, folders to generate, letters to add, preparations
  requested. Applying the same
  documents twice changes nothing the second time.
- **ECH-23** · An invalid input to `decisions` returns a tool error with the message of
  ECH-10, and changes nothing.
- **ECH-24** · Each call opens the local database and closes it before answering, so
  that `moteur` commands run from a terminal at the same time are not blocked.
- **ECH-25** · The tools never call Claude and never generate a CV or a letter: they
  only read and record (generation stays `moteur generate`, which takes minutes).
- **ECH-26** · Single exception to ECH-25: `decisions` starts `moteur prepare` in the
  background when it records a new preparation request (PREP-41). It does not wait for
  it, and its answer does not depend on it.
- **ECH-27** · Tool `entreprises` (annotated read-only, no input): returns the companies
  followed and User's choices (CAT-10 to CAT-15), read at call time:
  - `entreprises`: for each company `cle` (normalised name, ID-01), `nom`, `origine`
    (`catalogue` or `perso`), `secteur`, `taille`, `pays`, `site`, `recherchee` (searched,
    CAT-13), `actif` and `actif_par_defaut` (its own state and the default, CAT-10),
    `spontanee` and `spontanee_par_defaut` (CAT-14);
  - `secteurs` and `tailles`: for each value of CAT-04 and CAT-03, `cle`, `actif` and the
    number of companies;
  - `sources`: France Travail, Choisir le service public and Station F, with `cle`,
    `nom`, `configuree` (`actif = true` in `config.toml`), `actif` (User's choice) and
    `recherchee` (CAT-15).
- **ECH-28** · Tool `selection` (input: `{"choix": [...]}`, each with `objet` =
  `entreprise`, `secteur`, `taille` or `source`, `cle`, and `actif` and/or `spontanee`
  for a company, `actif` otherwise; `null` means back to the default): records the
  choices (BASE-15) and returns the same answer as `entreprises`. The same choices sent
  twice change nothing the second time.
- **ECH-29** · An invalid input to `selection` (unknown `objet`, unknown key, wrong type)
  returns a tool error naming the faulty choice, and records none of them.
