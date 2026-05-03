# -*- coding: utf-8 -*-
"""
Tutoring Classifier
Specialized LLM classifier for tutoring posts.

Determines:
  - is_online: can this session happen 100% remotely?
  - poster_type: student | teacher | institution | unknown
  - subject_category: broad subject bucket
  - instruction_lang: french | english | both | other
  - level: primary | secondary | university | adult | all_levels | unknown

Reuses SemanticJobAnalyzer's content-hash cache (same cache/ directory,
same file format) so the two pipelines never re-analyze the same content.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict

from semantic_analyzer import retry_with_backoff
from groq_model_manager import GroqModelManager


class TutoringClassifier:
    """
    LLM-based classifier for tutoring job posts.
    Shares the content-hash cache with SemanticJobAnalyzer.
    """

    def __init__(self, groq_api_key: str = None, verbose: bool = False):
        self.groq_api_key = groq_api_key or os.getenv('GROQ_API_KEY')
        self.verbose = verbose
        self.groq_client = None
        self.model_manager = GroqModelManager()
        self.cache_dir = Path('cache')
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_stats = {'hits': 0, 'misses': 0}
        self.llm_calls = 0
        self.nlp_fallbacks = 0
        self.logger = logging.getLogger(__name__)

        if self.groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_api_key)
                if self.verbose:
                    print("✅ TutoringClassifier: Groq API ready")
            except Exception as e:
                self.logger.warning(f"Groq init failed: {e}")

    # ------------------------------------------------------------------ cache

    def _get_hash(self, title: str, description: str, location: str, model_name: str) -> str:
        import hashlib
        content = f"tutoring|{model_name}|{title}|{description}|{location}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _load_cache(self, h: str) -> Dict:
        f = self.cache_dir / f"{h}.json"
        if f.exists():
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    self.cache_stats['hits'] += 1
                    return json.load(fp)
            except Exception:
                pass
        self.cache_stats['misses'] += 1
        return None

    def _save_cache(self, h: str, result: Dict):
        f = self.cache_dir / f"{h}.json"
        try:
            with open(f, 'w', encoding='utf-8') as fp:
                json.dump(result, fp, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_cache_stats(self) -> Dict:
        total = self.cache_stats['hits'] + self.cache_stats['misses']
        return {
            'cache_hits': self.cache_stats['hits'],
            'cache_misses': self.cache_stats['misses'],
            'total_requests': total,
            'hit_rate_percentage': round(self.cache_stats['hits'] / total * 100, 2) if total else 0,
            'llm_calls': self.llm_calls,
            'nlp_fallbacks': self.nlp_fallbacks,
            'model_usage': self.model_manager.stats(),
        }

    # ------------------------------------------------------------------ LLM

    @retry_with_backoff(max_retries=3, base_delay=2)
    def _call_groq(self, title: str, description: str, location: str, model_name: str) -> Dict:
        prompt = f"""You are analyzing a tutoring or teaching listing. The listing may be in French or English.

LISTING:
Title: {title}
Location/Context: {location}
Description: {description}

YOUR TASK:
Classify this listing across 5 dimensions. Be concise and accurate.

---

1. IS_ONLINE
Can this tutoring/teaching session happen 100% online (video call, Zoom, Skype, Teams, etc.)?
- True if: "en ligne", "à distance", "online", "remote", "visio", "zoom", "via internet", OR if the platform is an online tutoring site
- False if: explicitly requires physical presence ("à domicile", "chez l'élève", "en présentiel", "sur place") WITHOUT also offering online
- True by default for digital/academic subjects with no location constraint

2. POSTER_TYPE
Who posted this listing?
- "student": a learner seeking a teacher ("je cherche un professeur", "looking for a tutor", "need help with", "I want to learn")
- "teacher": a teacher advertising their services ("je propose des cours", "I offer lessons", "je donne des cours", "experienced tutor available")
- "institution": a school, company, or organization posting ("notre école", "our academy", "we are looking for")
- "unknown": cannot determine

3. SUBJECT_CATEGORY
What is the main subject? Choose ONE:
- "math_science": mathematics, algebra, calculus, physics, chemistry, biology, sciences, statistics, astronomy
- "languages": French, English, Spanish, German, Arabic, Chinese, Italian, Portuguese, Japanese, any foreign language, FLE, IELTS, TOEFL
- "music": guitar, piano, violin, drums, singing, voice, solfège, music theory, any instrument
- "arts_humanities": history, geography, philosophy, literature, drawing, painting, art history
- "technology": programming, coding, IT, computer science, web development, data science
- "test_prep": SAT, GRE, GMAT, BAC, brevet, GCSE, A-level, LSAT, MCAT, any exam prep
- "other": sports coaching, yoga, cooking, other subjects not listed above

4. INSTRUCTION_LANGUAGE
What language will the lessons be taught in?
- "french": lessons in French (or FR subject like "cours de maths en français")
- "english": lessons in English (or EN subject like "English tutoring")
- "both": platform or listing explicitly mentions both languages
- "other": another language (Arabic, Spanish, German lessons taught IN that language)

5. LEVEL
What education level is this for?
- "primary": elementary school, école primaire, ages 6-11
- "secondary": middle/high school, collège, lycée, ages 11-18
- "university": higher education, uni, licence, master, grandes écoles
- "adult": professional adult learner, retraité, continuing education
- "all_levels": explicitly for all levels or not specified
- "unknown": cannot determine

---

RESPOND IN JSON FORMAT ONLY:
{{
    "is_online": true/false,
    "poster_type": "student|teacher|institution|unknown",
    "subject_category": "math_science|languages|music|arts_humanities|technology|test_prep|other",
    "instruction_language": "french|english|both|other",
    "level": "primary|secondary|university|adult|all_levels|unknown",
    "confidence": 0.0-1.0,
    "reason": "brief explanation max 12 words"
}}"""

        response = self.groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an expert education analyst. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            model=model_name,
            temperature=0.1,
            max_tokens=250,
        )

        text = response.choices[0].message.content.strip()
        if '{' in text:
            text = text[text.index('{'):text.rindex('}') + 1]

        return json.loads(text)

    def _classify_with_nlp(self, title: str, description: str, location: str) -> Dict:
        """Keyword-based fallback when Groq is unavailable."""
        text = f"{title} {description} {location}".lower()

        # is_online
        online_signals = ['en ligne', 'à distance', 'online', 'remote', 'visio', 'zoom', 'skype', 'teams', 'virtual']
        onsite_signals = ['à domicile', 'chez l\'élève', 'présentiel', 'sur place', 'en personne']
        is_online = any(s in text for s in online_signals) and not any(s in text for s in onsite_signals)

        # poster_type
        student_signals = ['je cherche', 'recherche professeur', 'looking for', 'need a tutor', 'want to learn', 'besoin d\'un']
        teacher_signals = ['je propose', 'je donne des cours', 'i offer', 'i teach', 'available for lessons']
        if any(s in text for s in student_signals):
            poster_type = 'student'
        elif any(s in text for s in teacher_signals):
            poster_type = 'teacher'
        else:
            poster_type = 'unknown'

        # subject_category
        if any(s in text for s in ['math', 'physique', 'chimie', 'biologie', 'science', 'calcul', 'algebra']):
            subject_category = 'math_science'
        elif any(s in text for s in ['guitare', 'piano', 'violon', 'musique', 'guitar', 'piano', 'music', 'chant', 'singing']):
            subject_category = 'music'
        elif any(s in text for s in ['anglais', 'espagnol', 'français langue', 'german', 'chinese', 'arabic', 'language', 'ielts', 'toefl']):
            subject_category = 'languages'
        elif any(s in text for s in ['programmation', 'informatique', 'coding', 'python', 'javascript']):
            subject_category = 'technology'
        elif any(s in text for s in ['histoire', 'philosophie', 'litterature', 'history', 'philosophy']):
            subject_category = 'arts_humanities'
        elif any(s in text for s in ['bac', 'brevet', 'sat', 'gre', 'exam', 'examen', 'gcse']):
            subject_category = 'test_prep'
        else:
            subject_category = 'other'

        # instruction_language
        if any(s in text for s in ['english tutor', 'english lesson', 'taught in english', 'en anglais']):
            instruction_language = 'english'
        elif any(s in text for s in ['cours en français', 'french lesson', 'french tutor', 'en français']):
            instruction_language = 'french'
        else:
            instruction_language = 'french'  # default for French-origin platforms

        return {
            'is_online': is_online,
            'poster_type': poster_type,
            'subject_category': subject_category,
            'instruction_language': instruction_language,
            'level': 'unknown',
            'confidence': 0.5,
            'reason': 'NLP fallback classification',
        }

    # ------------------------------------------------------------------ public

    def classify(self, title: str, description: str, location: str) -> Dict:
        """
        Classify a tutoring post. Returns cached result if available.

        Returns:
            dict with keys: is_online, poster_type, subject_category,
                            instruction_language, level, confidence, reason
        """
        model_name = self.model_manager.pick_model() if self.model_manager else None
        model_name = model_name or os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

        if not self.groq_client:
            self.nlp_fallbacks += 1
            result = self._classify_with_nlp(title, description, location)
        else:
            attempted_models = set()
            result = None
            while model_name and model_name not in attempted_models:
                attempted_models.add(model_name)
                h = self._get_hash(title, description, location, model_name)
                cached = self._load_cache(h)
                if cached is not None:
                    if self.verbose:
                        print("    ♻️  Tutoring cache hit")
                    return cached
                try:
                    raw = self._call_groq(title, description, location, model_name)
                    result = {
                        'is_online': bool(raw.get('is_online', False)),
                        'poster_type': raw.get('poster_type', 'unknown'),
                        'subject_category': raw.get('subject_category', 'other'),
                        'instruction_language': raw.get('instruction_language', 'french'),
                        'level': raw.get('level', 'unknown'),
                        'confidence': float(raw.get('confidence', 0.5)),
                        'reason': f"LLM: {raw.get('reason', '')}",
                        'model': model_name,
                    }
                    self.model_manager.record_call(model_name)
                    self.llm_calls += 1
                    break
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'not found' in error_msg or 'does not exist' in error_msg:
                        self.model_manager.disable_model(model_name)
                    elif 'rate_limit' in error_msg or '429' in error_msg:
                        self.model_manager.disable_model(model_name)
                    self.logger.error(f"Groq error for model {model_name}: {e}", exc_info=True)
                    model_name = self.model_manager.pick_model()

            if result is None:
                self.nlp_fallbacks += 1
                result = self._classify_with_nlp(title, description, location)

        h = self._get_hash(title, description, location, result.get('model', 'nlp'))
        self._save_cache(h, result)
        self.logger.info(
            f"Tutoring classified: {title[:40]}... "
            f"online={result['is_online']} poster={result['poster_type']} "
            f"subject={result['subject_category']}"
        )
        return result
