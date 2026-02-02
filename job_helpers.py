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
            
            # SPECIAL CASE: AlloVoisins - avoid collecting multiple listings
            if 'allovoisins.com' in job_url:
                # AlloVoisins shows "demandes similaires" (similar requests)
                # We need ONLY the main request, not the similar ones
                # IMPORTANT: If we can't extract cleanly, return empty string
                # to use the listing page description (which is already clean)
                
                # Try to find the main description
                article = soup.find('article')
                if article:
                    # Find all paragraphs
                    all_paragraphs = article.find_all('p')
                    
                    # Strategy: Look for paragraphs that are:
                    # 1. Not very short (>50 chars)
                    # 2. Not starting with a quote (likely from "demandes similaires")
                    # 3. Not part of "demandes similaires" section
                    
                    valid_paragraphs = []
                    for p in all_paragraphs:
                        text = p.get_text(strip=True)
                        # Skip if too short, a quote, or contains "demandes similaires"
                        if (len(text) > 50 and 
                            not text.startswith('"') and 
                            'demandes similaires' not in text.lower()):
                            valid_paragraphs.append(text)
                    
                    # Take ONLY the first valid paragraph if found
                    if valid_paragraphs:
                        return valid_paragraphs[0]
                
                # If no clean description found, return empty to use listing description
                return ''
            
            # Method 1: Look for card-body (jemepropose.com structure)
            card_body = soup.find('div', class_='card-body')
            if card_body:
                # Get all paragraphs in card body, preserving line breaks
                paragraphs = card_body.find_all('p')
                if paragraphs:
                    # Use separator to preserve sentence structure, filter empty paragraphs
                    texts = [p.get_text(separator=' ', strip=True) for p in paragraphs]
                    # DEDUPLICATE: Remove consecutive duplicates
                    unique_texts = []
                    for text in texts:
                        if text and (not unique_texts or text != unique_texts[-1]):
                            unique_texts.append(text)
                    description = ' '.join(unique_texts)
            
            # Method 1b: Look for article (alternative jemepropose structure)
            if not description:
                article = soup.find('article')
                if article:
                    paragraphs = article.find_all('p')
                    if paragraphs:
                        # DEDUPLICATE: Remove ALL duplicates (not just consecutive)
                        seen = set()
                        unique_texts = []
                        for p in paragraphs:
                            text = p.get_text(separator=' ', strip=True)
                            # Normalize: remove extra whitespace
                            normalized = ' '.join(text.split())
                            if normalized and normalized not in seen and len(normalized) > 30:
                                seen.add(normalized)
                                unique_texts.append(normalized)
                        
                        if unique_texts:
                            # Filter out generic messages like "Soyez le premier à déposer un avis"
                            filtered = [t for t in unique_texts if not any(phrase in t.lower() for phrase in [
                                'soyez le premier', 'déposer un avis', 'sign in', 'log in'
                            ])]
                            description = ' '.join(filtered) if filtered else ' '.join(unique_texts)
            
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
