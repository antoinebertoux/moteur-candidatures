# CV and cover letter generation

`moteur generer` prepares a folder for each `acceptee` application, from the `../latex/`
repository: CV template, block bank (fr or en), letter skeleton, paragraph bank and
`compiler.sh`. Writing is done by Claude (Sonnet by default).

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

## CV

- **CV-10** · Starting point: the repository's CV template. If there is an edit
  instruction and a `cv.tex` already exists, the existing CV is used instead.
- **CV-11** · Claude receives: the ad (company, title, location, summary, "unsolicited
  application" note when relevant, first 6,000 characters of the text), the language,
  the starting file, the bank, and Antoine's instruction marked as taking priority.
- **CV-12** · Instructions given to Claude for the CV *(untested: instruction to the
  model)*:
  - it only chooses macros from the bank: no free text, no invented experience or macro,
    preamble and structure kept;
  - a single headline, the one whose usage best matches the ad;
  - Eurofins: every bullet except those truly off-topic (at least 7), from most to least
    relevant;
  - both academic projects, the most relevant first;
  - interests: climbing and games; geopolitics only for a defence-focused role (DGSE,
    Armées, DGA, AID, defence industry), never elsewhere.
- **CV-13** · The response must be a complete LaTeX file (`\documentclass` …
  `\end{document}`), otherwise the folder fails.
- **CV-14** · **The CV fits on one page and fills it.** The program compiles the full
  version, then first removes the second project, then the last Eurofins bullets (keeping
  at least 5) until it fits on one page. It then tries to put back, in order, the removed
  items shorter than the first one, and keeps each one that fits.
- **CV-15** · If even the shortest version exceeds one page, the folder is still
  generated and a "to be reworked" warning is printed.

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
  - four paragraphs: hook (exact role, why this company); one or two Eurofins
    achievements that answer the ad; what he brings beyond technical skills; why them,
    with concrete elements;
  - no invented fact, everything comes from the paragraph bank; never "certified in
    generative AI"; no salary or expectations; geopolitics or Le Collimateur only for a
    defence-focused role;
  - unsolicited: proposes the given role;
  - direct style, no hollow phrases, 250 to 350 words, one page.
- **LET-04** · `moteur lettre` adds a letter to an already generated folder **without
  touching the CV**: for the given identifiers, or otherwise for every missing letter
  (BASE-08).
- **LET-05** · An existing letter is used as a starting point only if a letter
  instruction comes with it; otherwise it is rewritten from the skeleton.
- **LET-06** · A letter longer than one page is a failure: the folder keeps no letter. An
  identifier unknown to the database is a failure.
- **LET-07** · "Régénérer la lettre" in the page is taken into account only if the
  request is more recent than the current letter PDF; the letter then becomes missing
  again, with the letter instruction if any.

## Compilation and result

- **GEN-01** · Each file is compiled by `latex/compiler.sh <folder> <file>`. A
  compilation failure fails the folder, with the end of the log. `compiler.sh` reports an
  overflow as "`<name>.pdf fait N pages`".
- **GEN-02** · A successful folder becomes `generee` with the paths of its PDFs, relative
  to the root folder (`Candidatures/…/cv.pdf`). A failed folder is listed with the
  reason, stays `acceptee`, and does not block the following ones.
- **GEN-03** · After the folders, `generer` adds the missing letters then exports the
  file for the page automatically. *(untested)*
