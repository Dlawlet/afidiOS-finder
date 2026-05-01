"""
Job Results Exporter - Export and update job analysis results
Supports JSON and CSV formats with incremental updates
Enhanced with job history tracking
"""

import json
import csv
from datetime import datetime, timedelta
from pathlib import Path

from tutoring_helpers import TutoringPreFilter


class JobExporter:
    """Handle exporting job analysis results to various formats"""
    
    def __init__(self, output_dir='exports'):
        """
        Initialize the exporter
        
        Args:
            output_dir: Directory to store exported files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Generate timestamp for this export session
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # History file path
        self.history_file = self.output_dir / 'job_history.json'
    
    def load_job_history(self):
        """Load previously seen job IDs and URLs"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {'seen_urls': {}, 'last_update': None}
        return {'seen_urls': {}, 'last_update': None}
    
    def update_job_history(self, jobs):
        """Update history with new jobs"""
        history = self.load_job_history()
        
        for job in jobs:
            url = job.get('url')
            if url and url != 'N/A':
                # Preserve existing first_seen date if job was seen before
                existing_entry = history['seen_urls'].get(url, {})
                
                history['seen_urls'][url] = {
                    'first_seen': existing_entry.get('first_seen', self.date_str),
                    'last_seen': self.date_str,
                    'title': job.get('title'),
                    'is_remote': job.get('is_remote'),
                    'poster_type': job.get('poster_type', 'unknown'),
                    'description': job.get('description', 'N/A'),
                    'confidence': job.get('confidence', 'MEDIUM'),
                    'classification': job.get('classification', 'unknown'),
                    'reasoning': job.get('reasoning', 'N/A'),
                    'description_source': job.get('description_source', 'listing_page')
                }
        
        history['last_update'] = self.date_str
        
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"⚠️  Could not update history: {e}")
        
        return history
    
    def filter_new_jobs(self, jobs, days=7):
        """
        Return only jobs not seen in last N days
        
        Args:
            jobs: List of job dictionaries
            days: Number of days to consider as "new" (default 7)
            
        Returns:
            List of new jobs
        """
        history = self.load_job_history()
        cutoff = datetime.now() - timedelta(days=days)
        
        new_jobs = []
        for job in jobs:
            url = job.get('url')
            if url not in history['seen_urls']:
                new_jobs.append(job)
            else:
                last_seen = history['seen_urls'][url].get('last_seen')
                if last_seen:
                    try:
                        last_seen_date = datetime.strptime(last_seen, '%Y-%m-%d %H:%M:%S')
                        if last_seen_date < cutoff:
                            new_jobs.append(job)
                    except ValueError:
                        # If date parsing fails, include the job
                        new_jobs.append(job)
        
        return new_jobs
    
    def get_history_stats(self):
        """Get statistics about job history"""
        history = self.load_job_history()
        
        total_seen = len(history['seen_urls'])
        remote_seen = sum(1 for job in history['seen_urls'].values() if job.get('is_remote'))
        
        return {
            'total_jobs_seen': total_seen,
            'remote_jobs_seen': remote_seen,
            'last_update': history.get('last_update', 'Never')
        }
    
    def export_to_json(self, jobs, stats, filename=None, update_history=True):
        """
        Export job results to JSON format
        
        Args:
            jobs: List of job dictionaries
            stats: Statistics dictionary
            filename: Custom filename (optional)
        
        Returns:
            Path to the exported file
        """
        if filename is None:
            filename = f'jobs_{self.timestamp}.json'
        
        filepath = self.output_dir / filename
        
        if update_history:
            self.update_job_history(jobs)
        history_stats = self.get_history_stats()
        
        export_data = {
            'metadata': {
                'export_date': self.date_str,
                'total_jobs': stats['total'],
                'analysis_mode': 'LLM-Enhanced' if stats.get('llm_used', False) else 'NLP-Only',
                'history_stats': history_stats,
                # Provided by caller in stats so it reflects the full run, not just this slice
                'employee_posts_filtered': stats.get('employee_posts_filtered', 0),
            },
            'statistics': stats,
            'jobs': jobs
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        
        return filepath
    
    def export_to_csv(self, jobs, filename=None):
        """
        Export job results to CSV format
        
        Args:
            jobs: List of job dictionaries
            filename: Custom filename (optional)
        
        Returns:
            Path to the exported file
        """
        if filename is None:
            filename = f'jobs_{self.timestamp}.csv'
        
        filepath = self.output_dir / filename
        
        if not jobs:
            return filepath
        
        # Define CSV columns
        fieldnames = [
            'id',
            'title',
            'location',
            'category',
            'price',
            'poster',
            'date_posted',
            'source',           # which site the job came from
            'vertical',         # general | tutoring
            'poster_type',      # employer/employee/student/teacher/unknown
            'subject_category', # tutoring: math_science|languages|music|...  general: N/A
            'instruction_lang', # tutoring: french|english|both|other          general: N/A
            'level',            # tutoring: primary|secondary|...              general: N/A
            'classification',
            'confidence',
            'is_remote',
            'reasoning',
            'description_preview',
            'description_source',
            'was_reanalyzed',
            'url'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for job in jobs:
                row = {
                    'id': job.get('id', 'N/A'),
                    'title': job.get('title', 'N/A'),
                    'location': job.get('location', 'N/A'),
                    'category': job.get('category', 'N/A'),
                    'price': job.get('price', 'N/A'),
                    'poster': job.get('poster', 'N/A'),
                    'date_posted': job.get('date_posted', 'N/A'),
                    'source': job.get('source', 'N/A'),
                    'vertical': job.get('vertical', 'general'),
                    'poster_type': job.get('poster_type', 'unknown'),
                    'subject_category': job.get('subject_category', 'N/A'),
                    'instruction_lang': job.get('instruction_lang', 'N/A'),
                    'level': job.get('level', 'N/A'),
                    'classification': job.get('classification', 'N/A'),
                    'confidence': job.get('confidence', 'N/A'),
                    'is_remote': 'Yes' if job.get('is_remote', False) else 'No',
                    'reasoning': job.get('reasoning', 'N/A'),
                    'description_preview': job.get('description', 'N/A')[:200] + '...' if len(job.get('description', '')) > 200 else job.get('description', 'N/A'),
                    'description_source': job.get('description_source', 'listing_page'),
                    'was_reanalyzed': 'Yes' if job.get('was_reanalyzed', False) else 'No',
                    'url': job.get('url', 'N/A')
                }
                writer.writerow(row)
        
        return filepath
    
    def update_latest_export(self, jobs, stats):
        """
        Update the 'latest' export files (always overwrites)
        
        Args:
            jobs: List of job dictionaries
            stats: Statistics dictionary
        
        Returns:
            Dictionary with paths to updated files
        """
        json_path = self.export_to_json(jobs, stats, filename='jobs_latest.json')
        csv_path = self.export_to_csv(jobs, filename='jobs_latest.csv')
        
        return {
            'json': json_path,
            'csv': csv_path
        }
    
    def export_tutoring_opportunities(self, all_jobs: list, run_stats: dict) -> dict:
        """
        Export the tutoring opportunities slice: vertical=tutoring, is_online=True,
        poster_type=student (or unknown — we don't drop unknowns since on dedicated
        sites like VosCours all cards are students).

        Written to tutoring_opportunities_latest.json/csv so downstream consumers
        can consume it independently without re-filtering jobs_latest.

        Args:
            all_jobs: The full merged job list (general + tutoring)
            run_stats: Stats dict from the tutoring run

        Returns:
            dict with 'json', 'csv', 'count'
        """
        opportunities = [
            job for job in all_jobs
            if (
                job.get('vertical') == 'tutoring'
                and job.get('is_remote', False)
                and job.get('poster_type', 'unknown') != 'teacher'
                and job.get('poster_type', 'unknown') != 'institution'
            )
        ]

        stats = run_stats.copy()
        stats['total'] = len(opportunities)
        stats['filter'] = 'vertical=tutoring AND is_remote=True AND poster_type!=teacher'

        json_path = self.export_to_json(
            opportunities, stats, filename='tutoring_opportunities_latest.json'
        )
        csv_path = self.export_to_csv(
            opportunities, filename='tutoring_opportunities_latest.csv'
        )

        return {'json': json_path, 'csv': csv_path, 'count': len(opportunities)}

    def export_tutoring_stem_opportunities(self, all_jobs: list, run_stats: dict) -> dict:
        """
        Export the STEM tutoring opportunities slice: vertical=tutoring, is_remote=True,
        poster_type not teacher/institution, and subject_category in STEM buckets.

        Args:
            all_jobs: The full merged job list (general + tutoring)
            run_stats: Stats dict from the tutoring run

        Returns:
            dict with 'json', 'csv', 'count'
        """
        stem_categories = TutoringPreFilter.STEM_SUBJECT_CATEGORIES
        opportunities = [
            job for job in all_jobs
            if (
                job.get('vertical') == 'tutoring'
                and job.get('is_remote', False)
                and job.get('poster_type', 'unknown') not in ('teacher', 'institution')
                and job.get('subject_category') in stem_categories
            )
        ]

        stats = run_stats.copy()
        stats['total'] = len(opportunities)
        stats['filter'] = 'vertical=tutoring AND is_remote=True AND subject_category in STEM'

        json_path = self.export_to_json(
            opportunities, stats, filename='tutoring_stem_opportunities_latest.json'
        )
        csv_path = self.export_to_csv(
            opportunities, filename='tutoring_stem_opportunities_latest.csv'
        )

        return {'json': json_path, 'csv': csv_path, 'count': len(opportunities)}

    def export_archive_snapshot(self, jobs, stats, filename_prefix):
        """
        Export timestamped archive snapshots without overwriting latest files.
        History is not updated for archive snapshots to avoid duplicate history writes.

        Args:
            jobs: List of job dictionaries
            stats: Statistics dictionary
            filename_prefix: Prefix for archive files (e.g., jobs, remote_jobs)

        Returns:
            Dictionary with paths to archived files
        """
        archive_dir = self.output_dir / 'archive'
        archive_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        json_filename = f"archive/{filename_prefix}_{timestamp}.json"
        csv_filename = f"archive/{filename_prefix}_{timestamp}.csv"
        json_path = self.output_dir / json_filename
        csv_path = self.output_dir / csv_filename

        self.export_to_json(jobs, stats, filename=json_filename, update_history=False)
        self.export_to_csv(jobs, filename=csv_filename)

        return {'json': json_path, 'csv': csv_path}

    def export_remote_only(self, jobs, stats, filename_prefix='remote_jobs'):
        """
        Export only remote jobs to separate files
        
        Args:
            jobs: List of job dictionaries
            stats: Statistics dictionary
            filename_prefix: Prefix for the output files
        
        Returns:
            Dictionary with paths to exported files
        """
        remote_jobs = [
            job for job in jobs
            if job.get('is_remote', False) and job.get('poster_type', 'unknown') != 'employee'
        ]
        
        # Update stats for remote-only export
        remote_stats = stats.copy()
        remote_stats['total'] = len(remote_jobs)
        remote_stats['on_site_high'] = 0
        remote_stats['on_site_medium'] = 0
        remote_stats['on_site_low'] = 0
        
        json_path = self.export_to_json(
            remote_jobs, 
            remote_stats, 
            filename=f'{filename_prefix}_{self.timestamp}.json'
        )
        csv_path = self.export_to_csv(
            remote_jobs, 
            filename=f'{filename_prefix}_{self.timestamp}.csv'
        )
        
        return {
            'json': json_path,
            'csv': csv_path,
            'count': len(remote_jobs)
        }
    
    def create_summary_report(self, stats, filename=None):
        """
        Create a human-readable summary report
        
        Args:
            stats: Statistics dictionary
            filename: Custom filename (optional)
        
        Returns:
            Path to the report file
        """
        if filename is None:
            filename = f'summary_{self.timestamp}.txt'
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("JOB SCRAPING ANALYSIS SUMMARY\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Export Date: {self.date_str}\n")
            f.write(f"Analysis Mode: {'🤖 LLM-Enhanced' if stats.get('llm_used', False) else '📚 NLP-Only'}\n")
            f.write(f"Total Jobs Analyzed: {stats['total']}\n\n")
            
            f.write("-"*80 + "\n")
            f.write("CLASSIFICATION BREAKDOWN\n")
            f.write("-"*80 + "\n\n")
            
            f.write("Initial Classification:\n")
            f.write(f"  📍 ON-SITE HIGH:   {stats.get('on_site_high', 0)} jobs\n")
            f.write(f"  📍 ON-SITE MEDIUM: {stats.get('on_site_medium', 0)} jobs\n")
            f.write(f"  📍 ON-SITE LOW:    {stats.get('on_site_low', 0)} jobs\n")
            f.write(f"  🏠 REMOTE HIGH:    {stats.get('remote_high', 0)} jobs\n")
            f.write(f"  🏠 REMOTE MEDIUM:  {stats.get('remote_medium', 0)} jobs\n")
            f.write(f"  🏠 REMOTE LOW:     {stats.get('remote_low', 0)} jobs\n\n")
            
            f.write(f"🔄 Re-analyzed with Semantic Model: {stats.get('reanalyzed', 0)} jobs\n")
            f.write(f"📄 Full Descriptions Fetched: {stats.get('full_description_fetched', 0)} jobs\n\n")
            
            # Calculate final counts
            total_on_site = stats.get('final_on_site', 0)
            total_remote = stats.get('final_remote', 0)
            
            f.write("-"*80 + "\n")
            f.write("FINAL RESULTS\n")
            f.write("-"*80 + "\n\n")
            f.write(f"  📍 ON-SITE: {total_on_site} jobs ({total_on_site/stats['total']*100:.1f}%)\n")
            f.write(f"  🏠 REMOTE:  {total_remote} jobs ({total_remote/stats['total']*100:.1f}%)\n\n")
            
            f.write("="*80 + "\n")
        
        return filepath
    
    def get_export_summary(self):
        """
        Get a summary of all export files in the output directory
        
        Returns:
            Dictionary with file information
        """
        files = {
            'json': list(self.output_dir.glob('*.json')),
            'csv': list(self.output_dir.glob('*.csv')),
            'txt': list(self.output_dir.glob('*.txt'))
        }
        
        summary = {
            'export_directory': str(self.output_dir.absolute()),
            'total_files': sum(len(f) for f in files.values()),
            'by_type': {k: len(v) for k, v in files.items()},
            'latest_files': {
                'json': self.output_dir / 'jobs_latest.json',
                'csv': self.output_dir / 'jobs_latest.csv'
            }
        }
        
        return summary

    def cleanup_old_history(self, days=30):
        """Remove jobs from history that haven't been seen in N days"""
        history = self.load_job_history()
        seen_urls = history.get('seen_urls', {})

        cutoff = datetime.now() - timedelta(days=days)
        original_count = len(seen_urls)

        history['seen_urls'] = {
            url: data for url, data in seen_urls.items()
            if datetime.strptime(data.get('last_seen', '2000-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S') > cutoff
        }

        removed = original_count - len(history['seen_urls'])

        if removed > 0:
            try:
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
            except IOError as e:
                print(f"⚠️  Could not update history during cleanup: {e}")

        return removed
