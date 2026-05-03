# afidiOS-finder

Pipeline de scraping pour missions 100% en ligne, avec un focus sur le tutorat à distance.

## ✨ Objectif
- Maximiser les missions réalisables **100% en ligne**.
- Priorité au tutorat / cours de répétition (FR/EN).
- Exploiter au mieux la **free tier Groq** via rotation des modèles.

## 🚀 Utilisation rapide
Le script principal orchestre **général + tutorat** et exporte :
- `exports/jobs_latest.json|csv`
- `exports/remote_jobs_latest.json|csv`

Variables d’environnement utiles :
- `GROQ_API_KEY` (obligatoire pour LLM)
- `GROQ_MODEL` (fallback unique)
- `GROQ_MODELS` (rotation multi-modèles)
  - Exemple: `llama-3.3-70b-versatile:1200,gemma2-9b-it:2000`
- `GROQ_MODEL_STRATEGY` = `capacity` (défaut) ou `round_robin`
- `TUTORING_LLM_QUOTA` (budget LLM pour le pipeline tutorat)

## 🧠 Rotation des modèles Groq
Le manager choisit le modèle avec **plus de capacité restante** (ou round-robin).
Les résultats sont **cachés par modèle** pour éviter de mélanger les versions.

## 🔍 Sites ciblés (publics, sans login)
- Tutorat (entre particuliers) : `voscours`, `findtutors_uk`
- Général (entre particuliers) : `jemepropose`, `allovoisins`
- Pro / job boards (optionnel via `--include-pro-sources`) :
  `codeur`, `freelance.com`, `comet`, `remoteok`, `remotive`, `workingnomads`, `arbeitnow`
- Optionnel (bloqué sans contournement) : `malt` (HTTP 403)

## 🚫 Filtrage des offres pro
Les offres de type CDI/CDD/stage/emploi sont filtrées automatiquement pour ne garder
que des missions entre particuliers et des missions 100% à distance.
- Locaux (optionnels) : `jemepropose`, `allovoisins`

> Les sites nécessitant un compte (ex: RingTwice) sont exclus par défaut.

## 🧹 Nettoyage
Le cache est dans `cache/`, les logs dans `logs/`. Ces dossiers sont ignorés par git.

## ✅ Export attendu
- `remote_jobs_latest` contient **toutes** les missions remote, y compris tutorat.
- Les exports CSV incluent `source`, `vertical`, `poster_type`, etc.

---
Besoin d’ajouter un site ? Ajoute un scraper dans `site_scrapers.py` puis référence-le dans `scheduled_scraper_v3.py`.
