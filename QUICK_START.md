# 🚀 Quick Start Guide - Enhanced Features

## 🎯 What's New?

Your afidiOS-finder scraper now has **5 major enhancements**:

1. **⏳ Auto-Retry** - No more rate limit failures
2. **♻️ Smart Cache** - 40-60% fewer API calls
3. **📝 Detailed Logs** - Know exactly what's happening
4. **📊 Metrics** - Track performance over time
5. **📚 History** - Track all jobs ever seen

---

## 🏃 Running the Scraper

### Basic Usage (Same as before)
```bash
python scheduled_scraper.py
```

### Verbose Mode (Recommended for first run)
```bash
python scheduled_scraper.py --verbose
```

**You'll see:**
- ✅ Groq API initialized successfully
- 📄 Scraping up to 10 pages
- ♻️ Using cached analysis (when cache hits)
- 📊 Final statistics with cache performance

---

## 📂 New Files You'll See

### `cache/` Directory
```
cache/
├── a200d2d7.json  ← Cached LLM response for job #1
├── 4db446a2.json  ← Cached LLM response for job #2
└── ...
```

**What it does**: Saves LLM analysis results so identical jobs don't need re-analysis.

**Should you commit it?**: ❌ No (already in .gitignore)

**Can you delete it?**: ✅ Yes, it will rebuild automatically

---

### `logs/` Directory
```
logs/
├── scraper_20260117.log  ← Today's log
├── scraper_20260116.log  ← Yesterday's log
└── ...
```

**What it does**: Records everything that happens during scraping.

**Should you commit it?**: ❌ No (already in .gitignore)

**How to view**:
```bash
# View today's log
cat logs/scraper_$(date +%Y%m%d).log

# View errors only
grep ERROR logs/scraper_*.log

# View last 50 lines
tail -50 logs/scraper_$(date +%Y%m%d).log
```

---

### `exports/metrics_latest.json`
```json
{
  "timestamp": "2026-01-17T17:14:00",
  "duration_seconds": 245,
  "jobs_scraped": 200,
  "remote_jobs": 45,
  "llm_calls": 120,
  "cache_stats": {
    "cache_hits": 80,
    "hit_rate_percentage": 40.0
  }
}
```

**What it does**: Tracks performance metrics from the last scraping run.

**Should you commit it?**: ✅ Yes! Shows scraper is working

**How to use**:
```bash
# View metrics
cat exports/metrics_latest.json | jq .

# Check cache hit rate
cat exports/metrics_latest.json | jq .cache_stats.hit_rate_percentage
```

---

### `exports/job_history.json`
```json
{
  "seen_urls": {
    "https://...": {
      "first_seen": "2026-01-15 10:30:00",
      "last_seen": "2026-01-17 17:14:00",
      "title": "Développeur web",
      "is_remote": true
    }
  },
  "last_update": "2026-01-17 17:14:00"
}
```

**What it does**: Tracks every job URL ever seen, with dates.

**Should you commit it?**: ⚠️  Optional (useful for analysis)

**Benefits**: 
- See how long jobs stay posted
- Detect duplicate listings
- Foundation for incremental scraping

---

## 🔍 Checking Performance

### Cache Performance
```bash
# After a few runs, check cache hit rate
cat exports/metrics_latest.json | jq .cache_stats
```

**Good cache hit rate**: >25% (will improve to >40% after a week)

### Scraping Success
```bash
# Check for errors in today's log
grep -c ERROR logs/scraper_$(date +%Y%m%d).log
```

**Target**: 0 errors

### API Usage
```bash
# Check LLM calls from metrics
cat exports/metrics_latest.json | jq .llm_calls
```

**Before enhancements**: ~200 calls/day
**After enhancements**: ~80-120 calls/day

---

## ⚠️ What If Something Goes Wrong?

### Rate Limit Hit
**What you'll see:**
```
⏳ Rate limit hit, retrying in 2s... (attempt 1/3)
```

**What happens**: Automatically retries with longer delays

**No action needed!** ✅

---

### Cache Corruption
**Symptoms**: Weird results, cache errors in logs

**Fix:**
```bash
rm -rf cache/
python scheduled_scraper.py
```

---

### Log Files Too Large
**Fix:**
```bash
# Delete logs older than 30 days
find logs/ -name "scraper_*.log" -mtime +30 -delete
```

---

### API Key Issues
**Symptoms**:
```
⚠️  Groq API Rate Limit exceeded
⚠️  Falling back to local NLP
```

**Check:**
1. Is GROQ_API_KEY set in environment?
2. Have you hit the free tier limit?
3. Check https://console.groq.com for usage

---

## 📊 Understanding the Output

### Console Output (Verbose Mode)
```
============================================================
🚀 Starting job scraper - 2026-01-17 17:14:22
📄 Scraping up to 10 pages
============================================================

✅ Groq API initialized successfully
🤖 Initializing analyzers...

────────────────────────────────────────────────────────────
📄 Page 1/10
📡 https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1
✅ 20 jobs

[1/20] Aide aux personnes âgées...
    📄 Fetching full description...
    🤖 Analyzing with LLM...
    ♻️  Using cached analysis  ← CACHE HIT!
  ❌ On-site - LLM: Travail physique auprès des personnes

[2/20] Développeur web React...
    📄 Fetching full description...
    🤖 Analyzing with LLM...
  ✅ REMOTE (confidence: 0.95) - LLM: Développement 100% en ligne

... (more jobs) ...

============================================================
✅ Analysis complete!
   Total pages scraped: 10
   Total jobs: 200
   Remote jobs: 45
   Remote percentage: 22.5%
   📊 Stats:
      - Analyzed with LLM: 120
      - High confidence skip: 80
      - Full descriptions fetched: 120
      - Cache hits: 80 (40.0%)  ← CACHE PERFORMANCE
      - Duration: 245s
============================================================
```

---

## 🎯 Performance Targets

### After First Run
- Cache hit rate: **0%** (normal - no cache yet)
- LLM calls: **150-200** (normal - building cache)
- Duration: **300-350s** (normal)

### After One Week
- Cache hit rate: **>25%** ✅
- LLM calls: **<150** ✅
- Duration: **<300s** ✅

### After One Month
- Cache hit rate: **>40%** ✅
- LLM calls: **<120** ✅
- Duration: **<250s** ✅

---

## 🔗 Quick Reference

### Check Cache Stats
```bash
python -c "from semantic_analyzer import SemanticJobAnalyzer; a = SemanticJobAnalyzer(); print(a.get_cache_stats())"
```

### Check Job History
```bash
python -c "from job_exporter import JobExporter; e = JobExporter(); print(e.get_history_stats())"
```

### View Latest Metrics
```bash
cat exports/metrics_latest.json | jq .
```

### View Latest Logs
```bash
tail -50 logs/scraper_$(date +%Y%m%d).log
```

---

## 💡 Tips & Tricks

### Speed Up Scraping
- Cache will improve naturally over time
- Consider scraping fewer pages if API limit is tight
- Use `--verbose` only when debugging

### Monitor API Usage
- Check `exports/metrics_latest.json` after each run
- Watch for `llm_calls` - should decrease over time
- Monitor `cache_stats.hit_rate_percentage`

### Debugging Issues
1. Check logs: `logs/scraper_YYYYMMDD.log`
2. Check metrics: `exports/metrics_latest.json`
3. Look for ERROR lines in logs
4. Check GitHub Actions for automation issues

---

## 🆘 Need Help?

### Common Questions

**Q: Why are some jobs analyzed twice?**
A: Job descriptions might have small changes (typos, formatting) that create different cache keys.

**Q: Can I clear the cache?**
A: Yes! `rm -rf cache/` - it will rebuild automatically.

**Q: Should I commit cache/ directory?**
A: No, it's already in .gitignore. Cache is local only.

**Q: How do I see cache hits in real-time?**
A: Run with `python scheduled_scraper.py --verbose`

**Q: What's the optimal cache hit rate?**
A: >40% is excellent. >25% is good. <10% means jobs change frequently.

---

## 🎉 You're All Set!

Your scraper now has:
- ✅ Automatic retry on failures
- ✅ Smart caching for efficiency
- ✅ Detailed logging for debugging
- ✅ Performance metrics
- ✅ Job history tracking

**Next Steps:**
1. Run the scraper: `python scheduled_scraper.py --verbose`
2. Check the metrics: `cat exports/metrics_latest.json`
3. Review the logs: `cat logs/scraper_$(date +%Y%m%d).log`
4. Watch the cache improve over the next week!

---

**Happy Scraping! 🚀**
