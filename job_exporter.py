"""
Job Results Exporter - Export and update job analysis results
Supports JSON and CSV formats with incremental updates
"""

import json
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path


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
    
    def export_to_json(self, jobs, stats, filename=None):
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
        
        history_stats = self.get_history_stats()
        export_data = {
            'metadata': {
                'export_date': self.date_str,
                'total_jobs': stats['total'],
                'analysis_mode': 'LLM-Enhanced' if stats.get('llm_used', False) else 'NLP-Only',
                'history_stats': history_stats,
                'employee_posts_filtered': stats.get('employee_posts_filtered', 0)
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
            'source',
            'vertical',
            'poster_type',
            'subject_category',
            'instruction_lang',
            'level',
            'classification',
            'confidence',
            'is_remote',
            'remote_confidence',
            'reasoning',
            'reason',
            'description_preview',
            'description_source',
            'was_reanalyzed',
            'url'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for job in jobs:
                # Prepare row data
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
                    'remote_confidence': job.get('remote_confidence', 'N/A'),
                    'reasoning': job.get('reasoning', 'N/A'),
                    'reason': job.get('reason', 'N/A'),
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
        remote_jobs = [job for job in jobs if job.get('is_remote', False)]
        
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

    def load_job_history(self) -> dict:
        """Load job history from disk."""
        history_path = self.output_dir / 'job_history.json'
        if history_path.exists():
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {'seen_urls': {}, 'last_update': None}
        return {'seen_urls': {}, 'last_update': None}

    def update_job_history(self, jobs: list) -> dict:
        """Update job history with a new batch of jobs."""
        history = self.load_job_history()
        seen_urls = history.get('seen_urls', {})
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for job in jobs:
            url = job.get('url')
            if not url or url == 'N/A':
                continue

            entry = seen_urls.get(url)
            if entry:
                entry['last_seen'] = now
                entry['appearances'] = entry.get('appearances', 1) + 1
                entry['title'] = job.get('title', entry.get('title', ''))
                entry['is_remote'] = job.get('is_remote', entry.get('is_remote', False))
            else:
                seen_urls[url] = {
                    'first_seen': now,
                    'last_seen': now,
                    'title': job.get('title', ''),
                    'is_remote': job.get('is_remote', False),
                    'appearances': 1,
                }

        history['seen_urls'] = seen_urls
        history['last_update'] = now

        history_path = self.output_dir / 'job_history.json'
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

        return history

    def cleanup_old_history(self, days: int = 90) -> dict:
        """Remove history entries older than N days."""
        history = self.load_job_history()
        seen_urls = history.get('seen_urls', {})
        cutoff = datetime.now() - timedelta(days=days)

        cleaned = {}
        for url, entry in seen_urls.items():
            last_seen = entry.get('last_seen')
            try:
                last_seen_dt = datetime.strptime(last_seen, '%Y-%m-%d %H:%M:%S')
            except Exception:
                last_seen_dt = None
            if last_seen_dt and last_seen_dt >= cutoff:
                cleaned[url] = entry

        history['seen_urls'] = cleaned
        history['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        history_path = self.output_dir / 'job_history.json'
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

        return history

    def get_history_stats(self) -> dict:
        """Summarize history stats for metadata."""
        history = self.load_job_history()
        seen_urls = history.get('seen_urls', {})
        total_seen = len(seen_urls)
        remote_seen = sum(1 for entry in seen_urls.values() if entry.get('is_remote'))

        return {
            'total_jobs_seen': total_seen,
            'remote_jobs_seen': remote_seen,
            'last_update': history.get('last_update')
        }
