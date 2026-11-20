# LaTeX repository

`moteur generate` and `moteur letter` write CVs and letters from the `latex/` folder under
the root folder (CONF-07). That folder belongs to the user and stays outside the
repository (INV-02). The repository ships a working example for a fictional person,
`latex-exemple/`, to copy and adapt: this file is the contract between that folder and
the engine.

## Example shipped with the repository

- **LTX-01** · `latex-exemple/` contains every file of LTX-10, the classes they use (the
  fonts come with TeX Live and are not shipped), both banks (French and English) and both
  personal instruction files (LTX-17), for a fictional person (Jane Doe). It contains no
  personal data.
- **LTX-02** · The example follows LTX-12 to LTX-16: from its CV template the engine finds
  the bullets of the main experience and the projects, from `commun/coordonnees.tex` the
  first and last name.
- **LTX-03** · `moteur init-latex` copies `latex-exemple/` to `latex/` under the root
  folder, then says which files to adapt. It refuses, without changing anything, if
  `latex/` already exists.
- **LTX-04** · The example compiles to a one-page CV and a one-page letter, in French and
  in English. *(untested: needs a TeX installation, absent from CI; checked by hand)*

## Expected files

- **LTX-10** · Required files: `compiler.sh`, `commun/coordonnees.tex`,
  `cv/modele-cv.tex`, `lettres/modele-lettre.tex`, `lettres/banque-paragraphes.md`.
  Before preparing any folder, `generate` and `letter` check they exist; if one is
  missing they stop with the list of missing files and point to `moteur init-latex`,
  without changing any application. The bank of a language (`cv/banque-fr.tex`,
  `cv/banque-en.tex`) is needed only by the applications in that language: if it is
  missing, those folders fail with the bank's name (GEN-02) and the others carry on.
- **LTX-11** · `compiler.sh <folder> <file>` compiles the file inside the folder, returns
  a non-zero exit code on failure, and prints "`<name>.pdf fait N pages`" when the PDF has
  more than one page (GEN-01). The example's script uses `latexmk`, XeLaTeX and `pdfinfo`.
- **LTX-12** · The CV template has a `\def\latexroot{…}` line and loads its bank through
  a path containing `cv/banque-fr` or `cv/banque-en`; the engine rewrites both for the
  application's folder and language (CV-03).
- **LTX-13** · The **main experience** is the first `\explanationdetail{…}` after
  `\section{\secExperience}`: its bullets are bank macros named `\p` followed by a
  capital letter (`\pRAG`), separated by `\\`. The **projects** are macros named `\proj`
  followed by a capital letter, between `\section{\secProjets}` and the next `\section`.
  Commented-out lines (`%`) never count as these sections. These are what CV-14 removes to
  fit one page; a CV without them is compiled as written, without reduction.
- **LTX-14** · In a bank every block is a macro (`\newcommand`). Each headline is preceded
  by a `% Usage : …` comment saying which ads it suits; Claude picks the headline from it
  (CV-12).
- **LTX-15** · `commun/coordonnees.tex` defines `\coPrenom` and `\coNom` with
  `\newcommand` (CV-16), plus whatever contact macros the templates use.
- **LTX-16** · The letter skeleton writes the company in `\companyname{…}` and each
  paragraph in a `\lettercontent{…}` (LET-03).
- **LTX-17** · Personal instructions: `consignes-cv.md` and `consignes-lettre.md`, at the
  root of `latex/`, are optional. Their text is given to Claude after the general rules of
  CV-12 (CV) or LET-03 (letter), marked as the candidate's own rules. A missing or empty
  file adds nothing.
