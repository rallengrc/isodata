#!/usr/bin/env python3
"""
Diagnose what EIA API is actually returning.
"""

import os
import requests
from datetime import datetime, timedelta
import pytz

# Get API key
api_key = os.getenv("EIA_API_KEY")

# Test EIA API call
endpoint = "rto/region-data/data/"
base_url = "https://api.eia.gov/v2/electricity/"

start_date = datetime(2024, 1, 1, tzinfo=pytz.UTC)
end_date = datetime(2024, 1, 7, tzinfo=pytz.UTC)

start_str = start_date.strftime("%Y-%m-%dT%H")
end_str = end_date.strftime("%Y-%m-%dT%H")

params = {
    "frequency": "hourly",
    "data[0]": "value",
    "facets[respondent][]": "NYIS",
    "facets[type][]": "D",  # Day-ahead
    "start": start_str,
    "end": end_str,
    "sort[0][column]": "period",
    "sort[0][direction]": "asc",
    "length": 10,  # Just get a few records
}

if api_key:
    params['api_key'] = api_key

url = f"{base_url}{endpoint}"
print("=" * 80)
print("EIA API Diagnostic")
print("=" * 80)
print(f"URL: {url}")
print(f"Params: {params}")
print()

response = requests.get(url, params=params, timeout=30)
print(f"Status Code: {response.status_code}")
print()

if response.status_code == 200:
    data = response.json()
    print("Response structure:")
    print(f"  Keys: {list(data.keys())}")
    print()
    
    if "response" in data:
        resp = data["response"]
        print("Response object:")
        print(f"  Keys: {list(resp.keys())}")
        print()
        
        if "data" in resp and resp["data"]:
            print("Sample records (first 3):")
            for i, record in enumerate(resp["data"][:3]):
                print(f"\n  Record {i+1}:")
                for key, value in record.items():
                    print(f"    {key}: {value}")
            
            print()
            print("=" * 80)
            print("Analysis:")
            print("=" * 80)
            
            # Check what fields are available
            first_record = resp["data"][0]
            print(f"Available fields: {list(first_record.keys())}")
            print()
            
            # Check value field
            if "value" in first_record:
                print(f"Value field type: {type(first_record['value'])}")
                print(f"Value field value: {first_record['value']}")
                print(f"  Note: This might be in wrong units or wrong series!")
            
            # Check for series information
            if "series-description" in first_record:
                print(f"Series description: {first_record['series-description']}")
            
            # Check for units
            if "units" in first_record:
                print(f"Units: {first_record['units']}")
            
            # Check for type
            if "type" in first_record:
                print(f"Type: {first_record['type']}")
            
            # Check for respondent
            if "respondent" in first_record:
                print(f"Respondent: {first_record['respondent']}")
        else:
            print("No data in response")
            print(f"Response: {resp}")
    else:
        print("No 'response' key in data")
        print(f"Data: {data}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)

