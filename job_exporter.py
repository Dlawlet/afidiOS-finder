"""
Job Results Exporter - Export and update job analysis results
Supports JSON and CSV formats with incremental updates
Enhanced with job history tracking
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
                history['seen_urls'][url] = {
                    'first_seen': history['seen_urls'].get(url, {}).get('first_seen', self.date_str),
                    'last_seen': self.date_str,
                    'title': job.get('title'),
                    'is_remote': job.get('is_remote')
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
        
        # Update history
        self.update_job_history(jobs)
        history_stats = self.get_history_stats()
        
        export_data = {
            'metadata': {
                'export_date': self.date_str,
                'total_jobs': stats['total'],
                'analysis_mode': 'LLM-Enhanced' if stats.get('llm_used', False) else 'NLP-Only',
                'history_stats': history_stats
            },
            'statistics': stats,
            'jobs': jobs
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
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
                # Prepare row data
                row = {
                    'id': job.get('id', 'N/A'),
                    'title': job.get('title', 'N/A'),
                    'location': job.get('location', 'N/A'),
                    'category': job.get('category', 'N/A'),
                    'price': job.get('price', 'N/A'),
                    'poster': job.get('poster', 'N/A'),
                    'date_posted': job.get('date_posted', 'N/A'),
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
