import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def scrape_jobs(url):
    """
    Scrape job listings from jemepropose.com
    
    Args:
        url: The URL of the job listing page
    """
    try:
        # Send a GET request to the URL
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all job listings - looking for div with data-url attribute
        # This captures both fadeLeft and fadeRight animations
        job_cards = soup.find_all('div', attrs={'data-url': True})
        
        print(f"Found {len(job_cards)} job(s):\n")
        print("=" * 80)
        
        # Extract and print information for each job
        for idx, card in enumerate(job_cards, 1):
            # Get the data-url attribute
            job_url = card.get('data-url', 'N/A')
            job_full_url = urljoin(url, job_url) if job_url != 'N/A' else 'N/A'
            
            # Try to extract job title and other details
            job_title = 'N/A'
            job_description = 'N/A'
            job_location = 'N/A'
            job_price = 'N/A'
            job_poster = 'N/A'
            job_date = 'N/A'
            
            # Extract title from span with class "card-title"
            title_tag = card.find('span', class_='card-title')
            if title_tag:
                job_title = title_tag.get_text(strip=True)
            
            # Extract location from link with class "grey_jmp_text"
            location_tag = card.find('a', class_='grey_jmp_text')
            if location_tag:
                job_location = location_tag.get_text(strip=True)
            
            # Extract price from b tag with class "orange_jmp_text" and its sibling small tag
            price_tags_all = card.find_all('b', class_='orange_jmp_text')
            for price_tag in price_tags_all:
                if price_tag.parent.name == 'div':
                    price_text = price_tag.get_text(strip=True)
                    small_tag = price_tag.find_next_sibling('small')
                    if small_tag:
                        price_text += ' ' + small_tag.get_text(strip=True)
                    job_price = price_text
                    break
            
            # Extract poster name (first b tag with orange_jmp_text class that's in a p tag)
            poster_tags = card.find_all('b', class_='orange_jmp_text')
            for poster_tag in poster_tags:
                if poster_tag.parent.name == 'p':
                    job_poster = poster_tag.get_text(strip=True)
                    break
            
            # Extract date
            span_tags = card.find_all('span')
            for span in span_tags:
                text = span.get_text(strip=True)
                if '/' in text and len(text) == 10:  # Date format DD/MM/YYYY
                    job_date = text
                    break
            
            # Extract description from the last p tag in the card
            description_rows = card.find_all('div', class_='row')
            if description_rows:
                last_row = description_rows[-1]
                desc_p = last_row.find('p')
                if desc_p:
                    job_description = desc_p.get_text(strip=True)
            
            print(f"Job #{idx}")
            print(f"  Title: {job_title}")
            print(f"  Location: {job_location}")
            print(f"  Price: {job_price}")
            print(f"  Posted by: {job_poster}")
            print(f"  Date: {job_date}")
            print(f"  Description: {job_description[:150]}..." if len(job_description) > 150 else f"  Description: {job_description}")
            print(f"  URL: {job_full_url}")
            print("-" * 80)
        
        return job_cards
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


if __name__ == "__main__":
    # Default URL for jemepropose.com
    default_url = "https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1"
    
    print(f"Default URL: {default_url}")
    user_input = input("Press Enter to use default URL or enter a different URL: ").strip()
    
    target_url = user_input if user_input else default_url
    
    if target_url:
        scrape_jobs(target_url)
    else:
        print("No URL provided. Please run the script again with a valid URL.")
