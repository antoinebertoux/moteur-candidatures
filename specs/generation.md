# CV and cover letter generation

`moteur generate` prepares a folder for each `acceptee` application, from the `../latex/`
repository: CV template, block bank (fr or en), letter skeleton, paragraph bank,
personal instructions and `compiler.sh`. Its expected format is in
[latex-repository.md](latex-repository.md). Writing is done by Claude (Sonnet by default).

## Folder

- **CV-01** · Each application has its folder `Candidatures/<Company> - <Title>/`
  (`<Company> - spontanée/` for an unsolicited one), without characters forbidden in file
  names, at most 100 characters. The name depends only on the company, type and title: a
  regeneration reuses the same folder.
- **CV-02** · The folder contains `offre.md` (company, title, link, source, ad text),
  written on the first generation and never overwritten afterwards. *(untested)*
- **CV-03** · Language: the one detected at scoring (NOT-05); it picks the `banque-fr` or
  `banque-en` bank. Generated files point to `../../latex/` so they compile from their
  folder.

## Where the folder is filed

- **CV-17** · An application's folder (CV-01) sits in one of three places of
  `Candidatures/`, by where the application stands:
  - at the root (`Candidatures/<folder>/`): not sent yet (To review to To send in the
    page) or dropped by User (Rejected);
  - `Candidatures/sent/<folder>/`: applied (`statut` = `postulee`), not refused by the
    company;
  - `Candidatures/hold/<folder>/`: applied, then refused by the company (`suite` =
    `refus`, PAGE-08).
  `sent/old/` (applications of the previous job search, INV-04) is never touched.
- **CV-18** · Each synchronisation with the page (`moteur decisions`, ECH-12, and the
  direct link, ECH-22) files the folder of every document whose `statut` is `postulee`:
  into `hold/` when its `suite` is `refus`, otherwise into `sent/` (so it goes back to
  `sent/` if the refusal is undone). The folder is looked for under its CV-01 name at the
  root, in `sent/` and in `hold/`; `sent/` and `hold/` are created when missing, so a new
  installation needs nothing beforehand. A document without a folder is skipped. Folders
  of documents in any other status are never moved, and a folder is never moved back to
  the root.
- **CV-19** · Filing never loses a file. When the destination folder already exists
  (for example a preparation sheet written at the root by an older version), each file
  of the other copy is moved into it when absent there, dropped when identical, and
  otherwise left where it is with a warning; a copy left empty is removed.
- **CV-20** · After a move, the PDF paths engine B stores for the application
  (`cv_ref`, `lettre_ref`, GEN-02) point to the new place, and so do the CV and Letter
  links it sends to the page from then on.
- **CV-21** · Every step that writes into the folder of an application (generation,
  letter, interview preparation) uses the folder where it is filed (CV-17). When there is
  none yet, generation and letter create it at the root, and an interview preparation
  creates it in `sent/` (an application being prepared for an interview has been sent).

## CV

- **CV-10** · Starting point: the repository's CV template. If there is an edit
  instruction and a `cv.tex` already exists, the existing CV is used instead.
- **CV-11** · Claude receives: the ad (company, title, location, summary, "unsolicited
  application" note when relevant, first 6,000 characters of the text), the language,
  the starting file, the bank, and User's instruction marked as taking priority.
- **CV-12** · Instructions given to Claude for the CV *(untested: instruction to the
  model)*:
  - it only chooses macros from the bank: no free text, no invented experience or macro,
    preamble and structure kept;
  - a single headline, the one whose usage best matches the ad;
  - main experience (LTX-13): every bullet of the bank except those truly off-topic, from
    most to least relevant, since the program removes the last ones;
  - projects: every project of the bank, the most relevant first;
  - then the candidate's own rules from `consignes-cv.md` (LTX-17).
  The candidate-specific rules (minimum number of bullets, interests to show per kind of
  role…) live only in that file, never in the engine.
- **CV-13** · The response must be a complete LaTeX file (`\documentclass` …
  `\end{document}`), otherwise the folder fails.
- **CV-14** · **The CV fits on one page and fills it.** The program compiles the full
  version, then first removes the last projects (keeping one), then the last bullets of
  the main experience (LTX-13, keeping at least 5) until it fits on one page. It then tries to put back, in order, the removed
  items shorter than the first one, and keeps each one that fits.
- **CV-15** · If even the shortest version exceeds one page, the folder is still
  generated and a "to be reworked" warning is printed.
- **CV-16** · The compiled CV is named `cv_<first name>_<last name>.pdf`, both read from
  `\coPrenom` and `\coNom` in `latex/commun/coordonnees.tex` (e.g.
  `cv_Jane_Doe.pdf`); spaces and characters forbidden in file names become `-`. The
  source stays `cv.tex`. If the file or either macro is missing, the PDF keeps the name
  `cv.pdf`.

## Cover letter

- **LET-01** · A letter is written with the CV if it is planned (page choice, otherwise
  ad asking for one, otherwise rule ID-04) or for an unsolicited application; otherwise
  the folder has no letter.
- **LET-02** · The choice made with the page's toggle always wins over the ad's request
  and the default rule.
- **LET-03** · Instructions given to Claude for the letter *(untested: instruction to the
  model)*:
  - skeleton kept; only the content and the company name change;
  - in the ad's language; in English, "Dear Hiring Manager,";
  - four paragraphs: hook (exact role, why this company); one or two achievements of the
    main experience that answer the ad; what the candidate brings beyond technical
    skills; why them, with concrete elements;
  - no invented fact, everything comes from the paragraph bank; no salary or
    expectations;
  - unsolicited: proposes the given role;
  - direct style, no hollow phrases, 250 to 350 words, one page;
  - then the candidate's own rules from `consignes-lettre.md` (LTX-17), which hold every
    candidate-specific rule (claims to avoid, topics kept for some kinds of role…).
- **LET-04** · `moteur letter` adds a letter to an already generated folder **without
  touching the CV**: for the given identifiers, or otherwise for every missing letter
  (BASE-08).
- **LET-05** · An existing letter is used as a starting point only if a letter
  instruction comes with it; otherwise it is rewritten from the skeleton.
- **LET-06** · A letter longer than one page is a failure: the folder keeps no letter. An
  identifier unknown to the database is a failure.
- **LET-07** · "Regenerate the letter" in the page is taken into account only if the
  request is more recent than the current letter PDF; the letter then becomes missing
  again, with the letter instruction if any.

## Compilation and result

- **GEN-01** · Each file is compiled by `latex/compiler.sh <folder> <file>`. A
  compilation failure fails the folder, with the end of the log. `compiler.sh` reports an
  overflow as "`<name>.pdf fait N pages`".
- **GEN-02** · A successful folder becomes `generee` with the paths of its PDFs, relative
  to the root folder (`Candidatures/…/cv_<first name>_<last name>.pdf`, CV-16). A failed folder is listed with the
  reason, stays `acceptee`, and does not block the following ones.
- **GEN-03** · After the folders, `generate` adds the missing letters then exports the
  file for the page automatically. *(untested)*
