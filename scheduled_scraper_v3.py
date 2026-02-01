# -*- coding: utf-8 -*-
"""
Multi-Site Job Scraper - Phase 3
Supports multiple job platforms with incremental scraping and validation
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from semantic_analyzer import SemanticJobAnalyzer, setup_logging
from job_exporter import JobExporter
from job_helpers import JobDescriptionFetcher, BasicRemoteDetector
from incremental_scraper import IncrementalScraper
from models import JobListing, validate_job_data, ScraperMetrics
from site_scrapers import MultiSiteScraper, JeMeProposeScraper, MaltScraper, FreelanceComScraper, CometScraper, AlloVoisinsScraper
import json
from datetime import datetime
import logging
import argparse

# Free tier LLM quota (jobs per day)
DAILY_LLM_QUOTA = 250


def scrape_multi_site(
    sites=['jemepropose'],
    use_llm=True,
    verbose=False,
    max_pages=None,
    incremental=True,
    lookback_hours=24,
    llm_quota_per_site=None,
    reanalyze_cached=False
):
    """
    Multi-site job scraper with incremental support and intelligent quota management
    
    Args:
        sites: List of site names to scrape (['jemepropose', 'malt', 'freelance.com', 'comet'])
        use_llm: Whether to use Groq LLM
        verbose: Show detailed progress messages
        max_pages: Maximum number of pages per site (None = unlimited, stops at quota)
        incremental: Use incremental scraping
        lookback_hours: Hours to consider job as "recent"
        llm_quota_per_site: LLM quota per site (None = auto-calculate from DAILY_LLM_QUOTA)
        reanalyze_cached: Force re-analysis of cached jobs with updated prompt
    """
    logger = setup_logging(verbose)
    
    # Calculate fair share quota per site
    if llm_quota_per_site is None:
        llm_quota_per_site = DAILY_LLM_QUOTA // len(sites)
    
    # Track metrics
    metrics = {
        'start_time': datetime.now(),
        'jobs_scraped': 0,
        'jobs_analyzed': 0,
        'new_jobs': 0,
        'cached_jobs': 0,
        'llm_calls': 0,
        'cache_hits': 0,
        'validation_errors': 0,
        'errors': [],
        'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0},
        'sites_scraped': {},
    }
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"🚀 Starting MULTI-SITE job scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Sites: {', '.join(sites)}")
        if max_pages:
            print(f"📄 Max {max_pages} pages per site")
        else:
            print(f"📄 Default: 10 pages per site (quota applied after filtering)")
        print(f"🎯 LLM quota per site: {llm_quota_per_site} NEW jobs")
        print(f"🎯 Total LLM budget: {llm_quota_per_site * len(sites)} NEW jobs")
        print(f"♻️  Incremental mode: {'ENABLED' if incremental else 'DISABLED'}")
        if incremental:
            print(f"🕐 Lookback: {lookback_hours}h")
        print(f"{'='*60}\n")
    
    logger.info(f"Starting multi-site scraper - sites: {sites}, total_quota: {llm_quota_per_site * len(sites)}, incremental: {incremental}")
    
    try:
        # Initialize multi-site scraper
        multi_scraper = MultiSiteScraper(verbose=verbose)
        
        # Register requested scrapers
        scraper_map = {
            'jemepropose': JeMeProposeScraper,
            'malt': MaltScraper,
            'freelance.com': FreelanceComScraper,
            'comet': CometScraper,
            'allovoisins': AlloVoisinsScraper,
        }
        
        for site_name in sites:
            if site_name in scraper_map:
                multi_scraper.register_scraper(scraper_map[site_name](verbose=False))  # Turn off per-page verbosity
            else:
                logger.warning(f"Unknown site: {site_name}")
        
        # ===== PHASE 1 + 2: INTELLIGENT SCRAPING WITH QUOTA =====
        # Scrape page-by-page with incremental filtering and quota management
        if verbose:
            print(f"\n� Phase 1+2: Intelligent scraping with quota management...")
        
        # Setup incremental filter callback
        incremental_scraper = IncrementalScraper(verbose=False) if incremental else None
        
        def incremental_filter_callback(jobs, lookback_hours):
            """Callback to filter jobs incrementally"""
            if incremental_scraper:
                return incremental_scraper.filter_jobs_for_analysis(jobs, lookback_hours, reanalyze_cached)
            else:
                return jobs, []  # All jobs are new if no incremental
        
        # Scrape with intelligent quota management
        total_daily_quota = llm_quota_per_site * len(sites)
        scraped_jobs, jobs_to_analyze, jobs_from_cache, quota_used = multi_scraper.scrape_with_incremental_quota(
            daily_quota=total_daily_quota,
            enabled_sites=sites,
            max_pages_per_site=max_pages,
            incremental_filter_callback=incremental_filter_callback if incremental else None,
            lookback_hours=lookback_hours
        )
        
        metrics['jobs_scraped'] = len(scraped_jobs)
        metrics['new_jobs'] = len(jobs_to_analyze)
        metrics['cached_jobs'] = len(jobs_from_cache)
        
        # Track per-site statistics
        for site in sites:
            site_jobs = [j for j in scraped_jobs if j.get('source') == site]
            metrics['sites_scraped'][site] = len(site_jobs)
        
        # ===== PHASE 3: ANALYZE JOBS =====
        if verbose:
            print(f"\n🔍 Phase 3: Analyzing {len(jobs_to_analyze)} jobs...")
        
        # Initialize analyzers
        basic_detector = BasicRemoteDetector()
        description_fetcher = JobDescriptionFetcher()
        llm_analyzer = SemanticJobAnalyzer(use_groq=use_llm, verbose=verbose)
        
        stats = {
            'analyzed_with_llm': 0,
            'full_description_fetched': 0,
            'high_confidence_skip': 0
        }
        
        all_jobs = []
        remote_count = 0
        
        # Process jobs to analyze
        for idx, job_data in enumerate(jobs_to_analyze, 1):
            if verbose and idx <= 3:  # Show first 3 jobs
                print(f"\n[{idx}/{len(jobs_to_analyze)}] {job_data['title'][:50]}... ({job_data['source']})")
            
            job_title = job_data['title']
            job_description = job_data['description']
            job_location = job_data['location']
            job_price = job_data.get('price', 'N/A')
            job_url = job_data['url']
            job_source = job_data['source']
            
            # Try to get a better description upfront if listing description is missing
            if job_description == 'N/A' or len(job_description) < 50:
                if job_url != 'N/A':
                    better_desc = description_fetcher.fetch_full_description(job_url)
                    if better_desc and len(better_desc) > len(job_description):
                        job_description = better_desc
                        stats['full_description_fetched'] += 1
            
            # Basic detection
            basic_result = basic_detector.detect_confidence(job_title, job_description, job_location)
            
            # Track which description we'll use for export
            final_description = job_description
            description_source = 'listing_page' if job_description == job_data.get('description', 'N/A') else 'detail_page'
            
            # Analyze based on confidence
            if basic_result['confidence'] == 'LOW':
                # Fetch full description if still needed
                full_description = job_description
                if job_url != 'N/A' and (job_description == 'N/A' or len(job_description) < 100):
                    better_desc = description_fetcher.fetch_full_description(job_url)
                    if better_desc and len(better_desc) > len(job_description):
                        full_description = better_desc
                        final_description = better_desc  # Use full description for export
                        description_source = 'detail_page'
                        stats['full_description_fetched'] += 1
                
                # Analyze with LLM
                analysis = llm_analyzer.analyze_with_groq(job_title, full_description, job_location, job_price)
                
                # Use analysis result
                result = {
                    'is_remote': analysis.get('is_remote', False),
                    'confidence_score': analysis.get('remote_confidence', 0.5),
                    'reason': analysis.get('reason', 'LLM analysis'),
                    'confidence': 'HIGH' if analysis.get('remote_confidence', 0) > 0.8 else 'MEDIUM'
                }
                
                stats['analyzed_with_llm'] += 1
                metrics['llm_calls'] += 1
            else:
                # High confidence - skip LLM
                result = basic_result
                stats['high_confidence_skip'] += 1
            
            # Track confidence distribution
            confidence_level = result.get('confidence', 'MEDIUM').lower()
            if confidence_level in metrics['confidence_distribution']:
                metrics['confidence_distribution'][confidence_level] += 1
            
            # Create job object with all required fields
            job_object = {
                'id': 'N/A',  # Not available from listing pages
                'title': job_title,
                'description': final_description,  # Use the better description if fetched
                'url': job_url,
                'location': job_location,
                'category': 'N/A',  # Not available from listing pages
                'price': job_price,
                'poster': 'N/A',  # Not available from listing pages
                'date_posted': 'N/A',  # Not available from listing pages
                'source': job_source,
                'is_remote': result['is_remote'],
                'remote_confidence': result.get('confidence_score', 0.8 if result['confidence'] == 'HIGH' else 0.5),
                'reason': result['reason'],
                # Additional fields for CSV export
                'confidence': result.get('confidence', 'MEDIUM'),
                'reasoning': result['reason'],
                'classification': 'remote' if result['is_remote'] else 'on-site',
                'description_source': description_source,
                'was_reanalyzed': False  # Only true if we re-analyze an existing job
            }
            
            # Validate with Pydantic
            try:
                validated_job = JobListing(**job_object)
                all_jobs.append(validated_job.model_dump())
            except Exception as e:
                logger.warning(f"Validation error for job: {e}")
                all_jobs.append(job_object)
                metrics['validation_errors'] += 1
            
            if result['is_remote']:
                remote_count += 1
            
            metrics['jobs_analyzed'] += 1
        
        # Add cached jobs to results
        all_jobs.extend(jobs_from_cache)
        if jobs_from_cache:
            # Count remote jobs from cache
            remote_count += sum(1 for job in jobs_from_cache if job.get('is_remote'))
        
        logger.info(f"Analysis complete - Total: {len(all_jobs)}, Remote: {remote_count}")
        
        # ===== PHASE 4: EXPORT =====
        if verbose:
            print(f"\n{'='*60}")
            print(f"✅ Analysis complete!")
            print(f"   Total jobs: {len(all_jobs)}")
            print(f"   New/changed jobs analyzed: {len(jobs_to_analyze)}")
            print(f"   Jobs from cache: {len(jobs_from_cache)}")
            print(f"   Remote jobs: {remote_count}")
            print(f"   Remote percentage: {round(remote_count / len(all_jobs) * 100, 1) if all_jobs else 0}%")
            print(f"   📊 Stats:")
            print(f"      - Analyzed with LLM: {stats['analyzed_with_llm']}")
            print(f"      - High confidence skip: {stats['high_confidence_skip']}")
            print(f"      - Full descriptions fetched: {stats['full_description_fetched']}")
            if incremental:
                print(f"      - Incremental reduction: {metrics['cached_jobs']}/{len(all_jobs)} ({round(metrics['cached_jobs']/len(all_jobs)*100, 1) if all_jobs else 0}%)")
            if metrics['validation_errors'] > 0:
                print(f"      ⚠️  Validation errors: {metrics['validation_errors']}")
            print(f"{'='*60}\n")
        
        # Export metrics
        cache_stats = llm_analyzer.get_cache_stats()
        metrics['cache_hits'] = cache_stats.get('cache_hits', 0)
        duration = (datetime.now() - metrics['start_time']).seconds
        
        metrics_export = {
            'timestamp': metrics['start_time'].isoformat(),
            'duration_seconds': duration,
            'jobs_scraped': metrics['jobs_scraped'],
            'jobs_analyzed': metrics['jobs_analyzed'],
            'new_jobs': metrics['new_jobs'],
            'cached_jobs': metrics['cached_jobs'],
            'remote_jobs': remote_count,
            'llm_calls': metrics['llm_calls'],
            'cache_stats': cache_stats,
            'confidence_distribution': metrics['confidence_distribution'],
            'validation_errors': metrics['validation_errors'],
            'incremental_enabled': incremental,
            'sites_scraped': metrics['sites_scraped'],
            'errors': metrics['errors']
        }
        
        # Validate and export metrics
        try:
            validated_metrics = ScraperMetrics(**metrics_export)
            metrics_export = validated_metrics.model_dump()
            logger.info("Metrics validated successfully")
        except Exception as e:
            logger.warning(f"Metrics validation failed: {e}")
        
        try:
            with open('exports/metrics_latest.json', 'w', encoding='utf-8') as f:
                json.dump(metrics_export, f, indent=2, ensure_ascii=False, default=str)
            logger.info("Metrics exported successfully")
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
        
        # Export jobs
        if verbose:
            print("💾 Exporting results...")
        
        exporter = JobExporter()
        
        stats_all = {
            'total': len(all_jobs),
            'remote': remote_count,
            'on_site': len(all_jobs) - remote_count,
            'remote_percentage': round(remote_count / len(all_jobs) * 100, 2) if all_jobs else 0,
            'llm_used': use_llm,
            'incremental_enabled': incremental,
            'sites': list(metrics['sites_scraped'].keys()),
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        remote_jobs = [job for job in all_jobs if job['is_remote']]
        
        stats_remote = {
            'total': len(remote_jobs),
            'remote': len(remote_jobs),
            'on_site': 0,
            'remote_percentage': 100.0,
            'llm_used': use_llm,
            'sites': list(metrics['sites_scraped'].keys()),
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Export
        json_all = exporter.export_to_json(all_jobs, stats_all, filename='jobs_latest.json')
        csv_all = exporter.export_to_csv(all_jobs, filename='jobs_latest.csv')
        json_remote = exporter.export_to_json(remote_jobs, stats_remote, filename='remote_jobs_latest.json')
        csv_remote = exporter.export_to_csv(remote_jobs, filename='remote_jobs_latest.csv')
        
        if verbose:
            print(f"\n💾 Exported to:")
            print(f"   - {json_all}")
            print(f"   - {csv_all}")
            print(f"   - {json_remote}")
            print(f"   - {csv_remote}")
            print(f"   - exports/metrics_latest.json")
        
        logger.info(f"Export complete - Duration: {duration}s")
        
        if verbose:
            print(f"\n✅ Scraping completed successfully!")
            print(f"📊 {len(all_jobs)} jobs processed from {len(sites)} site(s)")
            print(f"🌍 {remote_count} remote jobs found")
        
        return {
            'success': True,
            'results': all_jobs,
            'stats': stats_all,
            'metrics': metrics_export
        }
        
    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        if verbose:
            print(f"\n❌ Error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Multi-Site Job Scraper with Intelligent Quota Management')
    parser.add_argument('--sites', nargs='+', default=['jemepropose'],
                       choices=['jemepropose', 'malt', 'freelance.com', 'comet', 'allovoisins'],
                       help='Sites to scrape (default: jemepropose)')
    parser.add_argument('--pages', type=int, default=None,
                       help='Max pages per site (default: None = unlimited, stops at quota)')
    parser.add_argument('--quota', type=int, default=None,
                       help=f'LLM quota per site (default: {DAILY_LLM_QUOTA} / num_sites)')
    parser.add_argument('--no-llm', action='store_true',
                       help='Disable LLM analysis (use NLP only)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed progress')
    parser.add_argument('--no-incremental', action='store_true',
                       help='Disable incremental scraping')
    parser.add_argument('--lookback', type=int, default=24,
                       help='Lookback window in hours (default: 24)')
    parser.add_argument('--reanalyze', action='store_true',
                       help='Force re-analysis of cached jobs with updated prompt')
    
    args = parser.parse_args()
    
    scrape_multi_site(
        sites=args.sites,
        use_llm=not args.no_llm,
        verbose=args.verbose,
        max_pages=args.pages,
        incremental=not args.no_incremental,
        lookback_hours=args.lookback,
        llm_quota_per_site=args.quota,
        reanalyze_cached=args.reanalyze
    )
