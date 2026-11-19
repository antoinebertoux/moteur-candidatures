# Collection and filter

`moteur collecter` queries the sources, keeps the ads that pass the filter, then
proposes unsolicited applications. No call to Claude.

## Collection

- **COL-01** · A failing source is reported and skipped: the others carry on.
- **COL-02** · Order: query every source → filter → open the page of the retained ads
  only, when their text is missing (SRC-24) → add unsolicited applications. If a page
  cannot be opened, the ad is kept without text.
- **COL-03** · An unsolicited application is proposed for each tracked company marked
  `spontanee = true` that has **no retained ad** in this collection and has **never been
  seen** (neither in the local database nor in `suivi/entreprises_vues.csv`). Its title
  is `role_spontane`, its link the company website, its source `cible`.
- **COL-04** · `suivi/entreprises_vues.csv` (`;` separator, `entreprise` column) is
  optional. Rows whose status column contains "historique" (previous job search) are
  ignored: those companies can be proposed again.
- **COL-05** · Every company already in the local database, whatever its status, counts
  as seen.
- **COL-06** · The command prints the number of retained ads and, among them, the number
  of new ones. *(untested)*

## Filter

Only the title, location and salary matter, on whole words (ID-03). **Missing
information never gets an ad rejected.**

- **FILT-01** · If keywords are configured, the title must contain at least one.
- **FILT-02** · A title containing an exclusion (stage, alternance, intern…) is rejected.
- **FILT-03** · If locations are configured, an ad with a known location must contain one
  of them; an ad without location passes.
- **FILT-04** · Salary: an ad is rejected only if its **displayed annual maximum** is
  below the floor. Understood labels: "Annuel de X Euros à Y Euros…" and "Mensuel de X
  Euros sur N mois" (×12 if N is missing). An unreadable or missing salary passes. Floor
  at 0 = no filter.
- **FILT-05** · Two ads with the same identifier (ID-02): only the first is kept.
