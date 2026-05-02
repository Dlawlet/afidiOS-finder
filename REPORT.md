# Investigation Report — GitHub Actions Failures & Remote Jobs = 1

**Date:** 2026-05-02  
**Run investigated:** Daily Job Scraper #25249538388 (2026-05-02 10:07 UTC)

---

## Issue 1 — `remote_jobs` contains only 1 result

### Root cause

The LLM model configured in `semantic_analyzer.py` (`moonshotai/kimi-k2-instruct`) **no longer exists** on Groq:

```
groq.NotFoundError: Error code: 404 — The model `moonshotai/kimi-k2-instruct` does not exist
or you do not have access to it.
```

Every LLM call fails, and the code falls back to local NLP keyword scoring.

### How the NLP fallback behaves

The NLP fallback counts keyword hits from two lists:

| List | Keywords |
|------|---------|
| Remote | télétravail, remote, distance, en ligne, numérique, web, design, … |
| On-site | sur place, présentiel, domicile, nettoyer, réparer, construire, … |

For **allovoisins** and **ringtwice** jobs (neighbourhood help / small missions), most listings:
- Have no description (`N/A`)
- Title only: "Recherche Jardinier à Pessac", "Besoin aide déménagement", …
- Both remote and on-site scores = **0**

When scores tie at 0/0, the fallback **defaults to `is_remote=False`** (see `semantic_analyzer.py` lines 532–539). This means almost every ambiguous job (which is the majority) gets classified as on-site.

### Result

478 jobs processed → **477 classified on-site** by NLP default → **1 classified remote** (the single job whose title contained "Secrétariat", scoring 3 vs 0).

### Fix required

- Switch to a valid Groq model (e.g. `llama-3.3-70b-versatile`).
- Make the model configurable via an environment variable so future deprecations are handled without code changes.
- Improve the NLP fallback: ambiguous digital-category jobs should default to `is_remote=True` instead of `False` (the LLM prompt already encodes this rule — rule #6).

---

## Issue 2 — `git` exit code 128 warning

### Log evidence

```
fatal: No url found for submodule path '.claude/worktrees/agent-ae66ddd8' in .gitmodules
##[warning]The process '/usr/bin/git' failed with exit code 128
```

### Root cause

The `actions/checkout@v4` post-job cleanup runs:
```bash
git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' …"
```

Git detects two gitlink entries (mode `160000`) in the repository index:
- `.claude/worktrees/agent-ae66ddd8`
- `.claude/worktrees/agent-af54d916`

These are leftover Copilot agent worktree directories that were accidentally `git add`-ed and committed as **gitlink/submodule references**. Because there is no `.gitmodules` file defining these paths, `git submodule foreach` fails with exit code 128.

### Impact

The push itself **succeeded** (`a5eb693..4d54dbf  main -> main`). The exit code 128 is only from the cleanup step — it does not block the workflow, but it is a warning and will become a problem in future action versions.

### Fix required

- Remove `.claude/worktrees/agent-ae66ddd8` and `.claude/worktrees/agent-af54d916` from git tracking (`git rm -r --cached`).
- Add `.claude/worktrees/` to `.gitignore`.

---

## Issue 3 — Node.js 20 deprecation warnings

### Warning

```
Node.js 20 actions are deprecated. The following actions are running on Node.js 20 and may not work
as expected: actions/cache@v4, actions/checkout@v4, actions/setup-python@v5.
Actions will be forced to run with Node.js 24 by default starting June 2nd, 2026.
```

### Cause

The workflow files pin `actions/cache@v4`, `actions/checkout@v4`, and `actions/setup-python@v5`. These `@v4`/`@v5` tags still point to Node.js 20 runtimes.

### Fix

Add the `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` environment variable to the workflow env block, which opts in to Node.js 24 now (before the forced migration deadline). Alternatively, update to newer patch/minor versions of the actions that bundle Node.js 24 when/if available.

---

## Summary table

| # | Issue | Root cause | Impact | Fixed in this PR |
|---|-------|-----------|--------|-----------------|
| 1 | `remote_jobs` = 1 | Invalid Groq model `moonshotai/kimi-k2-instruct` | All jobs classified on-site by broken NLP default | ✅ |
| 2 | git exit code 128 | `.claude/worktrees` committed as gitlinks | Warning in CI post-cleanup | ✅ |
| 3 | Node.js 20 deprecation | Actions using Node.js 20 runtime | Will break after 2026-06-02 | ✅ |
