# 🚀 Branch Testing - afidiOS-finder

## 📌 Vue d'ensemble

Cette branche contient les améliorations majeures pour le scraper:

1. ✅ **WorkingNomads Scraper** - Nouvelle source de jobs distants
2. ✅ **Mission Type Filter** - Détection et filtrage des types de missions
3. ✅ **Integration Tests** - Suite de tests pour valider les fonctionnalités
4. ✅ **Documentation** - Guides d'utilisation complets

## 📋 What's New

### 1. WorkingNomads Support
```python
from site_scrapers import WorkingNomadsScraper

scraper = WorkingNomadsScraper(verbose=True)
jobs, has_more = scraper.scrape_page(1)
```

**URL**: https://www.workingnomads.co/jobs
**Type**: Remote jobs aggregator
**Status**: ✅ Prêt à l'emploi

### 2. Mission Type Detection
```python
from mission_type_filter import filter_jobs_by_mission_type

# Filtrer jobs pour exclure CDI/CDD/Freelance marketplace
filtered_jobs, stats = filter_jobs_by_mission_type(
    jobs,
    exclude_types=['cdi', 'cdd', 'freelance']
)

# Stats retournées:
# {
#     'total': 100,
#     'included': 60,        # Missions valides
#     'cdi': 10,             # Exclu
#     'cdd': 8,              # Exclu
#     'freelance': 22,       # Exclu (Malt, Freelance.com, etc)
#     'mission': 50,         # Inclus
#     'unknown': 10
# }
```

**Types Détectés**:
- `cdi` - Contrat permanent → ❌ Exclu
- `cdd` - Contrat temporaire → ❌ Exclu
- `freelance` - Marketplace (Malt, Freelance.com) → ❌ Exclu
- `mission` - Missions entre particuliers → ✅ Inclus
- `unknown` - Indéterminé (supposé mission) → ✅ Inclus

### 3. Pipeline Complet

```
Scraping
    ↓
[Phase 1] Scraper Multi-Site (jemepropose, malt, workingnomads, etc)
    ↓
[Phase 2] Incremental Filtering (new vs cached)
    ↓
[Phase 2.5] 🆕 MISSION TYPE FILTERING (CDI/CDD/Freelance excluded)
    ↓
[Phase 3] Groq LLM Analysis (remote detection)
    ↓
Export (CSV/JSON)
```

## 🧪 Tests

### Lancer la suite de tests

```bash
# Full test suite
python test_groq_integration.py

# Individual tests
python -c "from test_groq_integration import test_mission_type_filter; test_mission_type_filter()"
```

### Résultats Attendus

```
✅ Mission Type Filter: 5/5 tests PASS
  - CDI detection
  - CDD detection
  - Freelance marketplace detection
  - Valid missions detection
  - Source-based detection

✅ Mission Filtering: Correctement filtre 2/4 jobs
  - Inclus: Missions valides
  - Exclu: CDI, Freelance

⚠️  Groq API: En attente de GROQ_API_KEY en environnement
```

## 💻 Utilisation

### Option 1: Scraper Single Site
```bash
# WorkingNomads seulement
python scheduled_scraper_v3.py --sites workingnomads --pages 3 --verbose
```

### Option 2: Multi-Site avec Filtrage
```bash
# Tous les sites avec filtrage
python scheduled_scraper_v3.py \
  --sites jemepropose allovoisins workingnomads \
  --pages 5 \
  --verbose
```

### Option 3: Python API
```python
from scheduled_scraper_v3 import scrape_multi_site

results = scrape_multi_site(
    sites=['jemepropose', 'workingnomads'],
    use_llm=True,
    verbose=True
)
```

## 📊 Fichiers Modifiés

```
Modified:
- site_scrapers.py              (+WorkingNomadsScraper)
- scheduled_scraper_v3.py       (+MissionTypeFilter import, Phase 2.5)

New Files:
- mission_type_filter.py        (Mission type detection & filtering)
- test_groq_integration.py      (6 test cases)
- IMPROVEMENTS_V2.md            (Documentation)
- BRANCH_TESTING.md             (This file)
```

## 🔐 Configuration Groq

Pour tester avec Groq LLM:

```bash
# Windows PowerShell
$env:GROQ_API_KEY = "gsk_..."

# Linux/Mac
export GROQ_API_KEY="gsk_..."

# Puis lancer le scraper
python scheduled_scraper_v3.py --sites workingnomads --verbose
```

## 🎯 Prochaines Étapes

### Avant Merge à Main:
- [ ] Tester avec vraies données (Groq API)
- [ ] Vérifier les scrapers sur pages réelles
- [ ] Améliorer les sélecteurs CSS/XPath
- [ ] Tester le filtrage end-to-end

### Pour la v2:
- [ ] Ajouter Playwright pour sites JS-heavy
- [ ] Intégrer plus de sources (TaskRabbit, RingTwice)
- [ ] Dashboard de monitoring
- [ ] Performance optimization

## 📚 Documentation

- `IMPROVEMENTS_V2.md` - Détails complets des features
- `README.md` (root) - Documentation générale du projet
- Code comments - Explications inline

## 🐛 Troubleshooting

### Groq API not found
```bash
# Vérifier que la clé est définie
echo $env:GROQ_API_KEY  # PowerShell
echo $GROQ_API_KEY      # Linux/Mac
```

### Jobs not scraped
Les selectors CSS doivent être ajustés pour chaque site. Vérifier:
- `site_scrapers.py` → classes `JeMeProposeScraper`, `AlloVoisinsScraper`, etc.
- Adapter les `find_all()` et `find()` selectors

### Tests fail
```bash
# Run with verbose output
python test_groq_integration.py  # Shows detailed errors

# Debug individual test
python -c "
from test_groq_integration import test_mission_type_filter
test_mission_type_filter()
"
```

## 📞 Support

Issues/questions sur cette branche → créer une discussion GitHub

## ✨ Commits sur cette branche

```
435ff8a - docs: Add documentation and integrate mission type filter
6c8d64a - feat: Add WorkingNomads scraper + Mission Type Filter
```

---

**Status**: ✅ Ready for Testing
**Target**: Merge to `main` après validation
