# -*- coding: utf-8 -*-
"""
Job Description Fetcher - Retrieves full job descriptions from job pages
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class JobDescriptionFetcher:
    """Fetches full job descriptions from individual job pages"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    
    def fetch_full_description(self, job_url):
        """
        Fetch full description from job page
        
        Args:
            job_url: URL of the job page
            
        Returns:
            str: Full description or empty string if failed
        """
        try:
            response = requests.get(job_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find description in job page
            description = ''
            
            # Method 1: Look for card-body (jemepropose.com structure)
            card_body = soup.find('div', class_='card-body')
            if card_body:
                # Get all paragraphs in card body
                paragraphs = card_body.find_all('p')
                if paragraphs:
                    description = ' '.join([p.get_text(strip=True) for p in paragraphs])
            
            # Method 2: Look for description div
            if not description:
                desc_div = soup.find('div', class_='card-text')
                if desc_div:
                    description = desc_div.get_text(strip=True)
            
            # Method 3: Look for main content area
            if not description:
                main_content = soup.find('main') or soup.find('article')
                if main_content:
                    paragraphs = main_content.find_all('p')
                    long_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50]
                    if long_paragraphs:
                        description = ' '.join(long_paragraphs)
            
            # Method 4: Look for any large text block
            if not description:
                paragraphs = soup.find_all('p')
                long_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 100]
                if long_paragraphs:
                    description = ' '.join(long_paragraphs[:3])  # Max 3 paragraphs
            
            return description
            
        except Exception as e:
            print(f"    ⚠️ Failed to fetch full description: {e}")
            return ''
    
    def is_description_short(self, description, min_length=50):
        """Check if description is too short and needs full fetch"""
        return len(description) < min_length


class BasicRemoteDetector:
    """Fast keyword-based remote detection for pre-filtering"""
    
    def __init__(self):
        # Strong remote indicators
        self.remote_keywords_high = [
            'télétravail', 'teletravail', 'remote', 'à distance',
            'travail à domicile', 'home office', 'full remote',
            'distanciel', '100% remote', 'télé-travail'
        ]
        
        # Possible remote indicators
        self.remote_keywords_medium = [
            'visio', 'vidéo', 'zoom', 'teams', 'skype',
            'en ligne', 'online', 'virtuel', 'internet'
        ]
        
        # Strong on-site indicators
        self.onsite_keywords_high = [
            'ménage', 'menage', 'nettoyage', 'repassage',
            'jardinage', 'bricolage', 'plomberie', 'électricité',
            'déménagement', 'demenagement', 'livraison',
            'garde d\'enfant', 'baby', 'babysitter', 'nounou',
            'cuisine', 'cuisinier', 'chef', 'restaur',
            'coiffure', 'massage', 'soins', 'esthétique',
            'construction', 'maçon', 'peinture', 'charpente',
            'mécanique', 'mecanique', 'réparation', 'reparation',
            'chauffeur', 'conducteur', 'transport', 'camion',
            'manuel', 'physique', 'sur place', 'à domicile',
            'présence', 'presence'
        ]
    
    def detect_confidence(self, job_title, job_description, job_location):
        """
        Fast keyword-based detection
        
        Returns:
            dict: {'is_remote': bool, 'confidence': str, 'reason': str}
                  confidence: 'HIGH', 'MEDIUM', 'LOW'
        """
        text = f"{job_title} {job_description} {job_location}".lower()
        
        # Check strong remote indicators
        for keyword in self.remote_keywords_high:
            if keyword in text:
                return {
                    'is_remote': True,
                    'confidence': 'HIGH',
                    'reason': f"Keyword: {keyword}"
                }
        
        # Check strong on-site indicators
        for keyword in self.onsite_keywords_high:
            if keyword in text:
                return {
                    'is_remote': False,
                    'confidence': 'HIGH',
                    'reason': f"On-site keyword: {keyword}"
                }
        
        # Check medium remote indicators
        for keyword in self.remote_keywords_medium:
            if keyword in text:
                return {
                    'is_remote': True,
                    'confidence': 'MEDIUM',
                    'reason': f"Possible remote: {keyword}"
                }
        
        # Uncertain - needs LLM analysis
        return {
            'is_remote': False,
            'confidence': 'LOW',
            'reason': 'Uncertain - needs LLM analysis'
        }
