# Exports

Ce dossier contient les résultats du scraping automatique.

## Fichiers

### Toutes les missions (général + tutorat)
- `jobs_latest.json` - **Toutes les missions** scrapées (format JSON) — inclut les missions de tutorat (`vertical='tutoring'`)
- `jobs_latest.csv` - **Toutes les missions** scrapées (format CSV)

Les missions de tutorat sont dans le même fichier que les autres missions, identifiables via le champ `vertical='tutoring'`.

### Archives (snapshots horodatés)
- `archive/jobs_YYYYMMDD_HHMMSS.json/csv`

## Accès public

**Toutes les missions (JSON):**
```
https://raw.githubusercontent.com/Dlawlet/afidiOS-finder/main/exports/jobs_latest.json
```

**Toutes les missions (CSV):**
```
https://raw.githubusercontent.com/Dlawlet/afidiOS-finder/main/exports/jobs_latest.csv
```

## Mise à jour

Automatiquement mis à jour chaque jour à 6h UTC (missions générales) et 9h UTC (tutorat) via GitHub Actions.

## Sites scrapés

### Missions de voisinage / petites missions
- **jemepropose.com** — Services locaux francophones
- **allovoisins.com** — Entraide de voisinage, toute la France
- **ringtwice.be** — Petites missions de voisinage, Belgique

### Tutorat (pipeline séparé)
- **voscours.fr** — Demandes d'élèves (France/UE)
- **findtutors.co.uk** — Demandes d'élèves (Royaume-Uni)
