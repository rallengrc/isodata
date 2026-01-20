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
from urllib.parse import urljoin, urlparse, unquote
import requests
from bs4 import BeautifulSoup
import sys
import time

# Try to import Selenium for JavaScript-rendered pages
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class NYISOExcelDownloader:
    """Downloads ICAP Market Report Excel files from NYISO website."""
    
    BASE_URL = "https://www.nyiso.com"
    ICAP_MARKET_PAGE = f"{BASE_URL}/installed-capacity-market"
    SEARCH_URL = f"{BASE_URL}/search"
    
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
    
    def find_excel_links(self, url: str, debug: bool = True, save_html: bool = False) -> List[Tuple[str, str]]:
        """
        Find all ICAP Market Report Excel file links on a page.
        
        Args:
            url: URL to scrape
            debug: Enable debug output
            
        Returns:
            List of (url, filename) tuples
        """
        excel_links = []
        
        try:
            print(f"Fetching page: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            if debug:
                print(f"  Response status: {response.status_code}")
                print(f"  Response headers: Content-Type = {response.headers.get('Content-Type', 'N/A')}")
                print(f"  Response size: {len(response.content):,} bytes")
            
            # Try to handle encoding better
            try:
                # Try to decode with UTF-8 first
                content = response.content.decode('utf-8', errors='replace')
            except:
                # Fallback to latin-1
                content = response.content.decode('latin-1', errors='replace')
            
            # Save HTML for debugging if requested
            if save_html:
                html_file = self.download_dir.parent / f"debug_page_{url.replace('https://', '').replace('http://', '').replace('/', '_')}.html"
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                if debug:
                    print(f"  Saved HTML to: {html_file}")
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # DEBUG: Count all links
            all_links = soup.find_all('a', href=True)
            if debug:
                print(f"  Found {len(all_links)} total links on page")
            
            # DEBUG: Show all links that might be relevant
            relevant_links = []
            excel_candidates = []
            
            # Find all links
            for link in all_links:
                href = link['href']
                text = link.get_text(strip=True)
                
                # Check for any Excel files
                if '.xlsx' in href.lower() or '.xls' in href.lower():
                    excel_candidates.append((href, text))
                    if debug:
                        print(f"  DEBUG: Excel candidate - href: {href}, text: '{text}'")
                
                # Check for ICAP/Market/Report keywords
                href_lower = href.lower()
                text_lower = text.lower()
                if any(keyword in href_lower or keyword in text_lower for keyword in ['icap', 'market', 'report', 'capacity', 'auction']):
                    relevant_links.append((href, text))
                    if debug and len(relevant_links) <= 20:  # Limit output
                        print(f"  DEBUG: Relevant link - href: {href}, text: '{text[:50]}'")
            
            if debug:
                print(f"  Found {len(excel_candidates)} Excel file candidates")
                print(f"  Found {len(relevant_links)} relevant links (ICAP/Market/Report/Capacity/Auction)")
            
            # Process Excel candidates
            for href, text in excel_candidates:
                # Make absolute URL
                if href.startswith('http'):
                    full_url = href
                else:
                    full_url = urljoin(url, href)
                
                # Check if it matches ICAP Market Report pattern
                filename = Path(urlparse(full_url).path).name
                
                # More lenient matching - check for ICAP or Market in filename or path
                is_icap_file = (
                    self.EXCEL_PATTERN.search(filename) or 
                    ('icap' in filename.lower() and 'market' in filename.lower()) or
                    ('icap' in full_url.lower() and 'market' in full_url.lower()) or
                    ('icap' in filename.lower() and 'report' in filename.lower())
                )
                
                if is_icap_file:
                    excel_links.append((full_url, filename))
                    print(f"  ✓ Found Excel file: {filename} (from {href})")
                elif debug:
                    print(f"  DEBUG: Excel file rejected - filename: {filename}, href: {href}")
            
            # Also check for direct document links (NYISO uses /documents/ paths)
            # Look for links to /documents/ directories
            document_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/documents/' in href or '/document/' in href:
                    document_links.append(href)
            
            if debug:
                print(f"  Found {len(document_links)} document directory links")
            
            # Try to fetch document pages and look for Excel files
            for href in document_links[:10]:  # Limit to first 10 to avoid too many requests
                if href.startswith('http'):
                    doc_url = href
                else:
                    doc_url = urljoin(url, href)
                
                if debug:
                    print(f"  DEBUG: Checking document directory: {doc_url}")
                
                # Recursively search document pages (but limit depth)
                try:
                    doc_response = self.session.get(doc_url, timeout=30)
                    if doc_response.status_code == 200:
                        doc_soup = BeautifulSoup(doc_response.content, 'html.parser')
                        doc_excel_links = doc_soup.find_all('a', href=True)
                        
                        if debug:
                            print(f"    Found {len(doc_excel_links)} links in document directory")
                        
                        for doc_link in doc_excel_links:
                            doc_href = doc_link['href']
                            doc_text = doc_link.get_text(strip=True)
                            
                            if '.xlsx' in doc_href.lower() or '.xls' in doc_href.lower():
                                if debug:
                                    print(f"    DEBUG: Excel in documents - href: {doc_href}, text: '{doc_text[:50]}'")
                                
                                if doc_href.startswith('http'):
                                    full_url = doc_href
                                else:
                                    full_url = urljoin(doc_url, doc_href)
                                
                                filename = Path(urlparse(full_url).path).name
                                
                                # More lenient matching
                                is_icap_file = (
                                    self.EXCEL_PATTERN.search(filename) or 
                                    'icap' in filename.lower() or
                                    'icap' in full_url.lower() or
                                    'icap' in doc_text.lower()
                                )
                                
                                if is_icap_file:
                                    excel_links.append((full_url, filename))
                                    print(f"  ✓ Found Excel file in documents: {filename} (from {doc_href})")
                except Exception as e:
                    if debug:
                        print(f"    DEBUG: Error accessing document directory {doc_url}: {e}")
                    # Skip if we can't access the document page
                    pass
            
            # DEBUG: Also check for iframes or embedded content that might contain links
            if debug:
                iframes = soup.find_all('iframe')
                print(f"  Found {len(iframes)} iframes (may contain dynamic content)")
                
                # Check for script tags that might contain URLs
                scripts = soup.find_all('script')
                script_urls = []
                for script in scripts:
                    if script.string:
                        # Look for URLs in script content
                        url_matches = re.findall(r'https?://[^\s"\'<>]+', script.string)
                        script_urls.extend(url_matches)
                
                if script_urls:
                    print(f"  Found {len(script_urls)} URLs in script tags (showing first 5):")
                    for script_url in script_urls[:5]:
                        if 'icap' in script_url.lower() or 'market' in script_url.lower():
                            print(f"    DEBUG: Relevant script URL: {script_url}")
            
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
        
        return excel_links
    
    def _get_selenium_driver(self, headless: bool = True):
        """Create and return a Selenium WebDriver instance."""
        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium is required for JavaScript-rendered pages. "
                "Install it with: pip install selenium webdriver-manager"
            )
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    
    def find_excel_links_from_search(self, query: str = "ICAP market report", debug: bool = True, save_html: bool = False, delta: int = 200, start: int = 1) -> List[Tuple[str, str]]:
        """
        Find Excel files by searching NYISO's search page.
        
        Args:
            query: Search query string
            debug: Enable debug output
            save_html: Save HTML pages for inspection
            delta: Number of results per page (default: 200)
            start: Starting result number for pagination (default: 1)
            
        Returns:
            List of (url, filename) tuples
        """
        excel_links = []
        
        try:
            # Construct search URL with delta and start parameters
            search_url = f"{self.SEARCH_URL}?q={query.replace(' ', '+')}&sort=&delta={delta}&start={start}"
            
            if debug:
                print(f"\nSearching NYISO: {search_url}")
            
            # Try using Selenium for JavaScript-rendered pages
            if SELENIUM_AVAILABLE:
                if debug:
                    print("  Using Selenium to render JavaScript content...")
                
                driver = None
                try:
                    driver = self._get_selenium_driver(headless=True)
                    driver.get(search_url)
                    
                    # Wait for search results to load (look for links or result containers)
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, "a"))
                        )
                        # Give it a bit more time for dynamic content
                        time.sleep(2)
                    except:
                        if debug:
                            print("  Warning: Timeout waiting for page elements")
                    
                    # Get the rendered HTML
                    content = driver.page_source
                    
                    if debug:
                        print(f"  Rendered page size: {len(content):,} bytes")
                    
                    # Save HTML for debugging
                    if save_html:
                        html_file = self.download_dir.parent / f"debug_search_{query.replace(' ', '_')}.html"
                        with open(html_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                        if debug:
                            print(f"  Saved rendered HTML to: {html_file}")
                    
                    soup = BeautifulSoup(content, 'html.parser')
                    
                finally:
                    if driver:
                        driver.quit()
            
            else:
                # Fallback to regular HTTP request
                if debug:
                    print("  Selenium not available, using HTTP request (may not work for JS pages)...")
                    print("  Install Selenium for full support: pip install selenium webdriver-manager")
                
                response = self.session.get(search_url, timeout=30, allow_redirects=True)
                
                # Handle 202 (Accepted) - might need to wait or follow redirect
                if response.status_code == 202:
                    if debug:
                        print(f"  Received 202 (Accepted) - page requires JavaScript")
                        print(f"  Install Selenium to handle JavaScript-rendered pages")
                    
                    # Check for Location header
                    if 'Location' in response.headers:
                        redirect_url = response.headers['Location']
                        if debug:
                            print(f"  Following redirect to: {redirect_url}")
                        response = self.session.get(redirect_url, timeout=30, allow_redirects=True)
                    else:
                        # Wait a bit and retry
                        time.sleep(2)
                        response = self.session.get(search_url, timeout=30, allow_redirects=True)
                
                response.raise_for_status()
                
                if debug:
                    print(f"  Response status: {response.status_code}")
                    print(f"  Response size: {len(response.content):,} bytes")
                    if response.status_code != 200:
                        print(f"  Warning: Unexpected status code {response.status_code}")
                
                # Handle encoding
                try:
                    content = response.content.decode('utf-8', errors='replace')
                except:
                    content = response.content.decode('latin-1', errors='replace')
                
                # Save HTML for debugging
                if save_html:
                    html_file = self.download_dir.parent / f"debug_search_{query.replace(' ', '_')}.html"
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    if debug:
                        print(f"  Saved search HTML to: {html_file}")
                
                soup = BeautifulSoup(content, 'html.parser')
            
            # Check if page is empty or has very little content
            if len(content) < 100:
                if debug:
                    print(f"  Warning: Page content is very small ({len(content)} bytes)")
                    print(f"  This might indicate JavaScript-loaded content")
                    print(f"  Checking for JSON data or API endpoints in page...")
                
                # Look for JSON data in script tags that might contain search results
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        # Look for JSON data structures
                        if 'documents' in script.string.lower() or 'search' in script.string.lower():
                            if debug:
                                print(f"    Found potential data in script tag")
                                # Try to extract URLs from script
                                url_matches = re.findall(r'https?://[^\s"\'<>)]+', script.string)
                                if url_matches:
                                    if debug:
                                        print(f"    Found {len(url_matches)} URLs in script")
                                    for url_match in url_matches[:10]:  # Show first 10
                                        if 'icap' in url_match.lower() or 'market' in url_match.lower():
                                            if debug:
                                                print(f"      Potential URL: {url_match[:100]}")
            
            # Find all links in search results
            all_links = soup.find_all('a', href=True)
            
            if debug:
                print(f"  Found {len(all_links)} total links in search results")
                
                # Also check for data attributes that might contain URLs
                elements_with_data = soup.find_all(attrs={'data-url': True})
                if elements_with_data:
                    print(f"  Found {len(elements_with_data)} elements with data-url attributes")
                    for elem in elements_with_data[:5]:
                        data_url = elem.get('data-url', '')
                        if 'icap' in data_url.lower() or 'market' in data_url.lower():
                            print(f"    Data URL: {data_url[:100]}")
            
            # Look for Excel files in search results
            # Search results might be in various structures - check common patterns
            excel_candidates = []
            
            for link in all_links:
                href = link['href']
                text = link.get_text(strip=True)
                
                # Check if it's an Excel file
                if '.xlsx' in href.lower() or '.xls' in href.lower():
                    excel_candidates.append((href, text, link))
                    if debug:
                        print(f"  DEBUG: Excel candidate - href: {href}, text: '{text[:80]}'")
                
                # Also check link text for ICAP Market Report indicators
                text_lower = text.lower()
                if ('.xlsx' in text_lower or '.xls' in text_lower) and ('icap' in text_lower or 'market' in text_lower):
                    if (href, text, link) not in excel_candidates:
                        excel_candidates.append((href, text, link))
                        if debug:
                            print(f"  DEBUG: Excel candidate (from text) - href: {href}, text: '{text[:80]}'")
            
            if debug:
                print(f"  Found {len(excel_candidates)} Excel file candidates in search results")
            
            # Also check for links in data attributes or other attributes
            for link in all_links:
                # Check data-url, data-href, or other URL attributes
                for attr in ['data-url', 'data-href', 'data-link', 'href', 'data-fileurl', 'data-download']:
                    attr_value = link.get(attr)
                    if attr_value and ('.xlsx' in attr_value.lower() or '.xls' in attr_value.lower()):
                        if (attr_value, link.get_text(strip=True), link) not in excel_candidates:
                            excel_candidates.append((attr_value, link.get_text(strip=True), link))
                            if debug:
                                print(f"  DEBUG: Excel candidate (from {attr}) - href: {attr_value}, text: '{link.get_text(strip=True)[:80]}'")
            
            # Also check for div/span elements that might contain document links
            # Some sites use divs with onclick handlers instead of <a> tags
            for elem in soup.find_all(['div', 'span', 'li'], class_=re.compile(r'result|item|document|file', re.I)):
                onclick = elem.get('onclick', '')
                if onclick and ('.xlsx' in onclick.lower() or '.xls' in onclick.lower()):
                    # Try to extract URL from onclick
                    url_match = re.search(r'["\']([^"\']*\.xlsx?[^"\']*)["\']', onclick, re.I)
                    if url_match:
                        url_from_onclick = url_match.group(1)
                        text = elem.get_text(strip=True)
                        if (url_from_onclick, text, elem) not in excel_candidates:
                            excel_candidates.append((url_from_onclick, text, elem))
                            if debug:
                                print(f"  DEBUG: Excel candidate (from onclick) - href: {url_from_onclick}, text: '{text[:80]}'")
            
            if debug:
                print(f"  Total Excel candidates after checking attributes: {len(excel_candidates)}")
            
            # Process Excel candidates
            for href, text, link in excel_candidates:
                # Make absolute URL
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('//'):
                    full_url = 'https:' + href
                elif href.startswith('/'):
                    full_url = self.BASE_URL + href
                else:
                    full_url = urljoin(self.SEARCH_URL, href)
                
                # Extract filename
                filename = Path(urlparse(full_url).path).name
                
                # Handle NYISO document URLs that might have query parameters or paths
                # NYISO URLs often look like: /documents/20142/12345/File-Name.xlsx/guid?t=timestamp
                # Or: /documents/20142/1410927/ICAP%20Market%20Report%20-%20November%202014.xls/5f4d21c7-f530-88de-5da6-00dcb863e1e7
                # We need to extract the actual filename
                if '/documents/' in full_url:
                    # Try to extract filename from path
                    # URL decode first
                    decoded_url = unquote(full_url)
                    path_parts = decoded_url.split('/')
                    
                    # Look for parts with .xlsx or .xls
                    for i, part in enumerate(path_parts):
                        if '.xlsx' in part.lower() or '.xls' in part.lower():
                            # This should be the filename
                            filename = part.split('?')[0]  # Remove query params
                            # URL decode the filename
                            filename = unquote(filename)
                            break
                    
                    # If we still don't have a good filename, try the part before the GUID
                    if not filename or len(filename) < 5:
                        for i, part in enumerate(path_parts):
                            if '.xlsx' in part.lower() or '.xls' in part.lower():
                                # The filename might be in this part or the previous one
                                if i > 0:
                                    potential_name = path_parts[i-1] + '/' + part
                                    if '.xlsx' in potential_name.lower() or '.xls' in potential_name.lower():
                                        filename = part.split('?')[0]
                                        filename = unquote(filename)
                                        break
                
                # If filename is still a GUID or unclear, try to get it from link text
                if not filename or len(filename) < 5 or filename.startswith('?'):
                    # Try to extract from text
                    text_match = re.search(r'([^/]+\.xlsx?)', text, re.IGNORECASE)
                    if text_match:
                        filename = text_match.group(1)
                    else:
                        # Use a sanitized version of the text
                        filename = re.sub(r'[^\w\s.-]', '', text)[:100] + '.xlsx'
                
                # Check if it's an ICAP Market Report file
                filename_lower = filename.lower()
                url_lower = full_url.lower()
                text_lower = text.lower()
                
                is_icap_file = (
                    'icap' in filename_lower and ('market' in filename_lower or 'report' in filename_lower) or
                    'icap' in url_lower and ('market' in url_lower or 'report' in url_lower) or
                    'icap' in text_lower and ('market' in text_lower or 'report' in text_lower) or
                    self.EXCEL_PATTERN.search(filename) or
                    self.EXCEL_PATTERN.search(text)
                )
                
                if is_icap_file:
                    excel_links.append((full_url, filename))
                    print(f"  ✓ Found Excel file: {filename} (from search)")
                    if debug:
                        print(f"    URL: {full_url}")
                        print(f"    Link text: {text[:100]}")
                elif debug:
                    print(f"  DEBUG: Excel file rejected - filename: {filename}, href: {href}")
            
            # Also check for search result containers that might have download links
            # Look for common search result patterns
            result_containers = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'result|search|item|document', re.I))
            
            if debug:
                print(f"  Found {len(result_containers)} potential search result containers")
            
            for container in result_containers:
                # Look for download links within containers
                container_links = container.find_all('a', href=True)
                for link in container_links:
                    href = link['href']
                    if '.xlsx' in href.lower() or '.xls' in href.lower():
                        if href.startswith('http'):
                            full_url = href
                        else:
                            full_url = urljoin(self.SEARCH_URL, href)
                        
                        filename = Path(urlparse(full_url).path).name
                        
                        # Check if we already have this file
                        if not any(existing_url == full_url for existing_url, _ in excel_links):
                            text = link.get_text(strip=True)
                            text_lower = text.lower()
                            filename_lower = filename.lower()
                            
                            if 'icap' in filename_lower or 'icap' in text_lower:
                                excel_links.append((full_url, filename))
                                if debug:
                                    print(f"  ✓ Found Excel file in container: {filename}")
            
        except requests.RequestException as e:
            print(f"Error searching NYISO: {e}")
        except Exception as e:
            print(f"Error parsing search results: {e}")
            if debug:
                import traceback
                traceback.print_exc()
        
        return excel_links
    
    def extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        """
        Extract date from filename like "ICAP Market Report - December 2023.xlsx"
        or "ICAP-Market-Report-July-2024.xlsx"
        
        Args:
            filename: Excel filename
            
        Returns:
            datetime object or None if can't parse
        """
        # Month name mapping (full names only for regex matching)
        months = {
            'january': 1,
            'february': 2,
            'march': 3,
            'april': 4,
            'may': 5,
            'june': 6,
            'july': 7,
            'august': 8,
            'september': 9,
            'october': 10,
            'november': 11,
            'december': 12,
        }
        
        filename_lower = filename.lower()
        
        # Try to find month name and year using regex
        # Pattern: month name (full) followed by year (4 digits)
        # Handles: "December 2023", "December-2023", "December_2023", etc.
        month_year_pattern = re.compile(
            r'(january|february|march|april|may|june|july|august|september|october|november|december)[\s\-_]+(\d{4})',
            re.IGNORECASE
        )
        
        match = month_year_pattern.search(filename)
        if match:
            month_name = match.group(1).lower()
            year = int(match.group(2))
            
            if month_name in months:
                month_num = months[month_name]
                try:
                    return datetime(year, month_num, 1)
                except ValueError:
                    pass
        
        # Fallback: try the original pattern (for formats like "ICAP-Market-Report-July-2024")
        match = self.EXCEL_PATTERN.search(filename)
        if match:
            # Extract year from pattern
            year = int(match.group(1))
            
            # Find month name in filename
            for month_name, month_num in months.items():
                if month_name in filename_lower:
                    try:
                        return datetime(year, month_num, 1)
                    except ValueError:
                        continue
        
        # Last fallback: try to extract year from filename (default to January)
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
        
        # Check date filters (year + month comparison)
        if start_date or end_date:
            file_date = self.extract_date_from_filename(filename)
            if file_date:
                # Compare full dates (year + month, day set to 1 for comparison)
                # Normalize dates to first of month for comparison
                file_date_normalized = datetime(file_date.year, file_date.month, 1)
                start_date_normalized = datetime(start_date.year, start_date.month, 1) if start_date else None
                end_date_normalized = datetime(end_date.year, end_date.month, 1) if end_date else None
                
                if start_date_normalized:
                    if file_date_normalized < start_date_normalized:
                        return False, f"File date {file_date.strftime('%B %Y')} before start date {start_date.strftime('%B %Y')}"
                if end_date_normalized:
                    if file_date_normalized > end_date_normalized:
                        return False, f"File date {file_date.strftime('%B %Y')} after end date {end_date.strftime('%B %Y')}"
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
        additional_urls: Optional[List[str]] = None,
        debug: bool = True,
        save_html: bool = False,
        search_query: str = 'ICAP market report',
        no_search: bool = False,
        manual_urls: Optional[List[str]] = None,
        delta: int = 200,
        start: int = 1
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
        # Store manual URLs
        self._manual_urls = manual_urls
        
        print("=" * 80)
        print("NYISO ICAP Market Report Excel Downloader")
        print("=" * 80)
        print(f"Download directory: {self.download_dir}")
        if start_date:
            print(f"Start date filter: {start_date.strftime('%Y-%m-%d')}")
        if end_date:
            print(f"End date filter: {end_date.strftime('%Y-%m-%d')}")
        if not no_search:
            print(f"Search query: {search_query}")
        if manual_urls:
            print(f"Manual URLs provided: {len(manual_urls)}")
        print()
        
        # URLs to search
        urls_to_search = [self.ICAP_MARKET_PAGE]
        
        if additional_urls:
            urls_to_search.extend(additional_urls)
        
        # Find all Excel links from main page
        all_links = []
        
        # Process manually provided URLs first
        if self._manual_urls:
            print(f"\n{'='*80}")
            print("Processing manually provided URLs...")
            print(f"{'='*80}")
            for manual_url in self._manual_urls:
                print(f"\nProcessing manual URL: {manual_url}")
                # Extract filename from URL
                parsed = urlparse(manual_url)
                path_parts = unquote(parsed.path).split('/')
                
                # Find the filename in the path
                filename = None
                for part in path_parts:
                    if '.xlsx' in part.lower() or '.xls' in part.lower():
                        filename = part.split('?')[0]
                        filename = unquote(filename)
                        break
                
                if not filename:
                    # Generate a filename from the URL
                    filename = f"ICAP_Market_Report_{parsed.path.split('/')[-1]}.xlsx"
                
                # Check if it's an ICAP file
                if 'icap' in filename.lower() or 'icap' in manual_url.lower():
                    all_links.append((manual_url, filename))
                    print(f"  ✓ Added manual URL: {filename}")
                elif debug:
                    print(f"  DEBUG: Manual URL doesn't match ICAP pattern: {filename}")
        for url in urls_to_search:
            print(f"\nSearching URL: {url}")
            links = self.find_excel_links(url, debug=debug, save_html=save_html)
            print(f"  Found {len(links)} Excel files from this URL")
            all_links.extend(links)
        
        # Search NYISO search page for ICAP Market Reports (unless disabled)
        if not no_search:
            print(f"\n{'='*80}")
            print("Searching NYISO search page for ICAP Market Reports...")
            print(f"{'='*80}")
            search_links = self.find_excel_links_from_search(
                query=search_query,
                debug=debug,
                save_html=save_html,
                delta=delta,
                start=start
            )
            print(f"  Found {len(search_links)} Excel files from search")
            all_links.extend(search_links)
            
            # Try additional search queries
            additional_queries = [
                "ICAP Market Report Excel",
                "ICAP Market Report xlsx",
                "capacity market report",
            ]
            
            for query in additional_queries:
                if debug:
                    print(f"\nTrying additional search query: {query}")
                try:
                    query_links = self.find_excel_links_from_search(
                        query=query,
                        debug=debug,
                        save_html=save_html,
                        delta=delta,
                        start=start
                    )
                    if query_links:
                        print(f"  Found {len(query_links)} Excel files from query '{query}'")
                        all_links.extend(query_links)
                except Exception as e:
                    if debug:
                        print(f"  Error with query '{query}': {e}")
        
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
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable verbose debug output'
    )
    
    parser.add_argument(
        '--no-debug',
        action='store_true',
        help='Disable debug output (default is enabled)'
    )
    
    parser.add_argument(
        '--save-html',
        action='store_true',
        help='Save fetched HTML pages to files for inspection'
    )
    
    parser.add_argument(
        '--search-query',
        type=str,
        default='ICAP market report',
        help='Search query to use on NYISO search page (default: "ICAP market report")'
    )
    
    parser.add_argument(
        '--no-search',
        action='store_true',
        help='Skip searching NYISO search page (only use direct page scraping)'
    )
    
    parser.add_argument(
        '--manual-urls',
        nargs='*',
        help='Manually provide document URLs to download (e.g., from search results page)'
    )
    
    parser.add_argument(
        '--delta',
        type=int,
        default=200,
        help='Number of search results per page (default: 200)'
    )
    
    parser.add_argument(
        '--start',
        type=int,
        default=1,
        help='Starting result number for pagination (default: 1)'
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
    
    # Determine debug mode
    debug_mode = not args.no_debug if args.no_debug else (args.debug if args.debug else True)
    
    # Create downloader and run
    downloader = NYISOExcelDownloader(args.download_dir)
    result = downloader.download_all(
        start_date=start_date,
        end_date=end_date,
        force=args.force,
        additional_urls=args.additional_urls,
        debug=debug_mode,
        save_html=args.save_html,
        search_query=args.search_query,
        no_search=args.no_search,
        manual_urls=args.manual_urls,
        delta=args.delta,
        start=args.start
    )
    
    # Exit with error code if downloads failed
    if result['failed'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
