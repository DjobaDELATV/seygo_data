# Impressions encore absentes : causes à traiter plus tard

Audit du 2026-11-09, après le correctif des collisions de clé dans `parse_tcg_ocg_set`
(impressions d'une même carte et rareté avec des codes différents).

Méthode : toutes les pages `Set Card Lists:* (TCG|OCG-*)` de Yugipedia, redirections de noms
résolues, comparées ligne à ligne à l'export corrigé. Les chiffres sont ceux du scan ; certains
groupes contiennent probablement des faux positifs du scan lui-même (signalés ci-dessous).

## Lignes de liste sans impression correspondante : 1 686 (1 475 OCG, 211 TCG)

Par locale de page : jp 580, ae 359, kr 228, ja 207, sc 101, en 59, de/fr/it/sp 36, pt 8.

1. **Listes OCG anciennes rattachées à une page homonyme TCG.** `Metal Raiders (OCG-JP)`,
   `Legend of Blue Eyes White Dragon (OCG-JP)`, `Pharaoh's Servant`, `Labyrinth of Nightmare`,
   `Pharaonic Guardian`, `Gold Series`, `Millennium Pack`, `Token Pack`, `Duelist Pack: Yugi`
   (JP et KR). Codes japonais/coréens d'un autre produit (`ME-00`, `LB-00`, `GS01-JP001`,
   `MP01-KR001`, `DP00-KR000`…) : le set exporté n'a aucun contenu pour ces locales. À vérifier :
   soit le produit OCG doit être un set à part, soit la liste doit être importée dans ce set.
2. **Listes `(OCG-JA)` sans contenu.** `Duelist Alliance`, `Collectors Pack: Duelist of Legend
   Version`, `Structure Deck: HERO's Strike` : le set a une locale `jp` mais aucun contenu issu
   de la liste `-JA`. Piste : traitement de la clé de région `ja` vs `jp`.
3. **Tournament Packs (2024-2026), listes AE et SC.** Codes `24AT-AE100`, `26SP-SC100`… : le set
   n'a que la locale `jp`, les listes asiatiques-anglaises et chinoises ne sont pas importées.
4. **Listes AE partiellement importées.** Ex. `Blazing Dominion (OCG-AE)` : 112 impressions
   présentes, 59 lignes absentes (raretés secrètes). Cause non identifiée (correspondance de
   rareté ?).
5. **Lignes sans code (103).** Ex. `Original Artwork Collection (OCG-JP)` : en partie des
   impressions présentes avec un suffixe vide (faux positifs du scan), le reste à vérifier.
6. **Tokens génériques (l'essentiel des 211 TCG).** Lignes `Token (card)` de Token Pack,
   Legendary Collection 3/4, Battle City Tournament Kit, Speed Duel Tournament Pack 3, packs
   `Plus`… Les tokens sont rattachés à une carte par la description de la ligne, ce que le scan
   ne reproduit pas : probablement des faux positifs, à confirmer.

## Lignes sans carte : 5 971 (3 237 OCG, 2 734 TCG)

- 5 184 « card not found » : surtout des cartes OCG inédites absentes de la base.
- 787 « no card name » : lignes sans nom de carte (placeholders, lignes à compléter sur le wiki).

Depuis le correctif, l'import les journalise (`Skipped row of …`) avec un récapitulatif final.

## Pages de liste dont le set n'est pas dans l'export : 382

Ex. campagnes `"… Special Red Version" GET Campaign`, `5th Anniversary Pack`, `Advance Pack:*`,
`Battle Pack 2022/2023 Vol.*`, `Battle Bonus Pack 2026 Vol.*`… Produits OCG non importés.

## Sets à plusieurs préfixes : décision, pas de changement de format

14 sets ont plusieurs préfixes réels par locale (ex. `2-Player Starter Set` : `STAS-EN` et
`STAX-EN` ; aussi DPC, SD, J, VJ, WJ, HL…). Le format ne stocke qu'un `prefix` par locale :
l'import garde leur partie commune (`STA`) et les suffixes portent le reste (`X-EN001`).
`prefix + suffix` redonne le bon code, le consommateur le reconstitue déjà.

Décision (2026-11-09) : on laisse tel quel. Une liste de préfixes changerait le format de
sortie et obligerait le consommateur à s'adapter sans gain réel.

## Cache des URLs d'images : à laisser en l'état pour l'instant

Les URLs d'images viennent telles quelles de l'API Yugipedia (`imageinfo`) et sont gardées dans
`imagesCache` du cache `temp`, restauré par la CI ; une entrée n'est rafraîchie que si la page du
fichier change. Yugipedia ayant changé d'hôte, la release mélange `ms.yugipedia.com//`
(~356 000 URLs, redirigées en 301) et `img.yugipedia.com/` (~10 500). Certaines entrées pointent
aussi vers d'anciennes révisions (`/archive/…%21…`).

Rien n'est cassé : le consommateur extrait la clé d'image du nom de fichier, quel que soit
l'hôte ou le chemin `/archive/`. Vider tout le cache d'un coup ferait ~366 000 appels à l'API.
Si on le fait un jour : expiration progressive (par lots), en remplaçant d'abord les entrées
en `/archive/`.

## Reproduire le scan

Scripts d'audit (non versionnés) : récupération des pages de listes via l'API Yugipedia
(`generator=allpages`, `gapnamespace=3006`), puis comparaison ligne à ligne avec un export
`individual` (raretés normalisées avec les tables de `importers/yugipedia.py`).
