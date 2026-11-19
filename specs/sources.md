# Sources

Each source returns a list of job ads (company, title, location, link, source, text,
salary, publication date), without calling Claude. A field the source does not provide
stays empty.

## General

- **SRC-01** · An unexpected response from a site (missing field, wrong type, unreadable
  feed) does not crash the source: unusable entries are skipped, and an ad without a
  title is never kept.
- **SRC-02** · HTML in ad texts is turned into plain text, HTML entities (even
  double-escaped) decoded, whitespace collapsed.
- **SRC-03** · HTTP calls identify themselves as `moteur-candidatures/0.1 (usage
  personnel)`, follow redirects and give up after 20 s. An HTTP error becomes a source
  error quoting the status code and the start of the response. *(untested)*
- **SRC-04** · "Too many requests" (HTTP 429) is retried at most twice, after waiting
  the delay given by the site (`Retry-After`, capped at 30 s) or 5 s otherwise. Still
  429 after that: source error (SRC-03).
- **SRC-06** · A server error (HTTP 500 to 599) is retried once, after 2 s. Still an
  error after that: source error (SRC-03).
- **SRC-05** · A source running several searches (Choisir le service public: one per
  keyword and pass; Workday: one per keyword) runs them in parallel, at most 4 at a time.
  The pages of one search are read in order. The result does not depend on which search
  answers first: ads are merged in the order of the searches, then deduplicated.

## France Travail

- **SRC-10** · Active only if `[france_travail] actif = true` **and**
  `FRANCE_TRAVAIL_ID` and `FRANCE_TRAVAIL_SECRET` are set; otherwise it is skipped with a
  warning. *(untested)*
- **SRC-11** · Gets an OAuth token, then runs one search per keyword and per département
  (or one per keyword if no département), limited to ads published in the last
  `publiee_depuis` days, at most 150 results per search. Without a token in the
  response, the source fails.
- **SRC-12** · Missing company → "Entreprise non précisée". Link: the original ad if the
  API provides it, otherwise the ad page on France Travail. The salary label is kept as
  is for the filter.

## Choisir le service public

- **SRC-20** · No credentials. Each keyword is searched on the whole site, then again
  among the tracked employers only (the general search is sorted by relevance and could
  miss them). Domains, if any, filter both passes.
- **SRC-21** · The search address follows the order imposed by the site:
  `mot-cles/…/domaine/…/organisme/…/page/n/`.
- **SRC-22** · Pagination: 20 ads per page; stops as soon as a page is incomplete, the
  announced total is reached or `pages_max` pages are read.
- **SRC-23** · From a result card: employer ("Fonction publique" if missing), location,
  date "En ligne depuis le 16 novembre 2026" converted to `2026-11-16`. The same ad
  (same link) is kept only once.
- **SRC-24** · Results do not include the ad text: the page of each **retained** ad is
  opened to fetch the missions and profile, one paragraph per line.

## Career pages (ATS)

- **SRC-30** · Address queried for each tool, from the identifier:

  | ATS | Address |
  | --- | --- |
  | greenhouse | `boards-api.greenhouse.io/v1/boards/<id>/jobs?content=true` |
  | lever | `api.lever.co/v0/postings/<id>?mode=json` |
  | ashby | `api.ashbyhq.com/posting-api/job-board/<id>` |
  | smartrecruiters | `api.smartrecruiters.com/v1/companies/<id>/postings?limit=100` |
  | recruitee | `<id>.recruitee.com/api/offers/` |
  | teamtailor | `<id>.teamtailor.com/jobs.rss` (RSS feed) |
  | workable | `apply.workable.com/api/v1/widget/accounts/<id>?details=true` |

  A company without a supported ATS cannot become a source.
- **SRC-31** · Each ATS provides title, location, link and, when available, the text and
  publication date (YYYY-MM-DD). SmartRecruiters gives no text; its link is rebuilt as
  `jobs.smartrecruiters.com/<id>/<ad>` and its location as "City, COUNTRY".
- **SRC-32** · Workable: the location is "City, Country" (the first non-empty of the
  ad's fields and of its first listed location), followed by "Remote" when the ad allows
  remote work; the date is `published_on`.

## Workday

- **SRC-40** · The identifier is the career page address as shown in the browser
  (`https://<tenant>.wdN.myworkdayjobs.com/[fr-FR/]<site>`); the language segment is
  ignored. An address outside `myworkdayjobs.com` is rejected.
- **SRC-41** · Workday does not list everything: each of the company's keywords (by
  default "machine learning", "intelligence artificielle", "data scientist") is searched,
  20 ads per page, at most 5 pages. An ad found by several keywords is kept only once.
  Search results give no ad text (see SRC-42).
- **SRC-42** · The page of each **retained** ad is opened (as in SRC-24) through the site's
  public detail address (`/wday/cxs/<tenant>/<site>/job/<path>`): its description
  (plain, SRC-02) becomes the ad text. An unreadable detail leaves the ad without text.

## Radancy (TalentBrew)

Career sites built on Radancy (for instance Moody's). Their search is forbidden to
robots by `robots.txt`; the sitemap and the ad pages are allowed.

- **SRC-50** · The identifier is the career site host (`careers.example.com`). The source
  reads `https://<host>/sitemap.xml` and keeps the addresses of the form
  `…/job/<city>/<title>/<organisation>/<number>`: the title and the location come from
  those two segments (hyphens become spaces, each word capitalised). Any other address
  is ignored; an unreadable sitemap gives no ad.
- **SRC-51** · The page of each **retained** ad is opened (as in SRC-24): its
  `JobPosting` data gives the exact title, the text (plain, SRC-02) and the publication
  date. A page without that data leaves the ad unchanged.


## Welcome Kit

Career sites that Welcome to the Jungle hosts for a company (for instance
`jobs.zama.org`). `robots.txt` allows everything. The Welcome to the Jungle site itself
refuses automated requests (HTTP 403) and is not used.

- **SRC-60** · The identifier is the career site host. The source reads its home page
  and keeps each job link (`/jobs/<slug>` with its listed title); the spontaneous
  application link is ignored, and an ad listed twice is kept once. The provisional
  location is the part of the slug after the last `_` (hyphens become spaces, each word
  capitalised). An unreadable page gives no ad.
- **SRC-61** · The page of each **retained** ad is opened (as in SRC-24): its main
  title, its location and the text of its "about", "description", "profile" and "more"
  blocks (plain, SRC-02) replace the provisional values. A page without those blocks
  leaves the ad unchanged.
