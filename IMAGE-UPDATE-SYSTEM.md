# Système de Mise à Jour Automatique des Images

**Date de mise en place** : 15 janvier 2026
**Objectif** : Mettre à jour automatiquement les images des cartes lorsque de meilleures versions deviennent disponibles (scans japonais → images officielles)

---

## 🎯 Problème résolu

Auparavant, les images étaient capturées **une seule fois** lors de la génération initiale des fichiers individuels. Si une meilleure image devenait disponible plus tard (par exemple, passage d'un scan japonais à une image officielle anglaise), elle n'était jamais mise à jour.

**Exemple** : Une carte comme "H-E-R-O Flash!" avait initialement un scan japonais. Quelques semaines plus tard, une image propre apparaissait sur Yugipedia, mais n'était jamais récupérée.

---

## 🔧 Solutions implémentées

### 1. **Système de tracking temporel (YGOJSON)**

#### Fichier : `src/ygojson/database.py`

**Ajouts** :
- Nouveau champ `last_checked: datetime.datetime` dans la classe `CardImage` (ligne 644-647)
- Constantes de configuration :
  ```python
  RECENT_CARD_AGE_DAYS = 365 * 2  # 2 ans
  IMAGE_RECHECK_INTERVAL_DAYS = 10  # 10 jours
  ```

**Fonctions helper** (lignes 113-160) :
- `is_card_recent(card)` : Détermine si une carte a été sortie il y a moins de 2 ans
- `should_refresh_image(image)` : Vérifie si une image doit être re-vérifiée (> 10 jours depuis le dernier check)

**Sérialisation JSON** :
- Ajout de `lastChecked` dans le JSON exporté (ligne 1049)
- Parsing de `lastChecked` lors de l'import (lignes 3129-3133)

---

### 2. **Logique de re-vérification intelligente (YGOJSON)**

#### Fichier : `src/ygojson/importers/yugipedia.py`

**Modification de la condition** (lignes 805-811) :
```python
should_fetch_yugipedia_images = all(
    (not image.card_art and not image.crop_art)
    or "yugipedia.com" in (image.card_art or "")
    for image in card.images
) or (
    is_card_recent(card) and any(should_refresh_image(img) for img in card.images)
)
```

**Comportement** :
- Vérifie Yugipedia pour les cartes **récentes** (< 2 ans) si dernière vérification > 10 jours
- Met à jour `last_checked` lors de la récupération (ligne 838)
- **Optimisation** : Les cartes anciennes (> 2 ans) ne sont plus jamais re-vérifiées

#### Fichier : `src/ygojson/importers/ygoprodeck.py`

**Ajout du timestamp** (ligne 260) :
```python
existing_image.last_checked = datetime.datetime.now()
```

---

### 3. **Système de téléchargement priorisé (sync-images.js)**

#### Fichier : `backend/scripts/sync-images.js`

**Principe fondamental** :
> **YGOPRODeck = Source de référence (toujours prioritaire)**
> **Yugipedia = Fallback (uniquement si YGOPRODeck retourne 404)**

#### Modifications principales :

**1. Fonction `getImageUrlsFromDB()` ajoutée** (lignes 65-90)
- Parse la colonne `images` de `cards_source`
- Extrait les URLs `card` et `art` pour utilisation comme fallback

**2. Fonction `syncCardImage()` modifiée** (lignes 92-211)
```javascript
// Ordre de priorité :
1. Essayer YGOPRODeck (référence)
2. Si 404 ET URL Yugipedia disponible → Essayer Yugipedia
3. Si les deux échouent → Erreur
```

**3. Artworks alternatifs corrigés** (lignes 197-277)
- Réutilise `syncCardImage()` pour chaque artwork alternatif
- Respecte la même priorité : YGOPRODeck → Yugipedia
- **Important** : Les artworks alternatifs ont des passwords uniques

**4. Mise à jour des 500 cartes récentes** (lignes 374-491)
```javascript
// Gère TOUS les types de cartes :
- Cartes avec pass → YGOPRODeck prioritaire, Yugipedia fallback
- Cartes sans pass (UUID) → Yugipedia uniquement (forceUpdate)
```

**Correction critique** :
- ❌ AVANT : `WHERE pass IS NOT NULL` (excluait les cartes récentes japonaises)
- ✅ APRÈS : Pas de filtre sur pass (inclut toutes les cartes)

**5. Images cropped (artwork)** (lignes 163-192)
- **Uniquement YGOPRODeck** (Yugipedia n'a pas d'images cropped)
- Pas de fallback pour éviter les tentatives inutiles

---

## 📊 Flux de travail complet

```
┌─────────────────────────────────────────────────────────────┐
│ 1. YGOJSON (GitHub Action)                                  │
│    Fréquence : Automatique (webhook ou schedule)            │
└─────────────────────────────────────────────────────────────┘
         │
         ├─► YGOPRODeck import
         │   └─ Met à jour last_checked = now()
         │
         ├─► Yugipedia import
         │   └─ Si carte récente (< 2 ans) ET last_checked > 10 jours
         │      → Re-vérifie les images sur Yugipedia
         │      → Met à jour last_checked = now()
         │
         └─► Génère individual.zip avec nouvelles URLs et timestamps

         ↓

┌─────────────────────────────────────────────────────────────┐
│ 2. update-all.js (Render)                                   │
│    Importe les données dans la base SQLite                  │
└─────────────────────────────────────────────────────────────┘
         │
         └─► Colonne cards_source.images contient les URLs à jour

         ↓

┌─────────────────────────────────────────────────────────────┐
│ 3. sync-images.js (Render)                                  │
│    Télécharge les images selon la priorité                  │
└─────────────────────────────────────────────────────────────┘
         │
         ├─► Cartes normales (avec pass)
         │   1. Essayer YGOPRODeck/{pass}.jpg
         │   2. Si 404 → Essayer URL de cards_source.images
         │
         ├─► Cartes sans pass (UUID)
         │   → Télécharger depuis cards_source.images (Yugipedia)
         │
         ├─► Artworks alternatifs
         │   → Même logique que cartes normales (YGOPRODeck prioritaire)
         │
         └─► 500 cartes récentes (forceUpdate)
             → Force la re-téléchargement même si fichiers existent
             → Détecte quand YGOPRODeck publie une nouvelle image
```

---

## 🎨 Gestion des types d'images

| Type d'image | Fichier | Source prioritaire | Fallback | Notes |
|--------------|---------|-------------------|----------|-------|
| **Card principale** | `{pass}_large.webp`<br>`{pass}_small.webp` | YGOPRODeck | Yugipedia | ✅ |
| **Card sans pass** | `{uuid}_large.webp`<br>`{uuid}_small.webp` | Yugipedia | Aucun | UUID seulement |
| **Artwork cropped** | `{pass}_cropped.webp` | YGOPRODeck | ❌ Aucun | Yugipedia n'en a pas |
| **Artwork alternatif** | `{alt_pass}_*.webp` | YGOPRODeck | Yugipedia | Password alternatif |

---

## ⚙️ Configuration

### YGOJSON (`database.py`)

```python
RECENT_CARD_AGE_DAYS = 365 * 2  # Cartes < 2 ans sont "récentes"
IMAGE_RECHECK_INTERVAL_DAYS = 10  # Re-vérifier tous les 10 jours
```

### sync-images.js

```javascript
const RATE_LIMIT_MS = 200;  // Délai entre téléchargements (éviter blacklist)
updateRecentCardImages(DB_PATH, 500);  // 500 cartes les plus récentes
```

---

## 🔍 Stratégie d'optimisation

### Cartes anciennes (> 2 ans)
- ❌ **Ne sont plus re-vérifiées** dans YGOJSON
- ✅ Images stables, pas de changement attendu
- ✅ Économise des milliers de requêtes API

### Cartes récentes (< 2 ans)
- ✅ **Re-vérifiées tous les 10 jours** dans YGOJSON
- ✅ Capture les nouvelles images dès qu'elles sont disponibles
- ✅ Passage automatique scan → image officielle

### 500 cartes les plus récentes
- ✅ **Force update** dans sync-images.js
- ✅ Re-téléchargement même si fichiers existent
- ✅ Détection immédiate quand YGOPRODeck publie l'image

---

## 📝 Exemples de cas d'usage

### Cas 1 : Nouvelle carte japonaise
```
1. YGOJSON génère avec image Yugipedia (scan japonais)
   → images[0].card = "https://yugipedia.com/wiki/Special:FilePath/..."
   → images[0].last_checked = 2026-01-15T10:00:00

2. sync-images.js
   → Essaie YGOPRODeck → 404 (pas encore disponible)
   → Télécharge depuis Yugipedia
   → Sauvegarde: {uuid}_large.webp

3. 3 semaines plus tard
   → YGOJSON re-vérifie Yugipedia (> 10 jours)
   → Trouve image anglaise officielle
   → Met à jour l'URL + last_checked

4. sync-images.js (updateRecentCardImages)
   → Force update
   → Télécharge nouvelle image
   → Remplace le scan japonais ✅
```

### Cas 2 : Carte avec pass qui obtient une image YGOPRODeck
```
1. Initialement : Yugipedia uniquement
   → sync-images.js télécharge depuis Yugipedia

2. YGOPRODeck publie l'image
   → updateRecentCardImages() force update
   → Essaie YGOPRODeck → 200 OK ✅
   → Remplace l'image Yugipedia par YGOPRODeck
```

### Cas 3 : Artwork alternatif
```
1. Carte avec 3 artworks
   → images[0].password = "12345678" (principale)
   → images[1].password = "12345679" (alt 1)
   → images[2].password = "12345680" (alt 2)

2. sync-images.js
   → syncCardImage("12345678", { cardUrl: ..., artUrl: ... })
   → syncAlternativeArtworks()
      → syncCardImage("12345679", { cardUrl: ..., artUrl: ... })
      → syncCardImage("12345680", { cardUrl: ..., artUrl: ... })
   → Tous respectent : YGOPRODeck prioritaire ✅
```

---

## 📦 Fichiers modifiés

### YGOJSON
- `src/ygojson/database.py` : Structure de données + helpers
- `src/ygojson/importers/yugipedia.py` : Logique de re-vérification
- `src/ygojson/importers/ygoprodeck.py` : Mise à jour timestamp

### YGOSITEJTV
- `backend/scripts/sync-images.js` : Téléchargement priorisé

---

## ✅ Garanties

1. ✅ **YGOPRODeck toujours prioritaire** : Source de référence officielle
2. ✅ **Yugipedia comme fallback fiable** : Re-vérifié tous les 10 jours pour cartes récentes
3. ✅ **Optimisation performance** : Cartes anciennes ne sont plus re-vérifiées
4. ✅ **Artworks alternatifs cohérents** : Même logique que l'image principale
5. ✅ **Cartes sans pass gérées** : UUID + Yugipedia uniquement
6. ✅ **500 cartes récentes protégées** : Force update systématique

---

## 🚀 Déploiement

1. **Push YGOJSON** vers GitHub
   → Déclenche la GitHub Action
   → Génère individual.zip avec nouveaux timestamps

2. **Render (automatique ou manuel)**
   ```bash
   npm run update-all    # Import données
   npm run sync-images   # Télécharge images
   ```

3. **Résultat**
   → Images à jour sur votre site
   → Logs détaillés : YGOPRODeck vs DB (Yugipedia)

---

## 📊 Monitoring

Les logs de `sync-images.js` indiquent la source de chaque image :

```
[SYNC] Début de la synchronisation des cartes...
   -> 10 images créées (1000/14000) [DB: 8, YGOPRODeck: 2]

[UPDATE-RECENT] Updated 250/500 recent cards (DB: 230, YGOPRODeck: 20)

[ALT-ARTWORKS] Done. Created: 45 (YGOPRODeck: 12, DB: 33)
```

**Interprétation** :
- `DB` = Yugipedia (fallback ou carte sans pass)
- `YGOPRODeck` = Source prioritaire (référence)
- Plus de `DB` pour cartes récentes = Normal (cartes japonaises sans pass)

---

## 🔄 Maintenance future

### Modifier la fréquence de re-vérification
```python
# database.py
IMAGE_RECHECK_INTERVAL_DAYS = 7  # Plus fréquent
IMAGE_RECHECK_INTERVAL_DAYS = 30  # Moins fréquent
```

### Modifier la définition de "carte récente"
```python
# database.py
RECENT_CARD_AGE_DAYS = 365 * 1  # 1 an
RECENT_CARD_AGE_DAYS = 365 * 3  # 3 ans
```

### Modifier le nombre de cartes récentes à forcer
```javascript
// sync-images.js
updateRecentCardImages(DB_PATH, 1000);  // 1000 cartes
```

---

**Fin du document**
