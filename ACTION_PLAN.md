# Plan d’action — Missions remote & tutorat

**Date:** 2026-05-02

## 1) Diagnostic rapide (état actuel)
- Les sorties `remote_jobs_latest` sont vides car la sortie ne fusionnait pas le pipeline tutorat.
- Incohérences de pipeline : scrapers tutorat référencés mais absents, et historique des jobs incomplet.
- Une partie des sélecteurs HTML est “template” → forte probabilité de 0 résultats si le DOM change.
- Fichiers historiques (logs, cache, archives) encombrent le repo.

## 2) Objectif
Maximiser les missions 100% en ligne (priorité tutorat), **en FR/EN**, via :
- Scraping multi-sites publics
- Rotation Groq multi-modèles
- Exports unifiés (jobs + remote)

## 3) Sites retenus (publics, sans login)
### Tutorat (entre particuliers)
- `voscours` — demandes d’élèves
- `findtutors_uk` — demandes d’élèves UK

### Général (entre particuliers)
- `jemepropose`
- `allovoisins`

### Pro / job boards (optionnel via `--include-pro-sources`)
- `codeur`
- `freelance.com`
- `comet`
- `remoteok`
- `remotive`
- `workingnomads`
- `arbeitnow`
- `malt` — *bloqué (HTTP 403) sans contournement*

### Sites locaux optionnels
- `jemepropose`, `allovoisins` (faible densité remote)

> Sites nécessitant login : **exclus** (ex: RingTwice).

## 4) Feuille de route technique
1. **Nettoyage repo** : purge cache/logs/archives, suppression fichiers obsolètes.
2. **Scrapers manquants** : implémenter `VosCoursScraper`, `FindTutorsUKScraper`, `CodeurScraper`.
3. **Pipeline unifié** : exécuter général + tutorat, fusionner dans `jobs_latest` et `remote_jobs_latest`.
4. **Historique & cache** : historiser URLs, invalidation par modèle, métriques cohérentes.
5. **Rotation Groq** : bascule automatique sur le modèle dispo (quota/capacité).
6. **Validation HTML** : après 1er run, ajuster les sélecteurs selon le DOM réel.

## 5) Tests & validation
- `remote_jobs_latest.json` contient tutorat + général remote.
- `jobs_latest.json` contient tous les postes avec métadonnées enrichies.
- `metrics_latest.json` inclut usage cache + modèles.

## 6) Suivi recommandé (prochaine itération)
- Ajuster les sélecteurs avec le HTML réel des pages.
- Ajouter d’autres sites tutorat FR/EN si ouverts.
- Ajouter détection légère de langue si besoin (FR/EN).
