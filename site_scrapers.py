# -*- coding: utf-8 -*-
"""
Multi-Site Scraper Architecture
Generalized scraper framework supporting multiple job platforms
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import re
import html
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

MAX_DESCRIPTION_LENGTH = 800


def clean_html_description(raw_text: str) -> str:
    if not raw_text:
        return ''
    cleaned = re.sub(r'<[^>]+>', ' ', raw_text)
    cleaned = html.unescape(' '.join(cleaned.split()))
    return cleaned[:MAX_DESCRIPTION_LENGTH]


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
        return "https://www.freelance.com/freelance-recherche-nouvelle-mission/"
    
    def build_page_url(self, page_num: int) -> str:
        if page_num == 1:
            return self.base_url
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
        return "https://www.comet.co/fr/freelances/trouver-une-mission"
    
    def build_page_url(self, page_num: int) -> str:
        if page_num == 1:
            return self.base_url
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


class AlloVoisinsScraper(BaseSiteScraper):
    """Scraper for allovoisins.com - Job rental/services platform"""
    
    @property
    def site_name(self) -> str:
        return "allovoisins"
    
    @property
    def base_url(self) -> str:
        # Clean base URL without tracking parameters
        return "https://www.allovoisins.com/r/-3/0/33908"
    
    def build_page_url(self, page_num: int) -> str:
        # URL pattern: /r/-3/0/33908/{page}/Job/location-vente
        # Page 0 = first page (0-indexed)
        page_index = page_num - 1
        return f"{self.base_url}/{page_index}/Job/location-vente"
    
    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        jobs = []
        
        # AlloVoisins uses various possible selectors
        # Try multiple patterns to find job cards
        job_cards = soup.find_all('article', class_='job-card') or \
                   soup.find_all('div', class_='job-item') or \
                   soup.find_all('div', class_='listing-item') or \
                   soup.find_all('article', class_='listing') or \
                   soup.find_all('div', attrs={'data-job-id': True}) or \
                   soup.find_all('a', class_='job-link')
        
        # If no specific cards found, try generic article/div containers
        if not job_cards:
            job_cards = soup.find_all('article') or soup.find_all('div', class_='card')
        
        for card in job_cards:
            # Extract job URL
            link_tag = card.find('a', href=True)
            if not link_tag and card.name == 'a':
                link_tag = card
            job_url = urljoin(page_url, link_tag['href']) if link_tag else 'N/A'
            
            # Extract title (try multiple selectors)
            title_tag = card.find('h2') or \
                       card.find('h3') or \
                       card.find('h4') or \
                       card.find(class_='title') or \
                       card.find(class_='job-title') or \
                       card.find(class_='listing-title')
            job_title = title_tag.get_text(strip=True) if title_tag else 'N/A'
            
            # Skip if no valid title
            if job_title == 'N/A' or len(job_title) < 3:
                continue
            
            # Extract description
            desc_tag = card.find('p', class_='description') or \
                      card.find('div', class_='description') or \
                      card.find('p', class_='excerpt') or \
                      card.find('div', class_='content')
            job_description = desc_tag.get_text(strip=True) if desc_tag else 'N/A'
            
            # Extract location
            location_tag = card.find(class_='location') or \
                          card.find('span', class_='city') or \
                          card.find(class_='address')
            job_location = location_tag.get_text(strip=True) if location_tag else 'France'
            
            # Extract price
            price_tag = card.find(class_='price') or \
                       card.find(class_='rate') or \
                       card.find('span', string=lambda s: s and '€' in s)
            job_price = price_tag.get_text(strip=True) if price_tag else 'N/A'
            
            jobs.append({
                'url': job_url,
                'title': job_title,
                'description': job_description,
                'location': job_location,
                'price': job_price,
            })
        
        return jobs


class VosCoursScraper(BaseSiteScraper):
    """Scraper for voscours.fr student requests (tutoring)."""

    @property
    def site_name(self) -> str:
        return "voscours"

    @property
    def base_url(self) -> str:
        return "https://www.voscours.fr/annonces/eleves"

    def build_page_url(self, page_num: int) -> str:
        if page_num == 1:
            return self.base_url
        return f"{self.base_url}?page={page_num}"

    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        jobs = []
        seen = set()

        links = soup.select('a[href*="/annonces/eleves/"]')
        for link in links:
            href = link.get('href')
            if not href:
                continue

            if not re.search(r"/annonces/eleves/\d+", href):
                continue

            job_url = urljoin(page_url, href)
            if job_url in seen:
                continue
            seen.add(job_url)

            title = link.get_text(strip=True)
            card = link.find_parent('article') or link.find_parent('div') or link.parent
            description = 'N/A'
            location = 'N/A'
            poster = 'N/A'
            date_posted = 'N/A'

            if card:
                title_tag = card.find(['h2', 'h3'])
                if title_tag:
                    title = title_tag.get_text(strip=True)

                desc_tag = card.find('p')
                if desc_tag:
                    description = desc_tag.get_text(strip=True)

                loc_tag = card.find(class_='city') or card.find(class_='location')
                if loc_tag:
                    location = loc_tag.get_text(strip=True)

                poster_tag = card.find(class_='author') or card.find(class_='name')
                if poster_tag:
                    poster = poster_tag.get_text(strip=True)

                date_tag = card.find('time') or card.find(class_='date')
                if date_tag:
                    date_posted = date_tag.get_text(strip=True)

            if not title:
                title = "Demande de cours"

            jobs.append({
                'url': job_url,
                'title': title,
                'description': description,
                'location': location,
                'price': 'N/A',
                'poster': poster,
                'date_posted': date_posted,
                'poster_type': 'student',
            })

        return jobs


class FindTutorsUKScraper(BaseSiteScraper):
    """Scraper for findtutors.co.uk tutoring requests."""

    @property
    def site_name(self) -> str:
        return "findtutors_uk"

    @property
    def base_url(self) -> str:
        return "https://www.findtutors.co.uk/browse/pupils"

    def build_page_url(self, page_num: int) -> str:
        if page_num == 1:
            return self.base_url
        return f"{self.base_url}?page={page_num}"

    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        jobs = []
        seen = set()

        links = soup.select('a[href]')
        for link in links:
            href = link.get('href', '')
            if not href:
                continue

            if not ("tutoring" in href or "tutor" in href):
                continue

            job_url = urljoin(page_url, href)
            if job_url in seen:
                continue
            seen.add(job_url)

            title = link.get_text(strip=True)
            card = link.find_parent('article') or link.find_parent('div') or link.parent
            description = 'N/A'
            location = 'United Kingdom'

            if card:
                title_tag = card.find(['h2', 'h3'])
                if title_tag:
                    title = title_tag.get_text(strip=True)

                desc_tag = card.find('p')
                if desc_tag:
                    description = desc_tag.get_text(strip=True)

                loc_tag = card.find(class_='location') or card.find(class_='city')
                if loc_tag:
                    location = loc_tag.get_text(strip=True)

            if not title:
                title = "Tutoring request"

            jobs.append({
                'url': job_url,
                'title': title,
                'description': description,
                'location': location,
                'price': 'N/A',
                'poster_type': 'student',
            })

        return jobs


class CodeurScraper(BaseSiteScraper):
    """Scraper for codeur.com freelance missions (remote-friendly)."""

    @property
    def site_name(self) -> str:
        return "codeur"

    @property
    def base_url(self) -> str:
        return "https://www.codeur.com/projects"

    def build_page_url(self, page_num: int) -> str:
        if page_num == 1:
            return self.base_url
        return f"{self.base_url}?page={page_num}"

    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        jobs = []

        seen = set()
        project_links = soup.select('a[href*="/projects/"]')
        for link_tag in project_links:
            href = link_tag.get('href')
            if not href or '/projects/' not in href:
                continue

            job_url = urljoin(page_url, href)
            if job_url in seen:
                continue
            seen.add(job_url)

            card = link_tag.find_parent('article') or link_tag.find_parent('div') or link_tag.parent
            title_tag = (card.find(['h2', 'h3']) if card else None) or link_tag
            title = title_tag.get_text(strip=True) if title_tag else 'N/A'

            desc_tag = card.find('p') if card else None
            description = desc_tag.get_text(strip=True) if desc_tag else 'N/A'

            price_tag = card.find(class_='budget') if card else None
            if not price_tag and card:
                price_tag = card.find(class_='price')
            price = price_tag.get_text(strip=True) if price_tag else 'N/A'

            jobs.append({
                'url': job_url,
                'title': title,
                'description': description,
                'location': 'Remote',
                'price': price,
            })

        return jobs


class RemoteOKScraper(BaseSiteScraper):
    """RemoteOK API scraper (remote-only)."""

    @property
    def site_name(self) -> str:
        return "remoteok"

    @property
    def base_url(self) -> str:
        return "https://remoteok.com/api"

    def build_page_url(self, page_num: int) -> str:
        return self.base_url if page_num == 1 else None

    def scrape_page(self, page_num: int) -> tuple[List[Dict], bool]:
        if page_num > 1:
            return [], False

        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            raw = response.json()
            entries = [e for e in raw if isinstance(e, dict) and e.get('position')]

            jobs = []
            for item in entries:
                job_url = item.get('url', '')
                if job_url and not job_url.startswith('http'):
                    job_url = f"https://remoteok.com{job_url}"

                description = clean_html_description(item.get('description', ''))
                if item.get('tags'):
                    description = f"{description} | Skills: {', '.join(item.get('tags', [])[:8])}"

                jobs.append({
                    'url': job_url or 'N/A',
                    'title': item.get('position', 'N/A'),
                    'description': description or 'Remote position',
                    'location': item.get('location') or 'Remote / Worldwide',
                    'price': item.get('salary', 'N/A'),
                    'source': self.site_name,
                    'is_remote': True,
                    'remote_confidence': 0.99,
                    'reason': 'RemoteOK API (remote-only)',
                    'skip_analysis': True,
                })

            return jobs, False
        except Exception as e:
            self.logger.error(f"RemoteOK API error: {e}")
            return [], False

    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        _ = soup, page_url
        return []


class RemotiveScraper(BaseSiteScraper):
    """Remotive API scraper (remote-only)."""

    @property
    def site_name(self) -> str:
        return "remotive"

    @property
    def base_url(self) -> str:
        return "https://remotive.com/api/remote-jobs"

    def build_page_url(self, page_num: int) -> str:
        return self.base_url if page_num == 1 else None

    def scrape_page(self, page_num: int) -> tuple[List[Dict], bool]:
        if page_num > 1:
            return [], False

        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
            entries = payload.get('jobs', [])

            jobs = []
            for item in entries:
                description = clean_html_description(item.get('description', ''))
                jobs.append({
                    'url': item.get('url', 'N/A'),
                    'title': item.get('title', 'N/A'),
                    'description': description or 'Remote position',
                    'location': item.get('candidate_required_location') or item.get('location') or 'Remote / Worldwide',
                    'price': item.get('salary', 'N/A'),
                    'source': self.site_name,
                    'is_remote': True,
                    'remote_confidence': 0.99,
                    'reason': 'Remotive API (remote-only)',
                    'skip_analysis': True,
                })

            return jobs, False
        except Exception as e:
            self.logger.error(f"Remotive API error: {e}")
            return [], False

    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        _ = soup, page_url
        return []


class WorkingNomadsScraper(BaseSiteScraper):
    """WorkingNomads API scraper (remote-only)."""

    PAGE_SIZE = 100

    @property
    def site_name(self) -> str:
        return "workingnomads"

    @property
    def base_url(self) -> str:
        return "https://www.workingnomads.com/jobsapi/jobposts"

    def build_page_url(self, page_num: int) -> str:
        offset = (page_num - 1) * self.PAGE_SIZE
        return f"{self.base_url}?count={self.PAGE_SIZE}&offset={offset}"

    def scrape_page(self, page_num: int) -> tuple[List[Dict], bool]:
        url = self.build_page_url(page_num)
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 405:
                response = requests.post(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            entries = response.json()
            if not entries:
                return [], False

            jobs = []
            for item in entries:
                description = clean_html_description(item.get('description', '') or item.get('content', ''))
                jobs.append({
                    'url': item.get('url', 'N/A'),
                    'title': item.get('title', 'N/A'),
                    'description': description or 'Remote position',
                    'location': item.get('location') or 'Remote / Worldwide',
                    'price': item.get('salary', 'N/A'),
                    'source': self.site_name,
                    'is_remote': True,
                    'remote_confidence': 0.99,
                    'reason': 'WorkingNomads API (remote-only)',
                    'skip_analysis': True,
                })

            has_more = len(entries) >= self.PAGE_SIZE
            return jobs, has_more
        except Exception as e:
            self.logger.error(f"WorkingNomads API error: {e}")
            return [], False

    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        _ = soup, page_url
        return []


class ArbeitnowScraper(BaseSiteScraper):
    """Arbeitnow API scraper (remote-only)."""

    @property
    def site_name(self) -> str:
        return "arbeitnow"

    @property
    def base_url(self) -> str:
        return "https://www.arbeitnow.com/api/job-board-api"

    def build_page_url(self, page_num: int) -> str:
        return self.base_url if page_num == 1 else f"{self.base_url}?page={page_num}"

    def scrape_page(self, page_num: int) -> tuple[List[Dict], bool]:
        url = self.build_page_url(page_num)
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
            entries = payload.get('data', [])

            jobs = []
            for item in entries:
                if not item.get('remote', False):
                    continue
                description = clean_html_description(item.get('description', ''))
                job_url = item.get('url') or item.get('slug') or 'N/A'
                if job_url and not str(job_url).startswith('http'):
                    job_url = f"https://www.arbeitnow.com/jobs/{job_url}"

                jobs.append({
                    'url': job_url,
                    'title': item.get('title', 'N/A'),
                    'description': description or 'Remote position',
                    'location': item.get('location') or 'Remote / Europe',
                    'price': 'N/A',
                    'source': self.site_name,
                    'is_remote': True,
                    'remote_confidence': 0.99,
                    'reason': 'Arbeitnow API (remote-only)',
                    'skip_analysis': True,
                })

            has_more = bool(payload.get('links', {}).get('next'))
            return jobs, has_more
        except Exception as e:
            self.logger.error(f"Arbeitnow API error: {e}")
            return [], False

    def extract_jobs_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        _ = soup, page_url
        return []


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
    
    def scrape_with_incremental_quota(
        self, 
        daily_quota: int,
        enabled_sites: Optional[List[str]] = None, 
        max_pages_per_site: Optional[int] = None,
        incremental_filter_callback = None,
        lookback_hours: int = 24
    ) -> tuple:
        """
        Intelligent page-by-page scraping with incremental quota management
        
        Process:
        1. For each site, scrape page-by-page
        2. After each page, apply incremental filtering
        3. Check NEW jobs against remaining quota
        4. If quota allows, continue to next page
        5. If site finishes with quota remaining, pass to next site
        
        Args:
            daily_quota: Total LLM jobs allowed per day (e.g., 250)
            enabled_sites: List of site names to scrape
            max_pages_per_site: Hard limit on pages per site (None = unlimited)
            incremental_filter_callback: Function to filter new vs cached jobs
            lookback_hours: Hours to look back for incremental filtering
            
        Returns:
            tuple: (all_scraped_jobs, jobs_to_analyze, quota_used)
        """
        all_scraped_jobs = []
        all_jobs_to_analyze = []
        all_cached_jobs = []  # Track cached jobs separately
        sites_to_scrape = enabled_sites if enabled_sites else list(self.scrapers.keys())
        
        remaining_quota = daily_quota
        num_sites = len(sites_to_scrape)
        quota_per_site = daily_quota // num_sites if num_sites > 0 else daily_quota
        
        if self.verbose:
            print(f"\n🌐 Intelligent quota-based scraping")
            print(f"   Total daily quota: {daily_quota} LLM calls")
            print(f"   Initial quota per site: {quota_per_site} jobs")
            print(f"   Sites: {len(sites_to_scrape)}")
        
        for site_idx, site_name in enumerate(sites_to_scrape, 1):
            if site_name not in self.scrapers:
                self.logger.warning(f"Scraper not found: {site_name}")
                continue
            
            scraper = self.scrapers[site_name]
            
            # Calculate quota for this site (redistribute if previous sites didn't use all)
            sites_remaining = num_sites - site_idx + 1
            site_quota = remaining_quota // sites_remaining if sites_remaining > 0 else remaining_quota
            
            if self.verbose:
                print(f"\n📡 [{site_idx}/{num_sites}] {site_name.upper()}")
                print(f"   🎯 Allocated quota: {site_quota} NEW jobs")
                print(f"   💰 Remaining budget: {remaining_quota}/{daily_quota}")
            
            if remaining_quota <= 0:
                if self.verbose:
                    print(f"   🛑 No quota remaining, skipping")
                break
            
            try:
                site_scraped_jobs = []
                site_new_jobs = []
                site_cached_jobs = []  # Track cached jobs for this site
                page_num = 1
                
                while True:
                    # Check page limit
                    if max_pages_per_site and page_num > max_pages_per_site:
                        if self.verbose:
                            print(f"   🛑 Reached page limit ({max_pages_per_site})")
                        break
                    
                    # Check if we've hit site quota
                    if len(site_new_jobs) >= site_quota:
                        if self.verbose:
                            print(f"   ✅ Site quota reached: {len(site_new_jobs)}/{site_quota}")
                        break
                    
                    if self.verbose:
                        print(f"   📄 Page {page_num} (NEW so far: {len(site_new_jobs)}/{site_quota})")
                    
                    # Scrape one page
                    jobs, has_more = scraper.scrape_page(page_num)
                    
                    if not jobs:
                        if self.verbose:
                            print(f"      No jobs found")
                        break
                    
                    if self.verbose:
                        print(f"      Scraped: {len(jobs)} jobs")
                    
                    site_scraped_jobs.extend(jobs)
                    
                    # Apply incremental filtering to this page
                    if incremental_filter_callback:
                        page_new_jobs, page_cached_jobs = incremental_filter_callback(
                            jobs, 
                            lookback_hours
                        )
                        
                        if self.verbose:
                            print(f"      Filter: {len(page_new_jobs)} NEW, {len(page_cached_jobs)} cached")
                        
                        # Track cached jobs
                        site_cached_jobs.extend(page_cached_jobs)
                        
                        # Add NEW jobs (respecting site quota)
                        space_remaining = site_quota - len(site_new_jobs)
                        jobs_to_add = page_new_jobs[:space_remaining]
                        site_new_jobs.extend(jobs_to_add)
                        
                        if self.verbose and len(jobs_to_add) < len(page_new_jobs):
                            print(f"      ⚠️  Quota limit: taking {len(jobs_to_add)}/{len(page_new_jobs)} NEW jobs")
                    else:
                        # No incremental filtering, count all as new
                        space_remaining = site_quota - len(site_new_jobs)
                        jobs_to_add = jobs[:space_remaining]
                        site_new_jobs.extend(jobs_to_add)
                    
                    # Check if we hit quota
                    if len(site_new_jobs) >= site_quota:
                        if self.verbose:
                            print(f"   ✅ Site quota reached after page {page_num}")
                        break
                    
                    # Check if more pages available
                    if not has_more:
                        if self.verbose:
                            print(f"   🏁 No more pages available")
                        break
                    
                    page_num += 1
                
                # Update totals
                all_scraped_jobs.extend(site_scraped_jobs)
                all_jobs_to_analyze.extend(site_new_jobs)
                all_cached_jobs.extend(site_cached_jobs)  # Track cached jobs
                
                quota_used = len(site_new_jobs)
                remaining_quota -= quota_used
                
                if self.verbose:
                    print(f"   📊 Site summary:")
                    print(f"      Total scraped: {len(site_scraped_jobs)} jobs")
                    print(f"      NEW jobs: {len(site_new_jobs)} (quota used)")
                    print(f"      Quota remaining: {remaining_quota}/{daily_quota}")
                
            except Exception as e:
                self.logger.error(f"Error scraping {site_name}: {e}")
                if self.verbose:
                    print(f"   ❌ Error: {e}")
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"📊 Scraping complete!")
            print(f"   Total scraped: {len(all_scraped_jobs)} jobs")
            print(f"   NEW jobs to analyze: {len(all_jobs_to_analyze)}")
            print(f"   Cached jobs: {len(all_cached_jobs)}")
            print(f"   Quota used: {daily_quota - remaining_quota}/{daily_quota}")
            print(f"   Quota remaining: {remaining_quota}")
            print(f"{'='*60}")
        
        return all_scraped_jobs, all_jobs_to_analyze, all_cached_jobs, daily_quota - remaining_quota
    
    def scrape_with_quota(self, quota_per_site: int, enabled_sites: Optional[List[str]] = None, max_pages_per_site: Optional[int] = None) -> List[Dict]:
        """
        Scrape sites with intelligent quota management
        
        Scrapes pages dynamically until:
        - Quota reached for that site, OR
        - No more pages available, OR
        - max_pages_per_site limit reached (if set)
        
        Args:
            quota_per_site: Target number of jobs per site
            enabled_sites: List of site names to scrape (None = all)
            max_pages_per_site: Hard limit on pages (None = unlimited, stops at quota)
            
        Returns:
            Unified list of all jobs with 'source' field
        """
        all_jobs = []
        sites_to_scrape = enabled_sites if enabled_sites else list(self.scrapers.keys())
        
        if self.verbose:
            print(f"\n🌐 Scraping {len(sites_to_scrape)} sites with quota-based pagination...")
        
        for site_name in sites_to_scrape:
            if site_name not in self.scrapers:
                self.logger.warning(f"Scraper not found: {site_name}")
                continue
            
            scraper = self.scrapers[site_name]
            
            if self.verbose:
                print(f"\n📡 {site_name.upper()}")
                print(f"  🎯 Target quota: {quota_per_site} jobs")
            
            try:
                site_jobs = []
                page_num = 1
                
                while True:
                    # Check page limit
                    if max_pages_per_site and page_num > max_pages_per_site:
                        if self.verbose:
                            print(f"  🛑 Reached page limit ({max_pages_per_site})")
                        break
                    
                    # Check quota
                    if len(site_jobs) >= quota_per_site:
                        if self.verbose:
                            print(f"  ✅ Quota reached: {len(site_jobs)}/{quota_per_site} jobs")
                        break
                    
                    if self.verbose:
                        print(f"  📄 {site_name} - Page {page_num} ({len(site_jobs)}/{quota_per_site} jobs)")
                    
                    # Scrape page
                    jobs, has_more = scraper.scrape_page(page_num)
                    
                    if not has_more or not jobs:
                        if self.verbose:
                            print(f"  🏁 No more jobs available")
                        break
                    
                    site_jobs.extend(jobs)
                    
                    if self.verbose:
                        print(f"     Found {len(jobs)} jobs ({len(site_jobs)} total)")
                    
                    page_num += 1
                
                # Limit to quota
                if len(site_jobs) > quota_per_site:
                    if self.verbose:
                        print(f"  ✂️  Trimming {len(site_jobs)} jobs to quota {quota_per_site}")
                    site_jobs = site_jobs[:quota_per_site]
                
                all_jobs.extend(site_jobs)
                
                if self.verbose:
                    print(f"  ✅ Total: {len(site_jobs)} jobs from {site_name}")
                
            except Exception as e:
                self.logger.error(f"Error scraping {site_name}: {e}")
        
        if self.verbose:
            print(f"\n📊 Total jobs across all sites: {len(all_jobs)}")
            # Count per site
            site_counts = {}
            for job in all_jobs:
                site = job.get('source', 'unknown')
                site_counts[site] = site_counts.get(site, 0) + 1
            for site_name, count in site_counts.items():
                print(f"  - {site_name}: {count} jobs")
        
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
    multi_scraper.register_scraper(AlloVoisinsScraper(verbose=True))  # NEW!
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
