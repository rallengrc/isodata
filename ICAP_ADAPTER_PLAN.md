# ICAP Adapter Implementation Plan

## Status
✅ **Structure Created**: `adapters/nyiso_capacity.py` with proper month tracking
✅ **DuckDB Views Fixed**: Views now properly handle schema evolution
⏳ **Next**: Implement actual scraping logic

## ICAP Data Sources

### 1. Monthly Auctions
- **URL**: `https://icappublic.nyiso.com/ucap/public/auc_view_monthly_selection.do`
- **Data**: Monthly auction results by zone
- **Auction Month**: Typically 1-2 months before delivery
- **Delivery Month**: The month capacity applies to
- **Format**: HTML table (needs scraping)

### 2. Strip Auctions (Capability Periods)
- **URL**: `https://icappublic.nyiso.com/ucap/public/auc_view_strip_selection.do`
- **Data**: Seasonal capacity auctions
- **Summer Period**: May-Oct (6 months)
- **Winter Period**: Nov-Apr (6 months, crosses year)
- **Format**: HTML table (needs scraping)

### 3. ICAP Market Reports (Excel)
- **URL**: Published periodically (e.g., `ICAP-Market-Report-July-2024.xlsx`)
- **Data**: Comprehensive auction results and market analysis
- **Format**: Excel files (can be downloaded and parsed)

## Implementation Strategy

### Phase 1: HTML Scraping (Current)
1. **Monthly Auctions**:
   - POST request to selection page with month/year
   - Parse HTML table response
   - Extract: zone, clearing price, cleared quantity, auction date

2. **Strip Auctions**:
   - POST request with capability period selection
   - Parse HTML table response
   - Extract: zone, clearing price, delivery months covered

### Phase 2: Excel Parsing (Future)
- Download ICAP Market Reports
- Parse Excel sheets for historical data
- Extract structured auction results

## Data Normalization

Each ICAP record will be normalized to `MarketPriceFact` with:
- `auction_month`: YYYYMM when auction ran
- `delivery_month`: YYYYMM when capacity applies
- `capability_period`: "SUMMER" or "WINTER"
- `auction_type`: "MONTHLY", "STRIP", or "SPOT"
- `zone`: Normalized zone name (using zone_normalization.py)
- `price`: Clearing price ($/kW-month)
- `unit`: "$/kW-month"

## Next Steps

1. **Test HTML Structure**: Inspect actual NYISO ICAP pages to understand HTML structure
2. **Implement Scraping**: Build BeautifulSoup parsers for monthly and strip auctions
3. **Handle Edge Cases**: 
   - Missing data
   - Different table formats
   - Timezone handling
4. **Test with Real Data**: Fetch recent ICAP data and verify normalization
5. **Add to Pipeline**: Integrate ICAP adapter into `run_pipeline.py`

## Notes

- NYISOToolkit doesn't support ICAP, so we must scrape directly
- ICAP data is less frequent than energy data (monthly vs hourly)
- Capability periods cross calendar years (Winter: Nov-Apr)
- Some auctions may have multiple delivery months (strip auctions)

