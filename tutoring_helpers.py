# -*- coding: utf-8 -*-
"""
Tutoring Pre-Filter
Fast keyword-based filter that discards non-tutoring posts before any LLM call.
Used on general-site traffic (jemepropose, allovoisins) to preserve Groq quota.
Dedicated tutoring sites (voscours, findtutors_uk) skip this filter entirely.
"""


class TutoringPreFilter:
    """
    Keyword pre-filter for tutoring relevance.

    Philosophy: cast a wide net — false positives are cheap (LLM handles them),
    false negatives are costly (missed opportunities). When in doubt, pass through.
    """

    KEYWORDS_FR = [
        # Direct tutoring vocabulary
        'cours de', 'cours particulier', 'cours particuliers', 'cours en ligne',
        'leçon de', 'leçons de', 'prof de', 'professeur de', 'professeure de',
        'soutien scolaire', 'aide scolaire', 'aide en', 'aide pour',
        'tutorat', 'tuteur', 'tutrice', 'formation en ligne', 'formation à distance',
        'apprendre', 'apprentissage', 'enseigner', 'enseignement',
        'répétiteur', 'répétitrices',
        # Academic subjects FR
        'mathématiques', 'maths', 'math ', 'algèbre', 'géométrie', 'calcul',
        'physique', 'chimie', 'biologie', 'svt', 'sciences',
        'histoire', 'géographie', 'histoire-géo',
        'philosophie', 'philo',
        'français', 'littérature', 'grammaire', 'orthographe', 'rédaction',
        'lecture', 'écriture',
        # Languages FR
        'anglais', 'espagnol', 'allemand', 'italien', 'portugais',
        'chinois', 'japonais', 'arabe', 'russe', 'néerlandais',
        'langue étrangère', 'fle ', 'français langue étrangère',
        # Music FR
        'guitare', 'piano', 'violon', 'batterie', 'solfège', 'musique',
        'chant', 'flûte', 'saxophone', 'trompette', 'contrebasse', 'violoncelle',
        'théorie musicale',
        # Tech / other FR
        'informatique', 'programmation', 'code', 'codage',
        'comptabilité', 'gestion', 'économie',
        'dessin', 'peinture artistique', 'aquarelle',
        'yoga', 'méditation',  # often online
    ]

    KEYWORDS_EN = [
        # Direct tutoring vocabulary EN
        'tutor', 'tutoring', 'tutored',
        'online lesson', 'online lessons', 'online class', 'online classes',
        'online course', 'private lesson', 'private lessons',
        'looking for teacher', 'looking for a teacher', 'looking for tutor',
        'need a teacher', 'need a tutor', 'teach me', 'teaching online',
        'homework help', 'academic help',
        # Subjects EN
        'maths tutor', 'math tutor', 'algebra', 'calculus', 'geometry',
        'physics tutor', 'chemistry tutor', 'biology tutor', 'science tutor',
        'english tutor', 'french tutor', 'spanish tutor', 'language tutor',
        'guitar lesson', 'piano lesson', 'violin lesson', 'music lesson',
        'drum lesson', 'singing lesson', 'voice lesson',
        'coding lesson', 'programming lesson',
        # Test prep EN
        'test prep', 'sat prep', 'gre prep', 'ielts', 'toefl', 'gcse', 'a-level',
    ]

    def is_tutoring_related(self, title: str, description: str, location: str) -> bool:
        """
        Returns True if the post is likely tutoring-related.
        Runs on combined text of all three fields, lowercased.
        """
        text = f"{title} {description} {location}".lower()
        for kw in self.KEYWORDS_FR + self.KEYWORDS_EN:
            if kw in text:
                return True
        return False

    def filter_jobs(self, jobs: list) -> tuple:
        """
        Split a list of jobs into (tutoring_related, discarded).

        Args:
            jobs: list of job dicts with 'title', 'description', 'location'

        Returns:
            (tutoring_jobs, discarded_jobs)
        """
        tutoring = []
        discarded = []
        for job in jobs:
            if self.is_tutoring_related(
                job.get('title', ''),
                job.get('description', ''),
                job.get('location', '')
            ):
                tutoring.append(job)
            else:
                discarded.append(job)
        return tutoring, discarded
