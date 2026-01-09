"""
Remote Job Detection Module
Analyzes job listings to determine if they can be done remotely
"""

class RemoteJobDetector:
    """Detects if a job can be done remotely based on various criteria"""
    
    # Job categories that are typically done remotely
    REMOTE_CATEGORIES = [
        'assistance comptable',
        'comptabilité',
        'coaching personnel',
        'cours en ligne',
        'traduction',
        'rédaction',
        'graphisme',
        'développement web',
        'programmation',
        'marketing digital',
        'community management',
        'saisie de données',
        'secrétariat',
        'télésecrétariat',
        'consulting',
        'formation en ligne',
        'assistance administrative',
    ]
    
    # Job categories that require physical presence
    ON_SITE_CATEGORIES = [
        'ménage',
        'baby-sitting',
        'garde d\'enfants',
        'auxiliaire de vie',
        'femme de chambre',
        'déménagement',
        'bricolage',
        'jardinage',
        'plomberie',
        'électricité',
        'peinture',
        'maçonnerie',
        'terrassement',
        'coiffure',
        'esthétique',
        'massage',
        'cuisine',
        'chauffeur',
        'livraison',
        'nettoyage',
    ]
    
    # Keywords indicating remote work
    REMOTE_KEYWORDS = [
        'distance',
        'remote',
        'télétravail',
        'teletravail',
        'en ligne',
        'online',
        'à distance',
        'a distance',
        'visio',
        'zoom',
        'skype',
        'teams',
        'virtuel',
        'internet',
        'email',
        'numérique',
        'digital',
    ]
    
    # Keywords indicating on-site work
    ON_SITE_KEYWORDS = [
        'domicile',
        'sur place',
        'présentiel',
        'presentiel',
        'déplacement',
        'deplacement',
        'maison',
        'appartement',
        'physique',
        'terrain',
    ]
    
    def __init__(self):
        """Initialize the detector"""
        pass
    
    def detect_remote_possibility(self, job_title, job_description, job_location):
        """
        Detect if a job can be done remotely
        
        Args:
            job_title: The job title
            job_description: The job description
            job_location: The job location/category
            
        Returns:
            dict with keys:
                - is_remote: bool (True if can be remote)
                - confidence: str ('high', 'medium', 'low')
                - reason: str (explanation)
        """
        # Combine all text for analysis
        text = f"{job_title} {job_description} {job_location}".lower()
        
        # Check for explicit remote keywords
        has_remote_keywords = any(keyword in text for keyword in self.REMOTE_KEYWORDS)
        has_onsite_keywords = any(keyword in text for keyword in self.ON_SITE_KEYWORDS)
        
        # Check job category
        category_is_remote = any(cat in job_location.lower() for cat in self.REMOTE_CATEGORIES)
        category_is_onsite = any(cat in job_location.lower() for cat in self.ON_SITE_CATEGORIES)
        
        # Decision logic
        if has_remote_keywords and not category_is_onsite:
            return {
                'is_remote': True,
                'confidence': 'medium',  # Changed from 'high' to 'medium' for semantic recheck
                'reason': 'Contains remote work keywords (needs semantic verification)'
            }
        
        if category_is_remote and not has_onsite_keywords:
            return {
                'is_remote': True,
                'confidence': 'medium',  # Changed from 'high' to 'medium' for semantic recheck
                'reason': 'Job category typically done remotely (needs semantic verification)'
            }
        
        if category_is_onsite:
            return {
                'is_remote': False,
                'confidence': 'high',  # Only ON-SITE HIGH keeps high confidence
                'reason': 'Job category requires physical presence'
            }
        
        if has_onsite_keywords:
            return {
                'is_remote': False,
                'confidence': 'medium',
                'reason': 'Contains on-site keywords'
            }
        
        # If unclear, check for mixed signals
        if has_remote_keywords and has_onsite_keywords:
            return {
                'is_remote': False,
                'confidence': 'low',
                'reason': 'Mixed signals - likely requires presence but may have remote aspects'
            }
        
        # Default: assume on-site if no clear indicators
        return {
            'is_remote': False,
            'confidence': 'low',
            'reason': 'No clear remote indicators - defaulting to on-site'
        }
    
    def format_remote_status(self, detection_result):
        """
        Format the detection result into a readable string
        
        Args:
            detection_result: dict from detect_remote_possibility
            
        Returns:
            str: formatted status
        """
        if detection_result['is_remote']:
            emoji = '🏠'
            status = 'REMOTE'
        else:
            emoji = '📍'
            status = 'ON-SITE'
        
        confidence = detection_result['confidence'].upper()
        return f"{emoji} {status} (Confidence: {confidence})"
