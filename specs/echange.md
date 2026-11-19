# Fichiers échangés avec la page

La page est un artefact claude.ai : elle ne peut pas appeler le PC (la plateforme bloque
tout `fetch()` vers un autre hôte, `127.0.0.1` compris). Les deux côtés s'échangent donc
des fichiers JSON qu'Antoine dépose à la main.

## Moteur B → page : `echange/pour-la-page.json`

- **ECH-01** · Tableau d'entrées avec : `type`, `entreprise`, `poste`, `lieu`, `url`,
  `source`, `moteur` = `B`, `resume`, `lettre_demandee`, et `score` si l'offre est notée.
  **Pas d'identifiant** : la page le recalcule (ID-02).
- **ECH-02** · Un dossier généré ajoute `cv_ref` et `genere_le` (date de modification du
  PDF du CV), et s'il a une lettre `lettre_ref` et `lettre_generee_le`. Dates au format
  `2026-11-17T21:45:48.123Z`, comparables à celles de la page.

## Page → moteur B : `candidatures-export.json`

- **ECH-10** · Accepté sous la forme `{"candidatures": [...]}` ou directement le
  tableau. Un fichier qui n'est pas du JSON ou sans tableau est refusé avec un message.
  Les entrées sans `id` ou sans `statut` sont ignorées.
- **ECH-11** · Champs lus : `id`, `statut`, `consigne`, `lettre_demandee`, `lettre`
  (`oui` / `non` ou booléen ; absent = pas de choix), `lettre_refaire_le`,
  `lettre_consigne`, et de quoi reconstruire l'offre si `entreprise` et `poste` sont
  présents (`type`, `lieu`, `url`, `source`, `texte_offre`).
- **ECH-12** · `moteur decisions <fichier>` applique, dans l'ordre : ajout des acceptées
  inconnues (BASE-07) ; choix de lettre des candidatures acceptées, prêtes ou validées
  (BASE-08) ; décisions de statut (BASE-05, BASE-06) ; régénérations de lettre (LET-07).
  Il affiche ensuite le bilan et ce qui reste à générer. *(non testé)*
