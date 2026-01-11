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
                # Get all paragraphs in card body, preserving line breaks
                paragraphs = card_body.find_all('p')
                if paragraphs:
                    # Use separator to preserve sentence structure, filter empty paragraphs
                    texts = [p.get_text(separator=' ', strip=True) for p in paragraphs]
                    description = ' '.join([t for t in texts if t])
            
            # Method 2: Look for description div
            if not description:
                desc_div = soup.find('div', class_='card-text')
                if desc_div:
                    # Get all text including nested elements
                    description = desc_div.get_text(separator=' ', strip=True)
            
            # Method 3: Look for main content area
            if not description:
                main_content = soup.find('main') or soup.find('article')
                if main_content:
                    paragraphs = main_content.find_all('p')
                    long_paragraphs = [p.get_text(separator=' ', strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 10]
                    if long_paragraphs:
                        description = ' '.join(long_paragraphs)
            
            # Method 4: Look for any large text block
            if not description:
                paragraphs = soup.find_all('p')
                long_paragraphs = [p.get_text(separator=' ', strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 100]
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
    """
    Fast keyword-based detector for pre-filtering BEFORE LLM analysis.
    
    PHILOSOPHY:
    - ONLY discard jobs that are OBVIOUSLY on-site (high confidence)
    - Let LLM handle everything else (it understands context better)
    - Do NOT try to detect remote jobs here - that's the LLM's job
    """
    
    def __init__(self):
        # ONLY track OBVIOUS on-site jobs that require physical presence
        # Everything else goes to LLM for intelligent context-aware analysis
        self.obvious_onsite_keywords = [
            # Physical/manual work - 100% requires presence
            'ménage', 'menage', 'nettoyage', 'repassage',
            'jardinage', 'bricolage', 'plomberie', 'électricité',
            'déménagement', 'demenagement', 'livraison',
            'construction', 'maçon', 'peinture', 'charpente',
            'mécanique', 'mecanique', 'réparation auto', 'reparation auto',
            
            # Childcare/personal care - 100% requires presence
            'garde d\'enfant', 'baby', 'babysitter', 'nounou',
            'baby-sitting', 'garde bébé', 'assistante maternelle',
            
            # Food/hospitality - 100% requires presence
            'cuisine', 'cuisinier', 'chef', 'restaur', 'serveur',
            'barman', 'plonge', 'commis de cuisine',
            
            # Personal services - 100% requires presence
            'coiffure', 'coiffeur', 'massage', 'masseur',
            'soins', 'esthétique', 'manucure', 'pédicure',
            
            # Transportation - 100% requires presence
            'chauffeur', 'conducteur', 'livreur', 'taxi',
            'uber', 'vtc', 'camion', 'transport de personnes',
            
            # Household help - 100% requires presence
            'aide ménagère', 'femme de ménage', 'homme de ménage',
            'repasseuse', 'garde malade', 'aide à domicile'
        ]
    
    def detect_confidence(self, job_title, job_description, job_location):
        """
        Pre-filter to catch OBVIOUS on-site jobs only.
        Everything else goes to LLM for intelligent analysis.
        
        Returns:
            dict: {'is_remote': bool, 'confidence': str, 'reason': str}
                  confidence: 'HIGH' = obvious on-site, skip LLM
                             'LOW' = uncertain, send to LLM
        """
        text = f"{job_title} {job_description} {job_location}".lower()
        
        # Check for OBVIOUS on-site work (physical presence required)
        for keyword in self.obvious_onsite_keywords:
            if keyword in text:
                return {
                    'is_remote': False,
                    'confidence': 'HIGH',
                    'reason': f"Obvious on-site work: {keyword}"
                }
        
        # Everything else: uncertain, let LLM decide with context
        return {
            'is_remote': False,  # Default, but will be analyzed by LLM
            'confidence': 'LOW',
            'reason': 'Uncertain - needs LLM context analysis'
        }
