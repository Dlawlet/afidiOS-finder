"""
Semantic Job Analyzer - Version 2
Enhanced caching with single JSON database instead of multiple files
"""

import os
import json
import time
import hashlib
import logging
from typing import Dict, Optional
from pathlib import Path
from functools import wraps
from datetime import datetime
from threading import Lock


def retry_with_backoff(max_retries=3, base_delay=2):
    """Decorator to retry function calls with exponential backoff"""
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


class CacheDatabase:
    """
    Single JSON file cache database with better organization
    
    Advantages over multiple files:
    - Single file to backup/transfer
    - Easy to view all cached jobs
    - Atomic writes with lock
    - Built-in expiration
    - Statistics in same file
    """
    
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.lock = Lock()  # Thread-safe operations
        self._cache = None
        self._load_cache()
    
    def _load_cache(self):
        """Load cache database from disk"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Cache file corrupted, creating new: {e}")
                self._cache = self._new_cache()
        else:
            self._cache = self._new_cache()
    
    def _new_cache(self) -> Dict:
        """Create new cache structure"""
        return {
            'version': '2.0',
            'created': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'statistics': {
                'total_entries': 0,
                'hits': 0,
                'misses': 0
            },
            'entries': {}  # job_hash -> {result, timestamp, access_count}
        }
    
    def _save_cache(self):
        """Save cache database to disk"""
        with self.lock:
            self._cache['last_updated'] = datetime.now().isoformat()
            
            # Create temp file first (atomic write)
            temp_file = self.cache_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            
            # Atomic rename
            temp_file.replace(self.cache_file)
    
    def get(self, job_hash: str, max_age_days: int = 30) -> Optional[Dict]:
        """
        Get cached result if exists and not expired
        
        Args:
            job_hash: MD5 hash of job content
            max_age_days: Maximum cache age in days (default 30)
        
        Returns:
            Cached result or None
        """
        with self.lock:
            entry = self._cache['entries'].get(job_hash)
            
            if entry is None:
                self._cache['statistics']['misses'] += 1
                return None
            
            # Check expiration
            cached_time = datetime.fromisoformat(entry['timestamp'])
            age_days = (datetime.now() - cached_time).days
            
            if age_days > max_age_days:
                # Expired - remove it
                del self._cache['entries'][job_hash]
                self._cache['statistics']['total_entries'] -= 1
                self._cache['statistics']['misses'] += 1
                self._save_cache()
                return None
            
            # Valid cache hit
            entry['access_count'] += 1
            entry['last_accessed'] = datetime.now().isoformat()
            self._cache['statistics']['hits'] += 1
            
            return entry['result']
    
    def set(self, job_hash: str, result: Dict):
        """
        Store result in cache
        
        Args:
            job_hash: MD5 hash of job content
            result: Analysis result to cache
        """
        with self.lock:
            is_new = job_hash not in self._cache['entries']
            
            self._cache['entries'][job_hash] = {
                'result': result,
                'timestamp': datetime.now().isoformat(),
                'last_accessed': datetime.now().isoformat(),
                'access_count': 1
            }
            
            if is_new:
                self._cache['statistics']['total_entries'] += 1
            
            # Save every 10 new entries or every 50 accesses
            should_save = (
                self._cache['statistics']['total_entries'] % 10 == 0 or
                (self._cache['statistics']['hits'] + self._cache['statistics']['misses']) % 50 == 0
            )
            
            if should_save:
                self._save_cache()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        with self.lock:
            stats = self._cache['statistics'].copy()
            total = stats['hits'] + stats['misses']
            stats['hit_rate_percentage'] = (stats['hits'] / total * 100) if total > 0 else 0
            return stats
    
    def cleanup_old_entries(self, max_age_days: int = 30):
        """Remove entries older than max_age_days"""
        with self.lock:
            now = datetime.now()
            to_remove = []
            
            for job_hash, entry in self._cache['entries'].items():
                cached_time = datetime.fromisoformat(entry['timestamp'])
                age_days = (now - cached_time).days
                
                if age_days > max_age_days:
                    to_remove.append(job_hash)
            
            for job_hash in to_remove:
                del self._cache['entries'][job_hash]
                self._cache['statistics']['total_entries'] -= 1
            
            if to_remove:
                self._save_cache()
                logging.info(f"Cleaned up {len(to_remove)} expired cache entries")
            
            return len(to_remove)
    
    def save(self):
        """Explicitly save cache to disk"""
        self._save_cache()


class SemanticJobAnalyzer:
    """
    Analyzes job descriptions using LLM or NLP to determine remote work possibility
    Enhanced with single-file database caching
    """
    
    def __init__(self, use_groq=True, groq_api_key=None, verbose=False):
        """Initialize the semantic analyzer"""
        self.use_groq = use_groq
        self.groq_api_key = groq_api_key or os.getenv('GROQ_API_KEY')
        self.groq_client = None
        self.nlp_model = None
        self.verbose = verbose
        
        # Initialize cache database (single file)
        self.cache_dir = Path('cache')
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_db = CacheDatabase(self.cache_dir / 'cache_database.json')
        
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
                self.logger.warning("Groq library not installed, falling back to NLP")
                self.use_groq = False
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Groq initialization failed: {e}")
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
                    print("⚠️  French model not found.")
                self.logger.warning("French spaCy model not found")
                self.nlp_model = None
        except ImportError:
            if self.verbose:
                print("⚠️  spaCy not installed.")
            self.logger.warning("spaCy not installed")
            self.nlp_model = None
    
    def _get_job_hash(self, title: str, description: str, location: str) -> str:
        """Generate unique hash for job content"""
        content = f"{title}|{description}|{location}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def get_cache_stats(self) -> Dict:
        """Get cache hit/miss statistics"""
        return self.cache_db.get_stats()
    
    def cleanup_cache(self, max_age_days: int = 30) -> int:
        """Remove cache entries older than max_age_days"""
        return self.cache_db.cleanup_old_entries(max_age_days)
    
    @retry_with_backoff(max_retries=3, base_delay=2)
    def _analyze_with_groq_impl(self, job_title: str, job_description: str, 
                                 job_location: str, current_classification: str) -> Dict:
        """Internal implementation of Groq analysis (wrapped with retry logic)"""
        prompt = f"""You are analyzing a French job listing to determine if it's a genuine remote work opportunity.

JOB LISTING:
Title: {job_title}
Location/Category: {job_location}
Description: {job_description}

YOUR TASK:
Determine if this is a GENUINE remote work opportunity where the worker can perform 100% of their duties from home/anywhere without needing to be physically present.

RESPOND IN JSON FORMAT ONLY:
{{
    "is_remote": true/false,
    "confidence": 0.0-1.0,
    "reason": "clear explanation in French (max 12 words)"
}}"""

        chat_completion = self.groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an expert job analyst. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model="moonshotai/kimi-k2-instruct",
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
            current_classification: Current classification
            
        Returns:
            dict with 'is_remote', 'remote_confidence', 'reason'
        """
        # Check cache first
        job_hash = self._get_job_hash(job_title, job_description, job_location)
        cached_result = self.cache_db.get(job_hash)
        
        if cached_result is not None:
            if self.verbose:
                print("    ♻️  Using cached analysis")
            return cached_result
        
        # Not in cache, proceed with analysis
        if not self.groq_client:
            return self._analyze_with_nlp(job_title, job_description, job_location)
        
        try:
            result = self._analyze_with_groq_impl(job_title, job_description, 
                                                   job_location, current_classification)
            
            # Cache the result
            self.cache_db.set(job_hash, result)
            self.logger.info(f"Analyzed job: {job_title[:50]}... -> Remote: {result['is_remote']}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Groq API error: {e}", exc_info=True)
            return self._analyze_with_nlp(job_title, job_description, job_location)
    
    def _analyze_with_nlp(self, job_title: str, job_description: str, 
                          job_location: str) -> Dict:
        """Analyze job using local NLP (fallback method)"""
        text = f"{job_title} {job_description} {job_location}".lower()
        
        strong_remote_keywords = [
            'télétravail', 'remote', 'distance', 'en ligne', 'online',
            'visio', 'zoom', 'numérique', 'digital'
        ]
        
        strong_onsite_keywords = [
            'sur place', 'physique', 'présentiel', 'déplacement'
        ]
        
        remote_score = sum(2 for kw in strong_remote_keywords if kw in text)
        onsite_score = sum(2 for kw in strong_onsite_keywords if kw in text)
        
        if remote_score > onsite_score + 1:
            return {
                'is_remote': True,
                'remote_confidence': 0.8,
                'reason': f'NLP Analysis: Strong remote indicators (score: {remote_score} vs {onsite_score})'
            }
        else:
            return {
                'is_remote': False,
                'remote_confidence': 0.3,
                'reason': f'NLP Analysis: On-site indicators (score: {onsite_score} vs {remote_score})'
            }
    
    def __del__(self):
        """Save cache on cleanup"""
        if hasattr(self, 'cache_db'):
            self.cache_db.save()


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SEMANTIC ANALYZER V2 TEST - Single Database File")
    print("="*80)
    
    analyzer = SemanticJobAnalyzer(use_groq=False, verbose=True)
    
    # Test caching
    test_job = {
        'title': 'Développeur web',
        'description': 'Création site WordPress, travail en télétravail',
        'location': 'A Distance'
    }
    
    print("\n1. First analysis (cache miss expected):")
    result1 = analyzer.analyze_with_groq(
        test_job['title'],
        test_job['description'],
        test_job['location'],
        ''
    )
    print(f"Result: {result1}")
    
    print("\n2. Second analysis (cache hit expected):")
    result2 = analyzer.analyze_with_groq(
        test_job['title'],
        test_job['description'],
        test_job['location'],
        ''
    )
    print(f"Result: {result2}")
    
    print("\n3. Cache statistics:")
    stats = analyzer.get_cache_stats()
    print(f"Stats: {stats}")
    
    print("\n4. Cache database location:")
    print(f"File: cache/cache_database.json")
    print(f"Entries: {stats['total_entries']}")
