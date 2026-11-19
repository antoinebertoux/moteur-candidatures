# Identifiers and rules shared with the page

The page and engine B must recognise the same application without talking to each
other, so each computes the same identifier. Every rule in this file exists twice
(Python in `modeles.py`, JavaScript in the page) and must change on both sides.

- **ID-01** · *Normalising* a text: lowercase, accents removed, every run of characters
  other than `a-z` and `0-9` replaced by a hyphen, leading and trailing hyphens removed.
  "Ministère des Armées" → `ministere-des-armees`.
- **ID-02** · An application's identifier is `<type>_<company>_<title>`, each part
  normalised (ID-01), the whole truncated to 150 characters. The type is `offre` (job ad)
  or `spontanee` (unsolicited): an ad and an unsolicited application to the same company
  are two distinct applications.
- **ID-03** · An expression is matched **on whole words**, ignoring accents and
  punctuation: "ia" does not match "commercial", "data scientist" matches
  "Data-Scientist (H/F)".
- **ID-04** · *Default cover letter*: a letter is planned by default for an unsolicited
  application, a public-sector ad (source `service_public`,
  `choisirleservicepublic.gouv.fr` or `place-emploi-public`), or a company whose name
  contains a word from the "public" list (ministère, DGSE, DGSI, DGA, DINUM, ANSSI,
  préfecture, gendarmerie, CNRS, Inria…) or the "bank" list (BNP Paribas, Société
  Générale, Crédit Agricole, Natixis, Bpifrance, HSBC…), on whole words (ID-03).
- **ID-05** · The lists of ID-04 and the function of ID-01 are identical in the page.
  *(untested: checked by hand on every change)*
