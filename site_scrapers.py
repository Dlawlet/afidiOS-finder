# -*- coding: utf-8 -*-
"""
Multi-Site Scraper Architecture
Generalized scraper framework supporting multiple job platforms
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging


class BaseSiteScraper(ABC):
    """
    Abstract base class for all site scrapers
    Each site implements its own parsing logic
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = logging.getLogger(self.__class__.__name__)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    
    @property
    @abstractmethod
    def site_name(self) -> str:
        """Return the site name (e.g., 'jemepropose', 'malt')"""
        pass
    
    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the base search URL"""
        pass
    
    @abstractmethod
    def build_page_url(self, page_num: int) -> str:
        """Build URL for a specific page number"""
        pass
    
    @abstractmethod
    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        """
        Extract job listings from a BeautifulSoup page
        
        Returns:
            List of job dictionaries with keys:
            - url: str
            - title: str
            - description: str
            - location: str
            - price: str (optional)
            - source: str (site name)
        """
        pass
    
    def scrape_page(self, page_num: int) -> tuple[List[Dict], bool]:
        """
        Scrape a single page
        
        Returns:
            (jobs_list, has_more_pages)
        """
        url = self.build_page_url(page_num)
        
        try:
            if self.verbose:
                self.logger.debug(f"Scraping {url}")
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = self.extract_jobs_from_page(soup, url)
            
            # Add source to each job
            for job in jobs:
                job['source'] = self.site_name
            
            has_more = len(jobs) > 0
            
            return jobs, has_more
            
        except Exception as e:
            self.logger.error(f"Error scraping {url}: {e}")
            return [], False
    
    def scrape_multiple_pages(self, max_pages: int = 10) -> List[Dict]:
        """
        Scrape multiple pages
        
        Args:
            max_pages: Maximum number of pages to scrape
            
        Returns:
            List of all jobs found
        """
        all_jobs = []
        
        for page_num in range(1, max_pages + 1):
            if self.verbose:
                print(f"  📄 {self.site_name} - Page {page_num}/{max_pages}")
            
            jobs, has_more = self.scrape_page(page_num)
            
            if not has_more:
                if self.verbose:
                    print(f"  ⚠️  No more jobs on {self.site_name} page {page_num}")
                break
            
            all_jobs.extend(jobs)
            
            if self.verbose:
                print(f"  ✅ Found {len(jobs)} jobs ({len(all_jobs)} total)")
        
        return all_jobs


class JeMeProposeScraper(BaseSiteScraper):
    """Scraper for jemepropose.com"""
    
    @property
    def site_name(self) -> str:
        return "jemepropose"
    
    @property
    def base_url(self) -> str:
        return "https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1"
    
    def build_page_url(self, page_num: int) -> str:
        if page_num == 1:
            return self.base_url
        return f"{self.base_url}&page={page_num}"
    
    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        jobs = []
        job_cards = soup.find_all('div', attrs={'data-url': True})
        
        for card in job_cards:
            job_url = card.get('data-url', 'N/A')
            job_full_url = urljoin(page_url, job_url) if job_url != 'N/A' else 'N/A'
            
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
            
            job_description = card.find('p', class_='card-text')
            job_description = job_description.get_text(strip=True) if job_description else 'N/A'
            
            jobs.append({
                'url': job_full_url,
                'title': job_title,
                'description': job_description,
                'location': job_location,
                'price': job_price,
            })
        
        return jobs


class MaltScraper(BaseSiteScraper):
    """Scraper for malt.fr - French freelance marketplace"""
    
    @property
    def site_name(self) -> str:
        return "malt"
    
    @property
    def base_url(self) -> str:
        # Malt's job search page (missions/projects)
        return "https://www.malt.fr/s?q=&l="
    
    def build_page_url(self, page_num: int) -> str:
        # Malt uses offset-based pagination
        offset = (page_num - 1) * 20
        return f"{self.base_url}&offset={offset}"
    
    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        jobs = []
        
        # Malt uses different HTML structure - adjust selectors accordingly
        # This is a template - actual selectors need to be verified
        job_cards = soup.find_all('div', class_='project-card') or \
                   soup.find_all('article', class_='mission-card') or \
                   soup.find_all('div', attrs={'data-testid': 'project-card'})
        
        for card in job_cards:
            # Extract job URL
            link_tag = card.find('a', href=True)
            job_url = urljoin(page_url, link_tag['href']) if link_tag else 'N/A'
            
            # Extract title
            title_tag = card.find('h3') or card.find('h2') or card.find(class_='title')
            job_title = title_tag.get_text(strip=True) if title_tag else 'N/A'
            
            # Extract description
            desc_tag = card.find('p', class_='description') or card.find('div', class_='content')
            job_description = desc_tag.get_text(strip=True) if desc_tag else 'N/A'
            
            # Extract location (Malt often shows remote or city)
            location_tag = card.find(class_='location') or card.find('span', string=lambda s: s and 'Remote' in s)
            job_location = location_tag.get_text(strip=True) if location_tag else 'Remote'
            
            # Extract budget/price
            price_tag = card.find(class_='budget') or card.find(string=lambda s: s and '€' in s)
            job_price = price_tag.get_text(strip=True) if price_tag else 'N/A'
            
            jobs.append({
                'url': job_url,
                'title': job_title,
                'description': job_description,
                'location': job_location,
                'price': job_price,
            })
        
        return jobs


class FreelanceComScraper(BaseSiteScraper):
    """Scraper for freelance.com - International freelance platform"""
    
    @property
    def site_name(self) -> str:
        return "freelance.com"
    
    @property
    def base_url(self) -> str:
        return "https://www.freelance.com/projects"
    
    def build_page_url(self, page_num: int) -> str:
        return f"{self.base_url}?page={page_num}"
    
    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        jobs = []
        
        # Freelance.com structure (template - needs verification)
        job_cards = soup.find_all('div', class_='project-item') or \
                   soup.find_all('article', class_='project')
        
        for card in job_cards:
            # Extract job URL
            link_tag = card.find('a', class_='project-title') or card.find('a', href=True)
            job_url = urljoin(page_url, link_tag['href']) if link_tag else 'N/A'
            
            # Extract title
            title_tag = card.find('h2') or card.find('h3') or link_tag
            job_title = title_tag.get_text(strip=True) if title_tag else 'N/A'
            
            # Extract description
            desc_tag = card.find('p', class_='description') or card.find('div', class_='project-description')
            job_description = desc_tag.get_text(strip=True) if desc_tag else 'N/A'
            
            # Extract location
            location_tag = card.find(class_='location') or card.find('span', class_='country')
            job_location = location_tag.get_text(strip=True) if location_tag else 'Remote'
            
            # Extract budget
            budget_tag = card.find(class_='budget') or card.find(string=lambda s: s and ('$' in s or '€' in s))
            job_price = budget_tag.get_text(strip=True) if budget_tag else 'N/A'
            
            jobs.append({
                'url': job_url,
                'title': job_title,
                'description': job_description,
                'location': job_location,
                'price': job_price,
            })
        
        return jobs


class CometScraper(BaseSiteScraper):
    """Scraper for comet.co - Tech freelance platform"""
    
    @property
    def site_name(self) -> str:
        return "comet"
    
    @property
    def base_url(self) -> str:
        return "https://www.comet.co/opportunities"
    
    def build_page_url(self, page_num: int) -> str:
        return f"{self.base_url}?page={page_num}"
    
    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        jobs = []
        
        # Comet structure (template - needs verification)
        job_cards = soup.find_all('div', class_='opportunity-card') or \
                   soup.find_all('article', class_='opportunity')
        
        for card in job_cards:
            # Extract job URL
            link_tag = card.find('a', href=True)
            job_url = urljoin(page_url, link_tag['href']) if link_tag else 'N/A'
            
            # Extract title
            title_tag = card.find('h2') or card.find('h3', class_='title')
            job_title = title_tag.get_text(strip=True) if title_tag else 'N/A'
            
            # Extract description
            desc_tag = card.find('p', class_='description') or card.find('div', class_='content')
            job_description = desc_tag.get_text(strip=True) if desc_tag else 'N/A'
            
            # Extract location (Comet is often remote)
            location_tag = card.find(class_='location')
            job_location = location_tag.get_text(strip=True) if location_tag else 'Remote'
            
            # Extract rate
            rate_tag = card.find(class_='rate') or card.find(string=lambda s: s and ('/day' in s or '/hour' in s))
            job_price = rate_tag.get_text(strip=True) if rate_tag else 'N/A'
            
            jobs.append({
                'url': job_url,
                'title': job_title,
                'description': job_description,
                'location': job_location,
                'price': job_price,
            })
        
        return jobs


class MultiSiteScraper:
    """
    Orchestrator for scraping multiple job sites
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = logging.getLogger('MultiSiteScraper')
        self.scrapers: Dict[str, BaseSiteScraper] = {}
    
    def register_scraper(self, scraper: BaseSiteScraper):
        """Register a site scraper"""
        self.scrapers[scraper.site_name] = scraper
        if self.verbose:
            print(f"✅ Registered scraper: {scraper.site_name}")
    
    def scrape_all_sites(self, max_pages_per_site: int = 10, enabled_sites: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """
        Scrape all registered sites
        
        Args:
            max_pages_per_site: Max pages to scrape per site
            enabled_sites: List of site names to scrape (None = all)
            
        Returns:
            Dictionary mapping site names to job lists
        """
        results = {}
        
        sites_to_scrape = enabled_sites if enabled_sites else list(self.scrapers.keys())
        
        if self.verbose:
            print(f"\n🌐 Scraping {len(sites_to_scrape)} sites...")
        
        for site_name in sites_to_scrape:
            if site_name not in self.scrapers:
                self.logger.warning(f"Scraper not found: {site_name}")
                continue
            
            scraper = self.scrapers[site_name]
            
            if self.verbose:
                print(f"\n📡 {site_name.upper()}")
            
            try:
                jobs = scraper.scrape_multiple_pages(max_pages=max_pages_per_site)
                results[site_name] = jobs
                
                if self.verbose:
                    print(f"  ✅ Total: {len(jobs)} jobs from {site_name}")
                
            except Exception as e:
                self.logger.error(f"Error scraping {site_name}: {e}")
                results[site_name] = []
        
        return results
    
    def scrape_all_sites_unified(self, max_pages_per_site: int = 10, enabled_sites: Optional[List[str]] = None) -> List[Dict]:
        """
        Scrape all sites and return unified job list
        
        Args:
            max_pages_per_site: Max pages to scrape per site
            enabled_sites: List of site names to scrape (None = all)
            
        Returns:
            Unified list of all jobs with 'source' field
        """
        results = self.scrape_all_sites(max_pages_per_site, enabled_sites)
        
        all_jobs = []
        for site_name, jobs in results.items():
            all_jobs.extend(jobs)
        
        if self.verbose:
            print(f"\n📊 Total jobs across all sites: {len(all_jobs)}")
            for site_name, jobs in results.items():
                print(f"  - {site_name}: {len(jobs)} jobs")
        
        return all_jobs


# ===== QUICK TEST =====
if __name__ == '__main__':
    """Test the multi-site scraper"""
    
    print("="*60)
    print("MULTI-SITE SCRAPER TEST")
    print("="*60)
    
    # Create multi-site scraper
    multi_scraper = MultiSiteScraper(verbose=True)
    
    # Register scrapers
    multi_scraper.register_scraper(JeMeProposeScraper(verbose=True))
    # multi_scraper.register_scraper(MaltScraper(verbose=True))  # Uncomment when ready
    # multi_scraper.register_scraper(FreelanceComScraper(verbose=True))
    # multi_scraper.register_scraper(CometScraper(verbose=True))
    
    # Test with just 1 page
    print("\nTesting with 1 page per site...")
    results = multi_scraper.scrape_all_sites(max_pages_per_site=1)
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    for site_name, jobs in results.items():
        print(f"\n{site_name.upper()}: {len(jobs)} jobs")
        if jobs:
            print(f"  Sample: {jobs[0]['title'][:50]}...")
    
    print("\n✅ Test complete!")
