---
name: trouver-entreprises
description: Find companies for User's job search and add them to engine B (the "moteur" MCP server). Use when User asks to add, follow, find or suggest companies, employers, start-ups or SMEs to search for jobs ("ajoute Doctolib", "trouve-moi des PME de cybersécurité à Lyon", "quelles boîtes suivre en imagerie médicale ?"), or to stop following one.
---

# Finding companies for engine B

Engine B collects job ads from companies' career pages. It already ships a catalogue of
large groups and public bodies; User's **own companies** (start-ups, SMEs, anything else)
are added through the `moteur` MCP tools. User never writes a recruiting tool or an
identifier: that is your job. Rules: `specs/catalogue.md`, CAT-20 to CAT-34.

Talk to User in their language (French, usually). Keep tool inputs exactly as described
below: their keys are French.

## 1. Read what is already followed (CAT-30)

Call `entreprises` first. Each company has `cle`, `nom`, `origine` (`catalogue` or
`perso`), `secteur`, `taille`, `recherchee`, `actif`. Then:

- a company already followed and searched: tell User, do not add it again;
- a company followed but not searched (`recherchee` false): tell User why (`raison`:
  `choix`, `pays`, `secteur`, `taille`) and offer to turn it on with `selection`
  (`{"objet": "entreprise", "cle": …, "actif": true}`), or its sector or size;
- a catalogue company cannot be added: turn it on instead.

## 2. Find the companies (CAT-31)

- **A company named by User**: go straight to step 3.
- **A description** ("start-ups in medical imaging", "cybersecurity SMEs in Lyon"):
  search the web and gather candidates. Show User a short list, each with its size,
  sector, city and one line on why it fits. Add only those User keeps. Prefer companies
  that are hiring now, and that hire in User's country.

## 3. Find the recruiting tool (CAT-32)

Look for the company's career page ("careers", "jobs", "recrutement", "nous rejoindre")
and the tool behind it. Supported tools and what `identifiant` is:

| `ats` | Career page address | `identifiant` |
| --- | --- | --- |
| `greenhouse` | `job-boards.greenhouse.io/<id>`, `boards.greenhouse.io/<id>` | `<id>` |
| `greenhouse` (Europe) | `job-boards.eu.greenhouse.io/<id>` | `eu:<id>` |
| `lever` | `jobs.lever.co/<id>` | `<id>` |
| `ashby` | `jobs.ashbyhq.com/<id>` | `<id>` |
| `smartrecruiters` | `jobs.smartrecruiters.com/<id>` | `<id>` |
| `recruitee` | `<id>.recruitee.com` | `<id>` |
| `teamtailor` | `<id>.teamtailor.com`, or the company's own career host | `<id>`, or the host |
| `workable` | `apply.workable.com/<id>` | `<id>` |
| `workday` | `https://<tenant>.wd3.myworkdayjobs.com/<site>` | the full address |
| `radancy` | a Radancy career site (e.g. `careers.moodys.com`) | the site's address |
| `welcomekit` | a career page hosted by Welcome to the Jungle (e.g. `jobs.zama.org`) | that address |
| `talentsoft` | a Talentsoft (Cegid) site: `<x>.talent-soft.com`, or the company's own host serving `/offre-de-emploi/` pages | the host |
| `oracle` | `https://<host>.oraclecloud.com/hcmUI/CandidateExperience/<lang>/sites/<site>` | that address |
| `successfactors` | a SuccessFactors career site (ad links `/job/<City>-<Title>/<number>/`, e.g. `jobsearch.alstom.com`) | the host |
| `phenom` | a Phenom career site (e.g. `careers.bcg.com/global/en`) | the address with its country and language |
| `avature` | an Avature portal (e.g. `jobs.orano.group/fr_FR/jobs`) | the portal's address |
| `magnet` | a Magnet by Hellowork career site (calls `api.magnet.work`, e.g. `jobs.fivesgroup.com`) | the host |
| `gestmax` | a Gestmax career site (`<x>.gestmax.fr`) | the address of its search list of every ad (`<x>.gestmax.fr/search/index/frontsearchtab_id/<n>`, or `<x>.gestmax.fr/search/index` when the list is a table) |
| `sncf` | the SNCF group's site, `emploi.sncf.com` | the group company's number in the site's « company » filter (`6684` SNCF Réseau, `6685` SNCF Voyageurs) |
| `taleez` | a Taleez career site (`<x>.taleez.com`, ad links `taleez.com/apply/…`) | the host (e.g. `tehtris.taleez.com`) |
| `werecruit` | a WeRecruit career site (`careers.werecruit.io/<language>/<company>`) | that address with its language, as shown in the browser (e.g. `careers.werecruit.io/en/unseenlabs`) |
| `cornerstone` | a Cornerstone OnDemand career site (`<x>.csod.com/ux/ats/careersite/<n>/home?c=<x>`) | that address, as shown in the browser |
| `rippling` | a Rippling career site (`ats.rippling.com/<board>/jobs`) | that address, as shown in the browser |
| `talentry` | a Talentry career site (ad links `<host>/our-offers/<id>`, e.g. `fr.jobs.cerbahealthcare.com`) | the host |
| `join` | a JOIN career page (`join.com/companies/<company>`) | that address, as shown in the browser |
| `sitemap` | an in-house career site whose `robots.txt` sitemap lists every offer, each page holding `JobPosting` data | the address the offers sit under (e.g. `careers.societegenerale.com/offres-d-emploi/`) |

When you are not sure of the identifier, give the career page as `adresse` instead of
`ats` and `identifiant`: engine B finds the tool in the page. A company whose career page
uses none of these tools (its own form, a plain e-mail address, LinkedIn only) cannot be
followed: tell User, with its career page, and do not add it.

## 4. Add them (ECH-30)

Call `ajouter_entreprises` with 1 to 20 companies:

```json
{"entreprises": [
  {"nom": "Exemple Santé", "ats": "greenhouse", "identifiant": "exemplesante",
   "secteur": "sante", "taille": "pme", "site": "https://exemple-sante.fr",
   "pays": ["fr", "de"]},
  {"nom": "Exemple Numérique", "adresse": "https://exemple.fr/carrieres",
   "secteur": "numerique", "taille": "startup"}
]}
```

- `nom`, `secteur`, `taille` are required, plus either `ats` and `identifiant`, or
  `adresse`. `site`, `linkedin` (http(s) addresses) and `pays` (two-letter codes of the
  countries where it hires) are optional.
- `taille`: `public` (State, local authorities, public bodies, public research),
  `grand-groupe` (500 employees or more), `pme` (fewer than 500), `startup`.
- `secteur`, exactly one of: `administration`, `defense`, `aeronautique-spatial`,
  `naval-maritime`, `cybersecurite`, `energie`, `environnement`, `sante`,
  `pharmacie-biotech`, `banque`, `assurance`, `industrie`, `automobile`,
  `chimie-materiaux`, `electronique-semiconducteurs`, `transport-logistique`,
  `numerique`, `telecommunications`, `jeux-video`, `commerce-distribution`, `luxe-mode`,
  `medias-culture`, `tourisme-hotellerie`, `recherche-enseignement`, `conseil`, `esn`,
  `interim-rh`, `btp-immobilier`, `agroalimentaire`, `economie-sociale`.
- Never send `spontanee` nor `recherches`. To propose an unsolicited application to a
  company, once added, use `selection` (`{"objet": "entreprise", "cle": …,
  "spontanee": true}`) if User asks for it.

## 5. Report (CAT-33)

Each result has `statut`: `ajoutee`, `mise_a_jour` or `refusee`. Tell User, briefly,
the companies added with their number of ads right now (`annonces`; zero is fine: the
company may simply not be hiring), and each refusal with its `raison`. Retry a refused
company only with new information (another career page, another identifier), never the
same input. The ads themselves arrive with the next collection.

## Removing a company

`retirer_entreprises` with `{"cles": [...]}` stops following User's own companies (keys
from `entreprises`). Catalogue companies cannot be removed: untick them with `selection`
(`"actif": false`).
