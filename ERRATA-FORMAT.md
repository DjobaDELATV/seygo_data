# Errata des cartes — format JSON (seygo_data / YGOJSON v1)

Ce document décrit le champ `errata` des cartes produit par le pipeline YGOJSON
(GitHub Action nightly sur `DjobaDELATV/seygo_data`), à destination du code du site.

## 1. Où trouver les données

| Source | Contenu |
|---|---|
| Release `v1` → `aggregate.zip` → `cards.json` | **tableau** de toutes les cartes (≈15 000) |
| Release `v1` → `individual.zip`, ou branche `v1/individual` → `cards/<uuid>.json` | une carte par fichier |
| `aggregate.zip` → `sets.json` | les sets, pour résoudre les uuids de `errata.*[].sets` |
| `meta.json` | `increment` et dates de dernière lecture (`lastYugipediaRead`) pour savoir si les données ont changé |

Mise à jour : une fois par jour (départ 1h17 UTC, export disponible vers 2h30 UTC). Les
errata sont suivis automatiquement (toute modification d'une page `Card Errata:` sur
Yugipedia est reprise au run suivant).

Clés d'identification d'une carte (pour faire la jointure avec la BDD du site) :
- `id` : uuid YGOJSON, **stable** dans le temps → clé recommandée ;
- `passwords` : liste des codes à 8 chiffres (ex. `["17412721"]`) ;
- `externalIDs.dbID` : id Konami (Yu-Gi-Oh! Card Database) ;
- `text.en.name` / `text.fr.name` : noms actuels.

## 2. Structure

```jsonc
"errata": {                       // ABSENT si la carte n'a aucun errata EN/FR
  "en": [ Version, Version, ... ],// ABSENT si pas d'errata anglais
  "fr": [ Version, Version, ... ] // ABSENT si pas d'errata français
}
```

- Seules les langues **`en`** et **`fr`** existent. Une langue n'est présente que si
  elle a **au moins 2 versions** (l'originale + au moins un errata).
- Le tableau est **chronologique dans l'ordre du tableau** : index `0` = texte
  original (première impression), dernier index = texte le plus récent (en
  général le texte officiel actuel). **Ne pas trier par date** : des dates peuvent
  être égales ou même décroissantes (≈170 cas, réimpressions d'anciens sets),
  l'ordre du tableau fait foi.
- Volume actuel : ~4 900 cartes avec errata (en : ~4 860, fr : ~380),
  ~15 000 versions, jusqu'à 14 versions pour une carte (la plupart en ont 2 ou 3).

### Objet `Version`

Tous les champs sont **optionnels** (absents plutôt que `null`).

| Champ | Type | Signification |
|---|---|---|
| `name` | string | Nom de la carte dans cette version (texte brut) |
| `nameDiff` | string | Idem avec balises `<ins>`/`<del>` |
| `effect` | string | Texte de la carte (effet / lore). Pour un monstre Pendule séparé : l'effet de monstre |
| `effectDiff` | string | Idem avec balises |
| `pendulumEffect` | string | Effet Pendule, seulement quand le texte a été séparé en deux parties |
| `pendulumEffectDiff` | string | Idem avec balises |
| `typeLine` | string | Ligne de type telle qu'imprimée, ex. `[Insect/Flip/Effect]`, `[ Spell Card ]` |
| `typeLineDiff` | string | Idem avec balises |
| `date` | string `YYYY-MM-DD` | Date de la version (voir §4) |
| `dateSource` | `"set"` \| `"explicit"` | Origine de la date. Présent **uniquement** si `date` est présent |
| `printings` | string[] | Codes d'impression où cette version est apparue, ex. `["RA04-EN226"]` |
| `sets` | uuid[] | Sets correspondants (→ `sets.json`, champ `id`) |
| `reference` | string (URL) | Source quand il n'y a pas d'impression : souvent la fiche de la base officielle Konami (`db.yugioh-card.com`, `request_locale=en|fr`), parfois une archive web |

Les textes utilisent `\n` pour les retours à la ligne. Aucun autre HTML/wikicode
n'est présent (seulement `<ins>`, `<del>` dans les champs `*Diff`).

## 3. Champs texte : brut vs `*Diff`

Pour chaque champ texte (`name`, `effect`, `pendulumEffect`, `typeLine`) :

- le champ **brut** (`effect`) = le texte exact de cette version, sans balises → à
  utiliser pour l'affichage simple, la recherche, la copie ;
- le champ **`*Diff`** (`effectDiff`) n'existe que si cette version contient des
  balises. **S'il est absent, la version n'a rien de marqué : afficher le brut.**

Convention des balises (celle de Yugipedia), pour la version N :

- `<ins>…</ins>` = texte **ajouté** dans la version N par rapport à N-1 ;
- `<del>…</del>` = texte présent dans la version N qui sera **retiré** dans la
  version N+1.

Donc une même version peut contenir des `<ins>` (ce qui vient d'arriver) et des
`<del>` (ce qui va partir). Retirer les balises en gardant leur contenu redonne
exactement le texte brut. Les balises peuvent être **imbriquées**
(`<ins><del>the</del> Struggle</ins>` : ajouté dans N, puis retiré dans N+1) ;
≈1 300 cas, il faut donc un parseur qui gère l'imbrication (un simple
remplacement des balises par `<span class>` suffit, pas de regex non gourmande sur
des paires).

Exemple Elder Entity Norden (en) :

```json
[
  { "effect": "1 Synchro or Xyz Monster + 1 Synchro or Xyz Monster\nWhen this card is Special Summoned: You can target 1 Level 4 or lower monster in your Graveyard; ...",
    "effectDiff": "... monster in your <del>Graveyard</del>; ...",
    "date": "2015-09-17", "dateSource": "set",
    "printings": ["CT12-EN003"], "sets": ["be677623-a485-4a52-a025-6117537c1361"] },
  { "effect": "... monster in your GY; ...",
    "effectDiff": "<del>1</del> Synchro or Xyz <del>Monster + 1 Synchro or Xyz Monster</del>\n... in your <ins>GY</ins>; ...",
    "date": "2025-04-10", "dateSource": "set",
    "printings": ["RA04-EN226"], "sets": ["2badda17-03d3-4d13-8ab5-aa1072df59c1"] },
  { "effect": "2 monsters (Synchro and/or Xyz)\nWhen this card is Special Summoned from the Extra Deck: ...",
    "effectDiff": "<ins>2 monsters (</ins>Synchro <ins>and/</ins>or Xyz<ins>)</ins>\n...",
    "reference": "https://www.db.yugioh-card.com/yugiohdb/card_search.action?ope=2&cid=11207&request_locale=en" }
]
```

Affichage conseillé :
- vue simple : afficher `effect` de chaque version avec sa date ;
- vue « changements » : rendre `effectDiff` (ou `effect` s'il est absent) avec
  `<ins>` en surligné/vert et `<del>` en barré/rouge.

## 4. Dates

- `dateSource: "explicit"` : date écrite explicitement sur Yugipedia pour cet
  errata (rare, ~16 versions) → la plus fiable.
- `dateSource: "set"` : date de sortie la plus ancienne, **dans la langue de la
  version** (en → sortie TCG anglaise NA/EU/OC, fr → sortie française), parmi les
  sets listés dans `printings`/`sets`.
- **Pas de `date`** (~320 versions) : version connue seulement par une source sans
  impression (souvent la dernière version, publiée sur la base officielle Konami →
  voir `reference`). Aucune date approximative n'est inventée : afficher
  « date inconnue » ou se baser sur la position dans le tableau.

## 5. Particularités à gérer

- **Champs absents d'une version à l'autre** : `name` n'est présent que si la page
  d'errata donne les noms (~800 versions) ; `typeLine` seulement pour certaines
  cartes ; ~1 000 versions n'ont pas d'`effect` (errata portant uniquement sur le
  nom ou le type). Si un champ manque, se rabattre sur le texte actuel de la carte
  (`text.<lang>.name`, `text.<lang>.effect`) ou sur la version précédente.
- **Nom seul** : ex. `Couveuse Cellule "A"` → `Incubateur Cellule "A"` (fr) : les
  versions n'ont que `name`/`nameDiff`.
- **Pendule** : quand le texte d'errata était séparé (libellés « Pendulum Effect »,
  « Effet Pendule »…), on a `pendulumEffect` + `effect` (effet de monstre). Sinon
  tout est dans `effect` et le libellé (« Pendulum Effect: … ») peut apparaître dans
  le texte (~40 versions).
- Le **dernier élément** correspond normalement au texte actuel de la carte, mais
  il peut différer légèrement de `text.<lang>.effect` (sources différentes) : pour
  le texte officiel courant, utiliser `text.<lang>`.
- Les errata `en` et `fr` sont **indépendants** : nombres de versions et dates
  différents, pas de correspondance index à index.

## 6. Stockage en base de données (site)

Le schéma YGOJSON a toujours prévu un champ `errata` sur les cartes ; la BDD du
site a peut-être déjà une colonne `errata` : vérifier son type, l'ancien contenu
n'a pas ce format.

Recommandé : une colonne `errata` de type **JSON/JSONB** (ou TEXT contenant du
JSON) sur la table des cartes, qui stocke **l'objet `errata` tel quel**
(`{"en":[...],"fr":[...]}`), `NULL` si la carte n'a pas le champ.

Import (à chaque mise à jour) :
1. lire `cards.json` (aggregate) ;
2. pour chaque carte, retrouver la ligne de la BDD via `id` (sinon `passwords` /
   `externalIDs.dbID`) ;
3. écrire `errata = card.errata ?? NULL` (**remplacer** entièrement, ne pas
   fusionner : les versions peuvent être corrigées ou réordonnées en amont, et
   une carte peut perdre ses errata).

Si des requêtes SQL sur les versions sont nécessaires (ex. « errata depuis telle
date »), une table dérivée `card_errata(card_id, lang, idx, name, effect,
effect_diff, pendulum_effect, type_line, date, date_source, printings, reference)`
peut être regénérée à partir de la colonne JSON ; `idx` = position dans le tableau
et doit servir de tri.

Le schéma JSON officiel est `schema/v1/card.json` (propriété `errata`).
