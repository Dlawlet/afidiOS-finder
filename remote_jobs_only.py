import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from remote_detector import RemoteJobDetector

def scrape_remote_jobs_only(url):
    """
    Scrape and filter only remote jobs from jemepropose.com
    
    Args:
        url: The URL of the job listing page
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
        
        detector = RemoteJobDetector()
        
        remote_jobs = []
        on_site_jobs = []
        
        # Analyze all jobs
        for card in job_cards:
            job_url = card.get('data-url', 'N/A')
            job_full_url = urljoin(url, job_url) if job_url != 'N/A' else 'N/A'
            
            # Extract job details
            job_title = 'N/A'
            job_description = 'N/A'
            job_location = 'N/A'
            job_price = 'N/A'
            
            title_tag = card.find('span', class_='card-title')
            if title_tag:
                job_title = title_tag.get_text(strip=True)
            
            location_tag = card.find('a', class_='grey_jmp_text')
            if location_tag:
                job_location = location_tag.get_text(strip=True)
            
            price_tags_all = card.find_all('b', class_='orange_jmp_text')
            for price_tag in price_tags_all:
                if price_tag.parent.name == 'div':
                    price_text = price_tag.get_text(strip=True)
                    small_tag = price_tag.find_next_sibling('small')
                    if small_tag:
                        price_text += ' ' + small_tag.get_text(strip=True)
                    job_price = price_text
                    break
            
            description_rows = card.find_all('div', class_='row')
            if description_rows:
                last_row = description_rows[-1]
                desc_p = last_row.find('p')
                if desc_p:
                    job_description = desc_p.get_text(strip=True)
            
            # Detect remote possibility
            remote_analysis = detector.detect_remote_possibility(
                job_title, 
                job_description, 
                job_location
            )
            
            job_data = {
                'title': job_title,
                'location': job_location,
                'price': job_price,
                'description': job_description,
                'url': job_full_url,
                'remote_analysis': remote_analysis
            }
            
            if remote_analysis['is_remote']:
                remote_jobs.append(job_data)
            else:
                on_site_jobs.append(job_data)
        
        # Display results
        print(f"\n{'='*80}")
        print(f"SUMMARY: Found {len(job_cards)} total jobs")
        print(f"  🏠 REMOTE: {len(remote_jobs)} jobs")
        print(f"  📍 ON-SITE: {len(on_site_jobs)} jobs")
        print(f"{'='*80}\n")
        
        if remote_jobs:
            print(f"\n🏠 REMOTE JOBS ({len(remote_jobs)}):\n")
            print("=" * 80)
            
            for idx, job in enumerate(remote_jobs, 1):
                print(f"\nJob #{idx}")
                print(f"  Title: {job['title']}")
                print(f"  Location: {job['location']}")
                print(f"  Price: {job['price']}")
                print(f"  Confidence: {job['remote_analysis']['confidence'].upper()}")
                print(f"  Reason: {job['remote_analysis']['reason']}")
                print(f"  Description: {job['description'][:150]}..." if len(job['description']) > 150 else f"  Description: {job['description']}")
                print(f"  URL: {job['url']}")
                print("-" * 80)
        else:
            print("\n⚠️  No remote jobs found in this search.")
        
        return remote_jobs, on_site_jobs
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return [], []
    except Exception as e:
        print(f"An error occurred: {e}")
        return [], []


if __name__ == "__main__":
    default_url = "https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1"
    
    print(f"Default URL: {default_url}")
    user_input = input("Press Enter to use default URL or enter a different URL: ").strip()
    
    target_url = user_input if user_input else default_url
    
    if target_url:
        scrape_remote_jobs_only(target_url)
    else:
        print("No URL provided.")
