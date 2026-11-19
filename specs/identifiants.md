# Identifiants et règles partagées avec la page

La page et le moteur B doivent reconnaître la même candidature sans se parler : ils
calculent donc chacun le même identifiant. Toute règle de ce fichier existe en double
(Python dans `modeles.py`, JavaScript dans la page) et doit changer des deux côtés.

- **ID-01** · *Normaliser* un texte : minuscules, accents retirés, toute suite de
  caractères autres que `a-z` et `0-9` remplacée par un tiret, tirets retirés au début et
  à la fin. « Ministère des Armées » → `ministere-des-armees`.
- **ID-02** · L'identifiant d'une candidature est `<type>_<entreprise>_<poste>`, chaque
  partie normalisée (ID-01), le tout tronqué à 150 caractères. Le type vaut `offre` ou
  `spontanee` : une offre et une spontanée chez la même entreprise sont deux
  candidatures distinctes.
- **ID-03** · Une expression est cherchée **en mots entiers**, accents et ponctuation
  ignorés : « ia » ne trouve pas « commercial », « data scientist » trouve
  « Data-Scientist (H/F) ».
- **ID-04** · *Lettre par défaut* : une lettre est prévue d'office pour une candidature
  spontanée, une offre du secteur public (source `service_public`,
  `choisirleservicepublic.gouv.fr` ou `place-emploi-public`), ou une entreprise dont le
  nom contient un mot de la liste « public » (ministère, DGSE, DGSI, DGA, DINUM, ANSSI,
  préfecture, gendarmerie, CNRS, Inria…) ou « banque » (BNP Paribas, Société Générale,
  Crédit Agricole, Natixis, Bpifrance, HSBC…), en mots entiers (ID-03).
- **ID-05** · Les listes de ID-04 et la fonction de ID-01 sont identiques dans la page.
  *(non testé : vérifié à la main lors de chaque modification)*
