#!/usr/bin/env bash
# Compile le CV et la lettre d'un dossier de candidature (ou un modèle).
# Usage : ./compiler.sh "../Candidatures/Nom Entreprise" [cv.tex lettre.tex ...]
# Sans fichier précisé, compile tous les .tex du dossier.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DIR="$(cd "${1:?Usage : $0 <dossier>}" && pwd)"
export TEXINPUTS="$ROOT/cv//:$ROOT/lettres//:$ROOT/commun//:${TEXINPUTS:-}"
shift
cd "$DIR"
if [ $# -gt 0 ]; then fichiers=("$@"); else fichiers=(*.tex); fi
for f in "${fichiers[@]}"; do
  latexmk -xelatex -interaction=nonstopmode -halt-on-error "$f"
  pages=$(pdfinfo "${f%.tex}.pdf" 2>/dev/null | awk '/^Pages/{print $2}')
  [ "${pages:-1}" -gt 1 ] && echo "⚠️  ${f%.tex}.pdf fait $pages pages"
done
latexmk -c >/dev/null 2>&1 || true
