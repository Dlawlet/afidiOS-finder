# -*- coding: utf-8 -*-
"""
Scheduled Job Scraper - Run automatically via Windows Task Scheduler
Generates remote jobs export for external applications
"""

import sys
import io
# Force UTF-8 encoding for console output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from remote_detector import RemoteJobDetector
from semantic_analyzer import SemanticJobAnalyzer
from description_fetcher import JobDescriptionFetcher
from job_exporter import JobExporter
import os
import json
from datetime import datetime
from pathlib import Path


def scrape_and_export_remote_jobs(url, use_llm=True):
    """
    Scrape jobs and export only remote-friendly jobs
    Optimized for automated scheduling
    """
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting scheduled scraping...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        job_cards = soup.find_all('div', attrs={'data-url': True})
        
        print(f"Found {len(job_cards)} jobs to analyze")
        
        # Initialize detectors
        basic_detector = RemoteJobDetector()
        semantic_analyzer = SemanticJobAnalyzer(use_groq=use_llm)
        description_fetcher = JobDescriptionFetcher()
        
        stats = {
            'total': len(job_cards),
            'on_site_high': 0,
            'on_site_low': 0,
            'on_site_medium': 0,
            'remote_high': 0,
            'remote_low': 0,
            'remote_medium': 0,
            'reanalyzed': 0,
            'full_description_fetched': 0
        }
        
        results = []
        
        for idx, card in enumerate(job_cards, 1):
            # Extract job data
            job_url = card.get('data-url', 'N/A')
            job_full_url = urljoin(url, job_url) if job_url != 'N/A' else 'N/A'
            
            job_title = 'N/A'
            job_description = 'N/A'
            job_location = 'N/A'
            job_price = 'N/A'
            job_poster = 'N/A'
            job_date = 'N/A'
            
            # Extract title
            title_tag = card.find('span', class_='card-title')
            if title_tag:
                job_title = title_tag.get_text(strip=True)
            
            # Extract location
            location_tag = card.find('a', class_='grey_jmp_text')
            if location_tag:
                job_location = location_tag.get_text(strip=True)
            
            # Extract price
            price_tags_all = card.find_all('b', class_='orange_jmp_text')
            for price_tag in price_tags_all:
                if price_tag.parent.name == 'div':
                    price_text = price_tag.get_text(strip=True)
                    small_tag = price_tag.find_next_sibling('small')
                    if small_tag:
                        price_text += ' ' + small_tag.get_text(strip=True)
                    job_price = price_text
                    break
            
            # Extract poster
            poster_tags = card.find_all('b', class_='orange_jmp_text')
            for poster_tag in poster_tags:
                if poster_tag.parent.name == 'p':
                    job_poster = poster_tag.get_text(strip=True)
                    break
            
            # Extract date
            span_tags = card.find_all('span')
            for span in span_tags:
                text = span.get_text(strip=True)
                if '/' in text and len(text) == 10:
                    job_date = text
                    break
            
            # Extract description
            description_rows = card.find_all('div', class_='row')
            if description_rows:
                last_row = description_rows[-1]
                desc_p = last_row.find('p')
                if desc_p:
                    job_description = desc_p.get_text(strip=True)
            
            # Initial classification
            initial_analysis = basic_detector.detect_remote_possibility(
                job_title,
                job_description,
                job_location
            )
            
            classification_type = f"{'remote' if initial_analysis['is_remote'] else 'on_site'}_{initial_analysis['confidence']}"
            stats[classification_type] = stats.get(classification_type, 0) + 1
            
            # Check if we need full description
            needs_semantic = initial_analysis['confidence'].lower() in ['low', 'medium']
            description_to_use = job_description
            description_source = 'listing_page'
            
            if needs_semantic:
                if description_fetcher.needs_full_description(job_description):
                    full_desc_result = description_fetcher.get_best_description(
                        job_description,
                        job_url,
                        force_fetch=False
                    )
                    
                    if full_desc_result['was_fetched']:
                        description_to_use = full_desc_result['description']
                        description_source = full_desc_result['source']
                        stats['full_description_fetched'] += 1
            
            # Semantic re-analysis
            final_analysis = initial_analysis.copy()
            
            if initial_analysis['confidence'].lower() in ['low', 'medium']:
                stats['reanalyzed'] += 1
                
                job_data = {
                    'title': job_title,
                    'description': description_to_use,
                    'location': job_location,
                    'price': job_price
                }
                
                semantic_result = semantic_analyzer.reanalyze_low_confidence(
                    job_data,
                    initial_analysis
                )
                
                final_analysis = semantic_result
            
            # Store results
            job_result = {
                'id': idx,
                'title': job_title,
                'location': job_location,
                'price': job_price,
                'poster': job_poster,
                'date_posted': job_date,
                'description': job_description,
                'full_description': description_to_use,
                'description_source': description_source,
                'url': job_full_url,
                'initial_classification': initial_analysis,
                'final_classification': final_analysis,
                'was_reanalyzed': initial_analysis['confidence'].lower() in ['low', 'medium']
            }
            
            results.append(job_result)
        
        # Count final classifications
        final_stats = {
            'on_site': sum(1 for r in results if not r['final_classification']['is_remote']),
            'remote': sum(1 for r in results if r['final_classification']['is_remote'])
        }
        
        stats['final_on_site'] = final_stats['on_site']
        stats['final_remote'] = final_stats['remote']
        stats['llm_used'] = use_llm
        
        print(f"Analysis complete: {stats['final_remote']} remote jobs found out of {stats['total']}")
        
        # Export ONLY remote jobs to a fixed filename
        exporter = JobExporter()
        
        # Prepare ONLY remote jobs for export
        remote_jobs = []
        for idx, result in enumerate(results, 1):
            final_class = result['final_classification']
            if final_class['is_remote']:  # Only include remote jobs
                remote_jobs.append({
                    'id': idx,
                    'title': result['title'],
                    'location': result['location'],
                    'category': result['location'].split(' - ')[0] if ' - ' in result['location'] else 'N/A',
                    'price': result['price'],
                    'poster': result['poster'],
                    'date_posted': result['date_posted'],
                    'classification': 'REMOTE',
                    'confidence': final_class['confidence'].upper(),
                    'is_remote': True,
                    'reasoning': final_class['reason'],
                    'description': result['description'],
                    'description_source': result['description_source'],
                    'was_reanalyzed': result['was_reanalyzed'],
                    'url': result['url']
                })
        
        # Export to FIXED filename for external app access
        json_path = exporter.export_to_json(remote_jobs, stats, filename='remote_jobs_latest.json')
        csv_path = exporter.export_to_csv(remote_jobs, filename='remote_jobs_latest.csv')
        
        print(f"\n✅ Remote jobs exported:")
        print(f"   JSON: {json_path}")
        print(f"   CSV:  {csv_path}")
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scraping completed successfully")
        
        return remote_jobs, stats
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return [], {}


if __name__ == "__main__":
    # Check for Groq API key
    groq_key = os.environ.get('GROQ_API_KEY')
    use_llm = bool(groq_key)
    
    print(f"Mode: {'LLM-Enhanced' if use_llm else 'NLP-Only'}")
    
    url = "https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1"
    
    remote_jobs, stats = scrape_and_export_remote_jobs(url, use_llm=use_llm)
    
    # Log to file for monitoring
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"scrape_log_{datetime.now().strftime('%Y%m%d')}.txt"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total jobs: {stats.get('total', 0)}\n")
        f.write(f"Remote jobs: {stats.get('final_remote', 0)}\n")
        f.write(f"Mode: {'LLM' if use_llm else 'NLP'}\n")
        f.write(f"Status: {'SUCCESS' if remote_jobs is not None else 'FAILED'}\n")
    
    # Push to GitHub for web access (if configured)
    try:
        from github_publisher import git_push_results
        print("\n🌐 Publishing to GitHub...")
        git_push_results()
    except Exception as e:
        print(f"ℹ️  GitHub push skipped: {e}")
