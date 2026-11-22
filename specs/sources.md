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
  keyword and pass; Workday, Oracle, SuccessFactors, Phenom, Avature: one per keyword)
  runs them in parallel, at most 4 at a time.
  The pages of one search are read in order. The result does not depend on which search
  answers first: ads are merged in the order of the searches, then deduplicated.

## France Travail

- **SRC-10** · Active only if `[france_travail] actif = true` **and**
  `FRANCE_TRAVAIL_ID` and `FRANCE_TRAVAIL_SECRET` are set; otherwise it is skipped with a
  warning. *(untested)*
- **SRC-11** · Gets an OAuth token, then runs one search per keyword (CONF-11) and per département
  (or one per keyword if no département), limited to ads published in the last
  `publiee_depuis` days, at most 150 results per search. Without a token in the
  response, the source fails.
- **SRC-12** · Missing company → "Entreprise non précisée". Link: the original ad if the
  API provides it, otherwise the ad page on France Travail. The salary label is kept as
  is for the filter.

## Choisir le service public

- **SRC-20** · No credentials. Each keyword (CONF-11) is searched on the whole site, then again
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

  Workday, Radancy, Welcome Kit, Talentsoft, Oracle, SuccessFactors, Phenom and Avature
  have sections of their own below. A company without a supported ATS cannot become a
  source.
- **SRC-33** · Greenhouse boards hosted in Europe: an identifier written `eu:<id>` is
  queried at `boards-api.eu.greenhouse.io/v1/boards/<id>/jobs?content=true`.
- **SRC-34** · Teamtailor career sites on the company's own domain: an identifier that
  contains a dot is the site's host (`careers.example.com`), and its feed is read at
  `<host>/jobs.rss`.
- **SRC-35** · SmartRecruiters searches: the plain address of SRC-30 gives only a
  company's 100 most recent ads, worldwide, which misses most of a large group's board.
  Two settings narrow the request: the terms of `[criteres] recherches` (CONF-11,
  `q=<keyword>`, full-text: the site matches it in titles and texts) and the countries
  of `[criteres] pays` (`country=<code>`; the site accepts one country per request).
  One search is run per keyword and per country (per keyword only when `pays` is
  empty), 100 ads per page (`offset`), at
  most 5 pages; a search stops when a page is incomplete or the announced total
  (`totalFound`) is reached. Searches run as in SRC-05. An ad found by several searches
  (same SmartRecruiters id) is kept once.
  The location filter (`lieux`) still applies to the ads found; an ad of another country
  is not requested at all, even if it allows remote work.
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
- **SRC-41** · Workday does not list everything: each term of `[criteres] recherches`
  (CONF-11) is searched,
  20 ads per page, at most 5 pages. An ad found by several keywords is kept only once.
  Search results give no ad text (see SRC-42).
- **SRC-42** · The page of each **retained** ad is opened (as in SRC-24) through the site's
  public detail address (`/wday/cxs/<tenant>/<site>/job/<path>`): its description
  (plain, SRC-02) becomes the ad text. An unreadable detail leaves the ad without text.
- **SRC-43** · Workday sites answer "too many requests" (HTTP 429) to bursts, for a few
  seconds, which SRC-04's short waits do not always cover. A search page still refused
  with 429 after SRC-04 is asked again after a 30 s pause, at most twice; only then does
  the source fail (SRC-03).

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

## Station F

The Station F job board (`jobs.stationf.co`) gathers the ads of the start-ups hosted at
Station F. It is a Welcome Kit site: its search page queries Algolia with a public
search key that the page itself publishes, restricted to the board's ads. `robots.txt`
allows everything.

- **SRC-70** · Active only if `[station_f] actif = true`. No credentials: at each run the
  source reads the search key from `https://jobs.stationf.co/search` (hidden field
  `algolia_api_key`), since it may change. A page without that key: source error.
- **SRC-71** · One search per keyword (CONF-11) on the index
  `wk_cms_jobs_production_careers` (application `CSEKHVMS53`), 50 ads per page, at most
  `pages_max` pages; it stops after the last page announced by the site. Searches run as
  in SRC-05. An ad found by several keywords (same Algolia identifier) is kept once.
- **SRC-72** · Kept only: ads published in the last `publiee_depuis` days, and whose
  contract is neither an internship (`INTERNSHIP`) nor an apprenticeship
  (`APPRENTICESHIP`). An ad without a readable publication date is kept.
- **SRC-73** · From each result: company = the organisation's name; title = the ad's
  name; location = the office city, followed by « télétravail total », « télétravail
  partiel » or « télétravail ponctuel » (`remote` = `fulltime`, `partial`, `punctual`);
  link = `https://jobs.stationf.co/companies/<organisation slug>/jobs/<ad slug>`; date =
  the day of `published_at` (YYYY-MM-DD); salary, from the yearly bounds, written like
  France Travail's so that the salary floor applies: « Annuel de <min> Euros à <max>
  Euros », « Annuel jusqu'à <max> Euros », or « À partir de <min> Euros par an » (a lower
  bound alone never rejects an ad); provisional text = the profile (plain, SRC-02), preceded by
  « Expérience demandée : N ans. » when the site gives a minimum.
- **SRC-74** · The page of each **retained** ad is opened and read as in SRC-61; its text
  replaces the provisional one, preceded by the same experience sentence. A page without
  text blocks leaves the ad unchanged.

## Magnet by Hellowork

Career sites built on Magnet by Hellowork (formerly CVCatcher, for instance
`jobs.fivesgroup.com`). The page reads its ads from `api.magnet.work` with a short-lived
anonymous token: every visitor's browser gets one by sending the site's public key,
published in the page itself, and the current time. No account is involved.
`robots.txt` allows everything.

- **SRC-75** · The identifier is the career site host. The source reads
  `https://<host>/` and takes its public key (`"publicKey": "…"`); a page without one
  is a source error. It then asks `https://api.magnet.work/v2/security/login` for a
  token, sending the key and the current UTC time (ISO 8601), each in base64, as the
  page does; an answer without a token is a source error.
- **SRC-76** · With that token, the source reads every ad of the site from
  `/v2/job-offers` (no filter: the site lists all its ads with their text), 100 per
  page, at most 20 pages; it stops at an incomplete page or once the announced total
  (`total`) is reached.
- **SRC-77** · From each ad: title; location = city and country of its first place
  (« Yvetot, France »); text = its description (plain, SRC-02); date = the day of
  `publication_date`; link = `https://<host>/<language>/offer/<id>` (language of the ad,
  `fr` when missing). An ad without a title or an id is skipped (SRC-01).

## Talentsoft (Cegid)

Career sites built on Talentsoft (for instance `casa-cacib-recrute.talent-soft.com` for
Crédit Agricole CIB, or `carriere.dassault-aviation.com`). Each one publishes all its ads,
with their full text, in one public RSS feed.

- **SRC-80** · The identifier is the career site host. The source reads
  `https://<host>/handlers/offerRss.ashx?LCID=1036&top=1000` (the feed holds only 20
  ads without `top`). An unreadable feed gives no ad.
- **SRC-81** · From each item: title = the item's title without its reference prefix
  (`2026-110801 - Originateur H/F` → `Originateur H/F`); link = the item's link; text =
  its description (plain, SRC-02); date = the day of `pubDate` (YYYY-MM-DD); location =
  the item's third `category` (the first two are the job family and the contract), empty
  when there are fewer than three.

## Oracle Recruiting Cloud

Career sites of Oracle's recruiting tool (for instance Technip Energies,
`hcxg.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1`). The page itself
queries a public search address of the same host.

- **SRC-85** · The identifier is the career page address as shown in the browser
  (`https://<host>/hcmUI/CandidateExperience/<language>/sites/<site>`, anything after the
  site ignored). An address without `/sites/<site>` is rejected.
- **SRC-86** · Each term of `[criteres] recherches` (CONF-11) is searched at
  `https://<host>/hcmRestApi/resources/latest/recruitingCEJobRequisitions`, 25 ads per
  page, at most 5 pages; a search stops when a page is incomplete or the announced total
  (`TotalJobsCount`) is reached. Searches run as in SRC-05. An ad found by several
  keywords (same `Id`) is kept once.
- **SRC-87** · From each result: title = `Title`, location = `PrimaryLocation`, date =
  `PostedDate`, no text (see SRC-88), link =
  `https://<host>/hcmUI/CandidateExperience/<language>/sites/<site>/job/<Id>`.
- **SRC-88** · The details of each **retained** ad are read (as in SRC-24) from
  `recruitingCEJobRequisitionDetails` on the same host: its description,
  responsibilities and qualifications (plain, SRC-02), one after the other, become the
  ad text. Unreadable details leave the ad without text.

## SAP SuccessFactors

Career sites built with SuccessFactors' site builder (for instance
`jobsearch.alstom.com`, `careers.idemia.com`). Their search page is allowed to robots;
their RSS feeds (`/services/`) are not.

- **SRC-90** · The identifier is the career site host. Each term of `[criteres]
  recherches` (CONF-11) is searched at `https://<host>/search/?q=<term>&startrow=<n>`,
  and, when `[criteres] pays` is set, once per country with
  `optionsFacetsDD_country=<CODE>` (upper case), as in SRC-35. 25 ads per page, at most 5
  pages; a search stops when a page has fewer than 25 ads or the announced total
  (« Results 1 – 25 of N ») is reached. Searches run as in SRC-05. An ad found by several
  searches (same link) is kept once.
- **SRC-91** · From each result row: title and link (`https://<host>/job/…`) from the
  title link, location from the location column ("City, FR, 92400"); the date is left
  empty, since its format depends on the site's language.
- **SRC-92** · The page of each **retained** ad is opened (as in SRC-24): its
  `jobdescription` block (plain, SRC-02) becomes the ad text. A page without that block
  leaves the ad unchanged.

## Phenom

Career sites built on Phenom (for instance `careers.bcg.com/global/en`). The page
queries a public search address of the same host, `/widgets`, which `robots.txt` allows.

- **SRC-94** · The identifier is the career site address with its country and language
  (`careers.bcg.com/global/en`): these two path segments give the search's `country`
  (`global`) and `lang` (`en_global`). An address without them is rejected.
- **SRC-95** · Each term of `[criteres] recherches` (CONF-11) is searched with a POST to
  `https://<host>/widgets` (`ddoKey` = `refineSearch`), 50 ads per page, at most 5 pages;
  a search stops when a page is incomplete or the announced total (`totalHits`) is
  reached. Searches run as in SRC-05. An ad found by several keywords (same `jobId`) is
  kept once. From each result: title, location (`location`, otherwise `city`), date (the
  day of `postedDate`), link = `https://<host>/<country>/<language>/job/<jobId>`.
- **SRC-96** · The page of each **retained** ad is opened and read as in SRC-51
  (`JobPosting` data: title, text, date). A page without that data leaves the ad
  unchanged.

## Avature

Career sites built on Avature (for instance `jobs.orano.group/fr_FR/jobs`). Their search page shows 6 ads at a time; their
RSS feed gives the first 20 ads of a search.

- **SRC-97** · The identifier is the career portal address (`<host>/<locale>/<portal>`).
  Each term of `[criteres] recherches` (CONF-11) is searched once through the feed
  `https://<host>/<locale>/<portal>/SearchJobs/feed/?search=<term>`, so at most 20 ads
  per term. Searches run as in SRC-05. An ad found by several keywords (same link) is
  kept once. From each item: title, link, date (the day of `pubDate`); no location nor
  text.
- **SRC-98** · The page of each **retained** ad is opened (as in SRC-24). Its fields
  (label, value) give the location, « City, Country » (fields `City` and `Country`), and
  the text: the values of 100 characters or more (plain, SRC-02), one after the other. A
  page without fields leaves the ad unchanged.
