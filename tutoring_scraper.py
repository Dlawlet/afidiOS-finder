# -*- coding: utf-8 -*-
"""
Tutoring Scraper — vertical pipeline for online tutoring opportunities.

Scrapes platforms where STUDENTS post requests for online teachers/tutors.
Output is merged into jobs_latest.json/csv alongside the general pipeline,
tagged with vertical='tutoring' so downstream consumers can filter independently.

Active sites:
  voscours      — voscours.fr, French student requests (France/EU)
  findtutors_uk — findtutors.co.uk, UK student requests

Supplementary (general-site traffic filtered for tutoring content):
  jemepropose   — reuses existing JeMeProposeScraper
  allovoisins   — reuses existing AlloVoisinsScraper

Usage:
  python tutoring_scraper.py --sites voscours findtutors_uk jemepropose allovoisins --verbose
  python tutoring_scraper.py --sites voscours --no-llm --pages 2 --verbose   # dry run
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from semantic_analyzer import setup_logging
from job_exporter import JobExporter
from incremental_scraper import IncrementalScraper
from models import JobListing
from tutoring_helpers import TutoringPreFilter
from tutoring_classifier import TutoringClassifier
from site_scrapers import (
    MultiSiteScraper,
    VosCoursScraper,
    FindTutorsUKScraper,
    JeMeProposeScraper,
    AlloVoisinsScraper,
)

# Tutoring pipeline LLM budget (separate from general pipeline's budget).
# Both share the same Groq key; run at different UTC times to avoid rate collision.
TUTORING_LLM_QUOTA = int(os.getenv('TUTORING_LLM_QUOTA', '500'))

# Job history retention
HISTORY_RETENTION_DAYS = int(os.getenv('HISTORY_RETENTION_DAYS', '90'))

# Sites that are dedicated tutoring platforms — TutoringPreFilter is SKIPPED for these
# because every listing is already a student request.
DEDICATED_TUTORING_SITES = {'voscours', 'findtutors_uk'}

# General sites: TutoringPreFilter must pass before LLM is called
GENERAL_SITES = {'jemepropose', 'allovoisins'}


def scrape_tutoring(
    sites=('voscours', 'findtutors_uk'),
    use_llm=True,
    verbose=False,
    max_pages=None,
    incremental=True,
    lookback_hours=24,
    llm_quota=None,
    reanalyze_cached=False,
):
    """
    Main tutoring scraper pipeline.

    Steps:
      1. Scrape requested sites page-by-page with quota management
      2. For general sites: apply TutoringPreFilter (drop non-tutoring posts)
      3. Apply incremental filter (skip recently-seen URLs)
      4. Classify remaining posts with TutoringClassifier (LLM or NLP fallback)
      5. Merge into jobs_latest.json/csv alongside general jobs
      6. Write tutoring_opportunities_latest.json/csv (is_online + student posts)
    """
    logger = setup_logging(verbose)
    quota = llm_quota or TUTORING_LLM_QUOTA

    metrics = {
        'start_time': datetime.now(),
        'scraped': 0,
        'pre_filtered_out': 0,
        'incremental_skipped': 0,
        'llm_calls': 0,
        'stem_priority': 0,
        'quota_trimmed': 0,
        'errors': [],
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"🎓 Tutoring scraper — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Sites: {', '.join(sites)}")
        print(f"   LLM quota: {quota} | Incremental: {incremental}")
        print(f"{'='*60}\n")

    # ── Scraper registry ────────────────────────────────────────────────────
    scraper_map = {
        'voscours': VosCoursScraper,
        'findtutors_uk': FindTutorsUKScraper,
        'jemepropose': JeMeProposeScraper,
        'allovoisins': AlloVoisinsScraper,
    }

    multi = MultiSiteScraper(verbose=verbose)
    for site in sites:
        if site in scraper_map:
            multi.register_scraper(scraper_map[site](verbose=False))
        else:
            logger.warning(f"Unknown tutoring site: {site}")

    # ── Incremental filter callback ─────────────────────────────────────────
    inc = IncrementalScraper(verbose=False) if incremental else None

    def incremental_cb(jobs, lh):
        if inc:
            return inc.filter_jobs_for_analysis(jobs, lh, reanalyze_cached)
        return jobs, []

    # ── Scrape with quota management ────────────────────────────────────────
    scraped_all, jobs_to_analyze_raw, jobs_from_cache, _ = multi.scrape_with_incremental_quota(
        daily_quota=quota,
        enabled_sites=list(sites),
        max_pages_per_site=max_pages,
        incremental_filter_callback=incremental_cb if incremental else None,
        lookback_hours=lookback_hours,
    )
    metrics['scraped'] = len(scraped_all)

    # ── Pre-filter: drop non-tutoring from general sites ────────────────────
    pre_filter = TutoringPreFilter()
    jobs_to_analyze = []

    for job in jobs_to_analyze_raw:
        site = job.get('source', '')
        if site in DEDICATED_TUTORING_SITES:
            # All posts on these sites are student requests — pass through
            jobs_to_analyze.append(job)
        else:
            # General site — must match tutoring keywords
            if pre_filter.is_tutoring_related(
                job.get('title', ''),
                job.get('description', ''),
                job.get('location', ''),
            ):
                jobs_to_analyze.append(job)
            else:
                metrics['pre_filtered_out'] += 1

    if verbose:
        print(f"Pre-filter: {len(jobs_to_analyze_raw)} → {len(jobs_to_analyze)} tutoring posts "
              f"({metrics['pre_filtered_out']} dropped)")

    # ── STEM priority queue ────────────────────────────────────────────────
    stem_priority_jobs = []
    standard_jobs = []
    for job in jobs_to_analyze:
        if pre_filter.is_stem_related(
            job.get('title', ''),
            job.get('description', ''),
            job.get('location', ''),
        ):
            stem_priority_jobs.append(job)
        else:
            standard_jobs.append(job)

    metrics['stem_priority'] = len(stem_priority_jobs)
    jobs_to_analyze = stem_priority_jobs + standard_jobs

    if quota and len(jobs_to_analyze) > quota:
        metrics['quota_trimmed'] = len(jobs_to_analyze) - quota
        jobs_to_analyze = jobs_to_analyze[:quota]

    if verbose:
        print(f"STEM priority: {metrics['stem_priority']} posts queued first")
        if metrics['quota_trimmed'] > 0:
            print(f"Quota trim: {metrics['quota_trimmed']} posts deferred")

    # ── Classify ────────────────────────────────────────────────────────────
    classifier = TutoringClassifier(verbose=verbose) if use_llm else None
    all_jobs = []

    for job in jobs_to_analyze:
        title = job.get('title', '')
        description = job.get('description', '')
        location = job.get('location', '')
        source = job.get('source', '')

        # Dedicated tutoring sites: poster_type is already hardcoded 'student'
        # We still run the classifier for subject_category, level, instruction_lang
        if classifier:
            result = classifier.classify(title, description, location)
            metrics['llm_calls'] += 1
        else:
            # No LLM — use sensible defaults for dedicated sites
            if source in DEDICATED_TUTORING_SITES:
                result = {
                    'is_online': True,
                    'poster_type': 'student',
                    'subject_category': 'other',
                    'instruction_language': 'french',
                    'level': 'unknown',
                    'confidence': 0.7,
                    'reason': 'Dedicated tutoring site — no LLM',
                }
            else:
                result = {
                    'is_online': False,
                    'poster_type': 'unknown',
                    'subject_category': 'other',
                    'instruction_language': 'french',
                    'level': 'unknown',
                    'confidence': 0.3,
                    'reason': 'No LLM available',
                }

        # poster_type from scraper takes precedence over LLM if hardcoded
        scraper_poster_type = job.get('poster_type')
        if scraper_poster_type in ('student', 'employer', 'teacher'):
            poster_type = scraper_poster_type
        else:
            poster_type = result.get('poster_type', 'unknown')

        job_object = {
            'id': job.get('id', 'N/A'),
            'title': title,
            'description': description,
            'url': job.get('url', 'N/A'),
            'location': location,
            'category': 'N/A',
            'price': job.get('price', 'N/A'),
            'poster': job.get('poster', 'N/A'),
            'date_posted': job.get('date_posted', 'N/A'),
            'source': source,
            # General classification fields (tutoring posts are inherently remote
            # if is_online=True, but we keep the field consistent)
            'is_remote': result.get('is_online', False),
            'remote_confidence': result.get('confidence', 0.5),
            'reason': result.get('reason', 'Tutoring classification'),
            'confidence': 'HIGH' if result.get('confidence', 0) > 0.8 else 'MEDIUM',
            'reasoning': result.get('reason', 'Tutoring classification'),
            'classification': 'remote' if result.get('is_online', False) else 'on-site',
            'description_source': 'listing_page',
            'poster_type': poster_type,
            'was_reanalyzed': False,
            # Tutoring-specific fields
            'vertical': 'tutoring',
            'subject_category': result.get('subject_category', 'other'),
            'instruction_lang': result.get('instruction_language', 'french'),
            'level': result.get('level', 'unknown'),
        }

        try:
            validated = JobListing(**job_object)
            all_jobs.append(validated.model_dump())
        except Exception as e:
            logger.warning(f"Validation error: {e}")
            all_jobs.append(job_object)

    # Add cached tutoring jobs
    for job in jobs_from_cache:
        if job.get('vertical') == 'tutoring':
            all_jobs.append(job)

    if verbose:
        online = sum(1 for j in all_jobs if j.get('is_remote'))
        students = sum(1 for j in all_jobs if j.get('poster_type') == 'student')
        print(f"\n{'='*60}")
        print(f"✅ Tutoring scrape complete")
        print(f"   Total tutoring posts: {len(all_jobs)}")
        print(f"   Online/remote:        {online}")
        print(f"   Student requests:     {students}")
        print(f"   LLM calls used:       {metrics['llm_calls']}/{quota}")
        print(f"{'='*60}\n")

    logger.info(f"Tutoring scrape done — {len(all_jobs)} posts, {metrics['llm_calls']} LLM calls")

    # ── Export ───────────────────────────────────────────────────────────────
    # Load existing jobs_latest so we can merge without overwriting general jobs
    jobs_latest_path = Path('exports/jobs_latest.json')
    existing_general_jobs = []
    if jobs_latest_path.exists():
        try:
            with open(jobs_latest_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            existing_general_jobs = [
                j for j in existing_data.get('jobs', [])
                if j.get('vertical', 'general') == 'general'
            ]
        except Exception as e:
            logger.warning(f"Could not load existing jobs_latest: {e}")

    merged_jobs = existing_general_jobs + all_jobs
    duration = (datetime.now() - metrics['start_time']).seconds

    run_stats = {
        'total': len(merged_jobs),
        'tutoring_posts': len(all_jobs),
        'general_posts': len(existing_general_jobs),
        'remote': sum(1 for j in merged_jobs if j.get('is_remote')),
        'on_site': sum(1 for j in merged_jobs if not j.get('is_remote')),
        'remote_percentage': 0.0,
        'employee_posts_filtered': sum(1 for j in merged_jobs if j.get('poster_type') == 'employee'),
        'llm_used': use_llm,
        'incremental_enabled': incremental,
        'sites': list(sites),
        'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'duration_seconds': duration,
        'stem_priority': metrics['stem_priority'],
        'quota_trimmed': metrics['quota_trimmed'],
    }
    if merged_jobs:
        run_stats['remote_percentage'] = round(run_stats['remote'] / len(merged_jobs) * 100, 2)

    exporter = JobExporter()
    exporter.cleanup_old_history(days=HISTORY_RETENTION_DAYS)

    tutoring_opportunities = [
        job for job in merged_jobs
        if (
            job.get('vertical') == 'tutoring'
            and job.get('is_remote', False)
            and job.get('poster_type', 'unknown') not in ('teacher', 'institution')
        )
    ]
    stem_categories = {'math_science', 'technology', 'test_prep'}
    stem_opportunities = [
        job for job in tutoring_opportunities
        if job.get('subject_category') in stem_categories
    ]
    tutoring_stats = run_stats.copy()
    tutoring_stats['total'] = len(tutoring_opportunities)
    tutoring_stats['filter'] = 'vertical=tutoring AND is_remote=True AND poster_type!=teacher'
    stem_stats = run_stats.copy()
    stem_stats['total'] = len(stem_opportunities)
    stem_stats['filter'] = 'vertical=tutoring AND is_remote=True AND subject_category in STEM'

    json_all = exporter.export_to_json(merged_jobs, run_stats, filename='jobs_latest.json')
    csv_all = exporter.export_to_csv(merged_jobs, filename='jobs_latest.csv')
    tutoring_export = exporter.export_tutoring_opportunities(merged_jobs, run_stats)
    stem_export = exporter.export_tutoring_stem_opportunities(merged_jobs, run_stats)
    archive_all = exporter.export_archive_snapshot(merged_jobs, run_stats, filename_prefix='jobs')
    archive_tutoring = exporter.export_archive_snapshot(
        tutoring_opportunities, tutoring_stats, filename_prefix='tutoring_opportunities'
    )
    archive_stem = exporter.export_archive_snapshot(
        stem_opportunities, stem_stats, filename_prefix='tutoring_stem_opportunities'
    )

    if verbose:
        print(f"💾 Exported:")
        print(f"   {json_all}  ({len(merged_jobs)} total jobs)")
        print(f"   {csv_all}")
        print(f"   {tutoring_export['json']}  ({tutoring_export['count']} opportunities)")
        print(f"   {tutoring_export['csv']}")
        print(f"   {stem_export['json']}  ({stem_export['count']} STEM opportunities)")
        print(f"   {stem_export['csv']}")
        print(f"   {archive_all['json']}")
        print(f"   {archive_tutoring['json']}")
        print(f"   {archive_stem['json']}")

    return {
        'success': True,
        'tutoring_jobs': all_jobs,
        'merged_total': len(merged_jobs),
        'opportunities': tutoring_export['count'],
        'stem_opportunities': stem_export['count'],
        'metrics': run_stats,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tutoring Scraper — student request pipeline')
    parser.add_argument(
        '--sites', nargs='+',
        default=['voscours', 'findtutors_uk'],
        choices=['voscours', 'findtutors_uk', 'jemepropose', 'allovoisins'],
        help='Sites to scrape (default: voscours findtutors_uk)',
    )
    parser.add_argument('--pages', type=int, default=None, help='Max pages per site')
    parser.add_argument('--quota', type=int, default=None, help=f'LLM quota (default: {TUTORING_LLM_QUOTA})')
    parser.add_argument('--no-llm', action='store_true', help='Disable LLM — NLP fallback only')
    parser.add_argument('--verbose', action='store_true', help='Detailed output')
    parser.add_argument('--no-incremental', action='store_true', help='Disable incremental cache')
    parser.add_argument('--lookback', type=int, default=24, help='Lookback hours (default: 24)')
    parser.add_argument('--reanalyze', action='store_true', help='Force re-analysis of cached jobs')

    args = parser.parse_args()

    scrape_tutoring(
        sites=args.sites,
        use_llm=not args.no_llm,
        verbose=args.verbose,
        max_pages=args.pages,
        incremental=not args.no_incremental,
        lookback_hours=args.lookback,
        llm_quota=args.quota,
        reanalyze_cached=args.reanalyze,
    )
