# Page « Suivi des candidatures »

Artefact claude.ai privé (slug `34e12927-7588-4297-9860-6ed2374e9e20`), avec sa base
hébergée par Claude : collection `candidatures`, un document par candidature, dont
l'identifiant suit ID-02. Ces règles sont vérifiées à la main.

## Champs d'un document

`type`, `entreprise`, `poste`, `lieu`, `url`, `source`, `moteur` (`A`, `B`, `manuel` ;
absent = `manuel`), `statut`, `score`, `resume`, `lettre_demandee`, `lettre`
(`oui`/`non`), `cv_ref`, `lettre_ref`, `contact`, `notes`, `texte_offre`, `consigne`,
`retouche_le`, `lettre_refaire_le`, `lettre_consigne`, `suite`, `date_ajout`,
`date_maj`, `date_postulee`.

## Parcours

- **PAGE-01** · Six étapes, chacune avec son compteur (selon les filtres actifs) : À
  traiter, À préparer, À valider, À envoyer, Postulée, Refusée (statuts : voir le
  [README](README.md#statuts)).
- **PAGE-02** · Actions par étape :

  | Étape | Actions |
  | --- | --- |
  | À traiter | **Oui** → À préparer · **Non** → Refusée |
  | À préparer | « CV et lettre à générer » ; « CV prêt, passer à valider » (manuel) |
  | À valider | **Valider** → À envoyer · retouche (PAGE-05) |
  | À envoyer | **Marquer comme postulée** → Postulée, date d'envoi = aujourd'hui · retouche |
  | Postulée | suite donnée (PAGE-08) |
  | Refusée | **Remettre à traiter** |

  Hors À traiter et Refusée : **Abandonner** → Refusée. Partout : **Supprimer**, avec
  confirmation.
- **PAGE-03** · À traiter est trié par score décroissant ; les autres étapes par dernière
  modification, la plus récente en haut.
- **PAGE-04** · Filtres : type (offres / spontanées), moteur (A, B, manuel) et recherche
  libre sur entreprise, poste et lieu (accents ignorés).
- **PAGE-05** · Retouche : sur À valider ou À envoyer, Antoine écrit une consigne puis
  « Redemander avec la consigne » ; la candidature repasse À préparer avec l'heure de la
  demande. Sans consigne, la page refuse.
- **PAGE-06** · Lettre : tant qu'aucune lettre n'est faite (de À traiter à À envoyer), un
  interrupteur « Lettre : oui / non » montre et change le choix ; sans choix, la lettre
  est prévue si l'offre la demande ou selon ID-04. Une fois la lettre faite, un bouton
  « Régénérer la lettre » (avec consigne facultative ; vide = réécrite de zéro) note
  l'heure de la demande. Des pastilles signalent « Lettre à régénérer » et « Lettre à
  générer ».
- **PAGE-07** · En À préparer, pour une offre (pas une spontanée) qui ne vient pas du
  moteur B et n'a pas de texte, la page demande de coller le texte de l'offre, sinon le
  CV sera générique.
- **PAGE-08** · Postulée : la suite donnée vaut En attente, Relancée, Entretien, Refus de
  l'entreprise ou Proposition reçue, et s'affiche en pastille.
- **PAGE-09** · Chaque modification met `date_maj` à aujourd'hui ; un échec
  d'enregistrement s'affiche en message, sans perdre la saisie.

## Ajout manuel

- **PAGE-20** · Formulaire : type, entreprise (obligatoire), poste ou rôle, lieu, lien,
  contact, statut de départ (Postulée par défaut, avec la date d'envoi du jour), notes,
  texte de l'offre (20 000 caractères au plus). Moteur = `manuel`.
- **PAGE-21** · Une entrée déjà présente (même identifiant) est refusée.

## Import et export

- **PAGE-30** · Import du fichier du moteur B par le bouton ou par glisser-déposer
  n'importe où sur la page. Une entrée inconnue est créée À traiter (moteur `A` si le
  fichier le dit, sinon `B`). Une entrée sans entreprise est ignorée. Un bilan s'affiche
  (ajoutées, mises à jour, ignorées).
- **PAGE-31** · Une entrée connue ne reçoit que les mises à jour de `cv_ref`,
  `lettre_ref`, `resume`, `score` et `lettre_demandee`. Les décisions d'Antoine ne sont
  jamais écrasées.
- **PAGE-32** · Quand un CV arrive pour une candidature À préparer, elle passe À valider
  et sa consigne est effacée — sauf si une retouche a été demandée après la génération
  de ce CV (PDF plus ancien que la demande).
- **PAGE-33** · Une demande de régénération de lettre est effacée dès qu'une lettre plus
  récente que la demande arrive.
- **PAGE-34** · Export : télécharge `candidatures-export.json`
  (`{"exporte_le": …, "candidatures": [tous les documents]}`) ; si le téléchargement
  n'est pas possible, le contenu s'affiche à copier.

## Liens

- **PAGE-40** · Les boutons CV et Lettre ouvrent `cv_ref` / `lettre_ref` : un lien http(s)
  tel quel, un chemin relatif via `http://127.0.0.1:8765/<chemin>` (SRV-01), tout autre
  schéma est ignoré. Le lien de l'offre n'est affiché que s'il est en http(s).

## Comparaison des moteurs

- **PAGE-50** · Un tableau compte, pour A, B et manuel : proposées, à traiter,
  acceptées (À préparer, À valider, À envoyer ou Postulée), refusées, postulées, et le
  taux d'acceptation = acceptées / (acceptées + refusées).

## Robustesse et affichage

- **PAGE-60** · La liste se met à jour en direct quand la base change (tâches
  planifiées, autre appareil).
- **PAGE-61** · Base indisponible ou coupée : un message le dit ; sans réponse au bout de
  10 s, un message d'attente s'affiche.
- **PAGE-62** · Thème clair ou sombre selon le système ; sur mobile, les étapes passent
  sur trois colonnes.
