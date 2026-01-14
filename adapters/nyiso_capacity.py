"""
NYISO ICAP (Installed Capacity) adapter.

Fetches capacity market data from NYISO's public ICAP portal:
- Monthly auctions
- Strip auctions (capability periods)
- Spot auctions (rare)

Capability Periods:
- Summer: May 1 - October 31 (May, Jun, Jul, Aug, Sep, Oct)
- Winter: November 1 - April 30 (Nov, Dec, Jan, Feb, Mar, Apr)
"""

from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
import pandas as pd
import pytz
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re

from adapters.base import ISOAdapter
from canonical.schemas import MarketPriceFact
from canonical.normalize import normalize_capacity_price
from canonical.temporal_utils import datetime_to_yyyymm, get_capability_period, get_delivery_months_for_strip, yyyymm_to_datetime


class NYISOCapacityAdapter(ISOAdapter):
    """
    NYISO ICAP capacity market adapter.
    
    Fetches data from NYISO's public ICAP portal:
    - Monthly auction results
    - Strip auction results (capability periods)
    - Spot auction results (rare)
    """
    
    BASE_URL = "https://icappublic.nyiso.com/ucap/public"
    
    # ICAP zones (same as energy zones)
    ICAP_ZONES = [
        "NYCA", "NYC", "LI", "G-J", "WEST", "CENTRL", "NORTH",
        "MILLWD", "DUNWOD", "CAPITL", "HQ", "HUDVL", "MHKVL", "NPX", "OH"
    ]
    
    def __init__(self):
        """Initialize NYISO ICAP adapter."""
        super().__init__("NYISO")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_capacity_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        nodes: Optional[List[str]] = None,
        auction_type: Optional[str] = None,  # "MONTHLY", "STRIP", "SPOT", or None for all
    ) -> List[MarketPriceFact]:
        """
        Fetch NYISO ICAP capacity prices.
        
        IMPORTANT: Monthly auctions can cover multiple delivery months. We iterate
        by auction_month, and each auction returns multiple records (one per delivery month).
        
        Args:
            start_date: Start date (delivery period start)
            end_date: End date (delivery period end)
            nodes: Optional list of zones to fetch
            auction_type: Optional filter by auction type
        
        Returns:
            List of normalized MarketPriceFact objects
        """
        facts = []
        
        # Determine which delivery months we need
        current_date = start_date
        delivery_months_needed = set()
        
        while current_date <= end_date:
            yyyymm = datetime_to_yyyymm(current_date)
            delivery_months_needed.add(yyyymm)
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1, day=1)
        
        print(f"Fetching ICAP data for delivery months: {sorted(delivery_months_needed)}")
        
        # For monthly auctions, we need to determine which auction_months to fetch
        # Monthly auctions typically run 1-2 months before delivery
        # For now, we'll fetch auctions for the delivery months themselves
        # (The auction_month in NYISO is the month the auction is FOR, not when it runs)
        
        # Fetch monthly auctions
        if auction_type is None or auction_type.upper() == "MONTHLY":
            # For each delivery month, fetch the auction that covers it
            # In NYISO, the auction_month is typically the same as the first delivery month
            # in a capability period, or the month being auctioned
            auction_months_to_fetch = set()
            
            for delivery_month in sorted(delivery_months_needed):
                # The auction_month is typically the same as delivery_month for monthly auctions
                # But we need to be smarter - one auction can cover multiple months
                # For now, try the delivery month itself
                auction_months_to_fetch.add(delivery_month)
            
            for auction_month in sorted(auction_months_to_fetch):
                monthly_facts = self._fetch_monthly_auction(auction_month, season_id=None, nodes=nodes)
                facts.extend(monthly_facts)
        
        # Fetch strip auctions (capability periods)
        if auction_type is None or auction_type.upper() == "STRIP":
            # Determine which capability periods are needed
            capability_periods = set()
            for delivery_month in delivery_months_needed:
                period = get_capability_period(delivery_month)
                if period:
                    # For strip auctions, we need the year of the capability period start
                    year = int(delivery_month[:4])
                    if period == "WINTER":
                        # Winter starts in November, so if delivery is Jan-Apr, year is previous
                        month = int(delivery_month[4:6])
                        if month <= 4:
                            year = year - 1
                    capability_periods.add((str(year), period))
            
            for year, period in capability_periods:
                strip_facts = self._fetch_strip_auction(year, period, nodes)
                facts.extend(strip_facts)
        
        # Note: Spot auctions are very rare and would need special handling
        # For now, we skip them
        
        return facts
    
    def _fetch_monthly_auction(
        self,
        auction_month: str,  # YYYYMM - the month the auction is for (e.g., "202311")
        season_id: Optional[str] = None,  # Optional season ID from NYISO
        nodes: Optional[List[str]] = None,
    ) -> List[MarketPriceFact]:
        """
        Fetch monthly ICAP auction results.
        
        IMPORTANT: One auction can produce multiple records - one per delivery month
        in the capability period. The HTML table shows all delivery months in columns.
        
        Args:
            auction_month: YYYYMM when auction is for (e.g., "202311")
            season_id: Optional NYISO season ID (e.g., "702409" for Winter 2023-2024)
            nodes: Optional list of zones to fetch
        
        Returns:
            List of MarketPriceFact objects (one per delivery_month per zone)
        """
        facts = []
        
        try:
            # Parse auction month to get month/year for form submission
            year = int(auction_month[:4])
            month = int(auction_month[4:6])
            month_year_str = f"{month:02d}/{year}"  # Format: "11/2023"
            
            # URL for monthly auction detail page
            url = f"{self.BASE_URL}/auc_view_monthly_detail.do"
            
            # POST request with form data
            # Need to determine season_id if not provided
            # For now, we'll try to fetch the page and parse the season dropdown
            form_data = {
                'month': month_year_str,
            }
            
            if season_id:
                form_data['seasonId'] = season_id
            
            response = self.session.post(url, data=form_data, timeout=30)
            response.raise_for_status()
            
            # Parse HTML response
            parsed_data = self._parse_monthly_auction_html(response.text, auction_month)
            
            if not parsed_data:
                print(f"  No data found for auction month {auction_month}")
                return facts
            
            # Create MarketPriceFact objects for each (zone, delivery_month) combination
            for zone_name, delivery_data in parsed_data['zones'].items():
                # Filter by nodes if specified
                if nodes and zone_name not in nodes:
                    continue
                
                for delivery_month, values in delivery_data.items():
                    # Skip if no price (0.00 or missing)
                    if not values.get('price') or values['price'] == 0.0:
                        continue
                    
                    # Calculate start_time and end_time for this delivery month
                    delivery_dt = yyyymm_to_datetime(delivery_month, tz=pytz.UTC)
                    # Start of month
                    start_time = delivery_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    # End of month (last day)
                    if delivery_dt.month == 12:
                        end_time = delivery_dt.replace(year=delivery_dt.year + 1, month=1, day=1) - timedelta(seconds=1)
                    else:
                        end_time = delivery_dt.replace(month=delivery_dt.month + 1, day=1) - timedelta(seconds=1)
                    
                    fact = normalize_capacity_price(
                        iso_code=self.iso_code,
                        node_id=zone_name,
                        node_type="ZONE",
                        start_time=start_time,
                        end_time=end_time,
                        price=values['price'],
                        product="MONTHLY",
                        zone=zone_name,
                        auction_id=f"{auction_month}_{zone_name}",
                        source_url=url,
                        auction_time=None,  # Will use auction_month string
                        capability_period=parsed_data['capability_period'],
                        auction_type="MONTHLY",
                        awarded_mw=values.get('awarded_mw'),
                        posted_at=parsed_data.get('posted_at'),
                        season_id=parsed_data.get('season_id'),
                    )
                    
                    # Override auction_month (it's already set correctly from auction_month param)
                    # But ensure it matches
                    if fact.auction_month != auction_month:
                        fact.auction_month = auction_month
                    
                    facts.append(fact)
            
            print(f"  Fetched {len(facts)} records for auction month {auction_month}")
            
        except Exception as e:
            print(f"Error fetching monthly auction for {auction_month}: {e}")
            import traceback
            traceback.print_exc()
        
        return facts
    
    def _fetch_strip_auction(
        self,
        year: str,  # Year as string (e.g., "2024")
        capability_period: str,  # "SUMMER" or "WINTER"
        nodes: Optional[List[str]] = None,
    ) -> List[MarketPriceFact]:
        """
        Fetch strip auction results for a capability period.
        
        Strip auctions cover all months in a capability period:
        - Summer: May-Oct
        - Winter: Nov-Apr (crosses year boundary)
        
        Args:
            year: Year (e.g., "2024")
            capability_period: "SUMMER" or "WINTER"
            nodes: Optional list of zones to fetch
        
        Returns:
            List of MarketPriceFact objects (one per delivery month in period)
        """
        facts = []
        
        try:
            # URL for strip auction selection
            url = f"{self.BASE_URL}/auc_view_strip_selection.do"
            
            # For now, return empty list - will implement scraping in next step
            print(f"  Strip auction for {year} {capability_period}: Not yet implemented (scraping required)")
            
        except Exception as e:
            print(f"Error fetching strip auction for {year} {capability_period}: {e}")
        
        return facts
    
    def _parse_monthly_auction_html(self, html: str, auction_month: str) -> Optional[Dict]:
        """
        Parse HTML from NYISO ICAP monthly auction detail page.
        
        Expected HTML structure:
        - Header with season name (e.g., "Winter 2023-2024")
        - Header with auction month (e.g., "Auction Starting 11/2023")
        - Header with posted date (e.g., "Posted Date: 10/13/2023 10:00 AM")
        - Table with columns for each delivery month (Nov, Dec, Jan, Feb, Mar, Apr)
        - Rows for each zone with "Awarded (MW)" and "Price ($/kW - Month)" rows
        
        Args:
            html: HTML content from auction page
            auction_month: YYYYMM string for the auction month (for validation)
        
        Returns:
            Dictionary with parsed data:
            {
                'auction_month': '202311',
                'capability_period': 'WINTER',
                'season_id': '702409',
                'posted_at': datetime(...),
                'zones': {
                    'NYC': {
                        '202311': {'price': 13.04, 'awarded_mw': 656.9},
                        '202312': {'price': 13.04, 'awarded_mw': 545.0},
                        ...
                    },
                    ...
                }
            }
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        result = {
            'auction_month': auction_month,
            'capability_period': None,
            'season_id': None,
            'posted_at': None,
            'zones': {},
        }
        
        # Extract season_id from JavaScript (if present)
        # Look for: ICAP.dsTO.seasonId = '702409';
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                season_match = re.search(r"ICAP\.dsTO\.seasonId\s*=\s*['\"](\d+)['\"]", script.string)
                if season_match:
                    result['season_id'] = season_match.group(1)
                    break
        
        # Extract header information
        # Look for: "Winter 2023-2024 Monthly Auction Results for UCAP, Auction Starting 11/2023 Posted Date: 10/13/2023 10:00 AM"
        header_text = None
        header_elements = soup.find_all(['th', 'td'], class_='inputLabel')
        for elem in header_elements:
            text = elem.get_text(strip=True)
            if 'Monthly Auction Results' in text or 'Auction Starting' in text:
                header_text = text
                break
        
        if header_text:
            # Extract capability period (SUMMER or WINTER)
            if 'Winter' in header_text:
                result['capability_period'] = 'WINTER'
            elif 'Summer' in header_text:
                result['capability_period'] = 'SUMMER'
            
            # Extract posted date
            posted_match = re.search(r'Posted Date:\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)', header_text)
            if posted_match:
                month, day, year, hour, minute, am_pm = posted_match.groups()
                hour = int(hour)
                if am_pm.upper() == 'PM' and hour != 12:
                    hour += 12
                elif am_pm.upper() == 'AM' and hour == 12:
                    hour = 0
                try:
                    result['posted_at'] = pytz.timezone('US/Eastern').localize(
                        datetime(int(year), int(month), int(day), hour, int(minute))
                    ).astimezone(pytz.UTC)
                except Exception as e:
                    print(f"Warning: Could not parse posted date: {e}")
        
        # Find the main data table
        # Look for table with month headers (Nov, Dec, Jan, etc.)
        tables = soup.find_all('table')
        data_table = None
        
        for table in tables:
            # Check if this table has month headers
            headers = table.find_all('th')
            month_headers = [h.get_text(strip=True) for h in headers]
            # Look for month abbreviations
            month_abbrevs = ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct']
            if any(month in ' '.join(month_headers) for month in month_abbrevs):
                data_table = table
                break
        
        if not data_table:
            print("Warning: Could not find data table in HTML")
            return None
        
        # Extract delivery month columns
        # Find header row with month names
        header_row = None
        for row in data_table.find_all('tr'):
            cells = row.find_all('th')
            if cells:
                cell_texts = [c.get_text(strip=True) for c in cells]
                if any(month in ' '.join(cell_texts) for month in month_abbrevs):
                    header_row = row
                    break
        
        if not header_row:
            print("Warning: Could not find header row with month names")
            return None
        
        # Map month abbreviations to YYYYMM format
        # Need to determine year based on capability period and auction month
        auction_year = int(auction_month[:4])
        auction_month_num = int(auction_month[4:6])
        
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
            'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
            'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        
        # Extract column indices and delivery months
        # Header structure: [empty cell, Nov, Dec, Jan, Feb, Mar, Apr]
        # Data structure: [label, value1, value2, value3, value4, value5, value6]
        header_cells = header_row.find_all('th')
        delivery_month_cols = {}  # {column_index: 'YYYYMM'}
        
        for idx, cell in enumerate(header_cells):
            text = cell.get_text(strip=True)
            for abbrev, month_num in month_map.items():
                if abbrev in text:
                    # Determine year based on capability period
                    if result['capability_period'] == 'WINTER':
                        # Winter: Nov-Dec of auction year, Jan-Apr of next year
                        if month_num >= 11:
                            year = auction_year
                        else:
                            year = auction_year + 1
                    else:  # SUMMER
                        # Summer: May-Oct of auction year
                        year = auction_year
                    
                    # Column index matches between header and data rows
                    delivery_month_cols[idx] = f"{year}{month_num:02d}"
                    break
        
        if not delivery_month_cols:
            print("Warning: Could not extract delivery month columns")
            return None
        
        # Parse zone data
        # Structure: Zone name row (colspan="7") -> "Awarded (MW)" row (label in first cell, data in rest) -> "Price ($/kW - Month)" row (label in first cell, data in rest)
        current_zone = None
        
        rows = data_table.find_all('tr')
        i = 0
        while i < len(rows):
            row = rows[i]
            cells = row.find_all(['td', 'th'])
            if not cells:
                i += 1
                continue
            
            first_cell_text = cells[0].get_text(strip=True) if cells else ""
            
            # Check if this is a zone name row (has colspan="7")
            if cells[0].get('colspan') == '7':
                zone_name = first_cell_text.strip()
                # Skip summary rows
                if zone_name and zone_name not in ['Total ROS Awarded (MW)', 'Total Awarded (MW)', 
                                                    'ROS Price Paid By Bidders (Weighted Avg.)']:
                    # Normalize zone name (remove "Locality" suffix if present)
                    zone_name = zone_name.replace(' Locality', '').strip()
                    if zone_name:  # Make sure we have a valid zone name
                        current_zone = zone_name
                        if current_zone not in result['zones']:
                            result['zones'][current_zone] = {}
            
            # Check if this is an "Awarded (MW)" row (label in first cell, data in subsequent cells)
            elif 'Awarded (MW)' in first_cell_text and current_zone:
                # Parse awarded MW values from this row (skip first cell which is the label)
                for col_idx, delivery_month in delivery_month_cols.items():
                    # col_idx is 0-based from header, but we need to account for first cell being label
                    # Header row: [empty, Nov, Dec, Jan, Feb, Mar, Apr] -> indices 1-6
                    # Data row: [Awarded (MW), value1, value2, ...] -> indices 1-6
                    data_cell_idx = col_idx  # This should match since header starts at index 1
                    if data_cell_idx < len(cells):
                        cell_text = cells[data_cell_idx].get_text(strip=True)
                        
                        if delivery_month not in result['zones'][current_zone]:
                            result['zones'][current_zone][delivery_month] = {}
                        
                        try:
                            value_text = cell_text.replace(',', '').strip()
                            if value_text and value_text != '-':
                                value = float(value_text)
                                result['zones'][current_zone][delivery_month]['awarded_mw'] = value
                        except (ValueError, AttributeError):
                            pass
            
            # Check if this is a "Price ($/kW - Month)" row (label in first cell, data in subsequent cells)
            elif ('Price ($/kW - Month)' in first_cell_text or ('Price' in first_cell_text and '$/kW' in first_cell_text)) and current_zone:
                # Parse price values from this row (skip first cell which is the label)
                for col_idx, delivery_month in delivery_month_cols.items():
                    data_cell_idx = col_idx  # Should match header indices
                    if data_cell_idx < len(cells):
                        cell_text = cells[data_cell_idx].get_text(strip=True)
                        
                        if delivery_month not in result['zones'][current_zone]:
                            result['zones'][current_zone][delivery_month] = {}
                        
                        try:
                            # Remove $ sign and commas
                            value_text = cell_text.replace('$', '').replace(',', '').strip()
                            if value_text and value_text != '-':
                                value = float(value_text)
                                result['zones'][current_zone][delivery_month]['price'] = value
                        except (ValueError, AttributeError):
                            pass
            
            i += 1
        
        # Validate we got some data
        if not result['zones']:
            print("Warning: No zone data extracted from HTML")
            return None
        
        return result
    
    def _parse_excel_report(self, file_path: Path) -> List[dict]:
        """
        Parse NYISO ICAP Market Report Excel file.
        
        Args:
            file_path: Path to Excel file
        
        Returns:
            List of dictionaries with auction data
        """
        # Read Excel file
        df = pd.read_excel(file_path, sheet_name=None)  # Read all sheets
        
        results = []
        
        # Parse based on Excel structure
        # This will be implemented based on actual Excel format
        return results
    
    def fetch_nodes(self) -> List[dict]:
        """
        Fetch available NYISO ICAP zones.
        
        Returns:
            List of zone dictionaries
        """
        zones = []
        for zone_id in self.ICAP_ZONES:
            zones.append({
                "node_id": zone_id,
                "node_type": "ZONE",
                "zone": zone_id,
                "name": zone_id,  # Could expand with full names
            })
        return zones

