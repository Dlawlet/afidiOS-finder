# -*- coding: utf-8 -*-
"""
Scheduled Job Scraper - Optimized for GitHub Actions
Scrapes jemepropose.com and detects remote jobs using Groq LLM
"""

import sys
import io
# Force UTF-8 encoding for console output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from semantic_analyzer import SemanticJobAnalyzer
from job_exporter import JobExporter
from job_helpers import JobDescriptionFetcher, BasicRemoteDetector
import os
import json
from datetime import datetime


def scrape_and_analyze_jobs(url="https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1", use_llm=True):
    """
    Main scraping function - simplified version
    """
    print(f"\n{'='*60}")
    print(f"🚀 Starting job scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        print(f"📡 Fetching jobs from: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        job_cards = soup.find_all('div', attrs={'data-url': True})
        
        print(f"✅ Found {len(job_cards)} job listings\n")
        
        if len(job_cards) == 0:
            print("⚠️  No jobs found - check website structure")
            return None
        
        # Initialize tools
        print("🤖 Initializing analyzers...")
        basic_detector = BasicRemoteDetector()
        description_fetcher = JobDescriptionFetcher()
        llm_analyzer = SemanticJobAnalyzer(use_groq=use_llm)
        
        stats = {
            'total': len(job_cards),
            'analyzed_with_llm': 0,
            'full_description_fetched': 0,
            'high_confidence_skip': 0
        }
        
        results = []
        remote_count = 0
        
        for idx, card in enumerate(job_cards, 1):
            # Extract job data
            job_url = card.get('data-url', 'N/A')
            job_full_url = urljoin(url, job_url) if job_url != 'N/A' else 'N/A'
            
            # Extract title
            job_title = 'N/A'
            title_tag = card.find('span', class_='card-title')
            if title_tag:
                job_title = title_tag.get_text(strip=True)
            
            # Extract location
            job_location = 'N/A'
            location_tag = card.find('a', class_='grey_jmp_text')
            if location_tag:
                job_location = location_tag.get_text(strip=True)
            
            # Extract price
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
            
            # Extract poster
            job_poster = 'N/A'
            poster_tags = card.find_all('b', class_='orange_jmp_text')
            for poster_tag in poster_tags:
                if poster_tag.parent.name == 'p':
                    job_poster = poster_tag.get_text(strip=True)
                    break
            
            # Extract date
            job_date = 'N/A'
            span_tags = card.find_all('span')
            for span in span_tags:
                text = span.get_text(strip=True)
                if '/' in text and len(text) == 10:
                    job_date = text
                    break
            
            # Extract description (short preview)
            job_description = 'N/A'
            description_rows = card.find_all('div', class_='row')
            if description_rows:
                last_row = description_rows[-1]
                desc_p = last_row.find('p')
                if desc_p:
                    job_description = desc_p.get_text(strip=True)
            
            print(f"[{idx}/{len(job_cards)}] {job_title[:50]}...")
            
            # Step 1: Basic keyword detection
            basic_result = basic_detector.detect_confidence(
                job_title,
                job_description,
                job_location
            )
            
            # Step 2: Decide if we need full description and LLM
            needs_full_analysis = basic_result['confidence'] != 'HIGH'
            full_description = job_description
            
            if needs_full_analysis:
                # Fetch full description ONLY if description seems truncated (> 120 chars)
                # Si < 120 chars, c'est probablement complet
                if len(job_description) >= 120:
                    print(f"    📄 Fetching full description (truncated at {len(job_description)} chars)...")
                    fetched_desc = description_fetcher.fetch_full_description(job_full_url)
                    if fetched_desc and len(fetched_desc) > len(job_description):
                        full_description = fetched_desc
                        stats['full_description_fetched'] += 1
                        print(f"    ✅ Full description: {len(fetched_desc)} chars")
                    else:
                        print(f"    ⚠️ Could not fetch better description")
                else:
                    print(f"    ℹ️  Description seems complete ({len(job_description)} chars)")
                
                # Step 3: Analyze with LLM
                print(f"    🤖 Analyzing with LLM...")
                analysis = llm_analyzer.analyze_with_groq(
                    job_title,
                    full_description,
                    job_location,
                    job_price
                )
                stats['analyzed_with_llm'] += 1
                
                is_remote = analysis.get('is_remote', False)
                remote_confidence = analysis.get('remote_confidence', 0)
                remote_reason = analysis.get('reason', 'LLM analysis')
            else:
                # High confidence from keywords - skip LLM
                stats['high_confidence_skip'] += 1
                is_remote = basic_result['is_remote']
                remote_confidence = 1.0 if basic_result['confidence'] == 'HIGH' else 0.7
                remote_reason = f"Keyword detection: {basic_result['reason']}"
            
            # Display result
            if is_remote:
                remote_count += 1
                print(f"  ✅ REMOTE (confidence: {remote_confidence:.2f}) - {remote_reason}")
            else:
                print(f"  ❌ On-site - {remote_reason}")
            
            job_result = {
                'id': str(idx),
                'title': job_title,
                'location': job_location,
                'price': job_price,
                'poster': job_poster,
                'date_posted': job_date,
                'description': job_description,
                'full_description': full_description,
                'url': job_full_url,
                'is_remote': is_remote,
                'remote_confidence': remote_confidence,
                'remote_reason': remote_reason,
                'analyzed_with_llm': needs_full_analysis
            }
            
            results.append(job_result)
        
        print(f"\n{'='*60}")
        print(f"✅ Analysis complete!")
        print(f"   Total jobs: {len(results)}")
        print(f"   Remote jobs: {remote_count}")
        print(f"   Remote percentage: {(remote_count/len(results)*100):.1f}%")
        print(f"   📊 Stats:")
        print(f"      - Analyzed with LLM: {stats['analyzed_with_llm']}")
        print(f"      - High confidence skip: {stats['high_confidence_skip']}")
        print(f"      - Full descriptions fetched: {stats['full_description_fetched']}")
        print(f"{'='*60}\n")
        
        # Export results
        print("💾 Exporting results...")
        exporter = JobExporter()
        
        # Create stats for exporter
        stats_all = {
            'total': len(results),
            'remote': remote_count,
            'on_site': len(results) - remote_count,
            'remote_percentage': round(remote_count / len(results) * 100, 2) if results else 0,
            'llm_used': use_llm,
            'source': url,
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Filter remote jobs only
        remote_jobs = [job for job in results if job['is_remote']]
        
        stats_remote = {
            'total': len(remote_jobs),
            'remote': len(remote_jobs),
            'on_site': 0,
            'remote_percentage': 100.0,
            'llm_used': use_llm,
            'source': url,
            'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Export ALL jobs to jobs_latest.*
        print("📦 Exporting all jobs...")
        json_all = exporter.export_to_json(
            results,
            stats_all,
            filename='jobs_latest.json'
        )
        
        csv_all = exporter.export_to_csv(
            results,
            filename='jobs_latest.csv'
        )
        
        print(f"✅ All jobs JSON: {json_all}")
        print(f"✅ All jobs CSV: {csv_all}")
        
        # Export REMOTE ONLY to remote_jobs_latest.*
        print("🏠 Exporting remote jobs only...")
        json_remote = exporter.export_to_json(
            remote_jobs,
            stats_remote,
            filename='remote_jobs_latest.json'
        )
        
        csv_remote = exporter.export_to_csv(
            remote_jobs,
            filename='remote_jobs_latest.csv'
        )
        
        print(f"✅ Remote jobs JSON: {json_remote}")
        print(f"✅ Remote jobs CSV: {csv_remote}")
        
        return {
            'results': results,
            'remote_jobs': remote_jobs,
            'stats': stats_all
        }
        
    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main entry point"""
    # Check for Groq API key
    groq_key = os.getenv('GROQ_API_KEY')
    
    if not groq_key:
        print("⚠️  Warning: GROQ_API_KEY not found in environment")
        print("   Trying to load from .env file...")
        
        # Try to load from .env
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('GROQ_API_KEY='):
                        groq_key = line.split('=', 1)[1].strip()
                        os.environ['GROQ_API_KEY'] = groq_key
                        print("   ✅ Loaded from .env file")
                        break
        except FileNotFoundError:
            print("   ❌ .env file not found")
    
    if not groq_key:
        print("\n❌ ERROR: GROQ_API_KEY not configured")
        print("   Set it in GitHub Secrets or create a .env file")
        sys.exit(1)
    
    # Run scraper
    result = scrape_and_analyze_jobs()
    
    if result:
        print(f"\n🎉 Scraping completed successfully!")
        print(f"\n📊 Summary:")
        print(f"   - Total jobs scraped: {result['stats']['total']}")
        print(f"   - Remote jobs found: {result['stats']['remote']}")
        
        # Show public URLs
        print(f"\n🌍 Public access URLs:")
        print(f"   JSON: https://raw.githubusercontent.com/Dlawlet/afidiOS-finder/main/exports/remote_jobs_latest.json")
        print(f"   CSV:  https://raw.githubusercontent.com/Dlawlet/afidiOS-finder/main/exports/remote_jobs_latest.csv")
        
        return 0
    else:
        print("\n❌ Scraping failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
