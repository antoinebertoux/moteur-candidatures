% One-page cover letter class used by the example of the job application engine.
% Compiled with XeLaTeX; the Lato and Raleway fonts come with TeX Live
% (packages "lato" and "raleway"), found by file name.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{lettre}[2026/11/21 Cover letter class]
\LoadClass[11pt]{article}

\RequirePackage[hmargin=2cm, vmargin=2cm]{geometry}
\RequirePackage[hidelinks]{hyperref}
\RequirePackage{xcolor}
\RequirePackage{fontspec}

\definecolor{primary}{HTML}{2B2B2B}
\definecolor{accent}{HTML}{1F4E79}

\setmainfont{Raleway-Regular.otf}[
  BoldFont = Raleway-SemiBold.otf,
  ItalicFont = Raleway-RegularItalic.otf,
  Color = primary]
\newfontfamily\namelight{Lato-Light.ttf}
\newfontfamily\namebold{Lato-Bold.ttf}

\pagestyle{empty}
\setlength{\parindent}{0pt}

% Header: first name, last name, contact line.
\newcommand{\namesection}[3]{%
  \begin{center}
    {\fontsize{32pt}{40pt}\selectfont\namelight #1 \namebold #2}\\[4pt]
    {\small\color{accent} #3}
  \end{center}
  \vspace{10pt}}

\newcommand{\companyname}[1]{{\raggedright\namebold\large #1\par}}
\newcommand{\currentdate}[1]{{\raggedleft #1\par}}
% One paragraph of the letter: the engine rewrites the content of each one.
\newcommand{\lettercontent}[1]{{\raggedright #1\par}\vspace{9pt}}
\newcommand{\signature}[1]{\vspace{6pt}{\raggedright\namebold #1\par}}

% Language-neutral date: 21/11/2026.
\newcommand{\datejour}{\two@digits{\day}/\two@digits{\month}/\number\year}
