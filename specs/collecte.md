# Collecte et filtre

`moteur collecter` interroge les sources, garde les offres qui passent le filtre, puis
propose des candidatures spontanées. Aucun appel à Claude.

## Collecte

- **COL-01** · Une source en panne est signalée et ignorée : les autres continuent.
- **COL-02** · Ordre : interroger toutes les sources → filtrer → ouvrir la page des
  seules offres retenues dont le texte manque (SRC-24) → ajouter les spontanées. Si une
  page ne peut pas être ouverte, l'offre est gardée sans texte.
- **COL-03** · Une candidature spontanée est proposée pour chaque entreprise suivie
  marquée `spontanee = true` qui n'a **aucune offre retenue** dans cette collecte et qui
  n'a **jamais été vue** (ni dans la base locale, ni dans `suivi/entreprises_vues.csv`).
  Son intitulé est `role_spontane`, son lien le site de l'entreprise, sa source `cible`.
- **COL-04** · `suivi/entreprises_vues.csv` (séparateur `;`, colonne `entreprise`) est
  facultatif. Les lignes dont la colonne de statut contient « historique » (ancienne
  recherche) sont ignorées : ces entreprises peuvent être proposées de nouveau.
- **COL-05** · Toute entreprise déjà présente dans la base locale, quel que soit son
  statut, compte comme vue.
- **COL-06** · La commande affiche le nombre d'offres retenues et, parmi elles, le
  nombre de nouvelles. *(non testé)*

## Filtre

Tout se joue sur l'intitulé, le lieu et le salaire, en mots entiers (ID-03). **Une
information absente ne fait jamais rejeter une offre.**

- **FILT-01** · Si des mots-clés sont configurés, l'intitulé doit en contenir au moins un.
- **FILT-02** · Un intitulé qui contient une exclusion (stage, alternance, intern…) est
  rejeté.
- **FILT-03** · Si des lieux sont configurés, une offre dont le lieu est connu doit en
  contenir un ; une offre sans lieu passe.
- **FILT-04** · Salaire : une offre n'est rejetée que si le **maximum annuel affiché** est
  inférieur au plancher. Libellés compris : « Annuel de X Euros à Y Euros… » et
  « Mensuel de X Euros sur N mois » (×12 si N manque). Un salaire illisible ou absent
  passe. Plancher à 0 = pas de filtre.
- **FILT-05** · Deux offres de même identifiant (ID-02) : seule la première est gardée.
