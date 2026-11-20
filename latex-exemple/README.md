# LaTeX example (fictional person: Jane Doe)

Starting point for the `latex/` folder the engine writes CVs and letters from. Copy it
with `uv run moteur init-latex`, then replace Jane Doe with yourself. The format the
engine expects is described in [`specs/latex-repository.md`](../specs/latex-repository.md).

| File | Role |
| --- | --- |
| `compiler.sh` | compiles a folder with `latexmk -xelatex`, reports "`<name>.pdf fait N pages`" |
| `commun/coordonnees.tex` | contact details, `\coPrenom` and `\coNom` (they name the PDF) |
| `cv/jobcv.cls` | CV class; `\setphoto{…}` adds an optional photo |
| `cv/modele-cv.tex` | reference CV |
| `cv/banque-fr.tex`, `cv/banque-en.tex` | every CV block, same macro names in both languages |
| `lettres/lettre.cls` | letter class (Lato and Raleway fonts from TeX Live) |
| `lettres/modele-lettre.tex` | letter skeleton: `\companyname{…}`, `\lettercontent{…}` |
| `lettres/banque-paragraphes.md` | letter paragraphs Claude draws from |
| `consignes-cv.md`, `consignes-lettre.md` | your own rules for Claude, optional |

Compile the reference CV by hand to check your changes:

```bash
./compiler.sh cv modele-cv.tex
```
