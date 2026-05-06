#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test d'intégration Groq - Validation du scraper avec analyse LLM
Teste:
1. WorkingNomads scraper
2. Mission Type Filter
3. Groq LLM analysis
4. Filtrage global des jobs
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from semantic_analyzer import SemanticJobAnalyzer
from mission_type_filter import MissionTypeFilter, filter_jobs_by_mission_type
from site_scrapers import WorkingNomadsScraper, JeMeProposeScraper, AlloVoisinsScraper


def test_groq_connection():
    """Tester la connexion à Groq"""
    print("\n" + "="*60)
    print("🔧 TEST 1: Connexion Groq API")
    print("="*60)
    
    groq_key = os.getenv('GROQ_API_KEY')
    if not groq_key:
        print("❌ GROQ_API_KEY non trouvée dans les variables d'environnement")
        return False
    
    print(f"✅ Clé Groq trouvée: {groq_key[:10]}...")
    
    try:
        analyzer = SemanticJobAnalyzer(use_groq=True, groq_api_key=groq_key, verbose=True)
        if analyzer.groq_client:
            print("✅ Client Groq initialisé avec succès")
            return True
        else:
            print("❌ Impossible d'initialiser le client Groq")
            return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def test_mission_type_filter():
    """Tester le filtre de type de mission"""
    print("\n" + "="*60)
    print("🔧 TEST 2: Mission Type Filter")
    print("="*60)
    
    filter_obj = MissionTypeFilter(verbose=True)
    
    test_cases = [
        {
            'title': 'Développeur web React',
            'description': 'Création de site WordPress en télétravail, mission flexible',
            'location': 'Remote',
            'source': 'workingnomads',
            'expected': 'mission'
        },
        {
            'title': 'Recrutement: Développeur Senior CDI',
            'description': 'Poste permanent, contrat à durée indéterminée, Paris 15ème',
            'location': 'Paris',
            'source': 'linkedin',
            'expected': 'cdi'
        },
        {
            'title': 'Cours particulier Mathématiques',
            'description': 'Soutien scolaire pour lycéen, 1h par semaine à distance',
            'location': 'Remote',
            'source': 'jemepropose',
            'expected': 'mission'
        },
        {
            'title': 'Logo design - Freelance project',
            'description': 'Créer un logo pour notre entreprise via Malt',
            'location': 'Remote',
            'source': 'malt',
            'expected': 'freelance'
        },
        {
            'title': 'Aide au ménage CDD 3 mois',
            'description': 'Contrat à durée déterminée, 3 mois, à domicile',
            'location': 'Lyon',
            'source': 'allovoisins',
            'expected': 'cdd'
        },
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n  Test case {i}: {test['title'][:40]}...")
        mission_type, confidence = filter_obj.detect_mission_type(
            test['title'],
            test['description'],
            test['location'],
            test['source']
        )
        
        if mission_type == test['expected']:
            print(f"    ✅ PASS: Détecté {mission_type} (confiance: {confidence})")
            passed += 1
        else:
            print(f"    ❌ FAIL: Détecté {mission_type}, attendu {test['expected']}")
            failed += 1
    
    print(f"\n📊 Résultats: {passed} PASS, {failed} FAIL")
    return failed == 0


def test_scraper_workingnomads():
    """Tester le scraper WorkingNomads"""
    print("\n" + "="*60)
    print("🔧 TEST 3: WorkingNomads Scraper")
    print("="*60)
    
    try:
        scraper = WorkingNomadsScraper(verbose=True)
        print(f"✅ Scraper initialisé")
        print(f"   Site: {scraper.site_name}")
        print(f"   Base URL: {scraper.base_url}")
        
        # Essayer de scraper la première page
        print(f"\n  Scraping page 1...")
        jobs, has_more = scraper.scrape_page(1)
        
        print(f"  ✅ {len(jobs)} jobs trouvés")
        if jobs:
            print(f"  Exemple: {jobs[0]['title'][:50]}...")
        
        return len(jobs) > 0
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def test_jemepropose_scraper():
    """Tester le scraper JeMePropose"""
    print("\n" + "="*60)
    print("🔧 TEST 4: JeMePropose Scraper")
    print("="*60)
    
    try:
        scraper = JeMeProposeScraper(verbose=True)
        print(f"✅ Scraper initialisé")
        print(f"   Site: {scraper.site_name}")
        print(f"   Base URL: {scraper.base_url}")
        
        # Essayer de scraper la première page
        print(f"\n  Scraping page 1...")
        jobs, has_more = scraper.scrape_page(1)
        
        print(f"  ✅ {len(jobs)} jobs trouvés")
        if jobs:
            print(f"  Exemple: {jobs[0]['title'][:50]}...")
        
        return len(jobs) > 0
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def test_groq_analysis():
    """Tester l'analyse Groq sur un job sample"""
    print("\n" + "="*60)
    print("🔧 TEST 5: Groq LLM Analysis")
    print("="*60)
    
    groq_key = os.getenv('GROQ_API_KEY')
    if not groq_key:
        print("❌ Clé Groq non disponible, test skippé")
        return False
    
    try:
        analyzer = SemanticJobAnalyzer(use_groq=True, groq_api_key=groq_key, verbose=True)
        
        # Test job
        job_title = "Développeur web WordPress"
        job_description = "Créer un site WordPress moderne avec design responsive. Télétravail 100%. Mission flexible."
        job_location = "À distance"
        
        print(f"\n  Job: {job_title}")
        print(f"  Description: {job_description[:60]}...")
        print(f"\n  Analysing avec Groq...")
        
        result = analyzer.analyze_job(job_title, job_description, job_location, "unknown")
        
        if result:
            print(f"\n  ✅ Analyse complète:")
            print(f"     Is Remote: {result['is_remote']}")
            print(f"     Confiance: {result['remote_confidence']}")
            print(f"     Raison: {result['reason']}")
            return True
        else:
            print(f"  ❌ Impossible d'obtenir une analyse")
            return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mission_filtering():
    """Tester le filtrage global de missions"""
    print("\n" + "="*60)
    print("🔧 TEST 6: Mission Filtering Pipeline")
    print("="*60)
    
    # Sample jobs
    jobs = [
        {
            'title': 'Développeur web',
            'description': 'Créer un site en télétravail',
            'location': 'Remote',
            'source': 'jemepropose',
        },
        {
            'title': 'CDI: Développeur Senior',
            'description': 'Contrat permanent, Paris',
            'location': 'Paris',
            'source': 'linkedin',
        },
        {
            'title': 'Logo design Malt',
            'description': 'Projet freelance marketplace',
            'location': 'Remote',
            'source': 'malt',
        },
        {
            'title': 'Cours particulier Math',
            'description': 'Soutien scolaire à distance',
            'location': 'Remote',
            'source': 'jemepropose',
        },
    ]
    
    print(f"\n  Jobs avant filtrage: {len(jobs)}")
    filtered, stats = filter_jobs_by_mission_type(
        jobs,
        exclude_types=['cdi', 'cdd', 'freelance'],
        verbose=True
    )
    
    print(f"\n  Jobs après filtrage: {len(filtered)}")
    print(f"  Résultats du filtre:")
    print(f"    ✅ Inclus: {stats['included']}")
    print(f"    ❌ CDI: {stats['cdi']}")
    print(f"    ❌ CDD: {stats['cdd']}")
    print(f"    ❌ Freelance: {stats['freelance']}")
    
    return stats['included'] == 2  # Attendu: 2 jobs inclus (dev web + cours)


def main():
    """Exécuter tous les tests"""
    print("\n" + "="*70)
    print("🚀 INTEGRATION TEST SUITE - afidiOS-finder")
    print("="*70)
    
    results = {}
    
    # Test 1: Groq Connection
    results['Groq Connection'] = test_groq_connection()
    
    # Test 2: Mission Type Filter
    results['Mission Type Filter'] = test_mission_type_filter()
    
    # Test 3: WorkingNomads Scraper
    results['WorkingNomads Scraper'] = test_scraper_workingnomads()
    
    # Test 4: JeMePropose Scraper
    results['JeMePropose Scraper'] = test_jemepropose_scraper()
    
    # Test 5: Groq Analysis
    results['Groq Analysis'] = test_groq_analysis()
    
    # Test 6: Mission Filtering
    results['Mission Filtering'] = test_mission_filtering()
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n📈 Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 Tous les tests sont passés!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) échoué(s)")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
