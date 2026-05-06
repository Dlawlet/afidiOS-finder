#!/usr/bin/env pwsh
# Merge testing → main (PowerShell version for Windows)

Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "🔀 Merging testing → main" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. Check current branch
$current = git rev-parse --abbrev-ref HEAD
Write-Host "Current branch: $current" -ForegroundColor Yellow

# 2. Fetch latest
Write-Host "📥 Fetching latest..." -ForegroundColor Blue
git fetch origin

# 3. Check commits
Write-Host ""
Write-Host "📊 Comparing branches..." -ForegroundColor Blue
$commits = @(git log --oneline main..testing)
$newCommits = $commits.Count
Write-Host "New commits on testing: $newCommits"

if ($newCommits -eq 0) {
  Write-Host "⚠️  No new commits to merge" -ForegroundColor Yellow
  exit 1
}

# 4. Show changes
Write-Host ""
Write-Host "🔍 Changes to be merged:" -ForegroundColor Cyan
git log --oneline main..testing

Write-Host ""
Write-Host "📝 Files that will change:" -ForegroundColor Cyan
git diff --name-only main..testing

# 5. Confirm
Write-Host ""
$response = Read-Host "Continue with merge? (y/n)"
if ($response -ne 'y' -and $response -ne 'Y') {
  Write-Host "Merge cancelled" -ForegroundColor Yellow
  exit 1
}

# 6. Checkout main
Write-Host ""
Write-Host "🔀 Checking out main..." -ForegroundColor Blue
git checkout main

# 7. Merge
Write-Host "🔗 Merging testing → main..." -ForegroundColor Blue
git merge testing -m @"
Merge: Integrate testing features into main

- Add WorkingNomads scraper
- Add Mission Type Filter
- Integrate Phase 2.5 filtering
- Add comprehensive tests
- Add documentation
"@

# 8. Push
Write-Host ""
Write-Host "📤 Pushing to origin..." -ForegroundColor Blue
git push origin main

# 9. Success
Write-Host ""
Write-Host "✅ Merge complete!" -ForegroundColor Green
Write-Host "🎉 testing → main successful" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  - GitHub Actions will now run on main"
Write-Host "  - Results will be pushed to main branch"
Write-Host "  - Check: https://github.com/Dlawlet/afidiOS-finder/actions"
Write-Host ""

