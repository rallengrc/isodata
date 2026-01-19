#!/usr/bin/env python3
"""
Download NYISO ICAP Market Report Excel files from the NYISO website.

This script:
- Scrapes the NYISO Installed Capacity Market page
- Finds all ICAP Market Report Excel files (.xlsx)
- Downloads them to data/excel/nyiso/
- Supports filtering by date range or specific months
- Skips files that already exist (unless --force is used)
"""

import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class NYISOExcelDownloader:
    """Downloads ICAP Market Report Excel files from NYISO website."""
    
    BASE_URL = "https://www.nyiso.com"
    ICAP_MARKET_PAGE = f"{BASE_URL}/installed-capacity-market"
    
    # Pattern to match ICAP Market Report Excel files
    EXCEL_PATTERN = re.compile(
        r'ICAP-Market-Report[-_](?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-_]?(\d{4})\.xlsx',
        re.IGNORECASE
    )
    
    def __init__(self, download_dir: Path):
        """
        Initialize downloader.
        
        Args:
            download_dir: Directory to save downloaded Excel files
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def find_excel_links(self, url: str) -> List[Tuple[str, str]]:
        """
        Find all ICAP Market Report Excel file links on a page.
        
        Args:
            url: URL to scrape
            
        Returns:
            List of (url, filename) tuples
        """
        excel_links = []
        
        try:
            print(f"Fetching page: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True)
                
                # Check if it's an Excel file
                if '.xlsx' in href.lower() or '.xls' in href.lower():
                    # Make absolute URL
                    if href.startswith('http'):
                        full_url = href
                    else:
                        full_url = urljoin(url, href)
                    
                    # Check if it matches ICAP Market Report pattern
                    filename = Path(urlparse(full_url).path).name
                    if self.EXCEL_PATTERN.search(filename) or 'icap' in filename.lower() and 'market' in filename.lower():
                        excel_links.append((full_url, filename))
                        print(f"  Found Excel file: {filename}")
            
            # Also check for direct document links (NYISO uses /documents/ paths)
            # Look for links to /documents/ directories
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/documents/' in href:
                    # Try to fetch this page and look for Excel files
                    if href.startswith('http'):
                        doc_url = href
                    else:
                        doc_url = urljoin(url, href)
                    
                    # Recursively search document pages (but limit depth)
                    try:
                        doc_response = self.session.get(doc_url, timeout=30)
                        if doc_response.status_code == 200:
                            doc_soup = BeautifulSoup(doc_response.content, 'html.parser')
                            for doc_link in doc_soup.find_all('a', href=True):
                                doc_href = doc_link['href']
                                if '.xlsx' in doc_href.lower() or '.xls' in doc_href.lower():
                                    if doc_href.startswith('http'):
                                        full_url = doc_href
                                    else:
                                        full_url = urljoin(doc_url, doc_href)
                                    
                                    filename = Path(urlparse(full_url).path).name
                                    if self.EXCEL_PATTERN.search(filename) or 'icap' in filename.lower():
                                        excel_links.append((full_url, filename))
                                        print(f"  Found Excel file in documents: {filename}")
                    except Exception as e:
                        # Skip if we can't access the document page
                        pass
            
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
        
        return excel_links
    
    def extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        """
        Extract date from filename like "ICAP-Market-Report-July-2024.xlsx"
        
        Args:
            filename: Excel filename
            
        Returns:
            datetime object or None if can't parse
        """
        # Month name mapping
        months = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12,
        }
        
        # Try to extract month and year
        match = self.EXCEL_PATTERN.search(filename)
        if match:
            # Extract year from pattern
            year = int(match.group(1))
            
            # Find month name
            filename_lower = filename.lower()
            for month_name, month_num in months.items():
                if month_name in filename_lower:
                    try:
                        return datetime(year, month_num, 1)
                    except ValueError:
                        continue
        
        # Fallback: try to extract year from filename
        year_match = re.search(r'(\d{4})', filename)
        if year_match:
            year = int(year_match.group(1))
            # Default to January if we can't find month
            return datetime(year, 1, 1)
        
        return None
    
    def should_download(
        self,
        filename: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        force: bool = False
    ) -> Tuple[bool, str]:
        """
        Determine if a file should be downloaded.
        
        Args:
            filename: Excel filename
            start_date: Optional start date filter
            end_date: Optional end date filter
            force: Force download even if file exists
            
        Returns:
            (should_download, reason) tuple
        """
        file_path = self.download_dir / filename
        
        # Check if file already exists
        if file_path.exists() and not force:
            return False, "File already exists"
        
        # Check date filters
        if start_date or end_date:
            file_date = self.extract_date_from_filename(filename)
            if file_date:
                if start_date and file_date < start_date:
                    return False, f"File date {file_date.strftime('%Y-%m')} before start date"
                if end_date and file_date > end_date:
                    return False, f"File date {file_date.strftime('%Y-%m')} after end date"
            else:
                # If we can't parse date but filters are set, skip it
                if start_date or end_date:
                    return False, "Cannot parse date from filename"
        
        return True, "OK"
    
    def download_file(self, url: str, filename: str) -> bool:
        """
        Download an Excel file.
        
        Args:
            url: URL to download from
            filename: Local filename to save as
            
        Returns:
            True if successful, False otherwise
        """
        file_path = self.download_dir / filename
        
        try:
            print(f"  Downloading: {filename}")
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('Content-Type', '').lower()
            if 'excel' not in content_type and 'spreadsheet' not in content_type and 'octet-stream' not in content_type:
                print(f"    Warning: Unexpected content type: {content_type}")
            
            # Download file
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = file_path.stat().st_size
            print(f"    ✓ Downloaded {filename} ({file_size:,} bytes)")
            return True
            
        except requests.RequestException as e:
            print(f"    ✗ Error downloading {filename}: {e}")
            if file_path.exists():
                file_path.unlink()  # Remove partial download
            return False
        except Exception as e:
            print(f"    ✗ Error saving {filename}: {e}")
            if file_path.exists():
                file_path.unlink()  # Remove partial download
            return False
    
    def download_all(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        force: bool = False,
        additional_urls: Optional[List[str]] = None
    ) -> dict:
        """
        Download all ICAP Market Report Excel files.
        
        Args:
            start_date: Optional start date filter (only download files from this date onwards)
            end_date: Optional end date filter (only download files up to this date)
            force: Force re-download even if file exists
            additional_urls: Additional URLs to search for Excel files
            
        Returns:
            Dictionary with download statistics
        """
        print("=" * 80)
        print("NYISO ICAP Market Report Excel Downloader")
        print("=" * 80)
        print(f"Download directory: {self.download_dir}")
        if start_date:
            print(f"Start date filter: {start_date.strftime('%Y-%m-%d')}")
        if end_date:
            print(f"End date filter: {end_date.strftime('%Y-%m-%d')}")
        print()
        
        # URLs to search
        urls_to_search = [self.ICAP_MARKET_PAGE]
        if additional_urls:
            urls_to_search.extend(additional_urls)
        
        # Find all Excel links
        all_links = []
        for url in urls_to_search:
            links = self.find_excel_links(url)
            all_links.extend(links)
        
        # Remove duplicates
        seen = set()
        unique_links = []
        for url, filename in all_links:
            if filename not in seen:
                seen.add(filename)
                unique_links.append((url, filename))
        
        print(f"\nFound {len(unique_links)} unique Excel files")
        print()
        
        # Download files
        downloaded = 0
        skipped = 0
        failed = 0
        
        for url, filename in unique_links:
            should_dl, reason = self.should_download(filename, start_date, end_date, force)
            
            if not should_dl:
                print(f"  Skipping {filename}: {reason}")
                skipped += 1
                continue
            
            if self.download_file(url, filename):
                downloaded += 1
            else:
                failed += 1
        
        print()
        print("=" * 80)
        print(f"Download Summary:")
        print(f"  Downloaded: {downloaded}")
        print(f"  Skipped: {skipped}")
        print(f"  Failed: {failed}")
        print(f"  Total: {len(unique_links)}")
        print("=" * 80)
        
        return {
            'downloaded': downloaded,
            'skipped': skipped,
            'failed': failed,
            'total': len(unique_links)
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Download NYISO ICAP Market Report Excel files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all available Excel files
  python scripts/download_nyiso_excel.py
  
  # Download only files from 2024 onwards
  python scripts/download_nyiso_excel.py --start-date 2024-01-01
  
  # Download files for a specific year
  python scripts/download_nyiso_excel.py --start-date 2023-01-01 --end-date 2023-12-31
  
  # Force re-download existing files
  python scripts/download_nyiso_excel.py --force
        """
    )
    
    parser.add_argument(
        '--download-dir',
        type=Path,
        default=PROJECT_ROOT / 'data' / 'excel' / 'nyiso',
        help='Directory to save downloaded Excel files (default: data/excel/nyiso)'
    )
    
    parser.add_argument(
        '--start-date',
        type=str,
        help='Only download files from this date onwards (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        help='Only download files up to this date (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-download even if file already exists'
    )
    
    parser.add_argument(
        '--additional-urls',
        nargs='*',
        help='Additional URLs to search for Excel files'
    )
    
    args = parser.parse_args()
    
    # Parse dates
    start_date = None
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid start date format: {args.start_date}. Use YYYY-MM-DD")
            sys.exit(1)
    
    end_date = None
    if args.end_date:
        try:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid end date format: {args.end_date}. Use YYYY-MM-DD")
            sys.exit(1)
    
    # Create downloader and run
    downloader = NYISOExcelDownloader(args.download_dir)
    result = downloader.download_all(
        start_date=start_date,
        end_date=end_date,
        force=args.force,
        additional_urls=args.additional_urls
    )
    
    # Exit with error code if downloads failed
    if result['failed'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
