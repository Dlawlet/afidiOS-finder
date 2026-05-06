#!/bin/bash
# Merge testing → main avec sécurité

set -e

echo "════════════════════════════════════════"
echo "🔀 Merging testing → main"
echo "════════════════════════════════════════"

# 1. Vérifier que on est sur une branche valide
CURRENT=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $CURRENT"

# 2. Fetch latest
echo "📥 Fetching latest..."
git fetch origin

# 3. Check if testing has new commits vs main
echo ""
echo "📊 Comparing branches..."
NEW_COMMITS=$(git log --oneline main..testing | wc -l)
echo "New commits on testing: $NEW_COMMITS"

if [ $NEW_COMMITS -eq 0 ]; then
  echo "⚠️  No new commits to merge"
  exit 1
fi

# 4. Show what will be merged
echo ""
echo "🔍 Changes to be merged:"
git log --oneline main..testing

echo ""
echo "📝 Files that will change:"
git diff --name-only main..testing

# 5. Confirm before proceeding
echo ""
read -p "Continue with merge? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Merge cancelled"
  exit 1
fi

# 6. Checkout main
echo "🔀 Checking out main..."
git checkout main

# 7. Merge testing
echo "🔗 Merging testing → main..."
git merge testing -m "Merge: Integrate testing features into main

- Add WorkingNomads scraper
- Add Mission Type Filter
- Integrate Phase 2.5 filtering
- Add comprehensive tests
- Add documentation"

# 8. Push
echo ""
echo "📤 Pushing to origin..."
git push origin main

echo ""
echo "✅ Merge complete!"
echo "🎉 testing → main successful"
echo ""
echo "Next steps:"
echo "  - GitHub Actions will now run on main"
echo "  - Results will be pushed to main branch"
echo "  - Check: https://github.com/Dlawlet/afidiOS-finder/actions"

