# Company links

Each application can carry the exact address of the company website
(`site_entreprise`) and of its LinkedIn page (`linkedin_entreprise`). When one is
missing, the page falls back to the computed search links of PAGE-41.

Links belong to the **company**, not to the application: they are found once and shared
by every application of that company.

## Where the links come from

- **LNK-01** · Engine B keeps one record per company, keyed by the company name
  normalised as in ID-01, holding its website, its LinkedIn page, where each comes from,
  and the date of the last lookup (LNK-10).
- **LNK-02** · Sources, from strongest to weakest: User's correction in the page
  (PAGE-42) → the company in `config.toml` or in the catalogue (`site`, `linkedin`,
  CONF-09, CAT-02; the own company wins, CAT-06) → the
  lookup by Claude (LNK-10). A weaker source never replaces a link set by a stronger one.
  Each link (website, LinkedIn) is handled on its own.
- **LNK-03** · A link from the lookup is kept only if it has the expected form, otherwise
  it is dropped (as if not found):
  - LinkedIn: `https://<any>.linkedin.com/company/<name>`, stored as
    `https://www.linkedin.com/company/<name>/` (query and fragment removed);
  - website: an http(s) address whose host is not a job board, a recruiting tool, a
    social network or an encyclopedia (LinkedIn, Welcome to the Jungle, Indeed,
    Glassdoor, the tools of CONF-04, Wikipedia…), stored reduced to
    `https://<host>/`.

## Lookup by Claude

- **LNK-10** · `moteur links` looks up the companies of the applications sent to the page
  (BASE-04) and of accepted ones, when at least one of their two links is missing from
  every source and they have not been looked up in the last 30 days. Companies are sent
  in batches of 10, one call per batch. *(untested: network; selection checked by LNK-11)*
- **LNK-11** · Selection: a company already complete, or looked up less than 30 days
  ago, is not sent again; a company looked up but not found is retried after 30 days.
- **LNK-12** · The call uses the scoring model (`[modeles] notation`, Haiku by default)
  with the **WebSearch** tool only (CLA-04). For each company, Claude receives only its
  name and, to tell it from a namesake, the title, location and link of one of its ads.
  Never the profile, the CV, the notes nor the salary floor.
- **LNK-13** · Claude answers with a JSON array of `{entreprise, site, linkedin}`, a
  field left empty when not sure. *(untested: instruction to the model; reading checked by
  LNK-14)*
- **LNK-14** · Reading the response: an entry for a company that was not asked is
  ignored; each link goes through LNK-03; the lookup date is recorded for every company
  of the batch, found or not. A response that is not an array fails the batch: nothing is
  recorded, it is retried on the next run, and the other batches carry on.
- **LNK-15** · `moteur daily` runs `links` after `score` and before `export`. A
  failed lookup never stops the daily run.
