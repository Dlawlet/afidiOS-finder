"""
Data Models with Pydantic Validation
Ensures data quality and type safety throughout the scraper
"""

from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, Literal
from datetime import datetime


class JobListing(BaseModel):
    """Validated job listing model"""
    
    title: str = Field(..., min_length=1, max_length=500, description="Job title")
    description: str = Field(..., min_length=1, description="Job description")  # Relaxed from 10 to 1
    url: str = Field(..., description="Job posting URL")
    location: str = Field(..., min_length=1, max_length=200, description="Job location/category")
    price: str = Field(default="N/A", max_length=100, description="Job price/rate")
    is_remote: bool = Field(..., description="Whether job is remote")
    remote_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    reason: str = Field(..., min_length=3, max_length=500, description="Classification reason")  # Relaxed from 5 to 3
    scraped_at: Optional[datetime] = Field(default_factory=datetime.now, description="Scrape timestamp")
    
    @field_validator('title', 'description')
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Remove extra whitespace"""
        return ' '.join(v.split())
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL is valid"""
        if not v or v == 'N/A':
            return v
        if not v.startswith('http'):
            raise ValueError('URL must start with http:// or https://')
        return v
    
    @field_validator('remote_confidence')
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 2 decimal places"""
        return round(v, 2)
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Développeur web",
                "description": "Création de sites WordPress en télétravail",
                "url": "https://www.jemepropose.com/annonces/12345",
                "location": "A Distance",
                "price": "40€/h",
                "is_remote": True,
                "remote_confidence": 0.95,
                "reason": "LLM: Développement web explicitement en télétravail",
                "scraped_at": "2026-01-17T10:00:00"
            }
        }


class AnalysisResult(BaseModel):
    """LLM/NLP analysis result"""
    
    is_remote: bool
    remote_confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=5)
    
    @field_validator('remote_confidence')
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 2 decimal places"""
        return round(v, 2)


class ScraperMetrics(BaseModel):
    """Scraper performance metrics"""
    
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_seconds: int = Field(..., ge=0)
    jobs_scraped: int = Field(..., ge=0)
    jobs_analyzed: int = Field(..., ge=0)
    new_jobs: int = Field(..., ge=0)
    cached_jobs: int = Field(..., ge=0)
    remote_jobs: int = Field(..., ge=0)
    llm_calls: int = Field(..., ge=0)
    cache_stats: dict
    confidence_distribution: dict
    errors: list[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2026-01-17T10:00:00",
                "duration_seconds": 245,
                "jobs_scraped": 200,
                "jobs_analyzed": 80,
                "new_jobs": 80,
                "cached_jobs": 120,
                "remote_jobs": 45,
                "llm_calls": 80,
                "cache_stats": {
                    "cache_hits": 120,
                    "cache_misses": 80,
                    "hit_rate_percentage": 60.0
                },
                "confidence_distribution": {
                    "high": 150,
                    "medium": 35,
                    "low": 15
                },
                "errors": []
            }
        }


class JobHistory(BaseModel):
    """Job history tracking"""
    
    first_seen: datetime
    last_seen: datetime
    title: str
    is_remote: bool
    appearances: int = Field(default=1, ge=1)
    
    @field_validator('first_seen', 'last_seen', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        """Parse datetime from string if needed"""
        if isinstance(v, str):
            try:
                return datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return datetime.fromisoformat(v)
        return v


# Validation helper functions

def validate_job_data(job_data: dict) -> Optional[JobListing]:
    """
    Validate job data and return JobListing or None if invalid
    
    Args:
        job_data: Raw job data dictionary
        
    Returns:
        Validated JobListing or None
    """
    try:
        return JobListing(**job_data)
    except Exception as e:
        print(f"⚠️  Validation error for job: {e}")
        return None


def validate_analysis_result(result: dict) -> Optional[AnalysisResult]:
    """
    Validate analysis result
    
    Args:
        result: Raw analysis result dictionary
        
    Returns:
        Validated AnalysisResult or None
    """
    try:
        return AnalysisResult(**result)
    except Exception as e:
        print(f"⚠️  Analysis validation error: {e}")
        return None


# Testing
if __name__ == "__main__":
    print("\n" + "="*80)
    print("PYDANTIC MODELS TEST")
    print("="*80)
    
    # Test valid job
    print("\n1. Testing valid job:")
    valid_job = {
        'title': 'Développeur web',
        'description': 'Création de sites WordPress en télétravail',
        'url': 'https://www.jemepropose.com/annonces/12345',
        'location': 'A Distance',
        'price': '40€/h',
        'is_remote': True,
        'remote_confidence': 0.95,
        'reason': 'LLM: Développement web explicitement en télétravail'
    }
    
    job = validate_job_data(valid_job)
    if job:
        print(f"✅ Valid job: {job.title}")
        print(f"   Remote: {job.is_remote}, Confidence: {job.remote_confidence}")
    
    # Test invalid job (missing required fields)
    print("\n2. Testing invalid job (missing description):")
    invalid_job = {
        'title': 'Test Job',
        'url': 'https://example.com',
        'location': 'Paris',
        'is_remote': True,
        'remote_confidence': 0.8,
        'reason': 'Test'
    }
    
    job = validate_job_data(invalid_job)
    if job is None:
        print("❌ Validation failed as expected")
    
    # Test confidence rounding
    print("\n3. Testing confidence rounding:")
    job_with_long_confidence = valid_job.copy()
    job_with_long_confidence['remote_confidence'] = 0.956789
    
    job = validate_job_data(job_with_long_confidence)
    if job:
        print(f"✅ Confidence rounded: {job.remote_confidence} (from 0.956789)")
    
    # Test whitespace stripping
    print("\n4. Testing whitespace stripping:")
    job_with_whitespace = valid_job.copy()
    job_with_whitespace['title'] = '  Développeur    web  '
    
    job = validate_job_data(job_with_whitespace)
    if job:
        print(f"✅ Whitespace stripped: '{job.title}'")
    
    print("\n" + "="*80)
    print("All validation tests complete!")
    print("="*80 + "\n")
