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

        # Model name: configurable via GROQ_MODEL env variable
        self.groq_model = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

        # Initialize cache directory
        self.cache_dir = Path('cache')
        self.cache_dir.mkdir(exist_ok=True)

        # Cache statistics
        self.cache_stats = {'hits': 0, 'misses': 0, 'nlp_fallbacks': 0}

        # Setup logging
        self.logger = logging.getLogger(__name__)

        if self.use_groq and self.groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_api_key)
                # Validate model availability with a lightweight check
                self._validate_model()
                if self.use_groq and self.verbose:
                    print(f"✅ Groq API initialized (model: {self.groq_model})")
                if self.use_groq:
                    self.logger.info(f"Groq API initialized (model: {self.groq_model})")
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

    def _validate_model(self):
        """Verify the configured Groq model is accessible before processing jobs."""
        try:
            self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": "ok"}],
                model=self.groq_model,
                max_tokens=1,
            )
        except Exception as e:
            error_str = str(e)
            # 404 = model not found; surface a clear message and disable Groq
            if '404' in error_str or 'model_not_found' in error_str or 'does not exist' in error_str:
                self.logger.error(
                    f"[FATAL] Groq model '{self.groq_model}' is unavailable: {e}. "
                    "Set the GROQ_MODEL environment variable to a valid model name "
                    "(e.g. llama-3.3-70b-versatile). Falling back to local NLP."
                )
                print(
                    f"[FATAL] Groq model '{self.groq_model}' not found. "
                    "Set GROQ_MODEL env var to a valid Groq model. Falling back to NLP."
                )
                self.groq_client = None
                self.use_groq = False
                self._init_local_nlp()
            # Rate limit on the validation call is fine — model exists
    
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
    
    def _get_job_hash(self, title: str, description: str, location: str) -> str:
        """
        Generate unique hash for job content to detect duplicates
        
        Args:
            title: Job title
            description: Job description
            location: Job location
            
        Returns:
            MD5 hash string
        """
        content = f"{title}|{description}|{location}"
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
        nlp_fallbacks = self.cache_stats.get('nlp_fallbacks', 0)
        llm_calls = self.cache_stats['misses'] - nlp_fallbacks
        fallback_rate = (nlp_fallbacks / max(llm_calls + nlp_fallbacks, 1)) * 100

        return {
            'cache_hits': self.cache_stats['hits'],
            'cache_misses': self.cache_stats['misses'],
            'total_requests': total,
            'hit_rate_percentage': round(hit_rate, 2),
            'nlp_fallbacks': nlp_fallbacks,
            'llm_calls': max(llm_calls, 0),
            'nlp_fallback_rate_percentage': round(fallback_rate, 2),
            'model': self.groq_model if self.use_groq else 'local-nlp',
        }

    def cleanup_old_cache(self, days: int = 60) -> int:
        """
        Remove LLM cache files not accessed in the last N days.
        Uses file modification time as proxy for last use.

        Returns:
            Number of cache files removed
        """
        import os
        cutoff = time.time() - (days * 86400)
        removed = 0

        for cache_file in self.cache_dir.glob('*.json'):
            try:
                if os.path.getmtime(cache_file) < cutoff:
                    cache_file.unlink()
                    removed += 1
            except OSError:
                pass

        if removed > 0:
            self.logger.info(f"LLM cache cleanup: removed {removed} files older than {days} days")

        return removed
    
    @retry_with_backoff(max_retries=3, base_delay=2)
    def _analyze_with_groq_impl(self, job_title: str, job_description: str,
                                 job_location: str, current_classification: str = "") -> Dict:
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

REMOTE-CAPABLE JOB TYPES (default: remote unless stated otherwise):
- Web/Software development (sites web, applications, code, WordPress, HTML, CSS, JavaScript, Python, PHP, etc.)
- Graphic design / Design graphique (logos, affiches, visuels, Photoshop, Illustrator, Canva, etc.)
- Writing / Rédaction (articles, contenu, copywriting, traduction, blog, etc.)
- Digital marketing (SEO, réseaux sociaux, publicité en ligne, community management, Facebook Ads)
- Data entry / Saisie de données
- Virtual assistance / Assistance virtuelle (administrative tasks online)
- Online tutoring / Cours en ligne (except if explicitly requires physical classroom)
- Video editing / Montage vidéo (except if involves mandatory on-site filming)
- Accounting / Comptabilité (online services, bookkeeping)
- Customer service / Service client (if online/téléphone/chat)
- Consulting / Conseil (if deliverables are digital)
- E-commerce management (gestion boutique en ligne)

ALWAYS ON-SITE JOB TYPES:
- Physical services: ménage, jardinage, coiffure, cuisine, réparation, construction, plomberie, électricité, peinture
- Care work: garde d'enfants, aide à domicile, auxiliaire de vie, soins infirmiers, accompagnement personnes âgées
- Transportation: livraison, déménagement, chauffeur, remorquage, transport
- Events: animation, DJ, photographe (for events), serveur, traiteur, organisation événements
- Manual labor: bricolage, installation, assemblage, montage meubles

REMOTE INDICATORS (positive signals):
- "télétravail", "à distance", "remote", "100% en ligne", "depuis chez vous", "mission flexible", "nomade digital"
- "WordPress", "site web", "développement", "design", "rédaction", "marketing digital", "création de contenu"
- "visio", "Zoom", "Google Meet", "Skype", "en ligne", "virtuel"
- Flexible location or "France entière" without physical address requirements
- "freelance", "indépendant", "auto-entrepreneur" for digital services
- Digital deliverables: "logo", "site internet", "application", "contenu", "stratégie", "référencement"

NOT REMOTE INDICATORS (negative signals):
- Specific city/address requirements for physical presence ("à Paris 15ème", "sur place obligatoire")
- "sur place", "présentiel", "déplacement requis", "visite client", "intervention physique"
- Work that requires handling physical objects or being in specific locations
- "nettoyage", "réparation", "installation", "montage", "garde", "soins"

DECISION RULES:
1. Digital job (web, design, writing) + NO location constraint = REMOTE ✓
2. Digital job + "mission flexible" / "télétravail" = REMOTE ✓
3. Physical service (ménage, garde, réparation) = ALWAYS ON-SITE ✗
4. Job seeker posting ("Je cherche un emploi") = typically ON-SITE (unless explicitly remote)
5. Job offer for digital work ("Je cherche développeur") = REMOTE if no location mentioned ✓
6. Ambiguous digital job without clear signals = DEFAULT to REMOTE (web/design/writing are remote by nature)

POSTER TYPE DETECTION:
Determine if this listing is posted by an EMPLOYER (client seeking to hire/commission work) or by an EMPLOYEE/SELF-PROMOTER (individual advertising their own skills to be hired).

EMPLOYER indicators:
- "Je cherche", "Je recherche", "Nous cherchons", "Besoin de", "À la recherche de"
- "Pour mon entreprise", "Pour mon projet", "Mon site web a besoin"
- Describing a project/mission to be completed: "Créer un site", "Développer une app", "Rédiger des articles"
- The subject is the work to be done, not the person

EMPLOYEE/SELF-PROMOTER indicators:
- "Je propose mes services", "Je suis développeur", "Je suis graphiste"
- "Je mets à votre disposition mes compétences", "Mes compétences"
- "Disponible pour", "Je peux réaliser", "Expert en"
- The subject is themselves: "Fort de X années d'expérience", "Passionné par"
- CV-style listings with their own qualifications, skills, rates

CONTEXT MATTERS:
- "Refonte de site web WordPress" = REMOTE ✓ (digital deliverable)
- "Créer un logo pour mon entreprise" = REMOTE ✓ (digital deliverable)
- "Rédaction d'articles SEO" = REMOTE ✓ (digital deliverable)
- "Développement application mobile" = REMOTE ✓ (digital deliverable)
- "Je cherche un emploi de développeur" = ON-SITE (job seeker without remote mention)
- "Développement web - Mission flexible" = REMOTE ✓
- "Développement sur Paris + réunions hebdomadaires" = ON-SITE (location constraint)
- "Service de ménage à domicile" = ON-SITE ✗ (physical service)

RESPOND IN JSON FORMAT ONLY:
{{
    "is_remote": true/false,
    "confidence": 0.0-1.0,
    "poster_type": "employer|employee|unknown",
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
            model=self.groq_model,
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
            'poster_type': result.get('poster_type', 'unknown'),
            'reason': f"LLM: {result.get('reason', 'No reason provided')}"
        }
    
    def analyze_with_groq(self, job_title: str, job_description: str,
                          job_location: str, current_classification: str = "") -> Dict:
        """
        Analyze job using Groq LLM with caching.

        Args:
            job_title: Job title
            job_description: Job description
            job_location: Job location/category
            current_classification: Unused — kept for backwards compatibility

        Returns:
            dict with 'is_remote', 'remote_confidence', 'poster_type', 'reason'
        """
        # Check cache first
        job_hash = self._get_job_hash(job_title, job_description, job_location)
        cached_result = self._load_from_cache(job_hash)
        
        if cached_result is not None:
            return cached_result
        
        # Not in cache, proceed with analysis
        if not self.groq_client:
            return self._analyze_with_nlp(job_title, job_description, job_location)
        
        try:
            result = self._analyze_with_groq_impl(job_title, job_description, 
                                                   job_location, current_classification)
            
            # Cache the result
            self._save_to_cache(job_hash, result)
            self.logger.info(f"Analyzed job: {job_title[:50]}... -> Remote: {result['is_remote']}, Confidence: {result['remote_confidence']}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a rate limit error
            if 'rate_limit_exceeded' in error_msg or '429' in error_msg:
                if self.verbose or True:  # Always show rate limit warnings
                    print(f"⚠️  Groq API Rate Limit: {e}")
                    print("⚠️  Falling back to local NLP")
                    print("💡 Tip: Upgrade your Groq plan or reduce scraping frequency")
                self.logger.error(f"Groq API rate limit exceeded: {e}")
            else:
                if self.verbose:
                    print(f"⚠️  Groq API error: {e}")
                    print("⚠️  Falling back to local NLP")
                self.logger.error(f"Groq API error: {e}", exc_info=True)
            
            return self._analyze_with_nlp(job_title, job_description, job_location)

    def _analyze_with_nlp(self, job_title: str, job_description: str,
                          job_location: str) -> Dict:
        """
        Analyze job using local NLP (fallback method)

        Uses keyword frequency and context analysis
        """
        self.cache_stats['nlp_fallbacks'] += 1
        text = f"{job_title} {job_description} {job_location}".lower()

        # Enhanced keyword lists
        strong_remote_keywords = [
            'télétravail', 'remote', 'distance', 'en ligne', 'online',
            'visio', 'zoom', 'numérique', 'digital', 'internet',
            'email', 'virtuel', 'ordinateur', 'computer', 'web',
            'logiciel', 'software', 'données', 'data', 'rédaction',
            'traduction', 'graphisme', 'design', 'marketing',
            'cours particuliers', 'par téléphone', 'e-learning',
            'formation en ligne', 'en visio',
        ]

        strong_onsite_keywords = [
            'sur place', 'physique', 'présentiel', 'déplacement',
            'à votre domicile', 'à domicile', 'intervention à domicile',
            'nettoyer', 'réparer', 'construire', 'installer',
            'tournage', 'plateau', 'terrain', 'chantier',
            'ménage', 'jardinage', 'garde d\'enfant', 'livraison',
            'coiffure', 'déménagement', 'aide à domicile',
        ]

        # Explicit physical-service job types (always on-site regardless of description)
        onsite_job_types = [
            'jardinier', 'jardinage', 'ménage', 'nettoyage', 'repassage',
            'garde d\'enfant', 'baby-sitting', 'babysitting', 'nounou',
            'aide-soignant', 'aide soignant', 'auxiliaire de vie',
            'déménagement', 'déménageur', 'livraison', 'chauffeur',
            'plombier', 'plomberie', 'électricien', 'électricité',
            'peintre', 'peinture', 'maçon', 'maçonnerie',
            'coiffeur', 'coiffeuse', 'esthétique', 'massage',
            'cuisiner', 'cuisinier', 'traiteur',
        ]

        # Special remote-friendly job categories
        remote_job_types = [
            'comptable', 'comptabilité', 'assistance comptable',
            'secrétariat', 'télésecrétariat', 'saisie',
            'rédaction', 'traduction', 'graphisme',
            'développement', 'programmation', 'web',
            'référencement', 'seo', 'community manager',
            'montage vidéo', 'retouche photo', 'modélisation',
        ]

        # Count keyword occurrences
        remote_score = sum(2 for kw in strong_remote_keywords if kw in text)
        onsite_score = sum(2 for kw in strong_onsite_keywords if kw in text)

        # Check for explicit physical-service types (strong on-site signal)
        for job_type in onsite_job_types:
            if job_type in text:
                onsite_score += 4

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

        # Detect poster_type: is this from an employer or an employee self-promoting?
        employee_signals = [
            'je propose mes services', 'je suis disponible', 'je mets à disposition',
            'mes compétences', 'mon expérience', 'je peux réaliser', 'je suis développeur',
            'je suis graphiste', 'je suis rédacteur', 'fort de', 'années d\'expérience',
            'expert en', 'spécialisé en', 'je maîtrise', 'mon portfolio', 'mes réalisations',
            'tarif journalier', 'mon taux journalier', 'tjm'
        ]
        employer_signals = [
            'je cherche', 'je recherche', 'nous cherchons', 'besoin de', 'à la recherche de',
            'pour mon projet', 'pour mon entreprise', 'pour mon site', 'mission pour',
            'cherche développeur', 'cherche graphiste', 'cherche rédacteur', 'cherche freelance',
            'prestataire recherché', 'appel à candidatures'
        ]

        employee_score = sum(1 for kw in employee_signals if kw in text)
        employer_score = sum(1 for kw in employer_signals if kw in text)

        if employee_score > employer_score:
            poster_type = 'employee'
        elif employer_score > 0:
            poster_type = 'employer'
        else:
            poster_type = 'unknown'

        # Decision logic with lower threshold
        if remote_score > onsite_score + 1:
            return {
                'is_remote': True,
                'remote_confidence': 0.8,
                'poster_type': poster_type,
                'reason': f'NLP Analysis: Strong remote indicators (score: {remote_score} vs {onsite_score})'
            }
        elif remote_score > onsite_score:
            return {
                'is_remote': True,
                'remote_confidence': 0.6,
                'poster_type': poster_type,
                'reason': f'NLP Analysis: Likely remote work (score: {remote_score} vs {onsite_score})'
            }
        elif onsite_score > remote_score + 1:
            return {
                'is_remote': False,
                'remote_confidence': 0.2,
                'poster_type': poster_type,
                'reason': f'NLP Analysis: Strong on-site indicators (score: {onsite_score} vs {remote_score})'
            }
        elif onsite_score > remote_score:
            return {
                'is_remote': False,
                'remote_confidence': 0.4,
                'poster_type': poster_type,
                'reason': f'NLP Analysis: Likely on-site work (score: {onsite_score} vs {remote_score})'
            }
        else:
            # Tied scores — neighbourhood-help platforms are predominantly physical;
            # default to on-site when remote and on-site scores are equal.
            return {
                'is_remote': False,
                'remote_confidence': 0.3,
                'poster_type': poster_type,
                'reason': f'NLP Analysis: No clear remote/on-site signals — defaulting to on-site (scores tied at {remote_score})'
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
        test_job['location']
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
