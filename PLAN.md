# Enhancement Plan — afidiOS-finder

**Date:** 2026-05-02  
**Status:** In progress

---

## Overall objective

Automatically discover and export **remote-work** opportunities (and tutoring requests) from French/Belgian neighbourhood-help platforms. Results are pushed daily to the repository and consumed downstream.

---

## Immediate fixes (critical)

### 1. Fix the LLM model

- **Problem:** `moonshotai/kimi-k2-instruct` no longer exists on Groq → all jobs classified as on-site.
- **Fix:**
  - Change default model to `llama-3.3-70b-versatile` (currently available on Groq free tier).
  - Read the model name from `GROQ_MODEL` env variable so future changes need no code edit.
  - Add a one-time model-validation check at startup; log a clear error if the model is unavailable.

### 2. Fix NLP fallback default

- **Problem:** Ambiguous jobs (score 0/0) default to `is_remote=False`, but the LLM prompt rule #6 says digital work should default to remote.
- **Fix:**
  - When both NLP scores are 0 and the job title/description contains digital-category signals, default to `is_remote=True` with low confidence (0.3).
  - Return `reason` = `"NLP: Ambiguous — no physical-work signal, defaulting to on-site"` or `"NLP: Digital context, defaulting to remote"` for transparency.

### 3. Fix git cleanup exit code 128

- **Problem:** `.claude/worktrees/` committed as gitlinks causes `git submodule foreach` to fail.
- **Fix:**
  - `git rm -r --cached .claude/worktrees/`
  - Add `.claude/worktrees/` to `.gitignore`.

### 4. Opt in to Node.js 24 for GitHub Actions

- **Problem:** `actions/cache@v4`, `actions/checkout@v4`, `actions/setup-python@v5` run on deprecated Node.js 20.
- **Fix:** Add `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` to the `env:` block of both workflow files.

---

## Short-term improvements

### 5. Configurable model via environment variable

Allow the Groq model to be overridden without touching code:
```yaml
env:
  GROQ_MODEL: "llama-3.3-70b-versatile"
```

### 6. Smarter git push (handle concurrent runs)

The `git push` occasionally fails with a non-fast-forward rejection when two scheduled runs overlap. Add a pull-rebase-and-retry step:
```bash
git pull --rebase origin main && git push
```

### 7. Model availability guard at startup

Before processing any jobs, test a single tiny API call. If the model is unavailable, emit a clear `[ERROR]` log and fail fast instead of silently degrading to NLP for every job.

### 8. Richer description scraping

Most listings have `description: N/A` because the scraper only reads the listing-card preview. Implement per-source detail-page fetching for jemepropose and allovoisins (the `JobDescriptionFetcher` already exists but is only used for LOW-confidence jobs):
- Fetch the detail page for **every** new job before LLM analysis.
- This greatly increases LLM accuracy because the job body is richer.

### 9. Cache invalidation on model change

When the model name changes, existing cache files (hashed on title+description+location) may contain stale results from a different model. Add the model name as part of the hash or store it in cache metadata and skip cached entries from a different model.

### 10. Improve metrics export

Currently `metrics_latest.json` includes LLM call count but not:
- Per-site breakdown of remote vs on-site
- Model name used
- Fallback rate (% of jobs analyzed by NLP vs LLM)

Add these fields to help debug future classification regressions quickly.

---

## Medium-term improvements

### 11. Add more remote-friendly sources

The three current sites (jemepropose, allovoisins, ringtwice) are neighbourhood-help platforms where most missions are physical. Consider adding:
- **malt.fr** (already in scraper_map but not activated) — high density of remote digital freelance missions.
- **codeur.com** (already in scraper_map) — 100% digital.

### 12. Tutoring pipeline: fix concurrency push collision

Both the general scraper and the tutoring scraper push to `exports/`. If the tutoring run starts before the general run's push is visible, the tutoring run will fail to push (non-fast-forward). Add `git pull --rebase` before push in both workflows.

### 13. Improve NLP keyword coverage

Extend the remote and on-site keyword lists with more French neighbourhood-platform terms:
- Remote additions: `cours particuliers`, `en visio`, `par téléphone`, `e-learning`, `formation en ligne`
- On-site additions: `à votre domicile`, `intervention à`, `présence physique`, `cours à domicile`

---

## Applied in this PR

- [x] Fix 1: LLM model (`moonshotai/kimi-k2-instruct` → `llama-3.3-70b-versatile`, env-var configurable)
- [x] Fix 2: NLP fallback default (ambiguous digital → remote, physical → on-site)
- [x] Fix 3: Remove `.claude/worktrees` gitlinks, update `.gitignore`
- [x] Fix 4: `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` in both workflow files
- [x] Improvement 5: `GROQ_MODEL` env variable
- [x] Improvement 6: `git pull --rebase` before push in both workflows
- [x] Improvement 7: Model availability guard at startup
- [x] Improvement 10: Add model name + fallback rate to metrics export
