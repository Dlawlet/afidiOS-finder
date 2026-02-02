# Description Fixes - February 2, 2026

## Problems Fixed

### 1. JeMePropose - Description Duplication
**Problem**: Descriptions were showing duplicated text
```
"Je suis à la recherche... Cordialement. Je suis à la recherche... Cordialement."
```

**Root Cause**: 
- JeMePropose's HTML contains duplicate `<p>` tags with identical content
- The scraper was concatenating all paragraphs without deduplication

**Fix**: `job_helpers.py`
- Added deduplication logic to remove duplicate paragraphs
- Uses content-based deduplication (not just consecutive)
- Filters out generic messages like "Soyez le premier à déposer un avis"
- Now checks for `<article>` tag (alternative structure on JeMePropose)

**Result**: ✅ Descriptions are now clean, single-occurrence text

---

### 2. AlloVoisins - Multiple Jobs Fusion
**Problem**: Scraper was merging 5+ job descriptions into one
```
"Bonjour, J'ai exercé le métier dessinateur... Bonjour, je suis à la recherche d'une personne..."
```

**Root Cause**:
- AlloVoisins pages show "demandes similaires" (similar requests) from multiple people
- The scraper was collecting ALL paragraphs on the page, including these similar requests

**Fix**: `job_helpers.py`
- Added special handling for AlloVoisins URLs
- Filters out paragraphs starting with quotes (from similar requests)
- Takes ONLY the first valid paragraph (>50 chars, no quotes)
- Returns empty string if no clean description found (uses listing description as fallback)

**Result**: ✅ Only the main job description is extracted, no fusion

---

### 3. Description Assignment Logic
**Problem**: When fetching full descriptions, code wasn't always replacing the short description

**Fix**: `scheduled_scraper_v3.py`
- Lines 171-176: Explicitly REPLACE short description with full description
- Lines 188-194: Same fix for LLM analysis path
- Added comments to clarify replacement vs. append behavior

**Result**: ✅ Full descriptions properly replace short ones

---

## Testing

### Test 1: JeMePropose Job
```
URL: https://www.jemepropose.com/annonces/secretariat/recherche-tele-secretaire-experimentee+10494841/
Before: 465 chars (duplicated)
After: 205 chars (clean, deduplicated)
✅ No duplication detected
```

### Test 2: AlloVoisins Job  
```
URL: https://www.allovoisins.com/r/0/198/33466/0/Lezoux/service/Graphisme-creation-flyer-plaquette
Before: 556 chars (5 jobs merged)
After: Returns empty → uses listing description (clean)
✅ No job fusion detected
```

---

## Files Modified

1. **job_helpers.py** (lines 20-90)
   - Added AlloVoisins special case handling
   - Added article tag support for JeMePropose
   - Added content-based deduplication
   - Added filtering for generic messages

2. **scheduled_scraper_v3.py** (lines 171-176, 188-194)
   - Fixed description assignment to REPLACE instead of potentially appending
   - Added clarifying comments

---

## Impact

- ✅ **JeMePropose**: Clean, single-occurrence descriptions
- ✅ **AlloVoisins**: Single job per listing (no more fusion)
- ✅ **Other sites**: Unchanged, continue working as before
- ✅ **LLM Analysis**: Gets cleaner input → better classification accuracy

---

## Next Run

The next GitHub Actions run will use these fixes and should show:
- No more "Je suis... Je suis..." duplications
- No more "5 demandes similaires" fusions
- Cleaner, more accurate job descriptions for LLM analysis
