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
from site_scrapers import MultiSiteScraper, JeMeProposeScraper, MaltScraper, FreelanceComScraper, CometScraper
import json
from datetime import datetime
import logging
import argparse


def scrape_multi_site(
    sites=['jemepropose'],
    use_llm=True,
    verbose=False,
    max_pages=10,
    incremental=True,
    lookback_hours=24
):
    """
    Multi-site job scraper with incremental support
    
    Args:
        sites: List of site names to scrape (['jemepropose', 'malt', 'freelance.com', 'comet'])
        use_llm: Whether to use Groq LLM
        verbose: Show detailed progress messages
        max_pages: Maximum number of pages per site
        incremental: Use incremental scraping
        lookback_hours: Hours to consider job as "recent"
    """
    logger = setup_logging(verbose)
    
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
        print(f"📄 Max {max_pages} pages per site")
        print(f"♻️  Incremental mode: {'ENABLED' if incremental else 'DISABLED'}")
        if incremental:
            print(f"🕐 Lookback: {lookback_hours}h")
        print(f"{'='*60}\n")
    
    logger.info(f"Starting multi-site scraper - sites: {sites}, pages: {max_pages}, incremental: {incremental}")
    
    try:
        # ===== PHASE 1: SCRAPE ALL SITES =====
        if verbose:
            print(f"\n📡 Phase 1: Scraping job listings from {len(sites)} site(s)...")
        
        # Initialize multi-site scraper
        multi_scraper = MultiSiteScraper(verbose=verbose)
        
        # Register requested scrapers
        scraper_map = {
            'jemepropose': JeMeProposeScraper,
            'malt': MaltScraper,
            'freelance.com': FreelanceComScraper,
            'comet': CometScraper,
        }
        
        for site_name in sites:
            if site_name in scraper_map:
                multi_scraper.register_scraper(scraper_map[site_name](verbose=verbose))
            else:
                logger.warning(f"Unknown site: {site_name}")
        
        # Scrape all sites
        scraped_jobs = multi_scraper.scrape_all_sites_unified(
            max_pages_per_site=max_pages,
            enabled_sites=sites
        )
        
        metrics['jobs_scraped'] = len(scraped_jobs)
        
        # Track per-site statistics
        for site in sites:
            site_jobs = [j for j in scraped_jobs if j.get('source') == site]
            metrics['sites_scraped'][site] = len(site_jobs)
        
        if verbose:
            print(f"\n📊 Scraped {len(scraped_jobs)} total jobs")
            for site, count in metrics['sites_scraped'].items():
                print(f"  - {site}: {count} jobs")
        
        # ===== PHASE 2: INCREMENTAL FILTERING =====
        incremental_scraper = IncrementalScraper(verbose=verbose) if incremental else None
        
        if incremental and incremental_scraper:
            if verbose:
                print(f"\n♻️  Phase 2: Incremental filtering...")
            
            jobs_to_analyze, jobs_from_cache = incremental_scraper.filter_jobs_for_analysis(
                scraped_jobs,
                lookback_hours=lookback_hours
            )
            
            incremental_stats = incremental_scraper.get_stats(
                scraped_jobs,
                jobs_to_analyze,
                jobs_from_cache
            )
            
            metrics['new_jobs'] = len(jobs_to_analyze)
            metrics['cached_jobs'] = len(jobs_from_cache)
            
            if verbose:
                print(f"\n📊 Incremental Statistics:")
                print(f"   Total jobs scraped: {len(scraped_jobs)}")
                print(f"   Jobs to analyze: {len(jobs_to_analyze)} (NEW/CHANGED)")
                print(f"   Jobs from cache: {len(jobs_from_cache)} (RECENT)")
                print(f"   Reduction: {incremental_stats['reduction_percentage']:.1f}%")
                print(f"   Time saved: ~{incremental_stats['estimated_time_saved_seconds']}s")
                print(f"   API calls saved: {incremental_stats['estimated_api_calls_saved']}")
            
            logger.info(f"Incremental filtering: {len(jobs_to_analyze)} to analyze, {len(jobs_from_cache)} from cache")
        else:
            jobs_to_analyze = scraped_jobs
            jobs_from_cache = []
            metrics['new_jobs'] = len(jobs_to_analyze)
        
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
            
            # Basic detection
            basic_result = basic_detector.detect_confidence(job_title, job_description, job_location)
            
            # Analyze based on confidence
            if basic_result['confidence'] == 'LOW':
                # Fetch full description if needed
                full_description = job_description
                if job_url != 'N/A':
                    better_desc = description_fetcher.fetch_full_description(job_url)
                    if better_desc and len(better_desc) > len(job_description):
                        full_description = better_desc
                        stats['full_description_fetched'] += 1
                
                # Analyze with LLM
                result = llm_analyzer.analyze_job(job_title, full_description, job_location)
                stats['analyzed_with_llm'] += 1
                metrics['llm_calls'] += 1
            else:
                # High confidence - skip LLM
                result = basic_result
                stats['high_confidence_skip'] += 1
            
            # Create job object
            job_object = {
                'title': job_title,
                'description': job_description,
                'url': job_url,
                'location': job_location,
                'price': job_price,
                'source': job_source,
                'is_remote': result['is_remote'],
                'remote_confidence': result.get('confidence_score', 0.8 if result['confidence'] == 'HIGH' else 0.5),
                'reason': result['reason']
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
    parser = argparse.ArgumentParser(description='Multi-Site Job Scraper with Incremental Support')
    parser.add_argument('--sites', nargs='+', default=['jemepropose'],
                       choices=['jemepropose', 'malt', 'freelance.com', 'comet'],
                       help='Sites to scrape (default: jemepropose)')
    parser.add_argument('--pages', type=int, default=10,
                       help='Max pages per site (default: 10)')
    parser.add_argument('--no-llm', action='store_true',
                       help='Disable LLM analysis (use NLP only)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed progress')
    parser.add_argument('--no-incremental', action='store_true',
                       help='Disable incremental scraping')
    parser.add_argument('--lookback', type=int, default=24,
                       help='Lookback window in hours (default: 24)')
    
    args = parser.parse_args()
    
    scrape_multi_site(
        sites=args.sites,
        use_llm=not args.no_llm,
        verbose=args.verbose,
        max_pages=args.pages,
        incremental=not args.no_incremental,
        lookback_hours=args.lookback
    )
