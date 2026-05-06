# -*- coding: utf-8 -*-
"""
Mission Type Filter - Déterminer le type d'engagement (CDI/CDD/Mission/Freelance)
Permet d'exclure les CDI/CDD et les missions de marketplace freelance (Malt, Freelance.com, etc)
"""

import re
from typing import Literal, Dict, Tuple


class MissionTypeFilter:
    """
    Détecte le type de mission/contrat d'engagement
    
    Types:
    - cdi: Contrat à Durée Indéterminée
    - cdd: Contrat à Durée Déterminée
    - mission: Mission temporaire entre particuliers (gig work)
    - freelance: Missions marketplace (Malt, Freelance.com, etc)
    - unknown: Type indéterminé
    """
    
    # Expressions régulières pour détecter les types de contrats
    CDI_PATTERNS = [
        r'\bCDI\b',
        r'contrat à durée indéterminée',
        r'emploi permanent',
        r'emploi stable',
        r'poste permanent',
        r'embauche\s+(permanent|fixe)',
        r'recrutement\s+(permanent|classique)',
        r"nous recrutons|nous cherchons un employé",
        r'rémunération\s+mensuelle\s+fixe',
    ]
    
    CDD_PATTERNS = [
        r'\bCDD\b',
        r'\bCDT\b',
        r'contrat à durée déterminée',
        r'contrat temporaire',
        r'stage\s+rémunéré',
        r'alternance',
        r'contrat\s+de\s+\d+\s+(mois|ans|semaines)',
    ]
    
    # Signatures de marketplaces freelance
    FREELANCE_MARKETPLACE_PATTERNS = [
        r'malt\.fr',
        r'freelance\.com',
        r'comet\.co',
        r'upwork',
        r'fiverr',
        r'toptal',
        r'guru',
        r'peopleperhour',
        r'marketplace\s+freelance',
        r'plateforme\s+freelance',
        r'plateforme.*freelance|freelance.*plateforme',
    ]
    
    # Patterns pour détecter les missions entre particuliers (gig work)
    GIG_WORK_PATTERNS = [
        r'mission\s+ponctuelle',
        r'coup\s+de\s+main',
        r'petit\s+boulot',
        r'gig\s+work',
        r'mission\s+unique',
        r'projet\s+(court|rapide)',
        r'service\s+à\s+la\s+personne',
        r'aide\s+ponctuelle',
        r'travaux\s+ponctuels',
        r'mission\s+flexible',
        r'mission\s+au\s+projet',
    ]
    
    # Patterns pour missions en info/formation (toujours valides)
    VALID_MISSIONS_PATTERNS = [
        r'cours\s+particulier',
        r'soutien\s+scolaire',
        r'répétition',
        r'tutorat',
        r'coaching\s+personnel',
        r'formation\s+individuelle',
        r'cours\s+en\s+ligne',
        r'développement\s+web',
        r'création\s+de\s+site',
        r'consulting\s+tech',
        r'audit\s+informatique',
        r'assistance\s+informatique',
    ]
    
    def __init__(self, verbose: bool = False):
        """
        Initialiser le filtre
        
        Args:
            verbose: Afficher les détails de la détection
        """
        self.verbose = verbose
    
    def _compile_patterns(self, patterns: list) -> list:
        """Compiler les patterns regex"""
        return [re.compile(p, re.IGNORECASE) for p in patterns]
    
    def _match_patterns(self, text: str, patterns: list) -> bool:
        """Chercher si l'un des patterns correspond"""
        if not text:
            return False
        compiled = self._compile_patterns(patterns)
        return any(pattern.search(text) for pattern in compiled)
    
    def detect_mission_type(self, 
                           title: str, 
                           description: str, 
                           location: str,
                           source: str = 'unknown') -> Tuple[Literal['cdi', 'cdd', 'mission', 'freelance', 'unknown'], float]:
        """
        Détecter le type de mission/contrat
        
        Returns:
            Tuple: (mission_type, confidence) où confidence est 0.0-1.0
        """
        combined_text = f"{title} {description} {location}".lower()
        
        # 1. Vérifier si c'est un CDI
        if self._match_patterns(combined_text, self.CDI_PATTERNS):
            if self.verbose:
                print(f"  🔴 Détecté: CDI")
            return ('cdi', 0.95)
        
        # 2. Vérifier si c'est un CDD
        if self._match_patterns(combined_text, self.CDD_PATTERNS):
            if self.verbose:
                print(f"  🟡 Détecté: CDD")
            return ('cdd', 0.95)
        
        # 3. Vérifier si c'est une marketplace freelance
        if self._match_patterns(combined_text, self.FREELANCE_MARKETPLACE_PATTERNS) or \
           source.lower() in ['malt', 'freelance.com', 'comet', 'upwork']:
            if self.verbose:
                print(f"  🟠 Détecté: Freelance Marketplace")
            return ('freelance', 0.95)
        
        # 4. Vérifier si c'est une mission valide (info/formation)
        if self._match_patterns(combined_text, self.VALID_MISSIONS_PATTERNS):
            if self.verbose:
                print(f"  🟢 Détecté: Mission valide (info/formation)")
            return ('mission', 0.90)
        
        # 5. Vérifier si c'est du gig work (missions entre particuliers)
        if self._match_patterns(combined_text, self.GIG_WORK_PATTERNS):
            if self.verbose:
                print(f"  🟢 Détecté: Mission gig work")
            return ('mission', 0.85)
        
        # 6. Source: JeMePropose et AlloVoisins = toujours missions entre particuliers
        if source.lower() in ['jemepropose', 'allovoisins']:
            if self.verbose:
                print(f"  🟢 Détecté: Source {source} = missions entre particuliers")
            return ('mission', 0.90)
        
        # Par défaut: supposer que c'est une mission si pas d'indication contraire
        if self.verbose:
            print(f"  ❓ Type indéterminé, supposer: mission")
        return ('unknown', 0.5)
    
    def should_include_job(self, 
                          title: str, 
                          description: str, 
                          location: str,
                          source: str = 'unknown') -> Tuple[bool, str, str]:
        """
        Déterminer si on doit inclure cette mission
        
        Returns:
            Tuple: (should_include, reason, mission_type)
        """
        mission_type, confidence = self.detect_mission_type(title, description, location, source)
        
        if mission_type == 'cdi':
            return False, "❌ Exclu: CDI (contrat permanent)", mission_type
        elif mission_type == 'cdd':
            return False, "❌ Exclu: CDD (contrat temporaire non-flexible)", mission_type
        elif mission_type == 'freelance':
            return False, "❌ Exclu: Freelance Marketplace (Malt, Freelance.com, etc)", mission_type
        elif mission_type == 'mission':
            return True, "✅ Inclus: Mission valide", mission_type
        else:
            # Pour 'unknown', inclure par défaut (missions entre particuliers)
            return True, "✅ Inclus: Type indéterminé (supposé: mission)", mission_type


def filter_jobs_by_mission_type(jobs: list, 
                                exclude_types: list = None,
                                verbose: bool = False) -> Tuple[list, Dict[str, int]]:
    """
    Filtrer une liste de jobs par type de mission
    
    Args:
        jobs: Liste des jobs (chaque job doit avoir: title, description, location, source)
        exclude_types: Types à exclure (['cdi', 'cdd', 'freelance'])
        verbose: Afficher les détails
    
    Returns:
        Tuple: (filtered_jobs, stats)
    """
    if exclude_types is None:
        exclude_types = ['cdi', 'cdd', 'freelance']
    
    filter_obj = MissionTypeFilter(verbose=verbose)
    
    filtered_jobs = []
    stats = {
        'total': len(jobs),
        'included': 0,
        'cdi': 0,
        'cdd': 0,
        'freelance': 0,
        'mission': 0,
        'unknown': 0,
    }
    
    for job in jobs:
        title = job.get('title', '')
        description = job.get('description', '')
        location = job.get('location', '')
        source = job.get('source', 'unknown')
        
        mission_type, confidence = filter_obj.detect_mission_type(title, description, location, source)
        stats[mission_type] += 1
        
        # Inclure si ce type n'est pas exclu
        if mission_type not in exclude_types:
            filtered_jobs.append(job)
            stats['included'] += 1
    
    if verbose:
        print(f"\n📊 Mission Type Filter Stats:")
        print(f"  Total: {stats['total']}")
        print(f"  Inclus: {stats['included']}")
        print(f"  Exclus (CDI): {stats['cdi']}")
        print(f"  Exclus (CDD): {stats['cdd']}")
        print(f"  Exclus (Freelance): {stats['freelance']}")
        print(f"  Missions: {stats['mission']}")
        print(f"  Indéterminé: {stats['unknown']}")
    
    return filtered_jobs, stats
