"""
Semantic Job Analyzer
Uses LLM (Groq API) for accurate semantic analysis with NLP fallback
"""

import os
import json
from typing import Dict, Tuple

class SemanticJobAnalyzer:
    """
    Analyzes job descriptions using LLM or NLP to determine remote work possibility
    """
    
    def __init__(self, use_groq=True, groq_api_key=None, verbose=False):
        """
        Initialize the semantic analyzer
        
        Args:
            use_groq: Whether to use Groq API (True) or local NLP (False)
            groq_api_key: Groq API key (optional, can be set in environment)
            verbose: Show detailed progress messages (default False)
        """
        self.use_groq = use_groq
        self.groq_api_key = groq_api_key or os.getenv('GROQ_API_KEY')
        self.groq_client = None
        self.nlp_model = None
        self.verbose = verbose
        
        if self.use_groq and self.groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_api_key)
                if self.verbose:
                    print("✅ Groq API initialized successfully")
            except ImportError:
                if self.verbose:
                    print("⚠️  Groq library not installed. Run: pip install groq")
                    print("⚠️  Falling back to local NLP")
                self.use_groq = False
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Groq initialization failed: {e}")
                    print("⚠️  Falling back to local NLP")
                self.use_groq = False
        else:
            if self.verbose:
                print("ℹ️  Using local NLP (no Groq API key provided)")
            self.use_groq = False
        
        # Initialize local NLP as fallback
        if not self.use_groq:
            self._init_local_nlp()
    
    def _init_local_nlp(self):
        """Initialize local spaCy NLP model"""
        try:
            import spacy
            try:
                self.nlp_model = spacy.load("fr_core_news_md")
                if self.verbose:
                    print("✅ Local NLP (spaCy) initialized successfully")
            except OSError:
                if self.verbose:
                    print("⚠️  French model not found. Downloading...")
                    print("   Run: python -m spacy download fr_core_news_md")
                self.nlp_model = None
        except ImportError:
            if self.verbose:
                print("⚠️  spaCy not installed. Run: pip install spacy")
            self.nlp_model = None
    
    def analyze_with_groq(self, job_title: str, job_description: str, 
                          job_location: str, current_classification: str) -> Dict:
        """
        Analyze job using Groq LLM
        
        Args:
            job_title: Job title
            job_description: Job description
            job_location: Job location/category
            current_classification: Current classification (e.g., "ON-SITE LOW")
            
        Returns:
            dict with 'is_remote', 'confidence', 'reason'
        """
        if not self.groq_client:
            return self._analyze_with_nlp(job_title, job_description, job_location)
        
        try:
            prompt = f"""Analyze this French job listing and determine if it can be done remotely.

Job Title: {job_title}
Location/Category: {job_location}
Description: {job_description}

Current Classification: {current_classification}

Instructions:
1. Determine if this job CAN be done remotely (télétravail possible)
2. Consider ONLY the job description content - ignore location city name
3. Key factors:
   - Does it require physical presence? (cleaning, childcare, construction = NO)
   - Can it be done with computer/internet? (accounting, coaching, writing = YES)
   - Does it mention "sur place", "à domicile", "présentiel"? (= likely NO)
   - Does it mention "en ligne", "visio", "distance"? (= likely YES)

Response format (JSON ONLY):
{{
    "is_remote": true/false,
    "confidence": "high",
    "reason": "brief explanation in French (max 10 words)"
}}

Examples:
- "Assistance comptable" + computer work → {{"is_remote": true, "confidence": "high", "reason": "Travail comptable réalisable à distance avec ordinateur"}}
- "Coaching personnel" + no mention of "sur place" → {{"is_remote": true, "confidence": "high", "reason": "Coaching possible en visio/téléphone"}}
- "Coaching" + "intervenir auprès d'un public" → {{"is_remote": false, "confidence": "high", "reason": "Intervention en présentiel requise"}}
- "Ménage" → {{"is_remote": false, "confidence": "high", "reason": "Présence physique obligatoire"}}
- "Ingénieur du son pour tournage" → {{"is_remote": false, "confidence": "high", "reason": "Présence sur le plateau de tournage nécessaire"}}

Respond ONLY with valid JSON, no other text."""

            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert job analyst. Respond only with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",  # Updated: Latest stable Groq model
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=200,
            )
            
            response_text = chat_completion.choices[0].message.content.strip()
            
            # Try to extract JSON if there's extra text
            if '{' in response_text:
                start = response_text.index('{')
                end = response_text.rindex('}') + 1
                response_text = response_text[start:end]
            
            result = json.loads(response_text)
            
            return {
                'is_remote': result.get('is_remote', False),
                'confidence': result.get('confidence', 'medium'),
                'reason': f"LLM Analysis: {result.get('reason', 'No reason provided')}"
            }
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Groq API error: {e}")
                print("⚠️  Falling back to local NLP")
            return self._analyze_with_nlp(job_title, job_description, job_location)
    
    def _analyze_with_nlp(self, job_title: str, job_description: str, 
                          job_location: str) -> Dict:
        """
        Analyze job using local NLP (fallback method)
        
        Uses keyword frequency and context analysis
        """
        text = f"{job_title} {job_description} {job_location}".lower()
        
        # Enhanced keyword lists
        strong_remote_keywords = [
            'télétravail', 'remote', 'distance', 'en ligne', 'online',
            'visio', 'zoom', 'numérique', 'digital', 'internet',
            'email', 'virtuel', 'ordinateur', 'computer', 'web',
            'logiciel', 'software', 'données', 'data', 'rédaction',
            'traduction', 'graphisme', 'design', 'marketing'
        ]
        
        strong_onsite_keywords = [
            'sur place', 'physique', 'présentiel', 'déplacement',
            'maison', 'domicile', 'appartement', 'bureau',
            'nettoyer', 'réparer', 'construire', 'installer',
            'tournage', 'plateau', 'terrain', 'chantier'
        ]
        
        # Special remote-friendly job categories
        remote_job_types = [
            'comptable', 'comptabilité', 'assistance comptable',
            'secrétariat', 'télésecrétariat', 'saisie',
            'rédaction', 'traduction', 'graphisme',
            'développement', 'programmation', 'web'
        ]
        
        # Count keyword occurrences
        remote_score = sum(2 for kw in strong_remote_keywords if kw in text)
        onsite_score = sum(2 for kw in strong_onsite_keywords if kw in text)
        
        # Check for remote job types
        for job_type in remote_job_types:
            if job_type in text:
                remote_score += 3
        
        # Analyze with spaCy if available
        if self.nlp_model:
            doc = self.nlp_model(text[:1000])  # Limit to 1000 chars for speed
            
            # Look for action verbs that indicate physical work
            physical_verbs = ['nettoyer', 'garder', 'réparer', 'construire', 
                            'installer', 'déménager', 'cuisiner', 'conduire']
            
            for token in doc:
                if token.lemma_ in physical_verbs:
                    onsite_score += 2
        
        if self.verbose:
            print(f"    📊 NLP Scores - Remote: {remote_score}, On-site: {onsite_score}")
        
        # Decision logic with lower threshold
        if remote_score > onsite_score + 1:
            return {
                'is_remote': True,
                'confidence': 'high',
                'reason': f'NLP Analysis: Strong remote indicators (score: {remote_score} vs {onsite_score})'
            }
        elif remote_score > onsite_score:
            return {
                'is_remote': True,
                'confidence': 'medium',
                'reason': f'NLP Analysis: Likely remote work (score: {remote_score} vs {onsite_score})'
            }
        elif onsite_score > remote_score + 1:
            return {
                'is_remote': False,
                'confidence': 'high',
                'reason': f'NLP Analysis: Strong on-site indicators (score: {onsite_score} vs {remote_score})'
            }
        elif onsite_score > remote_score:
            return {
                'is_remote': False,
                'confidence': 'medium',
                'reason': f'NLP Analysis: Likely on-site work (score: {onsite_score} vs {remote_score})'
            }
        else:
            # Equal scores - default based on job category context
            return {
                'is_remote': False,
                'confidence': 'low',
                'reason': f'NLP Analysis: Ambiguous signals (remote: {remote_score}, onsite: {onsite_score})'
            }
    
    def reanalyze_low_confidence(self, job_data: Dict, current_result: Dict) -> Dict:
        """
        Re-analyze jobs with LOW or MEDIUM confidence using semantic analysis
        
        Args:
            job_data: Dict with 'title', 'description', 'location'
            current_result: Current classification result with 'confidence'
            
        Returns:
            Updated classification result
        """
        # Re-analyze if confidence is LOW or MEDIUM (includes REMOTE cases)
        confidence = current_result.get('confidence', '').lower()
        if confidence not in ['low', 'medium']:
            return current_result
        
        if self.verbose:
            print(f"  🔍 Re-analyzing with semantic model: {job_data.get('title', 'N/A')[:50]}...")
        
        if self.use_groq:
            classification = f"{'REMOTE' if current_result.get('is_remote') else 'ON-SITE'} LOW"
            result = self.analyze_with_groq(
                job_data.get('title', ''),
                job_data.get('description', ''),
                job_data.get('location', ''),
                classification
            )
        else:
            result = self._analyze_with_nlp(
                job_data.get('title', ''),
                job_data.get('description', ''),
                job_data.get('location', '')
            )
        
        return result


# Example usage and testing
if __name__ == "__main__":
    # Test both modes
    print("\n" + "="*80)
    print("SEMANTIC ANALYZER TEST")
    print("="*80)
    
    # Test without API key (local NLP)
    print("\n1. Testing LOCAL NLP mode:")
    analyzer_nlp = SemanticJobAnalyzer(use_groq=True)
    
    test_job = {
        'title': 'Assistance comptable',
        'description': 'Recherche personne pour aide à la comptabilité',
        'location': 'Comptabilité - Paris'
    }
    
    result = analyzer_nlp._analyze_with_nlp(
        test_job['title'],
        test_job['description'],
        test_job['location']
    )
    print(f"\nResult: {result}")
    
    # Test with Groq (if API key available)
    print("\n2. Testing GROQ API mode:")
    print("   Set GROQ_API_KEY environment variable to test")
    print("   Get free API key at: https://console.groq.com/")
