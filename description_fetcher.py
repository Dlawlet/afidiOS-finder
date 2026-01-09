"""
Full Job Description Fetcher
Fetches complete job descriptions from individual job pages
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional

class JobDescriptionFetcher:
    """Fetches full job descriptions from individual job pages"""
    
    def __init__(self, base_url="https://www.jemepropose.com"):
        """
        Initialize the fetcher
        
        Args:
            base_url: Base URL of the job site
        """
        self.base_url = base_url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
        }
    
    def needs_full_description(self, description: str, min_length: int = 100) -> bool:
        """
        Check if description is truncated and needs full fetch
        
        Args:
            description: Current description text
            min_length: Minimum length to consider complete
            
        Returns:
            True if description seems truncated or too short
        """
        if not description or description == 'N/A':
            return True
        
        # Check if too short
        if len(description) < min_length:
            return True
        
        # Check if ends with truncation indicators
        truncation_indicators = ['...', '…', 'Lire la suite', 'Voir plus']
        if any(indicator in description for indicator in truncation_indicators):
            return True
        
        return False
    
    def fetch_full_description(self, job_url: str) -> Optional[Dict[str, str]]:
        """
        Fetch full job description from individual job page
        
        Args:
            job_url: Relative or absolute URL to job page
            
        Returns:
            Dict with 'description' and 'full_details' or None if failed
        """
        try:
            # Build full URL if relative
            if job_url.startswith('/'):
                full_url = f"{self.base_url}{job_url}"
            else:
                full_url = job_url
            
            print(f"    📄 Fetching full description from: {job_url}")
            
            # Fetch the job page
            response = requests.get(full_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # Parse the page
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the description section
            # Looking for: <div class="col s12 pt-8"> containing <h2 class="title_page"><b>Description</b></h2>
            description_section = None
            
            # Method 1: Find h2 with "Description" then get parent section
            desc_headers = soup.find_all('h2', class_='title_page')
            for header in desc_headers:
                if 'Description' in header.get_text():
                    # Get the parent container
                    parent = header.find_parent('div', class_='col s12 pt-8')
                    if parent:
                        description_section = parent
                        break
            
            # Method 2: Direct search for div with description
            if not description_section:
                description_section = soup.find('div', class_='col s12 pt-8')
            
            if description_section:
                # Extract all paragraphs and text from the description section
                # Skip the header itself
                full_text = []
                
                for element in description_section.find_all(['p', 'div', 'span']):
                    text = element.get_text(strip=True)
                    if text and text not in full_text and 'Description' not in text:
                        full_text.append(text)
                
                full_description = ' '.join(full_text)
                
                if full_description:
                    return {
                        'description': full_description,
                        'full_details': full_description,
                        'source': 'full_page'
                    }
            
            # If we couldn't find the specific section, try to get all text content
            # from main content area
            main_content = soup.find('div', class_='card-content')
            if main_content:
                paragraphs = main_content.find_all('p')
                full_text = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                
                if full_text:
                    return {
                        'description': full_text,
                        'full_details': full_text,
                        'source': 'main_content'
                    }
            
            print(f"    ⚠️  Could not extract full description from page")
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"    ⚠️  Error fetching job page: {e}")
            return None
        except Exception as e:
            print(f"    ⚠️  Error parsing job page: {e}")
            return None
    
    def get_best_description(self, current_description: str, job_url: str, 
                            force_fetch: bool = False) -> Dict[str, str]:
        """
        Get the best available description (current or fetched)
        
        Args:
            current_description: Current description from listing page
            job_url: URL to job page
            force_fetch: Force fetching even if current seems complete
            
        Returns:
            Dict with 'description', 'source', and 'was_fetched'
        """
        # Check if we need to fetch full description
        if not force_fetch and not self.needs_full_description(current_description):
            return {
                'description': current_description,
                'source': 'listing_page',
                'was_fetched': False
            }
        
        # Try to fetch full description
        full_desc = self.fetch_full_description(job_url)
        
        if full_desc:
            return {
                'description': full_desc['description'],
                'source': full_desc['source'],
                'was_fetched': True
            }
        else:
            # Fall back to current description
            return {
                'description': current_description,
                'source': 'listing_page_fallback',
                'was_fetched': False
            }


# Example usage and testing
if __name__ == "__main__":
    fetcher = JobDescriptionFetcher()
    
    # Test with a real job URL
    test_url = "/annonces/ingenieur-du-son/recherche-inge-son-court-metrage-10-11-janvier-2026+10498916/"
    
    print("Testing Full Description Fetcher")
    print("=" * 80)
    
    result = fetcher.fetch_full_description(test_url)
    
    if result:
        print(f"\n✅ Successfully fetched description")
        print(f"Source: {result['source']}")
        print(f"Length: {len(result['description'])} characters")
        print(f"\nFirst 300 characters:")
        print(result['description'][:300])
    else:
        print("\n❌ Failed to fetch description")
