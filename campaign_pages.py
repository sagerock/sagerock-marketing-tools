#!/usr/bin/env python3
"""
Find pages visited via a specific campaign tracking code.
"""

import requests
import os
from datetime import datetime, timedelta
from urllib.parse import quote

MATOMO_URL = "https://alconox.matomo.cloud"
API_TOKEN = os.environ.get("MATOMO_API_TOKEN", "")

SITES = {
    1: "Alconox.com",
    6: "TechNotes",
}

CAMPAIGN_NAME = "email-campaign-email-sagerock"

def get_campaign_pages(site_id: int, site_name: str, campaign: str, days: int = 14):
    """Get pages visited via a specific campaign."""
    end = datetime.now()
    start = end - timedelta(days=days)
    date_str = f"{start.strftime('%Y-%m-%d')},{end.strftime('%Y-%m-%d')}"

    # Segment to filter by campaign name
    segment = f"referrerName=={quote(campaign, safe='')}"

    api_url = f"{MATOMO_URL}/index.php"

    # Get page URLs for this campaign
    params = {
        "module": "API",
        "method": "Actions.getPageUrls",
        "idSite": site_id,
        "period": "range",
        "date": date_str,
        "format": "json",
        "filter_limit": 100,
        "flat": 1,
        "segment": segment,
    }

    response = requests.post(api_url, params=params, data={"token_auth": API_TOKEN})
    response.raise_for_status()
    pages = response.json()

    # Also get entry pages (landing pages) for this campaign
    params["method"] = "Actions.getEntryPageUrls"
    response = requests.post(api_url, params=params, data={"token_auth": API_TOKEN})
    response.raise_for_status()
    entry_pages = response.json()

    # Get campaign summary stats
    params["method"] = "Referrers.getCampaigns"
    del params["flat"]
    response = requests.post(api_url, params=params, data={"token_auth": API_TOKEN})
    response.raise_for_status()
    campaigns = response.json()

    print(f"\n{'='*70}")
    print(f"  {site_name} (Site ID: {site_id})")
    print(f"  Campaign: {campaign}")
    print(f"  Date Range: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
    print(f"{'='*70}")

    # Show campaign stats if found
    campaign_found = False
    for c in campaigns if isinstance(campaigns, list) else []:
        if campaign.lower() in c.get("label", "").lower():
            campaign_found = True
            print(f"\n  Campaign Stats:")
            print(f"    Visits: {c.get('nb_visits', 0)}")
            print(f"    Pageviews: {c.get('nb_actions', 0)}")
            print(f"    Bounce Rate: {c.get('bounce_rate', 'N/A')}")

    if not campaign_found:
        print(f"\n  No visits found for this campaign in the date range.")
        return

    # Show landing pages
    print(f"\n  Entry/Landing Pages:")
    print(f"  {'-'*66}")
    if entry_pages and isinstance(entry_pages, list):
        for page in entry_pages[:20]:
            url = page.get("label", "Unknown")
            visits = page.get("nb_visits", 0)
            print(f"    {visits:>5} visits | {url}")
    else:
        print("    No entry pages found")

    # Show all pages viewed
    print(f"\n  All Pages Viewed:")
    print(f"  {'-'*66}")
    if pages and isinstance(pages, list):
        for page in pages[:30]:
            url = page.get("label", "Unknown")
            hits = page.get("nb_hits", 0)
            print(f"    {hits:>5} views  | {url}")
    else:
        print("    No pages found")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("  CAMPAIGN PAGE REPORT")
    print("="*70)

    for site_id, site_name in SITES.items():
        get_campaign_pages(site_id, site_name, CAMPAIGN_NAME)

    print()
