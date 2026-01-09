import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from remote_detector import RemoteJobDetector
from semantic_analyzer import SemanticJobAnalyzer
from description_fetcher import JobDescriptionFetcher
import os

def scrape_jobs_with_semantic_analysis(url, use_llm=True):
    """
    Scrape jobs with semantic re-analysis of low-confidence classifications
    
    Args:
        url: The URL to scrape
        use_llm: Whether to use LLM for semantic analysis (requires API key)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        job_cards = soup.find_all('div', attrs={'data-url': True})
        
        # Initialize detectors
        basic_detector = RemoteJobDetector()
        semantic_analyzer = SemanticJobAnalyzer(use_groq=use_llm)
        description_fetcher = JobDescriptionFetcher()
        
        print(f"\n{'='*80}")
        print(f"SCRAPING & ANALYSIS: {len(job_cards)} jobs found")
        print(f"Mode: {'🤖 LLM-Enhanced' if use_llm else '📚 NLP-Only'}")
        print(f"{'='*80}\n")
        
        # Statistics
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
            
            # PHASE 1: Initial classification with keyword/category detection
            initial_analysis = basic_detector.detect_remote_possibility(
                job_title,
                job_description,
                job_location
            )
            
            # Track initial classification
            classification_type = f"{'remote' if initial_analysis['is_remote'] else 'on_site'}_{initial_analysis['confidence']}"
            stats[classification_type] = stats.get(classification_type, 0) + 1
            
            # PHASE 1.5: Check if we need full description for semantic analysis
            needs_semantic = initial_analysis['confidence'].lower() in ['low', 'medium']
            description_to_use = job_description
            description_source = 'listing_page'
            
            if needs_semantic:
                # Check if description is truncated or too short
                if description_fetcher.needs_full_description(job_description):
                    print(f"  📄 Description seems incomplete for Job #{idx}, fetching full version...")
                    full_desc_result = description_fetcher.get_best_description(
                        job_description,
                        job_url,
                        force_fetch=False
                    )
                    
                    if full_desc_result['was_fetched']:
                        description_to_use = full_desc_result['description']
                        description_source = full_desc_result['source']
                        stats['full_description_fetched'] += 1
                        print(f"  ✅ Fetched full description ({len(description_to_use)} chars)")
            
            # PHASE 2: Semantic re-analysis for LOW and MEDIUM confidence cases
            final_analysis = initial_analysis.copy()
            
            if initial_analysis['confidence'].lower() in ['low', 'medium']:
                stats['reanalyzed'] += 1
                
                job_data = {
                    'title': job_title,
                    'description': description_to_use,  # Use full description if fetched
                    'location': job_location
                }
                
                semantic_result = semantic_analyzer.reanalyze_low_confidence(
                    job_data,
                    initial_analysis
                )
                
                # Update analysis with semantic results
                final_analysis = semantic_result
            
            # Store results
            job_result = {
                'id': idx,
                'title': job_title,
                'location': job_location,
                'price': job_price,
                'poster': job_poster,
                'date': job_date,
                'description': job_description,
                'full_description': description_to_use,
                'description_source': description_source,
                'url': job_full_url,
                'initial_classification': initial_analysis,
                'final_classification': final_analysis,
                'was_reanalyzed': initial_analysis['confidence'].lower() in ['low', 'medium']
            }
            
            results.append(job_result)
            
            # Display results
            is_remote = final_analysis['is_remote']
            confidence = final_analysis['confidence'].upper()
            emoji = '🏠' if is_remote else '📍'
            status = 'REMOTE' if is_remote else 'ON-SITE'
            reanalyzed_mark = ' 🔄 (Re-analyzed)' if job_result['was_reanalyzed'] else ''
            
            print(f"\nJob #{idx}")
            print(f"  Title: {job_title}")
            print(f"  Location: {job_location}")
            print(f"  Classification: {emoji} {status} - Confidence: {confidence}{reanalyzed_mark}")
            
            if job_result['was_reanalyzed']:
                print(f"    ├─ Initial: {initial_analysis['reason']}")
                print(f"    └─ Final: {final_analysis['reason']}")
            else:
                print(f"    └─ {final_analysis['reason']}")
            
            print(f"  Price: {job_price}")
            print(f"  Posted by: {job_poster} on {job_date}")
            print(f"  Description: {job_description[:120]}..." if len(job_description) > 120 else f"  Description: {job_description}")
            print(f"  URL: {job_full_url}")
            print("-" * 80)
        
        # Display summary statistics
        print(f"\n{'='*80}")
        print("CLASSIFICATION SUMMARY:")
        print(f"{'='*80}")
        print(f"Total Jobs: {stats['total']}")
        print(f"\nInitial Classification:")
        print(f"  📍 ON-SITE HIGH:   {stats.get('on_site_high', 0)} (No recheck needed)")
        print(f"  📍 ON-SITE MEDIUM: {stats.get('on_site_medium', 0)}")
        print(f"  📍 ON-SITE LOW:    {stats.get('on_site_low', 0)}")
        print(f"  🏠 REMOTE MEDIUM:  {stats.get('remote_medium', 0)} (Semantic recheck)")
        print(f"  🏠 REMOTE LOW:     {stats.get('remote_low', 0)}")
        print(f"\n🔄 Re-analyzed with Semantic Model: {stats['reanalyzed']} jobs")
        print(f"📄 Full Descriptions Fetched: {stats['full_description_fetched']} jobs")
        
        # Count final classifications
        final_stats = {
            'on_site': sum(1 for r in results if not r['final_classification']['is_remote']),
            'remote': sum(1 for r in results if r['final_classification']['is_remote'])
        }
        
        print(f"\nFinal Results:")
        print(f"  📍 ON-SITE: {final_stats['on_site']} jobs")
        print(f"  🏠 REMOTE:  {final_stats['remote']} jobs")
        print(f"{'='*80}\n")
        
        return results, stats
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return [], {}
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        return [], {}


if __name__ == "__main__":
    print("\n🚀 Advanced Job Scraper with Semantic Analysis")
    print("="*80)
    
    # Check for Groq API key
    groq_key = os.environ.get('GROQ_API_KEY')
    
    if groq_key:
        print("✅ Groq API key found - Using LLM for semantic analysis")
        use_llm = True
    else:
        print("⚠️  No Groq API key found")
        print("   Option 1: Set GROQ_API_KEY environment variable")
        print("   Option 2: Get free API key at: https://console.groq.com/")
        print("\n   Falling back to local NLP analysis...")
        use_llm = False
    
    print("\n")
    
    default_url = "https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1"
    print(f"Default URL: {default_url}")
    user_input = input("Press Enter to use default URL or enter a different URL: ").strip()
    
    target_url = user_input if user_input else default_url
    
    if target_url:
        results, stats = scrape_jobs_with_semantic_analysis(target_url, use_llm=use_llm)
    else:
        print("No URL provided.")
