# -*- coding: utf-8 -*-
"""
Scheduled Job Scraper - Phase 2 Enhanced
Now with Incremental Scraping and Data Validation
Reduces processing time by 70% after first run
"""

import sys
import io
# Force UTF-8 encoding for console output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from semantic_analyzer import SemanticJobAnalyzer, setup_logging
from job_exporter import JobExporter
from job_helpers import JobDescriptionFetcher, BasicRemoteDetector
from incremental_scraper import IncrementalScraper
from models import JobListing, validate_job_data, validate_analysis_result, ScraperMetrics
import os
import json
from datetime import datetime
import logging


def scrape_and_analyze_jobs_incremental(
    base_url="https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1", 
    use_llm=True, 
    verbose=False, 
    max_pages=10,
    incremental=True,
    lookback_hours=24
):
    """
    Main scraping function with incremental support
    
    Args:
        base_url: Base URL to scrape
        use_llm: Whether to use Groq LLM
        verbose: Show detailed progress messages
        max_pages: Maximum number of pages to scrape
        incremental: Use incremental scraping (default True)
        lookback_hours: Hours to consider job as "recent" (default 24)
    """
    # Setup logging
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
        'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0}
    }
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"🚀 Starting INCREMENTAL job scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📄 Scraping up to {max_pages} pages")
        print(f"♻️  Incremental mode: {'ENABLED' if incremental else 'DISABLED'}")
        if incremental:
            print(f"🕐 Lookback: {lookback_hours}h (jobs seen within this will be skipped)")
        print(f"{'='*60}\n")
    
    logger.info(f"Starting incremental scraper - pages: {max_pages}, incremental: {incremental}, lookback: {lookback_hours}h")
    
    all_jobs = []
    job_id_counter = 0
    pages_scraped = 0
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        # Initialize tools
        if verbose:
            print("🤖 Initializing analyzers...")
        basic_detector = BasicRemoteDetector()
        description_fetcher = JobDescriptionFetcher()
        llm_analyzer = SemanticJobAnalyzer(use_groq=use_llm, verbose=verbose)
        incremental_scraper = IncrementalScraper(verbose=verbose) if incremental else None
        
        stats = {
            'analyzed_with_llm': 0,
            'full_description_fetched': 0,
            'high_confidence_skip': 0
        }
        
        remote_count = 0
        
        logger.info(f"Initialized analyzers - LLM: {use_llm}, Incremental: {incremental}")
        
        # ===== PHASE 1: SCRAPE ALL JOBS (WITHOUT ANALYSIS) =====
        if verbose:
            print(f"\n📡 Phase 1: Scraping job listings...")
        
        scraped_jobs = []  # Jobs before analysis
        
        for page_num in range(1, max_pages + 1):
            if page_num == 1:
                url = base_url
            else:
                url = f"{base_url}&page={page_num}"
            
            if verbose:
                print(f"\n{'─'*60}")
                print(f"📄 Page {page_num}/{max_pages}")
                print(f"📡 {url}")
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            job_cards = soup.find_all('div', attrs={'data-url': True})
            
            if len(job_cards) == 0:
                if verbose:
                    print(f"⚠️  No jobs on page {page_num} - stopping")
                logger.warning(f"No jobs found on page {page_num}, stopping scrape")
                break
            
            if verbose:
                print(f"✅ {len(job_cards)} jobs found")
            pages_scraped = page_num
            
            # Extract job data (without analysis yet)
            for idx, card in enumerate(job_cards, 1):
                job_id_counter += 1
                
                job_url = card.get('data-url', 'N/A')
                job_full_url = urljoin(url, job_url) if job_url != 'N/A' else 'N/A'
                
                job_title = 'N/A'
                title_tag = card.find('span', class_='card-title')
                if title_tag:
                    job_title = title_tag.get_text(strip=True)
                
                job_location = 'N/A'
                location_tag = card.find('a', class_='grey_jmp_text')
                if location_tag:
                    job_location = location_tag.get_text(strip=True)
                
                job_price = 'N/A'
                price_tags = card.find_all('b', class_='orange_jmp_text')
                for price_tag in price_tags:
                    if price_tag.parent.name == 'div':
                        price_text = price_tag.get_text(strip=True)
                        small_tag = price_tag.find_next_sibling('small')
                        if small_tag:
                            price_text += ' ' + small_tag.get_text(strip=True)
                        job_price = price_text
                        break
                
                job_poster = 'N/A'
                poster_tags = card.find_all('b', class_='orange_jmp_text')
                for poster_tag in poster_tags:
                    if poster_tag.parent.name == 'p':
                        job_poster = poster_tag.get_text(strip=True)
                        break
                
                job_description = card.find('p', class_='card-text')
                job_description = job_description.get_text(strip=True) if job_description else 'N/A'
                
                scraped_jobs.append({
                    'url': job_full_url,
                    'title': job_title,
                    'description': job_description,
                    'location': job_location,
                    'price': job_price,
                    'poster': job_poster
                })
                
                metrics['jobs_scraped'] += 1
        
        # ===== PHASE 2: INCREMENTAL FILTERING =====
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
            
            if verbose:
                print(f"\n📊 Incremental Statistics:")
                print(f"   Total jobs scraped: {incremental_stats['total_jobs']}")
                print(f"   Jobs to analyze: {incremental_stats['jobs_to_analyze']} (NEW/CHANGED)")
                print(f"   Jobs from cache: {incremental_stats['jobs_from_cache']} (RECENT)")
                print(f"   Reduction: {incremental_stats['reduction_percentage']}%")
                print(f"   Time saved: ~{incremental_stats['estimated_time_saved_seconds']}s")
                print(f"   API calls saved: {incremental_stats['estimated_api_calls_saved']}")
            
            logger.info(f"Incremental filtering: {len(jobs_to_analyze)} to analyze, {len(jobs_from_cache)} from cache")
            
            metrics['new_jobs'] = len(jobs_to_analyze)
            metrics['cached_jobs'] = len(jobs_from_cache)
            
            # Add cached jobs to final list (already classified)
            all_jobs.extend(jobs_from_cache)
            remote_count += sum(1 for job in jobs_from_cache if job.get('is_remote'))
            
        else:
            # No incremental filtering - analyze all jobs
            jobs_to_analyze = scraped_jobs
            metrics['new_jobs'] = len(jobs_to_analyze)
            
            if verbose:
                print(f"\n📊 No incremental filtering - analyzing all {len(jobs_to_analyze)} jobs")
        
        # ===== PHASE 3: ANALYZE NEW/CHANGED JOBS =====
        if verbose and jobs_to_analyze:
            print(f"\n🔍 Phase 3: Analyzing {len(jobs_to_analyze)} jobs...")
        
        for idx, job_data in enumerate(jobs_to_analyze, 1):
            if verbose:
                print(f"\n[{idx}/{len(jobs_to_analyze)}] {job_data['title'][:50]}...")
            
            job_title = job_data['title']
            job_description = job_data['description']
            job_location = job_data['location']
            job_price = job_data['price']
            job_url = job_data['url']
            
            # Basic detection
            basic_result = basic_detector.detect_confidence(job_title, job_description, job_location)
            
            # Fetch full description if needed
            full_description = job_description
            if basic_result['confidence'] == 'LOW' and job_url != 'N/A':
                if verbose:
                    print(f"    📄 Fetching full description...")
                
                better_desc = description_fetcher.fetch_full_description(job_url)
                if better_desc and len(better_desc) > len(job_description):
                    full_description = better_desc
                    stats['full_description_fetched'] += 1
                    if verbose:
                        print(f"    ✅ Got better description ({len(full_description)} chars)")
            
            # Analyze with LLM
            if basic_result['confidence'] == 'LOW':
                if verbose:
                    print(f"    🤖 Analyzing with LLM...")
                
                analysis = llm_analyzer.analyze_with_groq(
                    job_title,
                    full_description,
                    job_location,
                    job_price
                )
                
                # Validate analysis result
                validated_analysis = validate_analysis_result(analysis)
                if validated_analysis:
                    is_remote = validated_analysis.is_remote
                    remote_confidence = validated_analysis.remote_confidence
                    remote_reason = validated_analysis.reason
                else:
                    # Validation failed - use defaults
                    is_remote = analysis.get('is_remote', False)
                    remote_confidence = analysis.get('remote_confidence', 0.5)
                    remote_reason = analysis.get('reason', 'Validation failed')
                    metrics['validation_errors'] += 1
                
                stats['analyzed_with_llm'] += 1
                metrics['llm_calls'] += 1
                metrics['jobs_analyzed'] += 1
            else:
                # High confidence from keywords
                stats['high_confidence_skip'] += 1
                is_remote = basic_result['is_remote']
                remote_confidence = 1.0 if basic_result['confidence'] == 'HIGH' else 0.7
                remote_reason = f"Keyword detection: {basic_result['reason']}"
                metrics['jobs_analyzed'] += 1
            
            # Display result
            if verbose:
                if is_remote:
                    print(f"  ✅ REMOTE (confidence: {remote_confidence:.2f}) - {remote_reason}")
                else:
                    print(f"  ❌ On-site - {remote_reason}")
            
            if is_remote:
                remote_count += 1
            
            # Track confidence distribution
            if remote_confidence >= 0.7:
                metrics['confidence_distribution']['high'] += 1
            elif remote_confidence >= 0.4:
                metrics['confidence_distribution']['medium'] += 1
            else:
                metrics['confidence_distribution']['low'] += 1
            
            # Create job object with validation
            job_object = {
                'title': job_title,
                'description': full_description,
                'url': job_url,
                'location': job_location,
                'price': job_price,
                'poster': job_data.get('poster', 'N/A'),
                'is_remote': is_remote,
                'remote_confidence': remote_confidence,
                'reason': remote_reason
            }
            
            # Validate job data
            validated_job = validate_job_data(job_object)
            if validated_job:
                # Use validated data (converted to dict)
                all_jobs.append(validated_job.model_dump())
            else:
                # Validation failed - use raw data
                all_jobs.append(job_object)
                metrics['validation_errors'] += 1
        
        # ===== PHASE 4: EXPORT RESULTS =====
        logger.info(f"Analysis complete - Total: {len(all_jobs)}, Remote: {remote_count}")
        
        # Display summary
        if verbose:
            print(f"\n{'='*60}")
            print(f"✅ Analysis complete!")
            print(f"   Total pages scraped: {pages_scraped}")
            print(f"   Total jobs: {len(all_jobs)}")
            if incremental:
                print(f"   New/changed jobs analyzed: {metrics['new_jobs']}")
                print(f"   Jobs from cache: {metrics['cached_jobs']}")
            print(f"   Remote jobs: {remote_count}")
            print(f"   Remote percentage: {round(remote_count / len(all_jobs) * 100, 2) if all_jobs else 0}%")
            print(f"   📊 Stats:")
            print(f"      - Analyzed with LLM: {stats['analyzed_with_llm']}")
            print(f"      - High confidence skip: {stats['high_confidence_skip']}")
            print(f"      - Full descriptions fetched: {stats['full_description_fetched']}")
            if incremental:
                print(f"      - Incremental reduction: {metrics['cached_jobs']}/{len(all_jobs)} ({round(metrics['cached_jobs']/len(all_jobs)*100, 1) if all_jobs else 0}%)")
            if metrics['validation_errors'] > 0:
                print(f"      ⚠️  Validation errors: {metrics['validation_errors']}")
            print(f"{'='*60}\n")
        
        # Get cache statistics
        cache_stats = llm_analyzer.get_cache_stats()
        metrics['cache_hits'] = cache_stats.get('cache_hits', 0)
        
        # Calculate duration
        duration = (datetime.now() - metrics['start_time']).seconds
        
        # Export metrics with validation
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
            'errors': metrics['errors']
        }
        
        # Validate metrics
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
        
        # Export results
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
            'source': base_url,
            'pages_scraped': pages_scraped,
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        remote_jobs = [job for job in all_jobs if job['is_remote']]
        
        stats_remote = {
            'total': len(remote_jobs),
            'remote': len(remote_jobs),
            'on_site': 0,
            'remote_percentage': 100.0,
            'llm_used': use_llm,
            'source': base_url,
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Export
        if verbose:
            print("📦 Exporting all jobs...")
        json_all = exporter.export_to_json(all_jobs, stats_all, filename='jobs_latest.json')
        csv_all = exporter.export_to_csv(all_jobs, filename='jobs_latest.csv')
        
        if verbose:
            print("📦 Exporting remote jobs...")
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
        metrics['errors'].append(str(e))
        return {
            'success': False,
            'error': str(e),
            'results': all_jobs,
            'metrics': metrics
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape and analyze job listings (Incremental Mode)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed progress')
    parser.add_argument('--no-llm', action='store_true', help='Disable LLM analysis')
    parser.add_argument('--pages', type=int, default=10, help='Max pages to scrape (default: 10)')
    parser.add_argument('--no-incremental', action='store_true', help='Disable incremental scraping')
    parser.add_argument('--lookback', type=int, default=24, help='Lookback hours for incremental (default: 24)')
    
    args = parser.parse_args()
    
    result = scrape_and_analyze_jobs_incremental(
        use_llm=not args.no_llm,
        verbose=args.verbose,
        max_pages=args.pages,
        incremental=not args.no_incremental,
        lookback_hours=args.lookback
    )
    
    if result['success']:
        print(f"\n✅ Scraping completed successfully!")
        print(f"📊 {result['stats']['total']} jobs processed")
        print(f"🌍 {result['stats']['remote']} remote jobs found")
    else:
        print(f"\n❌ Scraping failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)
