#!/usr/bin/env python3
"""
AI-powered analytics analyzer for Alconox web properties.
Aggregates data from Matomo, Google Ads, and LinkedIn, then sends to Claude API for analysis.
Requires ANTHROPIC_API_KEY environment variable (or .env file).
"""

from dotenv import load_dotenv
load_dotenv()

import json
import os
import sys
import csv
import io
from datetime import datetime
from typing import Optional

import anthropic

from matomo_analyzer import MatomoAPI, DateRange
from export_for_ai import export_comprehensive_data


# ============================================================
# Data Aggregation
# ============================================================

def aggregate_matomo_data(site_ids: list[dict], date_range: DateRange) -> dict:
    """Fetch Matomo data for selected sites, stripping raw_api_data to save tokens."""
    results = {}
    for site in site_ids:
        site_id = int(site["idsite"])
        site_name = site.get("name", f"Site {site_id}")
        print(f"  [Matomo] Fetching data for {site_name}...")
        try:
            data = export_comprehensive_data(site_id, date_range)
            data.pop("raw_api_data", None)
            results[site_name] = data
        except Exception as e:
            print(f"  [Matomo] Warning: Failed to fetch {site_name}: {e}")
            results[site_name] = {"error": str(e)}
    return results


def aggregate_google_ads_data(start_date: str, end_date: str) -> Optional[dict]:
    """Fetch Google Ads data. Returns None if unavailable."""
    try:
        from google_ads_analyzer import get_client, get_campaigns, get_campaign_summary
        print("  [Google Ads] Fetching campaign data...")
        client = get_client()
        customer_id = "4205046148"

        campaigns = get_campaigns(client, customer_id, start_date, end_date)
        summary = get_campaign_summary(client, customer_id, start_date, end_date)

        # Keep top 10 campaigns by spend
        top_campaigns = sorted(campaigns, key=lambda c: c.get("cost", 0), reverse=True)[:10]

        return {
            "summary": summary,
            "top_campaigns": top_campaigns,
            "total_campaigns": len(campaigns),
        }
    except Exception as e:
        print(f"  [Google Ads] Unavailable: {e}")
        return None


def aggregate_linkedin_data(linkedin_dir: str = "linkedin") -> Optional[dict]:
    """Parse LinkedIn campaign CSV exports from the linkedin/ directory."""
    abs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), linkedin_dir)
    if not os.path.isdir(abs_dir):
        print(f"  [LinkedIn] Directory not found: {abs_dir}")
        return None

    csv_files = [f for f in os.listdir(abs_dir) if f.endswith(".csv")]
    if not csv_files:
        print("  [LinkedIn] No CSV files found.")
        return None

    all_campaigns = {}
    for filename in csv_files:
        filepath = os.path.join(abs_dir, filename)
        print(f"  [LinkedIn] Parsing {filename}...")
        rows = _parse_linkedin_csv(filepath)
        for row in rows:
            # Deduplicate by campaign name (UTF-8 and UTF-16 files may overlap)
            key = row.get("campaign_name", "")
            if key and key not in all_campaigns:
                all_campaigns[key] = row
    all_campaigns = list(all_campaigns.values())

    if not all_campaigns:
        return None

    # Compute summary totals
    totals = {
        "total_spent": 0, "total_spent_compare": 0,
        "impressions": 0, "impressions_compare": 0,
        "clicks": 0, "clicks_compare": 0,
        "video_views": 0, "video_views_compare": 0,
        "video_completions": 0, "video_completions_compare": 0,
        "total_engagements": 0, "total_engagements_compare": 0,
    }
    for c in all_campaigns:
        totals["total_spent"] += c.get("total_spent", 0)
        totals["total_spent_compare"] += c.get("total_spent_compare", 0)
        totals["impressions"] += c.get("impressions", 0)
        totals["impressions_compare"] += c.get("impressions_compare", 0)
        totals["clicks"] += c.get("clicks", 0)
        totals["clicks_compare"] += c.get("clicks_compare", 0)
        totals["video_views"] += c.get("video_views", 0)
        totals["video_views_compare"] += c.get("video_views_compare", 0)
        totals["video_completions"] += c.get("video_completions", 0)
        totals["video_completions_compare"] += c.get("video_completions_compare", 0)
        totals["total_engagements"] += c.get("total_engagements", 0)
        totals["total_engagements_compare"] += c.get("total_engagements_compare", 0)

    # Derived metrics
    if totals["impressions"] > 0:
        totals["ctr"] = totals["clicks"] / totals["impressions"] * 100
    if totals["impressions_compare"] > 0:
        totals["ctr_compare"] = totals["clicks_compare"] / totals["impressions_compare"] * 100

    return {
        "summary": totals,
        "campaigns": all_campaigns,
        "total_campaigns": len(all_campaigns),
    }


def _parse_linkedin_csv(filepath: str) -> list[dict]:
    """Parse a single LinkedIn campaign performance CSV (UTF-8 or UTF-16)."""
    content = None
    # Try UTF-8 first, fall back to UTF-16
    for encoding in ("utf-8", "utf-16"):
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if content is None:
        print(f"    Warning: Could not decode {filepath}")
        return []

    lines = content.strip().split("\n")

    # Find the header row (starts with "Start Date")
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Start Date"):
            header_idx = i
            break

    if header_idx is None:
        print(f"    Warning: Could not find header row in {filepath}")
        return []

    # Parse as TSV from header row onward
    tsv_content = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(tsv_content), delimiter="\t")

    campaigns = []
    for row in reader:
        campaign = {
            "campaign_name": row.get("Campaign Name", "").strip('"'),
            "campaign_group": row.get("Campaign Group Name", "").strip('"'),
            "campaign_objective": row.get("Campaign Objective", ""),
            "campaign_status": row.get("Campaign Status", ""),
            "total_spent": _parse_number(row.get("Total Spent", "0")),
            "total_spent_compare": _parse_number(row.get("Total Spent Compare Time Range", "0")),
            "impressions": _parse_number(row.get("Impressions", "0")),
            "impressions_compare": _parse_number(row.get("Impressions Compare Time Range", "0")),
            "clicks": _parse_number(row.get("Clicks", "0")),
            "clicks_compare": _parse_number(row.get("Clicks Compare Time Range", "0")),
            "ctr": row.get("Click Through Rate", "0").strip("%"),
            "ctr_compare": row.get("Click Through Rate Compare Time Range", "0").strip("%"),
            "video_views": _parse_number(row.get("Video Views", "0")),
            "video_views_compare": _parse_number(row.get("Video Views Compare Time Range", "0")),
            "video_completions": _parse_number(row.get("Video Completions", "0")),
            "video_completions_compare": _parse_number(row.get("Video Completions Compare Time Range", "0")),
            "total_engagements": _parse_number(row.get("Total Engagements", "0")),
            "total_engagements_compare": _parse_number(row.get("Total Engagements Compare Time Range", "0")),
            "reactions": _parse_number(row.get("Reactions", "0")),
            "leads": _parse_number(row.get("Leads", "0")),
        }
        campaigns.append(campaign)

    return campaigns


def summarize_matomo_for_yoy(full_data: dict) -> dict:
    """Extract a compact summary from full Matomo export data for YoY comparison.
    Keeps overview metrics and top items from each section, discards bulk lists."""
    summary = {}
    for site_name, site_data in full_data.items():
        if not isinstance(site_data, dict) or "error" in site_data:
            summary[site_name] = site_data
            continue

        s = {}

        # Traffic overview (compact)
        s["traffic_overview"] = site_data.get("summary", {}).get("overview", {})

        # Traffic sources — keep full list (usually small)
        s["referrer_types"] = site_data.get("traffic_sources", {}).get("by_type", [])

        # Search engines — top 5
        engines = site_data.get("traffic_sources", {}).get("search_engines", [])
        s["top_search_engines"] = engines[:5]

        # Referring websites — top 10
        websites = site_data.get("traffic_sources", {}).get("referring_websites", [])
        s["top_referring_websites"] = websites[:10]

        # Social — keep all (usually small)
        s["social_networks"] = site_data.get("traffic_sources", {}).get("social_networks", [])

        # Campaigns — top 10
        campaigns = site_data.get("traffic_sources", {}).get("campaigns", [])
        s["top_campaigns"] = campaigns[:10]

        # Top pages — top 15
        pages = site_data.get("content_performance", {}).get("top_pages", [])
        s["top_pages"] = [_slim_item(p) for p in pages[:15]]

        # Entry pages — top 10
        entry = site_data.get("content_performance", {}).get("entry_pages", [])
        s["top_entry_pages"] = [_slim_item(p) for p in entry[:10]]

        # Devices — keep all (usually 3-4)
        s["devices"] = site_data.get("audience", {}).get("devices", [])

        # Countries — top 10
        countries = site_data.get("audience", {}).get("countries", [])
        s["top_countries"] = countries[:10]

        # Goals
        goals = site_data.get("goals", {})
        s["goals"] = goals

        summary[site_name] = s

    return summary


def _slim_item(item: dict) -> dict:
    """Strip verbose fields from a Matomo list item."""
    drop = {"subtable", "segment", "logo", "logoWidth", "logoHeight", "icon",
            "idsubdatatable", "url"}
    return {k: v for k, v in item.items() if k not in drop}


def _parse_number(value: str) -> float:
    """Parse a number string, handling commas and quotes."""
    if not value:
        return 0
    cleaned = value.strip().strip('"').replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0


# ============================================================
# Token Management & Truncation
# ============================================================

def estimate_tokens(data: dict) -> int:
    """Rough token estimate: ~2 chars per token for JSON with keys/formatting."""
    return len(json.dumps(data, default=str)) // 2


def _truncate_list_fields(obj, limit: int):
    """Recursively truncate any list values in a dict to `limit` items."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(val, list):
                obj[key] = val[:limit]
            elif isinstance(val, dict):
                _truncate_list_fields(val, limit)
    return obj


def _truncate_matomo_section(site_data: dict, page_limit: int, list_limit: int,
                             aggressive: bool) -> None:
    """Truncate a single Matomo site data dict in place."""
    if not isinstance(site_data, dict):
        return

    drop_fields = {"subtable", "segment", "logo", "logoWidth", "logoHeight",
                   "icon", "idsubdatatable", "url"}

    def slim_lists(section: dict, limit: int):
        for key, val in list(section.items()):
            if isinstance(val, list):
                section[key] = val[:limit]
                for item in section[key]:
                    if isinstance(item, dict):
                        for f in drop_fields:
                            item.pop(f, None)

    # Remove daily time-series data
    summary = site_data.get("summary", {})
    summary.pop("daily_visits", None)
    summary.pop("daily_pageviews", None)

    # Limit content performance lists
    cp = site_data.get("content_performance", {})
    for key in ("top_pages", "page_titles", "entry_pages", "exit_pages",
                "downloads", "outlinks"):
        if key in cp and isinstance(cp[key], list):
            cp[key] = cp[key][:page_limit]
    slim_lists(cp, page_limit)

    # Limit traffic source lists
    ts = site_data.get("traffic_sources", {})
    slim_lists(ts, list_limit)

    # Limit audience lists
    aud = site_data.get("audience", {})
    slim_lists(aud, list_limit)

    # YoY summarized data also has top-level lists
    for key in list(site_data.keys()):
        val = site_data[key]
        if isinstance(val, list):
            site_data[key] = val[:list_limit]
            for item in site_data[key]:
                if isinstance(item, dict):
                    for f in drop_fields:
                        item.pop(f, None)

    # In aggressive mode, remove goals and full audience detail
    if aggressive:
        site_data.pop("goals", None)
        for remove_key in ("cities", "browsers", "operating_systems",
                           "top_countries", "devices"):
            aud.pop(remove_key, None)
            site_data.pop(remove_key, None)
        # Trim pages more
        for key in ("top_pages", "top_entry_pages", "entry_pages", "exit_pages"):
            if key in site_data and isinstance(site_data[key], list):
                site_data[key] = site_data[key][:3]
            if key in cp and isinstance(cp[key], list):
                cp[key] = cp[key][:3]


def truncate_data(data: dict, aggressive: bool = False) -> dict:
    """Truncate data to fit within token limits."""
    truncated = json.loads(json.dumps(data, default=str))

    page_limit = 5 if aggressive else 15
    list_limit = 5 if aggressive else 10

    # Truncate all Matomo keys (handles "matomo", "matomo_2024", "matomo_2025")
    for data_key in list(truncated.keys()):
        if data_key.startswith("matomo"):
            matomo_section = truncated[data_key]
            if isinstance(matomo_section, dict):
                for site_name, site_data in matomo_section.items():
                    _truncate_matomo_section(site_data, page_limit, list_limit, aggressive)

    # Truncate all Google Ads keys (handles "google_ads", "google_ads_2024", etc.)
    for data_key in list(truncated.keys()):
        if data_key.startswith("google_ads") and truncated[data_key]:
            gads = truncated[data_key]
            if isinstance(gads, dict):
                campaign_limit = 3 if aggressive else 5
                if "top_campaigns" in gads and isinstance(gads["top_campaigns"], list):
                    gads["top_campaigns"] = gads["top_campaigns"][:campaign_limit]

    # Truncate LinkedIn to summary only in aggressive mode
    if aggressive and "linkedin_ads" in truncated and truncated["linkedin_ads"]:
        truncated["linkedin_ads"].pop("campaigns", None)

    return truncated


# ============================================================
# Analysis Prompt
# ============================================================

ANALYSIS_PROMPT = """You are a senior digital marketing analyst reviewing web analytics data for Alconox, Inc. — a manufacturer of critical cleaning products for lab, pharma, medical device, and industrial applications. Their web properties include alconox.com (main site with ecommerce), a Food Service microsite, Ledizolv.com (LED cleaning product), and TechNotes (technical blog/knowledge base).

Analyze the following multi-source analytics data and produce a comprehensive markdown report. Structure your analysis as follows:

## Executive Summary
- Create a metrics comparison table (site-by-site with key metrics and % changes)
- Write a 2-3 sentence "Bottom Line" takeaway

## Site-by-Site Analysis
For each Matomo site included:
- **Traffic Trends**: visits, pageviews, pages/visit, time on site, bounce rate — identify patterns
- **Referrer Trends**: breakdown by source type, note significant shifts
- **Content Performance**: top pages, entry/exit patterns
- **Key Observations**: 3-5 bullet points on notable findings

## Paid Media Performance
- **Google Ads**: spend, impressions, clicks, CTR, CPC, conversions — efficiency analysis
- **LinkedIn Ads**: spend, impressions, video views, engagement — B2B awareness metrics
- Compare current vs. prior period where data is available

## Cross-Channel Insights
- What's working well across channels
- Areas of concern or declining performance
- Emerging trends (AI traffic, video engagement, etc.)

## Strategic Recommendations
- **Short-term** (next 30 days): quick wins
- **Medium-term** (next quarter): tactical improvements
- **Long-term** (6-12 months): strategic initiatives

Use specific numbers from the data. Flag any data gaps or anomalies. Write in a professional but accessible tone suitable for marketing leadership.

---

DATA:
"""


YOY_ANALYSIS_PROMPT = """You are a senior digital marketing analyst producing a Year-over-Year (2024 vs 2025) comparison report for Alconox, Inc. — a manufacturer of critical cleaning products for lab, pharma, medical device, and industrial applications. Their web properties include alconox.com (main site with ecommerce), a Food Service microsite, Ledizolv.com (LED cleaning product), and TechNotes (technical blog/knowledge base).

You are given data from three sources:
- **matomo_2024 / matomo_2025**: Website analytics for each site, broken down by year
- **google_ads_2024 / google_ads_2025**: Google Ads campaign performance for each year
- **linkedin_ads**: LinkedIn campaign data where "Compare Time Range" columns represent 2024 data and primary columns represent 2025

Analyze the data and produce a comprehensive year-over-year comparison report in markdown. Structure your analysis as follows:

## Executive Summary
- Create a YoY comparison table with key metrics for each site and paid channel
- Include absolute numbers AND percentage changes
- Write a 3-4 sentence "Bottom Line" takeaway covering the most important shifts

## Site-by-Site YoY Analysis
For each Matomo site:
- **Traffic Trends**: Compare 2024 vs 2025 visits, pageviews, pages/visit, bounce rate, avg time
- **Referrer Shifts**: How did traffic sources change? (direct, search, social, campaigns, AI assistants)
- **Content Performance**: Notable changes in top pages, entry/exit patterns
- **Ecommerce** (alconox.com): Revenue, orders, AOV, conversion rate changes
- **Key Observations**: 3-5 bullet points on the most significant YoY changes

## Paid Media YoY Comparison
### Google Ads
- Compare 2024 vs 2025: spend, impressions, clicks, CTR, CPC, conversions, cost per conversion
- Efficiency analysis: are we getting more or less for our money?
- Campaign-level highlights (top performers, biggest changes)

### LinkedIn Ads
- Compare using the "compare" columns in the data (2024 baseline vs 2025 current)
- Spend, impressions, clicks, video views, video completions, engagement rate
- Campaign strategy shifts (new campaigns, paused campaigns, objective changes)

## Cross-Channel Insights
- What's working across the full marketing mix
- What's declining or concerning
- Emerging trends (AI traffic, video, B2B social)
- How paid and organic channels interact

## Strategic Recommendations
- **Short-term** (next 30 days): quick wins based on the data
- **Medium-term** (next quarter): tactical improvements
- **Long-term** (6-12 months): strategic initiatives

Use specific numbers and calculate percentage changes. Flag any data gaps or anomalies. Write in a professional but accessible tone suitable for marketing leadership.

---

DATA:
"""


# ============================================================
# Claude API Call
# ============================================================

def call_claude_api(data: dict, yoy: bool = False) -> str:
    """Send aggregated data to Claude API and return the analysis text."""
    client = anthropic.Anthropic()

    base_prompt = YOY_ANALYSIS_PROMPT if yoy else ANALYSIS_PROMPT
    data_json = json.dumps(data, indent=2, default=str)
    prompt = base_prompt + "\n" + data_json

    token_est = estimate_tokens(data)
    print(f"\n  Estimated tokens: ~{token_est:,}")

    # Always apply standard truncation to keep things reasonable
    if token_est > 80_000:
        print("  Applying standard truncation...")
        data = truncate_data(data, aggressive=False)
        data_json = json.dumps(data, indent=2, default=str)
        prompt = base_prompt + "\n" + data_json
        token_est = estimate_tokens(data)
        print(f"  Reduced to ~{token_est:,} tokens")

    # Aggressive truncation if still too large
    if token_est > 150_000:
        print("  Still too large, applying aggressive truncation...")
        data = truncate_data(data, aggressive=True)
        data_json = json.dumps(data, indent=2, default=str)
        prompt = base_prompt + "\n" + data_json
        token_est = estimate_tokens(data)
        print(f"  Reduced to ~{token_est:,} tokens")

    print("  Calling Claude API (this may take a minute)...")
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=16384,
            messages=[{
                "role": "user",
                "content": prompt,
            }],
        )
    except anthropic.APIStatusError as e:
        if "context_length" in str(e).lower() or "too many tokens" in str(e).lower():
            print("  Context window exceeded — retrying with aggressive truncation...")
            data = truncate_data(data, aggressive=True)
            data_json = json.dumps(data, indent=2, default=str)
            prompt = base_prompt + "\n" + data_json
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=16384,
                messages=[{
                    "role": "user",
                    "content": prompt,
                }],
            )
        else:
            raise

    # Handle stop reason
    if response.stop_reason == "refusal":
        print("  Error: The model refused to generate a response.")
        sys.exit(1)

    # Extract text blocks (skip thinking blocks)
    text_parts = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)

    if not text_parts:
        print("  Error: No text content in response.")
        sys.exit(1)

    usage = response.usage
    print(f"  Done. Input tokens: {usage.input_tokens:,}, Output tokens: {usage.output_tokens:,}")

    return "\n\n".join(text_parts)


# ============================================================
# Output
# ============================================================

def save_report(analysis: str, sites: list[dict], date_range: DateRange,
                data_sources: list[str]) -> str:
    """Save the analysis as a markdown report to reports/."""
    os.makedirs("reports", exist_ok=True)

    site_names = [s.get("name", "Unknown") for s in sites]
    sites_label = "_".join(s.replace(" ", "") for s in site_names)
    if len(sites_label) > 40:
        sites_label = f"{len(sites)}sites"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reports/AI_Analysis_{sites_label}_{timestamp}.md"

    header = f"""# AI-Powered Analytics Report
## {', '.join(site_names)}
### {date_range.label} ({date_range.start} to {date_range.end})

**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
**Data Sources:** {', '.join(data_sources)}
**Model:** Claude Opus 4.6

---

"""

    footer = f"""

---

*Report generated by AI Analyzer using Claude Opus 4.6*
*Data sources: {', '.join(data_sources)}*
*Date range: {date_range.label} ({date_range.start} to {date_range.end})*
"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(header + analysis + footer)

    return filename


# ============================================================
# Interactive CLI
# ============================================================

def main():
    """Main entry point — interactive CLI."""
    print("\n" + "=" * 60)
    print("  AI-POWERED ANALYTICS ANALYZER")
    print("=" * 60)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nError: ANTHROPIC_API_KEY environment variable is not set.")
        print("Set it with: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    # Connect to Matomo and list sites
    api = MatomoAPI()
    try:
        sites = api.get_sites()
        if not sites:
            print("No Matomo sites found.")
            return
    except Exception as e:
        print(f"Error connecting to Matomo: {e}")
        return

    # Site selection
    print(f"\nAvailable sites:")
    print(f"  0. All sites")
    for i, site in enumerate(sites, 1):
        print(f"  {i}. {site.get('name')} (ID: {site.get('idsite')})")

    try:
        choice = input(f"\nSelect site(s) (0-{len(sites)}): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting...")
        return

    if choice == "0":
        selected_sites = sites
    elif choice.isdigit() and 1 <= int(choice) <= len(sites):
        selected_sites = [sites[int(choice) - 1]]
    else:
        print("Invalid selection. Using all sites.")
        selected_sites = sites

    # Date range selection
    print("\nSelect date range:")
    print("  1. Last 7 days")
    print("  2. Last 30 days")
    print("  3. Last 90 days")
    print("  4. This month")
    print("  5. Last month")
    print("  6. This year")
    print("  7. Year-over-Year (2024 vs 2025)")

    try:
        dr_choice = input("\nChoice (1-7): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting...")
        return

    is_yoy = dr_choice == "7"

    date_ranges = {
        "1": DateRange.last_7_days(),
        "2": DateRange.last_30_days(),
        "3": DateRange.last_90_days(),
        "4": DateRange.this_month(),
        "5": DateRange.last_month(),
        "6": DateRange.this_year(),
        "7": DateRange("2025-01-01", "2025-12-31", "2024 vs 2025 Year-over-Year"),
    }
    date_range = date_ranges.get(dr_choice, DateRange.last_30_days())

    data = {}
    data_sources = []

    if is_yoy:
        date_range_2024 = DateRange("2024-01-01", "2024-12-31", "2024")
        date_range_2025 = DateRange("2025-01-01", "2025-12-31", "2025")

        # Matomo — fetch both years
        print(f"\nAggregating data for 2024 vs 2025...")
        print("-" * 40)

        print("  --- 2024 ---")
        matomo_2024_full = aggregate_matomo_data(selected_sites, date_range_2024)
        print("  --- 2025 ---")
        matomo_2025_full = aggregate_matomo_data(selected_sites, date_range_2025)
        if matomo_2024_full or matomo_2025_full:
            data["matomo_2024"] = summarize_matomo_for_yoy(matomo_2024_full)
            data["matomo_2025"] = summarize_matomo_for_yoy(matomo_2025_full)
            data_sources.append("Matomo Analytics")

        # Google Ads — fetch both years
        print("  --- Google Ads 2024 ---")
        google_2024 = aggregate_google_ads_data("2024-01-01", "2024-12-31")
        print("  --- Google Ads 2025 ---")
        google_2025 = aggregate_google_ads_data("2025-01-01", "2025-12-31")
        if google_2024 or google_2025:
            data["google_ads_2024"] = google_2024
            data["google_ads_2025"] = google_2025
            data_sources.append("Google Ads")

        # LinkedIn — already has compare columns (2024 vs 2025)
        linkedin_data = aggregate_linkedin_data()
        if linkedin_data:
            data["linkedin_ads"] = linkedin_data
            data_sources.append("LinkedIn Ads (CSV includes 2024 comparison data)")

    else:
        # Single date range mode
        print(f"\nAggregating data for {date_range.label}...")
        print("-" * 40)

        # Matomo
        matomo_data = aggregate_matomo_data(selected_sites, date_range)
        if matomo_data:
            data["matomo"] = matomo_data
            data_sources.append("Matomo Analytics")

        # Google Ads
        google_data = aggregate_google_ads_data(date_range.start, date_range.end)
        if google_data:
            data["google_ads"] = google_data
            data_sources.append("Google Ads")

        # LinkedIn
        linkedin_data = aggregate_linkedin_data()
        if linkedin_data:
            data["linkedin_ads"] = linkedin_data
            data_sources.append("LinkedIn Ads")

    if not data:
        print("\nNo data collected from any source. Exiting.")
        return

    print("-" * 40)
    print(f"Data sources collected: {', '.join(data_sources)}")

    # Call Claude API — use YoY prompt if applicable
    analysis = call_claude_api(data, yoy=is_yoy)

    # Save report
    filename = save_report(analysis, selected_sites, date_range, data_sources)

    print(f"\n{'=' * 60}")
    print(f"  REPORT SAVED")
    print(f"{'=' * 60}")
    print(f"\n  File: {filename}")
    print(f"  Sources: {', '.join(data_sources)}")
    print(f"  Date range: {date_range.label}")

    # Print first few lines as preview
    preview_lines = analysis.strip().split("\n")[:8]
    print(f"\n  Preview:")
    for line in preview_lines:
        print(f"    {line}")
    if len(analysis.strip().split("\n")) > 8:
        print(f"    ...")

    print()


if __name__ == "__main__":
    main()
