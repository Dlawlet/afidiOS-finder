"""
Semantic Job Analyzer - Enhanced Version
Uses LLM (Groq API) for accurate semantic analysis with NLP fallback
Includes: Retry logic, caching, and structured logging
"""

import os
import json
import time
import hashlib
import logging
from typing import Dict, Tuple
from pathlib import Path
from functools import wraps
from datetime import datetime

from groq_model_manager import GroqModelManager


def setup_logging(verbose=False):
    """Configure structured logging with rotation"""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def retry_with_backoff(max_retries=3, base_delay=2):
    """
    Decorator to retry function calls with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds (doubles each retry)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    is_rate_limit = any(keyword in error_str for keyword in 
                                       ['rate_limit', '429', 'too many requests'])
                    
                    if is_rate_limit and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"⏳ Rate limit hit, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        raise
            return None
        return wrapper
    return decorator


class SemanticJobAnalyzer:
    """
    Analyzes job descriptions using LLM or NLP to determine remote work possibility
    Enhanced with caching and retry logic
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
        self.model_manager = GroqModelManager()
        self.nlp_fallbacks = 0
        self.llm_calls = 0
        
        # Initialize cache directory
        self.cache_dir = Path('cache')
        self.cache_dir.mkdir(exist_ok=True)
        
        # Cache statistics
        self.cache_stats = {'hits': 0, 'misses': 0}
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        if self.use_groq and self.groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_api_key)
                if self.verbose:
                    print("✅ Groq API initialized successfully")
                self.logger.info("Groq API initialized successfully")
            except ImportError:
                if self.verbose:
                    print("⚠️  Groq library not installed. Run: pip install groq")
                    print("⚠️  Falling back to local NLP")
                self.logger.warning("Groq library not installed, falling back to NLP")
                self.use_groq = False
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Groq initialization failed: {e}")
                    print("⚠️  Falling back to local NLP")
                self.logger.error(f"Groq initialization failed: {e}", exc_info=True)
                self.use_groq = False
        else:
            if self.verbose:
                print("ℹ️  Using local NLP (no Groq API key provided)")
            self.logger.info("Using local NLP (no Groq API key provided)")
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
                self.logger.info("Local NLP (spaCy) initialized successfully")
            except OSError:
                if self.verbose:
                    print("⚠️  French model not found. Downloading...")
                    print("   Run: python -m spacy download fr_core_news_md")
                self.logger.warning("French spaCy model not found")
                self.nlp_model = None
        except ImportError:
            if self.verbose:
                print("⚠️  spaCy not installed. Run: pip install spacy")
            self.logger.warning("spaCy not installed")
            self.nlp_model = None
    
    def _get_job_hash(self, title: str, description: str, location: str, model_name: str) -> str:
        """
        Generate unique hash for job content to detect duplicates
        
        Args:
            title: Job title
            description: Job description
            location: Job location
            
        Returns:
            MD5 hash string
        """
        content = f"{model_name}|{title}|{description}|{location}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _load_from_cache(self, job_hash: str) -> Dict:
        """Load analysis result from cache if available"""
        cache_file = self.cache_dir / f"{job_hash}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    self.cache_stats['hits'] += 1
                    if self.verbose:
                        print("    ♻️  Using cached analysis")
                    self.logger.debug(f"Cache hit for job hash: {job_hash}")
                    return cached_data
            except (json.JSONDecodeError, IOError) as e:
                if self.verbose:
                    print(f"    ⚠️  Cache read error: {e}")
                self.logger.warning(f"Cache read error for {job_hash}: {e}")
        
        self.cache_stats['misses'] += 1
        return None
    
    def _save_to_cache(self, job_hash: str, result: Dict):
        """Save analysis result to cache"""
        cache_file = self.cache_dir / f"{job_hash}.json"
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"Cached result for job hash: {job_hash}")
        except IOError as e:
            if self.verbose:
                print(f"    ⚠️  Cache write error: {e}")
            self.logger.warning(f"Cache write error for {job_hash}: {e}")
    
    def get_cache_stats(self) -> Dict:
        """Get cache hit/miss statistics"""
        total = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            'cache_hits': self.cache_stats['hits'],
            'cache_misses': self.cache_stats['misses'],
            'total_requests': total,
            'hit_rate_percentage': round(hit_rate, 2),
            'nlp_fallbacks': self.nlp_fallbacks,
            'llm_calls': self.llm_calls,
            'model_usage': self.model_manager.stats()
        }
    
    @retry_with_backoff(max_retries=3, base_delay=2)
    def _analyze_with_groq_impl(self, job_title: str, job_description: str, 
                                 job_location: str, current_classification: str,
                                 model_name: str) -> Dict:
        """
        Internal implementation of Groq analysis (wrapped with retry logic)
        """
        prompt = f"""You are analyzing a French job listing to determine if it's a genuine remote work opportunity.

JOB LISTING:
Title: {job_title}
Location/Category: {job_location}
Description: {job_description}

YOUR TASK:
Determine if this is a GENUINE remote work opportunity where the worker can perform 100% of their duties from home/anywhere without needing to be physically present.

THINK LIKE A HUMAN:
- Is this even a job offer, or is someone looking for work themselves?
- Does the actual work require physical presence (visiting clients, handling physical objects, in-person meetings)?
- Can ALL the work be done (or the final result be shared) through a computer and internet connection?
- Are there explicit mentions of remote/télétravail, or clear indicators the work is 100% online?
- What is the INTENT behind the words, not just the keywords?

BE CONSERVATIVE:
- If it's ambiguous or unclear → classify as NOT remote
- If it requires ANY physical presence → NOT remote

CONTEXT MATTERS:
- "Je cherche une personne" (I'm hiring) ≠ "Je cherche un emploi" (I'm job hunting)
- "Accompagner en visio" (remote coaching) ≠ "Accompagner sur place" (in-person)
- "Commercial digital en ligne" (remote sales) ≠ "Commercial terrain" (field sales)
- "A Distance" in location doesn't guarantee remote - read the actual description

RESPOND IN JSON FORMAT ONLY:
{{
    "is_remote": true/false,
    "confidence": 0.0-1.0,
    "reason": "clear explanation in French (max 12 words)"
}}"""

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
            model=model_name,
            temperature=0.1,
            max_tokens=200,
        )
        
        response_text = chat_completion.choices[0].message.content.strip()
        
        # Try to extract JSON if there's extra text
        if '{' in response_text:
            start = response_text.index('{')
            end = response_text.rindex('}') + 1
            response_text = response_text[start:end]
        
        result = json.loads(response_text)
        
        # Extract and validate confidence score
        confidence = result.get('confidence', 0.5)
        if isinstance(confidence, str):
            # Convert old string format to float
            confidence_map = {'high': 0.9, 'medium': 0.6, 'low': 0.3}
            confidence = confidence_map.get(confidence.lower(), 0.5)
        
        return {
            'is_remote': result.get('is_remote', False),
            'remote_confidence': float(confidence),
            'reason': f"LLM: {result.get('reason', 'No reason provided')}"
        }
    
    def analyze_with_groq(self, job_title: str, job_description: str, 
                          job_location: str, current_classification: str) -> Dict:
        """
        Analyze job using Groq LLM with caching
        
        Args:
            job_title: Job title
            job_description: Job description
            job_location: Job location/category
            current_classification: Current classification (e.g., "ON-SITE LOW")
            
        Returns:
            dict with 'is_remote', 'confidence', 'reason'
        """
        model_name = self.model_manager.pick_model() if self.model_manager else None
        model_name = model_name or os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

        # Not in cache, proceed with analysis
        if not self.groq_client:
            self.nlp_fallbacks += 1
            return self._analyze_with_nlp(job_title, job_description, job_location)

        attempted_models = set()
        while model_name and model_name not in attempted_models:
            attempted_models.add(model_name)
            job_hash = self._get_job_hash(job_title, job_description, job_location, model_name)
            cached_result = self._load_from_cache(job_hash)

            if cached_result is not None:
                return cached_result
            try:
                result = self._analyze_with_groq_impl(
                    job_title, job_description, job_location, current_classification, model_name
                )
                result['model'] = model_name
                self.model_manager.record_call(model_name)
                self.llm_calls += 1

                # Cache the result
                self._save_to_cache(job_hash, result)
                self.logger.info(
                    f"Analyzed job: {job_title[:50]}... -> Remote: {result['is_remote']}, "
                    f"Confidence: {result['remote_confidence']} (model {model_name})"
                )
                return result

            except Exception as e:
                error_msg = str(e).lower()
                if 'not found' in error_msg or 'does not exist' in error_msg:
                    self.model_manager.disable_model(model_name)
                elif 'rate_limit' in error_msg or '429' in error_msg:
                    self.model_manager.disable_model(model_name)

                if self.verbose:
                    print(f"⚠️  Groq API error with {model_name}: {e}")
                    print("⚠️  Trying next model if available")
                self.logger.error(f"Groq API error for model {model_name}: {e}", exc_info=True)
                model_name = self.model_manager.pick_model()

        self.nlp_fallbacks += 1
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
        
        self.logger.debug(f"NLP Analysis - Remote score: {remote_score}, On-site score: {onsite_score}")
        
        # Decision logic with lower threshold
        if remote_score > onsite_score + 1:
            return {
                'is_remote': True,
                'remote_confidence': 0.8,
                'reason': f'NLP Analysis: Strong remote indicators (score: {remote_score} vs {onsite_score})'
            }
        elif remote_score > onsite_score:
            return {
                'is_remote': True,
                'remote_confidence': 0.6,
                'reason': f'NLP Analysis: Likely remote work (score: {remote_score} vs {onsite_score})'
            }
        elif onsite_score > remote_score + 1:
            return {
                'is_remote': False,
                'remote_confidence': 0.2,
                'reason': f'NLP Analysis: Strong on-site indicators (score: {onsite_score} vs {remote_score})'
            }
        elif onsite_score > remote_score:
            return {
                'is_remote': False,
                'remote_confidence': 0.4,
                'reason': f'NLP Analysis: Likely on-site work (score: {onsite_score} vs {remote_score})'
            }
        else:
            # Equal scores - default based on job category context
            return {
                'is_remote': False,
                'remote_confidence': 0.3,
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
    print("SEMANTIC ANALYZER TEST - ENHANCED VERSION")
    print("="*80)
    
    # Setup logging
    setup_logging(verbose=True)
    
    # Test without API key (local NLP)
    print("\n1. Testing LOCAL NLP mode:")
    analyzer_nlp = SemanticJobAnalyzer(use_groq=False, verbose=True)
    
    test_job = {
        'title': 'Assistance comptable',
        'description': 'Recherche personne pour aide à la comptabilité en télétravail',
        'location': 'Comptabilité - A Distance'
    }
    
    result = analyzer_nlp._analyze_with_nlp(
        test_job['title'],
        test_job['description'],
        test_job['location']
    )
    print(f"\nResult: {result}")
    
    # Test caching
    print("\n2. Testing CACHE functionality:")
    analyzer_cached = SemanticJobAnalyzer(use_groq=False, verbose=True)
    
    # First call - should miss cache
    result1 = analyzer_cached._analyze_with_nlp(
        test_job['title'],
        test_job['description'],
        test_job['location']
    )
    
    # Save to cache manually for testing
    job_hash = analyzer_cached._get_job_hash(
        test_job['title'],
        test_job['description'],
        test_job['location'],
        'local-nlp'
    )
    analyzer_cached._save_to_cache(job_hash, result1)
    
    # Second call - should hit cache
    result2 = analyzer_cached._load_from_cache(job_hash)
    print(f"\nCached result: {result2}")
    print(f"\nCache stats: {analyzer_cached.get_cache_stats()}")
    
    # Test with Groq (if API key available)
    print("\n3. Testing GROQ API mode:")
    print("   Set GROQ_API_KEY environment variable to test")
    print("   Get free API key at: https://console.groq.com/")
