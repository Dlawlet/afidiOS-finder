"""Analyze job_history.json to understand caching patterns"""
import json
from datetime import datetime, timedelta
from collections import Counter

# Load job history
with open('exports/job_history.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

jobs = data.get('seen_urls', {})
print(f"📊 Total jobs in history: {len(jobs)}\n")

# Analyze timestamps
now = datetime(2026, 2, 1, 18, 30)  # Approximate current time
lookback_24h = now - timedelta(hours=24)
lookback_48h = now - timedelta(hours=48)

recent_24h = []
recent_48h = []
older = []

for url, job in jobs.items():
    last_seen_str = job.get('last_seen', '')
    if last_seen_str:
        try:
            last_seen = datetime.strptime(last_seen_str, '%Y-%m-%d %H:%M:%S')
            if last_seen >= lookback_24h:
                recent_24h.append(job)
            elif last_seen >= lookback_48h:
                recent_48h.append(job)
            else:
                older.append(job)
        except:
            pass

print(f"🕐 Jobs seen in last 24h: {len(recent_24h)} (these would be CACHED in GitHub Actions)")
print(f"🕐 Jobs seen 24-48h ago: {len(recent_48h)} (expired from cache)")
print(f"🕐 Jobs older than 48h: {len(older)}\n")

# Analyze remote classifications
remote_count = sum(1 for j in jobs.values() if j.get('is_remote') == True)
onsite_count = sum(1 for j in jobs.values() if j.get('is_remote') == False)
print(f"🏠 Classification breakdown:")
print(f"  Remote: {remote_count} ({remote_count/len(jobs)*100:.1f}%)")
print(f"  On-site: {onsite_count} ({onsite_count/len(jobs)*100:.1f}%)\n")

# Check recent 24h classifications
if recent_24h:
    remote_24h = sum(1 for j in recent_24h if j.get('is_remote') == True)
    print(f"📅 Last 24h classifications:")
    print(f"  Remote: {remote_24h}/{len(recent_24h)} ({remote_24h/len(recent_24h)*100:.1f}%)")
    print(f"  On-site: {len(recent_24h) - remote_24h}/{len(recent_24h)} ({(len(recent_24h) - remote_24h)/len(recent_24h)*100:.1f}%)\n")

# Show sample of recent jobs
print(f"📝 Sample of last 5 jobs seen:")
sorted_jobs = sorted(
    [(url, job) for url, job in jobs.items()],
    key=lambda x: x[1].get('last_seen', ''),
    reverse=True
)
for i, (url, job) in enumerate(sorted_jobs[:5]):
    print(f"\n  {i+1}. {job.get('title', 'No title')}")
    print(f"     Last seen: {job.get('last_seen', 'N/A')}")
    print(f"     Remote: {job.get('is_remote', False)}")
    print(f"     Reasoning: {job.get('reasoning', 'N/A')[:80]}...")

# Reasoning patterns
print(f"\n🤖 Classification reasoning patterns:")
reasoning_counts = Counter()
for job in jobs.values():
    reasoning = job.get('reasoning', 'Unknown')
    if 'Obvious on-site' in reasoning:
        reasoning_counts['Obvious on-site'] += 1
    elif 'NLP Analysis' in reasoning:
        reasoning_counts['NLP Analysis (LLM)'] += 1
    elif 'digital job' in reasoning.lower() or 'remote' in reasoning.lower():
        reasoning_counts['Digital/Remote recognized'] += 1
    else:
        reasoning_counts['Other'] += 1

for reason, count in reasoning_counts.most_common():
    print(f"  {reason}: {count} ({count/len(jobs)*100:.1f}%)")
