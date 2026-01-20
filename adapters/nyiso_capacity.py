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
            # IMPORTANT: One auction can cover multiple delivery months in a capability period.
            # We need to group delivery months by capability period and find the auction_month
            # that covers them. Typically, the auction_month is the first month of the capability period.
            
            # Group delivery months by capability period
            capability_period_auctions = {}  # {(capability_period, start_year): [delivery_months]}
            
            for delivery_month in sorted(delivery_months_needed):
                period = get_capability_period(delivery_month)
                if period:
                    # Determine the auction month (typically first month of capability period)
                    year = int(delivery_month[:4])
                    month_num = int(delivery_month[4:6])
                    
                    if period == "WINTER":
                        # Winter: Nov-Apr, auction_month is typically November
                        if month_num >= 11:
                            auction_year = year
                            auction_month = f"{year}11"
                        else:
                            # Jan-Apr: auction was in previous year's November
                            auction_year = year - 1
                            auction_month = f"{year - 1}11"
                    else:  # SUMMER
                        # Summer: May-Oct, auction_month is typically May
                        auction_year = year
                        auction_month = f"{year}05"
                    
                    # Group by (period, auction_year) to avoid duplicate fetches
                    key = (period, auction_year)
                    if key not in capability_period_auctions:
                        capability_period_auctions[key] = {
                            'auction_month': auction_month,
                            'delivery_months': []
                        }
                    capability_period_auctions[key]['delivery_months'].append(delivery_month)
            
            # Fetch each unique auction (one auction can cover multiple delivery months)
            fetched_auctions = set()
            for key, info in capability_period_auctions.items():
                auction_month = info['auction_month']
                if auction_month not in fetched_auctions:
                    print(f"  Fetching auction {auction_month} (covers {len(info['delivery_months'])} delivery months)")
                    monthly_facts = self._fetch_monthly_auction(auction_month, season_id=None, nodes=nodes)
                    facts.extend(monthly_facts)
                    fetched_auctions.add(auction_month)
        
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
            
            # Step 1: GET the selection page to extract seasonId if not provided
            if not season_id:
                selection_url = f"{self.BASE_URL}/auc_view_monthly_detail.do"
                selection_response = self.session.get(selection_url, timeout=30)
                selection_response.raise_for_status()
                
                # Extract seasonId from JavaScript in the selection page
                selection_soup = BeautifulSoup(selection_response.text, 'html.parser')
                script_tags = selection_soup.find_all('script')
                for script in script_tags:
                    if script.string:
                        # Look for: ICAP.dsTO.seasonId = '702409';
                        season_match = re.search(r"ICAP\.dsTO\.seasonId\s*=\s*['\"](\d+)['\"]", script.string)
                        if season_match:
                            season_id = season_match.group(1)
                            print(f"  Extracted seasonId from selection page: {season_id}")
                            break
                
                # If still not found, try to find it by matching the auction month
                # Look for seasonId that matches the auction month in the JavaScript
                if not season_id:
                    # Try to find seasonId by looking for the month in the JavaScript
                    for script in script_tags:
                        if script.string and month_year_str in script.string:
                            # Look for seasonId near the month
                            season_match = re.search(r"ICAP\.dsTO\.seasonId\s*=\s*['\"](\d+)['\"]", script.string)
                            if season_match:
                                season_id = season_match.group(1)
                                print(f"  Extracted seasonId from month match: {season_id}")
                                break
            
            # Step 2: POST to detail page with month and seasonId
            url = f"{self.BASE_URL}/auc_view_monthly_detail.do"
            
            # Form data based on the HTML structure
            # The form needs: month, seasonId (if available), and display button
            form_data = {
                'month': month_year_str,
                'display': 'Display',  # The submit button value
            }
            
            if season_id:
                form_data['seasonId'] = season_id
            
            print(f"  POSTing to {url} with month={month_year_str}, seasonId={season_id}")
            response = self.session.post(url, data=form_data, timeout=30)
            response.raise_for_status()
            
            # Debug: Always save HTML for inspection
            debug_file = Path(f"debug_icap_{auction_month}.html")
            debug_file.write_text(response.text, encoding='utf-8')
            print(f"  Saved HTML response to: {debug_file}")
            
            # Check if we got the right page
            if 'Monthly Auction Summary' not in response.text and 'Monthly Auction Results' not in response.text:
                print(f"  Warning: Response doesn't contain expected content")
                print(f"  Response length: {len(response.text)} characters")
                print(f"  First 500 chars: {response.text[:500]}")
            
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
        
        IMPORTANT: Strip auctions have a different structure than monthly:
        - One price per zone for the ENTIRE capability period
        - We create one record per delivery month using the same price/awarded_mw
        - ROS data is formatted differently (summary rows at bottom)
        
        Args:
            year: Year (e.g., "2024")
            capability_period: "SUMMER" or "WINTER"
            nodes: Optional list of zones to fetch
        
        Returns:
            List of MarketPriceFact objects (one per delivery month in period per zone)
        """
        facts = []
        
        try:
            # Step 1: GET the selection page to extract seasonId
            selection_url = f"{self.BASE_URL}/auc_view_strip_selection.do"
            selection_response = self.session.get(selection_url, timeout=30)
            selection_response.raise_for_status()
            
            # Extract seasonId from JavaScript in the selection page
            selection_soup = BeautifulSoup(selection_response.text, 'html.parser')
            script_tags = selection_soup.find_all('script')
            season_id = None
            
            for script in script_tags:
                if script.string:
                    # Look for: ICAP.dsTO.seasonId = '702409';
                    season_match = re.search(r"ICAP\.dsTO\.seasonId\s*=\s*['\"](\d+)['\"]", script.string)
                    if season_match:
                        season_id = season_match.group(1)
                        print(f"  Extracted seasonId from strip selection page: {season_id}")
                        break
            
            if not season_id:
                print(f"  Warning: Could not extract seasonId for strip auction {year} {capability_period}")
                return facts
            
            # Step 2: POST to detail page with seasonId and capability period
            # Format capability period for form (e.g., "Winter 2023-2024")
            if capability_period == "WINTER":
                # Winter: Nov-Apr crosses year boundary
                # For year 2023, it's "Winter 2023-2024"
                season_str = f"Winter {year}-{int(year)+1}"
            else:  # SUMMER
                # Summer: May-Oct within same year
                season_str = f"Summer {year}"
            
            url = f"{self.BASE_URL}/auc_view_strip_detail.do"
            
            # Form data - strip auctions need seasonId and season selection
            form_data = {
                'seasonId': season_id,
                'season': season_str,  # e.g., "Winter 2023-2024"
                'display': 'Display',
            }
            
            print(f"  POSTing to {url} with seasonId={season_id}, season={season_str}")
            response = self.session.post(url, data=form_data, timeout=30)
            response.raise_for_status()
            
            # Debug: Save HTML for inspection
            debug_file = Path(f"debug_icap_strip_{year}_{capability_period}.html")
            debug_file.write_text(response.text, encoding='utf-8')
            print(f"  Saved HTML response to: {debug_file}")
            
            # Check if we got the right page
            if 'Strip Auction Summary' not in response.text and 'Strip Auction Results' not in response.text:
                print(f"  Warning: Response doesn't contain expected content")
                print(f"  Response length: {len(response.text)} characters")
            
            # Parse HTML response
            parsed_data = self._parse_strip_auction_html(response.text, year, capability_period)
            
            if not parsed_data:
                print(f"  No data found for strip auction {year} {capability_period}")
                return facts
            
            # Get all delivery months for this capability period
            # For strip auctions, we need to determine the auction month
            # Typically strip auctions run before the capability period starts
            # For Winter 2023-2024, auction might be in Oct 2023 (202310)
            # For Summer 2024, auction might be in Apr 2024 (202404)
            if capability_period == "WINTER":
                # Winter strip auction typically runs in October before the period
                auction_year = int(year)
                auction_month = f"{auction_year}10"  # October
            else:  # SUMMER
                # Summer strip auction typically runs in April before the period
                auction_month = f"{year}04"  # April
            
            # Get delivery months for the capability period (for calculating time range)
            delivery_months = get_delivery_months_for_strip(auction_month, capability_period)
            
            # Strip auctions: ONE record per zone (not per delivery month)
            # The price applies to ALL delivery months in the capability period
            # We use auction_month as delivery_month so all records go into one partition/file
            for zone_name, zone_data in parsed_data['zones'].items():
                # Filter by nodes if specified
                if nodes and zone_name not in nodes:
                    continue
                
                # Strip auctions have a single price/awarded_mw per zone (not per delivery month)
                price = zone_data.get('price')
                awarded_mw = zone_data.get('awarded_mw')
                
                # Skip if no price (0.00 or missing)
                if not price or price == 0.0:
                    continue
                
                # For strip auctions, use auction_month as delivery_month
                # This ensures all records go into one file (partitioned by auction_month)
                # The capability_period field indicates which months this price applies to
                delivery_month = auction_month
                
                # Calculate start_time and end_time for the capability period
                # Start: first delivery month of the period
                # End: last delivery month of the period
                delivery_months = get_delivery_months_for_strip(auction_month, capability_period)
                first_delivery = yyyymm_to_datetime(delivery_months[0], tz=pytz.UTC)
                last_delivery = yyyymm_to_datetime(delivery_months[-1], tz=pytz.UTC)
                
                # Start of first delivery month
                start_time = first_delivery.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                # End of last delivery month
                if last_delivery.month == 12:
                    end_time = last_delivery.replace(year=last_delivery.year + 1, month=1, day=1) - timedelta(seconds=1)
                else:
                    end_time = last_delivery.replace(month=last_delivery.month + 1, day=1) - timedelta(seconds=1)
                
                fact = normalize_capacity_price(
                    iso_code=self.iso_code,
                    node_id=zone_name,
                    node_type="ZONE",
                    start_time=start_time,
                    end_time=end_time,
                    price=price,
                    product="STRIP",
                    zone=zone_name,
                    auction_id=f"{auction_month}_STRIP_{zone_name}",
                    source_url=url,
                    auction_time=None,
                    capability_period=capability_period,
                    auction_type="STRIP",
                    awarded_mw=awarded_mw,
                    posted_at=parsed_data.get('posted_at'),
                    season_id=parsed_data.get('season_id'),
                )
                
                # Set auction_month and delivery_month (same for strip auctions)
                fact.auction_month = auction_month
                fact.delivery_month = delivery_month
                
                facts.append(fact)
            
            print(f"  Fetched {len(facts)} records for strip auction {year} {capability_period} (1 record per zone, applies to {len(delivery_months)} delivery months)")
            
        except Exception as e:
            print(f"Error fetching strip auction for {year} {capability_period}: {e}")
            import traceback
            traceback.print_exc()
        
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
        # The data is in a nested table structure, so we need to find the right one
        tables = soup.find_all('table')
        data_table = None
        
        for table in tables:
            # Check if this table has month headers in a <th> row
            # Look for a row with <th> elements containing month abbreviations
            rows = table.find_all('tr')
            for row in rows:
                headers = row.find_all('th')
                if headers:
                    month_headers = [h.get_text(strip=True) for h in headers]
                    month_abbrevs = ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct']
                    # Check if this row has month abbreviations (not just header text)
                    month_count = sum(1 for h in month_headers for month in month_abbrevs if month in h)
                    if month_count >= 3:  # At least 3 months found
                        data_table = table
                        break
            if data_table:
                break
        
        if not data_table:
            print("Warning: Could not find data table in HTML")
            return None
        
        # Extract delivery month columns
        # Find header row with month names
        # The header row has structure: [header text (index 0), Nov (index 1), Dec (index 2), ...]
        header_row = None
        for row in data_table.find_all('tr'):
            cells = row.find_all('th')
            if cells:
                cell_texts = [c.get_text(strip=True) for c in cells]
                # Check if this row contains month abbreviations (skip index 0 which is header text)
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
        # Header structure: [header text (index 0), Nov (index 1), Dec (index 2), Jan (index 3), Feb (index 4), Mar (index 5), Apr (index 6)]
        # Data structure: [label (index 0), Nov value (index 1), Dec value (index 2), ...]
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
                    # Index 0 is header text, months start at index 1
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
                # Skip summary rows (we'll handle ROS separately)
                if zone_name and zone_name not in ['Total ROS Awarded (MW)', 'Total Awarded (MW)', 
                                                    'ROS Price Paid By Bidders (Weighted Avg.)']:
                    # Normalize zone name (remove "Locality" suffix if present)
                    zone_name = zone_name.replace(' Locality', '').strip()
                    if zone_name:  # Make sure we have a valid zone name
                        current_zone = zone_name
                        if current_zone not in result['zones']:
                            result['zones'][current_zone] = {}
            
            # SPECIAL CASE: Parse ROS summary rows FIRST (before regular "Awarded (MW)" check)
            # "Total ROS Awarded (MW)" row - extract awarded_mw for ROS zone
            # This must be checked BEFORE the regular "Awarded (MW)" condition to avoid false matches
            if 'Total ROS Awarded (MW)' in first_cell_text and len(cells) >= 7:
                # Initialize ROS zone if not exists
                if 'ROS' not in result['zones']:
                    result['zones']['ROS'] = {}
                
                # Parse awarded MW values for ROS
                # cells[0] = label, cells[1] = Nov, cells[2] = Dec, etc.
                # delivery_month_cols maps header index to YYYYMM
                # Note: delivery_month_cols only contains indices 1-6 (months), not 0 (header text)
                for col_idx, delivery_month in delivery_month_cols.items():
                    # col_idx is 1-6 (months), which matches cells[1] through cells[6]
                    if col_idx < len(cells):
                        cell_text = cells[col_idx].get_text(strip=True)
                        
                        if delivery_month not in result['zones']['ROS']:
                            result['zones']['ROS'][delivery_month] = {}
                        
                        try:
                            value_text = cell_text.replace(',', '').strip()
                            if value_text and value_text != '-':
                                value = float(value_text)
                                result['zones']['ROS'][delivery_month]['awarded_mw'] = value
                        except (ValueError, AttributeError):
                            pass
            
            # SPECIAL CASE: "ROS Price Paid By Bidders (Weighted Avg.)" row - extract price for ROS zone
            # This must be checked BEFORE the regular "Price" condition to avoid false matches
            elif 'ROS Price Paid By Bidders' in first_cell_text or ('ROS Price' in first_cell_text and 'Weighted' in first_cell_text):
                # Initialize ROS zone if not exists
                if 'ROS' not in result['zones']:
                    result['zones']['ROS'] = {}
                
                # Parse price values for ROS
                # Same structure as awarded row
                for col_idx, delivery_month in delivery_month_cols.items():
                    # Skip index 0 (header text, not a month)
                    if col_idx == 0:
                        continue
                    # col_idx matches the cell index (1-6 for months)
                    if col_idx < len(cells):
                        cell_text = cells[col_idx].get_text(strip=True)
                        
                        if delivery_month not in result['zones']['ROS']:
                            result['zones']['ROS'][delivery_month] = {}
                        
                        try:
                            # Remove $ sign and commas
                            value_text = cell_text.replace('$', '').replace(',', '').strip()
                            if value_text and value_text != '-':
                                value = float(value_text)
                                result['zones']['ROS'][delivery_month]['price'] = value
                        except (ValueError, AttributeError):
                            pass
            
            # Check if this is an "Awarded (MW)" row (label in first cell, data in subsequent cells)
            # Must check for regular zones AFTER ROS rows to avoid false matches
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
    
    def _parse_strip_auction_html(
        self, 
        html: str, 
        year: str,
        capability_period: str
    ) -> Optional[Dict]:
        """
        Parse HTML from NYISO ICAP strip auction detail page.
        
        Strip auctions have a DIFFERENT structure than monthly auctions:
        - One price per zone for the ENTIRE capability period (not per delivery month)
        - Structure: Zone name -> "Awarded (MW)" row -> "Price ($/kW - Month)" row
        - ROS data is at the bottom with different labels:
          - "Total ROS Awarded (MW)" (single value, not per month)
          - "ROS Price Paid By Bidders (Weighted Avg.)" (single value)
        
        Expected HTML structure:
        - Header with season name (e.g., "Winter 2023-2024")
        - Header with "Strip Auction Results for UCAP, Auction Starting 11/2023"
        - Header with posted date (e.g., "Posted Date: 10/03/2023 10:02 AM")
        - Table with zone rows (NOT multiple delivery month columns)
        - Each zone has: "Awarded (MW)" and "Price ($/kW - Month)" rows
        - Summary rows at bottom: "Total ROS Awarded (MW)", "Total Awarded (MW)", "ROS Price Paid By Bidders (Weighted Avg.)"
        
        Args:
            html: HTML content from strip auction page
            year: Year as string (e.g., "2023")
            capability_period: "SUMMER" or "WINTER"
        
        Returns:
            Dictionary with parsed data:
            {
                'capability_period': 'WINTER',
                'season_id': '702409',
                'posted_at': datetime(...),
                'zones': {
                    'NYC': {'price': 12.90, 'awarded_mw': 580.4},
                    'G-J': {'price': 3.91, 'awarded_mw': 482.0},
                    'ROS': {'price': 3.829, 'awarded_mw': 1712.0},
                    ...
                }
            }
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        result = {
            'capability_period': capability_period,
            'season_id': None,
            'posted_at': None,
            'zones': {},
        }
        
        # Extract season_id from JavaScript (if present)
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                season_match = re.search(r"ICAP\.dsTO\.seasonId\s*=\s*['\"](\d+)['\"]", script.string)
                if season_match:
                    result['season_id'] = season_match.group(1)
                    break
        
        # Extract header information
        # Look for: "Winter 2023-2024 Strip Auction Results for UCAP, Auction Starting 11/2023 Posted Date: 10/03/2023 10:02 AM"
        header_text = None
        header_elements = soup.find_all(['th', 'td'], class_='inputLabel')
        for elem in header_elements:
            text = elem.get_text(strip=True)
            if 'Strip Auction Results' in text or 'Strip Auction Summary' in text:
                header_text = text
                break
        
        if header_text:
            # Extract capability period (SUMMER or WINTER) - should match input
            if 'Winter' in header_text:
                result['capability_period'] = 'WINTER'
            elif 'Summer' in header_text:
                result['capability_period'] = 'SUMMER'
            
            # Extract posted date
            posted_match = re.search(r'Posted Date:\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)', header_text)
            if posted_match:
                month, day, year_val, hour, minute, am_pm = posted_match.groups()
                hour = int(hour)
                if am_pm.upper() == 'PM' and hour != 12:
                    hour += 12
                elif am_pm.upper() == 'AM' and hour == 12:
                    hour = 0
                try:
                    result['posted_at'] = pytz.timezone('US/Eastern').localize(
                        datetime(int(year_val), int(month), int(day), hour, int(minute))
                    ).astimezone(pytz.UTC)
                except Exception as e:
                    print(f"Warning: Could not parse posted date: {e}")
        
        # Find the main data table
        # Strip auction table structure is simpler - no month columns, just zone rows
        tables = soup.find_all('table')
        data_table = None
        
        for table in tables:
            # Look for table with zone names (not month headers)
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    # Check if this row contains zone-like names (not month abbreviations)
                    first_cell = cells[0].get_text(strip=True) if cells else ""
                    # Zone names or "Awarded (MW)" / "Price" labels indicate data table
                    if any(keyword in first_cell for keyword in ['Locality', 'Awarded (MW)', 'Price ($/kW', 'Total ROS']):
                        data_table = table
                        break
            if data_table:
                break
        
        if not data_table:
            print("Warning: Could not find data table in HTML")
            return None
        
        # Parse zone data
        # Structure: Zone name row (colspan) -> "Awarded (MW)" row -> "Price ($/kW - Month)" row
        # Based on image description: Each zone has Awarded (MW) and Price ($/kW - Month) rows
        
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
            
            # Check if this is a zone name row (has colspan or is a zone name)
            if cells[0].get('colspan'):
                zone_name = first_cell_text.strip()
                # Skip summary rows (we'll handle ROS separately)
                if zone_name and zone_name not in ['Total ROS Awarded (MW)', 'Total Awarded (MW)', 
                                                    'ROS Price Paid By Bidders (Weighted Avg.)']:
                    # Normalize zone name (remove "Locality" suffix if present)
                    zone_name = zone_name.replace(' Locality', '').strip()
                    if zone_name:  # Make sure we have a valid zone name
                        current_zone = zone_name
                        if current_zone not in result['zones']:
                            result['zones'][current_zone] = {}
            
            # SPECIAL CASE: Parse ROS summary rows FIRST (before regular rows)
            # "Total ROS Awarded (MW)" row - extract awarded_mw for ROS zone
            # Strip auctions: ROS has a SINGLE value (not per delivery month)
            if 'Total ROS Awarded (MW)' in first_cell_text:
                # Initialize ROS zone if not exists
                if 'ROS' not in result['zones']:
                    result['zones']['ROS'] = {}
                
                # Strip auctions: ROS awarded MW is in the second cell (index 1)
                if len(cells) >= 2:
                    cell_text = cells[1].get_text(strip=True)
                    try:
                        value_text = cell_text.replace(',', '').strip()
                        if value_text and value_text != '-':
                            value = float(value_text)
                            result['zones']['ROS']['awarded_mw'] = value
                    except (ValueError, AttributeError):
                        pass
            
            # SPECIAL CASE: "ROS Price Paid By Bidders (Weighted Avg.)" row - extract price for ROS zone
            # Strip auctions: ROS price is a SINGLE value
            elif 'ROS Price Paid By Bidders' in first_cell_text or ('ROS Price' in first_cell_text and 'Weighted' in first_cell_text):
                # Initialize ROS zone if not exists
                if 'ROS' not in result['zones']:
                    result['zones']['ROS'] = {}
                
                # Strip auctions: ROS price is in the second cell (index 1)
                if len(cells) >= 2:
                    cell_text = cells[1].get_text(strip=True)
                    try:
                        # Remove $ sign and commas
                        value_text = cell_text.replace('$', '').replace(',', '').strip()
                        if value_text and value_text != '-':
                            value = float(value_text)
                            result['zones']['ROS']['price'] = value
                    except (ValueError, AttributeError):
                        pass
            
            # Check if this is an "Awarded (MW)" row for a regular zone
            elif 'Awarded (MW)' in first_cell_text and current_zone:
                # Strip auctions: Awarded MW is in the second cell (index 1)
                if len(cells) >= 2:
                    cell_text = cells[1].get_text(strip=True)
                    try:
                        value_text = cell_text.replace(',', '').strip()
                        if value_text and value_text != '-':
                            value = float(value_text)
                            result['zones'][current_zone]['awarded_mw'] = value
                    except (ValueError, AttributeError):
                        pass
            
            # Check if this is a "Price ($/kW - Month)" row for a regular zone
            elif ('Price ($/kW - Month)' in first_cell_text or ('Price' in first_cell_text and '$/kW' in first_cell_text)) and current_zone:
                # Strip auctions: Price is in the second cell (index 1)
                if len(cells) >= 2:
                    cell_text = cells[1].get_text(strip=True)
                    try:
                        # Remove $ sign and commas
                        value_text = cell_text.replace('$', '').replace(',', '').strip()
                        if value_text and value_text != '-':
                            value = float(value_text)
                            result['zones'][current_zone]['price'] = value
                    except (ValueError, AttributeError):
                        pass
            
            i += 1
        
        # Validate we got some data
        if not result['zones']:
            print("Warning: No zone data extracted from HTML")
            return None
        
        return result
    
    def _parse_excel_report(
        self, 
        file_path: Path,
        auction_types: Optional[List[str]] = None
    ) -> List[MarketPriceFact]:
        """
        Parse NYISO ICAP Market Report Excel file.
        
        Expected Excel structure:
        - Sheet "MCP Table": Market Clearing Prices by zone and auction type
        - Sheet "Monthly Auction Details": Detailed monthly auction results
        - Sheet "Strip Auction Details": Detailed strip auction results
        - Sheet "Spot Auction Details": Spot auction results (if present, rare)
        
        Args:
            file_path: Path to Excel file
            auction_types: Which auction types to parse (None = all: MONTHLY, STRIP, SPOT)
        
        Returns:
            List of MarketPriceFact objects
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {file_path}")
        
        facts = []
        source_url = str(file_path.absolute())  # Store absolute path as source URL
        
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            print(f"  Found {len(sheet_names)} sheets: {', '.join(sheet_names)}")
            
            # Parse MCP Table sheet (if present) - contains summary prices
            if 'MCP Table' in sheet_names or any('MCP' in name for name in sheet_names):
                mcp_sheet = 'MCP Table' if 'MCP Table' in sheet_names else [n for n in sheet_names if 'MCP' in n][0]
                print(f"  Parsing MCP Table from sheet: {mcp_sheet}")
                mcp_facts = self._parse_mcp_table(excel_file, mcp_sheet, auction_types, source_url)
                facts.extend(mcp_facts)
            
            # Parse Monthly Auction Details sheet
            monthly_sheets = [n for n in sheet_names if 'monthly' in n.lower() or 'monthly' in n.lower()]
            if monthly_sheets:
                for sheet_name in monthly_sheets:
                    print(f"  Parsing Monthly Auction Details from sheet: {sheet_name}")
                    monthly_facts = self._parse_monthly_details(excel_file, sheet_name, auction_types, source_url)
                    facts.extend(monthly_facts)
            
            # Parse Strip Auction Details sheet
            strip_sheets = [n for n in sheet_names if 'strip' in n.lower() or 'capability' in n.lower()]
            if strip_sheets:
                for sheet_name in strip_sheets:
                    print(f"  Parsing Strip Auction Details from sheet: {sheet_name}")
                    strip_facts = self._parse_strip_details(excel_file, sheet_name, auction_types, source_url)
                    facts.extend(strip_facts)
            
            # Parse Spot Auction Details sheet (rare)
            spot_sheets = [n for n in sheet_names if 'spot' in n.lower()]
            if spot_sheets:
                for sheet_name in spot_sheets:
                    print(f"  Parsing Spot Auction Details from sheet: {sheet_name}")
                    spot_facts = self._parse_spot_details(excel_file, sheet_name, auction_types, source_url)
                    facts.extend(spot_facts)
            
            # If no specific sheets found, try to parse any sheet that looks like auction data
            if not facts:
                print(f"  No standard sheets found, attempting to parse all sheets...")
                for sheet_name in sheet_names:
                    if sheet_name.lower() not in ['summary', 'index', 'contents', 'notes']:
                        try:
                            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=0)
                            # Try to detect structure and parse
                            parsed = self._parse_generic_sheet(df, sheet_name, auction_types, source_url)
                            if parsed:
                                facts.extend(parsed)
                        except Exception as e:
                            print(f"  Warning: Could not parse sheet '{sheet_name}': {e}")
            
            print(f"  Parsed {len(facts)} records from Excel file")
            
        except Exception as e:
            print(f"Error parsing Excel file {file_path}: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        return facts
    
    def _parse_mcp_table(
        self,
        excel_file: pd.ExcelFile,
        sheet_name: str,
        auction_types: Optional[List[str]] = None,
        source_url: Optional[str] = None
    ) -> List[MarketPriceFact]:
        """
        Parse MCP Table sheet - Market Clearing Prices by zone and auction type.
        
        Expected structure:
        - First column: Date (one date per row)
        - Other columns: Zone_AuctionType (e.g., NYCA_Strip, NYCA_Monthly, GHIJ_Spot)
        - Each row represents a different month/date
        - Each column represents a zone + auction type combination
        
        Args:
            excel_file: ExcelFile object
            sheet_name: Name of sheet to parse
            auction_types: Filter by auction types (None = all)
        
        Returns:
            List of MarketPriceFact objects
        """
        facts = []
        
        try:
            # Try reading with multi-level headers first
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=[0, 1])
            
            # Flatten multi-level headers if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ['_'.join(col).strip() for col in df.columns.values]
            
            # Find date column (usually first column, contains "Date")
            date_col = None
            for col in df.columns:
                if any(keyword in str(col).lower() for keyword in ['date', 'period', 'month', 'year']):
                    date_col = col
                    break
            
            if date_col is None:
                # Assume first column is date
                date_col = df.columns[0]
            
            # Parse each row (each row is a different date)
            for idx, row in df.iterrows():
                # Skip header row or rows without valid dates
                if pd.isna(row[date_col]) or str(row[date_col]).lower() in ['date', 'nan', 'none', '']:
                    continue
                
                # Extract date from first column
                try:
                    if isinstance(row[date_col], datetime):
                        delivery_month = datetime_to_yyyymm(row[date_col])
                        delivery_date = row[date_col]
                    elif isinstance(row[date_col], pd.Timestamp):
                        delivery_date = row[date_col].to_pydatetime()
                        delivery_month = datetime_to_yyyymm(delivery_date)
                    else:
                        # Try parsing string (handles "Apr-23" format if present)
                        period_str = str(row[date_col])
                        dt = pd.to_datetime(period_str)
                        delivery_date = dt.to_pydatetime()
                        delivery_month = datetime_to_yyyymm(delivery_date)
                except Exception as e:
                    # Skip rows with unparseable dates
                    continue
                
                # Parse all other columns (zone + auction type combinations)
                for col_name in df.columns:
                    if col_name == date_col:
                        continue
                    
                    # Skip columns that don't look like zone_auctiontype
                    if '_' not in str(col_name):
                        continue
                    
                    # Extract zone and auction type from column name
                    # Format: "NYCA_Strip", "GHIJ_Monthly", "NYC_Spot", etc.
                    parts = str(col_name).split('_')
                    if len(parts) < 2:
                        continue
                    
                    zone_name = parts[0].strip()
                    auction_type_str = '_'.join(parts[1:]).strip().lower()
                    
                    # Map auction type string to standard format
                    auction_type = None
                    if 'monthly' in auction_type_str:
                        auction_type = 'MONTHLY'
                    elif 'strip' in auction_type_str:
                        auction_type = 'STRIP'
                    elif 'spot' in auction_type_str:
                        auction_type = 'SPOT'
                    else:
                        # Skip if we can't identify auction type
                        continue
                    
                    # Check if this auction type should be included
                    if auction_types is not None and auction_type not in [a.upper() for a in auction_types]:
                        continue
                    
                    # Extract price value
                    price_value = row[col_name]
                    if pd.isna(price_value):
                        continue
                    
                    try:
                        # Convert to float, handling currency symbols and commas
                        price_str = str(price_value).replace('$', '').replace(',', '').strip()
                        price = float(price_str)
                        
                        # Only create fact if price is valid (can be negative in electricity markets)
                        if price != 0:  # Allow negative prices
                            fact = self._create_fact_from_mcp(
                                zone_name, delivery_month, price, auction_type, source_url
                            )
                            if fact:
                                facts.append(fact)
                    except (ValueError, AttributeError, TypeError):
                        # Skip invalid price values
                        continue
        
        except Exception as e:
            print(f"  Warning: Error parsing MCP Table sheet: {e}")
            import traceback
            traceback.print_exc()
        
        return facts
    
    def _parse_monthly_details(
        self,
        excel_file: pd.ExcelFile,
        sheet_name: str,
        auction_types: Optional[List[str]] = None,
        source_url: Optional[str] = None
    ) -> List[MarketPriceFact]:
        """
        Parse Monthly Auction Details sheet.
        
        Expected structure:
        - Columns: Auction Month | Delivery Month | Zone | Price | Awarded MW | ...
        
        Args:
            excel_file: ExcelFile object
            sheet_name: Name of sheet to parse
            auction_types: Filter by auction types (None = all)
        
        Returns:
            List of MarketPriceFact objects
        """
        facts = []
        
        if auction_types and 'MONTHLY' not in [a.upper() for a in auction_types]:
            return facts
        
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=0)
            
            # Find column indices
            auction_month_col = None
            delivery_month_col = None
            zone_col = None
            price_col = None
            awarded_col = None
            
            for col in df.columns:
                col_lower = str(col).lower()
                if 'auction' in col_lower and 'month' in col_lower:
                    auction_month_col = col
                elif 'delivery' in col_lower and 'month' in col_lower:
                    delivery_month_col = col
                elif any(keyword in col_lower for keyword in ['zone', 'locality', 'region']):
                    zone_col = col
                elif 'price' in col_lower or 'mcp' in col_lower:
                    price_col = col
                elif 'awarded' in col_lower or 'cleared' in col_lower or 'mw' in col_lower:
                    awarded_col = col
            
            # Parse each row
            for idx, row in df.iterrows():
                try:
                    # Extract auction month
                    if auction_month_col and pd.notna(row[auction_month_col]):
                        auction_month = self._parse_date_to_yyyymm(row[auction_month_col])
                    else:
                        continue  # Skip if no auction month
                    
                    # Extract delivery month
                    if delivery_month_col and pd.notna(row[delivery_month_col]):
                        delivery_month = self._parse_date_to_yyyymm(row[delivery_month_col])
                    else:
                        delivery_month = auction_month  # Default to auction month
                    
                    # Extract zone
                    if zone_col and pd.notna(row[zone_col]):
                        zone_name = str(row[zone_col]).strip()
                    else:
                        continue  # Skip if no zone
                    
                    # Extract price
                    if price_col and pd.notna(row[price_col]):
                        price = float(str(row[price_col]).replace('$', '').replace(',', '').strip())
                    else:
                        continue  # Skip if no price
                    
                    # Extract awarded MW (optional)
                    awarded_mw = None
                    if awarded_col and pd.notna(row[awarded_col]):
                        try:
                            awarded_mw = float(str(row[awarded_col]).replace(',', '').strip())
                        except:
                            pass
                    
                    # Create fact
                    fact = self._create_monthly_fact(
                        zone_name, auction_month, delivery_month, price, awarded_mw, source_url
                    )
                    if fact:
                        facts.append(fact)
                
                except Exception as e:
                    print(f"  Warning: Error parsing row {idx} in Monthly Details: {e}")
                    continue
        
        except Exception as e:
            print(f"  Warning: Error parsing Monthly Details sheet: {e}")
        
        return facts
    
    def _parse_strip_details(
        self,
        excel_file: pd.ExcelFile,
        sheet_name: str,
        auction_types: Optional[List[str]] = None,
        source_url: Optional[str] = None
    ) -> List[MarketPriceFact]:
        """
        Parse Strip Auction Details sheet.
        
        Expected structure:
        - Columns: Capability Period | Zone | Price | Awarded MW | Delivery Months | ...
        
        Args:
            excel_file: ExcelFile object
            sheet_name: Name of sheet to parse
            auction_types: Filter by auction types (None = all)
        
        Returns:
            List of MarketPriceFact objects
        """
        facts = []
        
        if auction_types and 'STRIP' not in [a.upper() for a in auction_types]:
            return facts
        
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=0)
            
            # Find column indices
            period_col = None
            zone_col = None
            price_col = None
            awarded_col = None
            delivery_months_col = None
            
            for col in df.columns:
                col_lower = str(col).lower()
                if 'capability' in col_lower or 'period' in col_lower or 'season' in col_lower:
                    period_col = col
                elif any(keyword in col_lower for keyword in ['zone', 'locality', 'region']):
                    zone_col = col
                elif 'price' in col_lower or 'mcp' in col_lower:
                    price_col = col
                elif 'awarded' in col_lower or 'cleared' in col_lower or 'mw' in col_lower:
                    awarded_col = col
                elif 'delivery' in col_lower and 'month' in col_lower:
                    delivery_months_col = col
            
            # Parse each row
            for idx, row in df.iterrows():
                try:
                    # Extract capability period
                    if period_col and pd.notna(row[period_col]):
                        period_str = str(row[period_col]).upper()
                        if 'WINTER' in period_str:
                            capability_period = 'WINTER'
                        elif 'SUMMER' in period_str:
                            capability_period = 'SUMMER'
                        else:
                            continue  # Skip if can't determine period
                    else:
                        continue
                    
                    # Extract zone
                    if zone_col and pd.notna(row[zone_col]):
                        zone_name = str(row[zone_col]).strip()
                    else:
                        continue
                    
                    # Extract price
                    if price_col and pd.notna(row[price_col]):
                        price = float(str(row[price_col]).replace('$', '').replace(',', '').strip())
                    else:
                        continue
                    
                    # Extract awarded MW (optional)
                    awarded_mw = None
                    if awarded_col and pd.notna(row[awarded_col]):
                        try:
                            awarded_mw = float(str(row[awarded_col]).replace(',', '').strip())
                        except:
                            pass
                    
                    # Extract delivery months or determine from capability period
                    if delivery_months_col and pd.notna(row[delivery_months_col]):
                        delivery_months_str = str(row[delivery_months_col])
                        # Try to parse (could be "Nov-Apr" or "202311-202404" or list)
                        delivery_months = self._parse_delivery_months(delivery_months_str, capability_period)
                    else:
                        # Determine from capability period and year
                        # Need to extract year from somewhere - try to find it
                        year = datetime.now().year  # Default
                        for col in df.columns:
                            if 'year' in str(col).lower() and pd.notna(row[col]):
                                try:
                                    year = int(row[col])
                                    break
                                except:
                                    pass
                        
                        # Determine auction month based on capability period
                        if capability_period == "WINTER":
                            auction_month = f"{year}10"  # October
                        else:  # SUMMER
                            auction_month = f"{year}04"  # April
                        
                        delivery_months = get_delivery_months_for_strip(auction_month, capability_period)
                    
                    # For strip auctions, create ONE record per zone (not per delivery month)
                    # Use auction_month as delivery_month so all records go into one file
                    # This matches the HTML scraping behavior
                    if delivery_months:
                        # Use first delivery month to determine auction_month
                        first_delivery = delivery_months[0]
                        year = int(first_delivery[:4])
                        
                        # Determine auction_month based on capability period
                        if capability_period == "WINTER":
                            auction_month = f"{year}10"  # October
                        else:  # SUMMER
                            auction_month = f"{year}04"  # April
                        
                        # Use auction_month as delivery_month (so all go into one partition)
                        delivery_month = auction_month
                        
                        # Calculate time range for entire capability period
                        first_delivery_dt = yyyymm_to_datetime(delivery_months[0], tz=pytz.UTC)
                        last_delivery_dt = yyyymm_to_datetime(delivery_months[-1], tz=pytz.UTC)
                        
                        start_time = first_delivery_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        if last_delivery_dt.month == 12:
                            end_time = last_delivery_dt.replace(year=last_delivery_dt.year + 1, month=1, day=1) - timedelta(seconds=1)
                        else:
                            end_time = last_delivery_dt.replace(month=last_delivery_dt.month + 1, day=1) - timedelta(seconds=1)
                        
                        fact = normalize_capacity_price(
                            iso_code=self.iso_code,
                            node_id=zone_name,
                            node_type="ZONE",
                            start_time=start_time,
                            end_time=end_time,
                            price=price,
                            product="SEASONAL",
                            zone=zone_name,
                            auction_id=f"{auction_month}_STRIP_{zone_name}",
                            source_url=source_url,
                            auction_time=None,
                            capability_period=capability_period,
                            auction_type="STRIP",
                            awarded_mw=awarded_mw,
                            posted_at=None,
                            season_id=None,
                        )
                        fact.auction_month = auction_month
                        fact.delivery_month = delivery_month
                        
                        if fact:
                            facts.append(fact)
                
                except Exception as e:
                    print(f"  Warning: Error parsing row {idx} in Strip Details: {e}")
                    continue
        
        except Exception as e:
            print(f"  Warning: Error parsing Strip Details sheet: {e}")
        
        return facts
    
    def _parse_spot_details(
        self,
        excel_file: pd.ExcelFile,
        sheet_name: str,
        auction_types: Optional[List[str]] = None,
        source_url: Optional[str] = None
    ) -> List[MarketPriceFact]:
        """
        Parse Spot Auction Details sheet (rare - spot auctions are infrequent).
        
        Expected structure:
        - Columns: Auction Date | Zone | Price | Awarded MW | ...
        
        Args:
            excel_file: ExcelFile object
            sheet_name: Name of sheet to parse
            auction_types: Filter by auction types (None = all)
        
        Returns:
            List of MarketPriceFact objects
        """
        facts = []
        
        if auction_types and 'SPOT' not in [a.upper() for a in auction_types]:
            return facts
        
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=0)
            
            # Find column indices
            date_col = None
            zone_col = None
            price_col = None
            awarded_col = None
            
            for col in df.columns:
                col_lower = str(col).lower()
                if 'date' in col_lower or 'auction' in col_lower:
                    date_col = col
                elif any(keyword in col_lower for keyword in ['zone', 'locality', 'region']):
                    zone_col = col
                elif 'price' in col_lower or 'mcp' in col_lower:
                    price_col = col
                elif 'awarded' in col_lower or 'cleared' in col_lower or 'mw' in col_lower:
                    awarded_col = col
            
            # Parse each row
            for idx, row in df.iterrows():
                try:
                    # Extract auction date
                    if date_col and pd.notna(row[date_col]):
                        auction_month = self._parse_date_to_yyyymm(row[date_col])
                    else:
                        continue
                    
                    # Extract zone
                    if zone_col and pd.notna(row[zone_col]):
                        zone_name = str(row[zone_col]).strip()
                    else:
                        continue
                    
                    # Extract price
                    if price_col and pd.notna(row[price_col]):
                        price = float(str(row[price_col]).replace('$', '').replace(',', '').strip())
                    else:
                        continue
                    
                    # Extract awarded MW (optional)
                    awarded_mw = None
                    if awarded_col and pd.notna(row[awarded_col]):
                        try:
                            awarded_mw = float(str(row[awarded_col]).replace(',', '').strip())
                        except:
                            pass
                    
                    # For spot auctions, delivery_month is typically same as auction_month
                    delivery_month = auction_month
                    
                    # Create fact
                    fact = self._create_spot_fact(
                        zone_name, auction_month, delivery_month, price, awarded_mw, source_url
                    )
                    if fact:
                        facts.append(fact)
                
                except Exception as e:
                    print(f"  Warning: Error parsing row {idx} in Spot Details: {e}")
                    continue
        
        except Exception as e:
            print(f"  Warning: Error parsing Spot Details sheet: {e}")
        
        return facts
    
    def _parse_generic_sheet(
        self,
        df: pd.DataFrame,
        sheet_name: str,
        auction_types: Optional[List[str]] = None,
        source_url: Optional[str] = None
    ) -> List[MarketPriceFact]:
        """
        Attempt to parse a generic sheet by detecting structure.
        
        Args:
            df: DataFrame from sheet
            sheet_name: Name of sheet
            auction_types: Filter by auction types
        
        Returns:
            List of MarketPriceFact objects (empty if can't parse)
        """
        # This is a fallback - try to detect structure
        # For now, return empty - can be enhanced later
        return []
    
    def _parse_date_to_yyyymm(self, value) -> str:
        """Convert various date formats to YYYYMM string."""
        try:
            if isinstance(value, datetime):
                return datetime_to_yyyymm(value)
            elif isinstance(value, pd.Timestamp):
                return datetime_to_yyyymm(value.to_pydatetime())
            else:
                # Try parsing string
                dt = pd.to_datetime(str(value))
                return datetime_to_yyyymm(dt.to_pydatetime())
        except:
            # Fallback: try to extract YYYYMM from string
            match = re.search(r'(\d{4})[-\s/]?(\d{2})', str(value))
            if match:
                return f"{match.group(1)}{match.group(2)}"
            return datetime_to_yyyymm(datetime.now())  # Default fallback
    
    def _parse_delivery_months(self, value: str, capability_period: str) -> List[str]:
        """Parse delivery months string to list of YYYYMM strings."""
        # Could be "Nov-Apr", "202311-202404", "Nov, Dec, Jan", etc.
        # For now, return empty and let caller determine from capability_period
        # This can be enhanced with more parsing logic
        return []
    
    def _create_fact_from_mcp(
        self,
        zone_name: str,
        delivery_month: str,
        price: float,
        auction_type: str,
        source_url: Optional[str] = None
    ) -> Optional[MarketPriceFact]:
        """Create MarketPriceFact from MCP Table data."""
        try:
            delivery_dt = yyyymm_to_datetime(delivery_month, tz=pytz.UTC)
            start_time = delivery_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if delivery_dt.month == 12:
                end_time = delivery_dt.replace(year=delivery_dt.year + 1, month=1, day=1) - timedelta(seconds=1)
            else:
                end_time = delivery_dt.replace(month=delivery_dt.month + 1, day=1) - timedelta(seconds=1)
            
            # For MCP table, auction_month is typically same as delivery_month
            auction_month = delivery_month
            
            capability_period = get_capability_period(delivery_month)
            
            product = "MONTHLY" if auction_type == "MONTHLY" else "SEASONAL"
            
            return normalize_capacity_price(
                iso_code=self.iso_code,
                node_id=zone_name,
                node_type="ZONE",
                start_time=start_time,
                end_time=end_time,
                price=price,
                product=product,
                zone=zone_name,
                auction_id=f"{auction_month}_{auction_type}_{zone_name}",
                source_url=source_url,
                auction_time=None,
                capability_period=capability_period,
                auction_type=auction_type,
                awarded_mw=None,  # MCP table typically doesn't have awarded_mw
                posted_at=None,
                season_id=None,
            )
        except Exception as e:
            print(f"  Warning: Error creating fact from MCP data: {e}")
            return None
    
    def _create_monthly_fact(
        self,
        zone_name: str,
        auction_month: str,
        delivery_month: str,
        price: float,
        awarded_mw: Optional[float] = None,
        source_url: Optional[str] = None
    ) -> Optional[MarketPriceFact]:
        """Create MarketPriceFact for monthly auction."""
        try:
            delivery_dt = yyyymm_to_datetime(delivery_month, tz=pytz.UTC)
            start_time = delivery_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if delivery_dt.month == 12:
                end_time = delivery_dt.replace(year=delivery_dt.year + 1, month=1, day=1) - timedelta(seconds=1)
            else:
                end_time = delivery_dt.replace(month=delivery_dt.month + 1, day=1) - timedelta(seconds=1)
            
            capability_period = get_capability_period(delivery_month)
            
            return normalize_capacity_price(
                iso_code=self.iso_code,
                node_id=zone_name,
                node_type="ZONE",
                start_time=start_time,
                end_time=end_time,
                price=price,
                product="MONTHLY",
                zone=zone_name,
                auction_id=f"{auction_month}_MONTHLY_{zone_name}",
                source_url=source_url,
                auction_time=None,
                capability_period=capability_period,
                auction_type="MONTHLY",
                awarded_mw=awarded_mw,
                posted_at=None,
                season_id=None,
            )
        except Exception as e:
            print(f"  Warning: Error creating monthly fact: {e}")
            return None
    
    def _create_strip_fact(
        self,
        zone_name: str,
        delivery_month: str,
        capability_period: str,
        price: float,
        awarded_mw: Optional[float] = None
    ) -> Optional[MarketPriceFact]:
        """Create MarketPriceFact for strip auction."""
        try:
            delivery_dt = yyyymm_to_datetime(delivery_month, tz=pytz.UTC)
            start_time = delivery_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if delivery_dt.month == 12:
                end_time = delivery_dt.replace(year=delivery_dt.year + 1, month=1, day=1) - timedelta(seconds=1)
            else:
                end_time = delivery_dt.replace(month=delivery_dt.month + 1, day=1) - timedelta(seconds=1)
            
            # For strip auctions, auction_month is typically October (Winter) or April (Summer)
            year = int(delivery_month[:4])
            if capability_period == "WINTER":
                auction_month = f"{year}10"  # October
            else:  # SUMMER
                auction_month = f"{year}04"  # April
            
            return normalize_capacity_price(
                iso_code=self.iso_code,
                node_id=zone_name,
                node_type="ZONE",
                start_time=start_time,
                end_time=end_time,
                price=price,
                product="SEASONAL",
                zone=zone_name,
                auction_id=f"{auction_month}_STRIP_{zone_name}",
                source_url=None,
                auction_time=None,
                capability_period=capability_period,
                auction_type="STRIP",
                awarded_mw=awarded_mw,
                posted_at=None,
                season_id=None,
            )
        except Exception as e:
            print(f"  Warning: Error creating strip fact: {e}")
            return None
    
    def _create_spot_fact(
        self,
        zone_name: str,
        auction_month: str,
        delivery_month: str,
        price: float,
        awarded_mw: Optional[float] = None,
        source_url: Optional[str] = None
    ) -> Optional[MarketPriceFact]:
        """Create MarketPriceFact for spot auction."""
        try:
            delivery_dt = yyyymm_to_datetime(delivery_month, tz=pytz.UTC)
            start_time = delivery_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if delivery_dt.month == 12:
                end_time = delivery_dt.replace(year=delivery_dt.year + 1, month=1, day=1) - timedelta(seconds=1)
            else:
                end_time = delivery_dt.replace(month=delivery_dt.month + 1, day=1) - timedelta(seconds=1)
            
            capability_period = get_capability_period(delivery_month)
            
            return normalize_capacity_price(
                iso_code=self.iso_code,
                node_id=zone_name,
                node_type="ZONE",
                start_time=start_time,
                end_time=end_time,
                price=price,
                product="MONTHLY",  # Spot uses MONTHLY product with SPOT auction_type
                zone=zone_name,
                auction_id=f"{auction_month}_SPOT_{zone_name}",
                source_url=source_url,
                auction_time=None,
                capability_period=capability_period,
                auction_type="SPOT",
                awarded_mw=awarded_mw,
                posted_at=None,
                season_id=None,
            )
        except Exception as e:
            print(f"  Warning: Error creating spot fact: {e}")
            return None
    
    def fetch_capacity_prices_from_excel(
        self,
        excel_file_path: Path,
        auction_types: Optional[List[str]] = None,
    ) -> List[MarketPriceFact]:
        """
        Fetch capacity prices from Excel Market Report file.
        
        Args:
            excel_file_path: Path to Excel file
            auction_types: Which auction types to parse (None = all: MONTHLY, STRIP, SPOT)
        
        Returns:
            List of MarketPriceFact objects
        """
        return self._parse_excel_report(excel_file_path, auction_types)
    
    def fetch_energy_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        nodes: Optional[List[str]] = None,
        product: str = "DA",
    ) -> List[MarketPriceFact]:
        """
        ICAP adapter does not fetch energy prices.
        This method is required by the base class but not applicable for capacity markets.
        
        Returns:
            Empty list
        """
        return []
    
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

