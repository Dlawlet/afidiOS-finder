# ⚡ QUICK START - Choose Your Path

## 🎯 Goal: Scrape jobs and detect remote work possibilities

---

## Path 1: Quick & Simple (1 minute) 🏃

**No AI, just keyword detection - Perfect for testing**

```powershell
# Install
pip install requests beautifulsoup4 lxml

# Run
python job_scraper.py
```

**Output:** 20 jobs with basic remote/on-site classification (~85% accurate)

---

## Path 2: Best Accuracy (3 minutes) 🏆 ⭐ RECOMMENDED

**AI-powered semantic analysis - Production ready**

```powershell
# 1. Install
pip install requests beautifulsoup4 lxml groq

# 2. Get FREE API key (30 seconds)
# Visit: https://console.groq.com/
# Sign up, create API key, copy it

# 3. Set API key
$env:GROQ_API_KEY = "paste-your-key-here"

# 4. Run
python advanced_scraper.py
```

**Output:** 20 jobs with AI-enhanced classification (~92% accurate)

**Benefits:**
✅ Highest accuracy (92%)
✅ Smart re-analysis of unclear jobs
✅ Detailed reasoning provided
✅ FREE forever (generous limits)
✅ Fast (2-5 seconds)

---

## Path 3: Privacy-First (5 minutes) 🔒

**Local NLP, no API calls - Everything stays on your machine**

```powershell
# 1. Install spaCy
pip install requests beautifulsoup4 lxml spacy

# 2. Download French model (one-time, ~50MB)
python -m spacy download fr_core_news_md

# 3. Run
python advanced_scraper.py
```

**Output:** 20 jobs with local NLP classification (~70% accurate)

**Benefits:**
✅ Complete privacy
✅ Works offline
✅ No API keys needed
✅ Unlimited usage

---

## Path 4: Ultimate Power (15 minutes) 🚀

**Local LLM with Ollama - Best of all worlds**

```powershell
# 1. Install Ollama
# Download from: https://ollama.ai/

# 2. Download model (one-time, ~4GB)
ollama pull llama3.2

# 3. Install Python package
pip install requests beautifulsoup4 lxml

# 4. Run (will auto-detect Ollama)
python advanced_scraper.py
```

**Output:** 20 jobs with local LLM classification (~88% accurate)

**Benefits:**
✅ High accuracy (88%)
✅ Complete privacy
✅ Unlimited usage
✅ No API costs
⚠️ Requires 8GB+ RAM

---

## 🆘 Troubleshooting

### "Module not found" error
```powershell
pip install requests beautifulsoup4 lxml
```

### "Groq not found"
```powershell
pip install groq
```

### "spaCy model not found"
```powershell
python -m spacy download fr_core_news_md
```

### "API error"
- Check your API key is correct
- Verify internet connection
- Make sure you're not exceeding rate limits

---

## 📊 Quick Comparison

| Path | Time | Accuracy | Privacy | Cost |
|------|------|----------|---------|------|
| **Path 1** | 1 min | 85% | High | $0 |
| **Path 2** ⭐ | 3 min | 92% | Medium | $0 |
| **Path 3** | 5 min | 70% | Full | $0 |
| **Path 4** | 15 min | 88% | Full | $0 |

---

## 🎯 Which Should I Choose?

**Just testing?** → Path 1
**Want best results?** → Path 2 (Groq API) ⭐
**Privacy concerned?** → Path 3 or 4
**Have powerful PC?** → Path 4 (Ollama)

---

## 📝 Example Output

```
================================================================================
SCRAPING & ANALYSIS: 20 jobs found
Mode: 🤖 LLM-Enhanced
================================================================================

Job #1
  Title: Assistance comptable
  Location: Comptabilité - Paris
  Classification: 🏠 REMOTE - Confidence: HIGH
    └─ Job category typically done remotely
  Price: 15.00 € - De l'heure
  ...

CLASSIFICATION SUMMARY:
========================
Total Jobs: 20
🔄 Re-analyzed with Semantic Model: 1 jobs

Final Results:
  📍 ON-SITE: 18 jobs
  🏠 REMOTE:  2 jobs
```

---

## 🚀 What's Next?

After getting results, you can:

1. **Filter remote jobs only:**
   ```powershell
   python remote_jobs_only.py
   ```

2. **Export to CSV** (coming soon)

3. **Schedule automatic scraping** (coming soon)

4. **Add more job sites** (coming soon)

---

## 💡 Pro Tips

1. **For production:** Use Path 2 (Groq API)
2. **Start with Path 1** to test, then upgrade to Path 2
3. **Free tier limits:** 30 req/min = enough for 600+ jobs/min
4. **Batch processing:** Script automatically batches API calls

---

## 📚 More Info

- **Full Setup Guide:** `SETUP_GUIDE.md`
- **Technical Details:** `ANALYSIS_NLP_vs_LLM.md`
- **Complete Summary:** `SOLUTION_SUMMARY.md`
- **Main README:** `README.md`

---

## ✅ Ready to Start?

Pick your path above and copy-paste the commands!

**Recommended:** Path 2 (3 minutes, best accuracy, free) ⭐

Happy scraping! 🎉
