#!/usr/bin/env python3
"""
Google Ads Analytics Tool
Fetches campaign performance data from Google Ads API.
"""

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
import yaml

# Load config
CONFIG_PATH = "google_ads_config.yaml"

def get_client():
    """Create and return a Google Ads client."""
    return GoogleAdsClient.load_from_storage(CONFIG_PATH, version="v19")

def get_campaigns(client, customer_id, start_date, end_date):
    """Get campaign performance data."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.ctr,
            metrics.average_cpc
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY metrics.cost_micros DESC
    """

    response = ga_service.search_stream(customer_id=customer_id, query=query)

    campaigns = []
    for batch in response:
        for row in batch.results:
            campaigns.append({
                "id": row.campaign.id,
                "name": row.campaign.name,
                "status": row.campaign.status.name,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": row.metrics.cost_micros / 1_000_000,  # Convert micros to dollars
                "conversions": row.metrics.conversions,
                "conversion_value": row.metrics.conversions_value,
                "ctr": row.metrics.ctr * 100,  # Convert to percentage
                "avg_cpc": row.metrics.average_cpc / 1_000_000 if row.metrics.average_cpc else 0,
            })

    return campaigns

def get_campaign_summary(client, customer_id, start_date, end_date):
    """Get aggregated campaign metrics."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM customer
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
    """

    response = ga_service.search_stream(customer_id=customer_id, query=query)

    totals = {
        "impressions": 0,
        "clicks": 0,
        "cost": 0,
        "conversions": 0,
        "conversion_value": 0,
    }

    for batch in response:
        for row in batch.results:
            totals["impressions"] += row.metrics.impressions
            totals["clicks"] += row.metrics.clicks
            totals["cost"] += row.metrics.cost_micros / 1_000_000
            totals["conversions"] += row.metrics.conversions
            totals["conversion_value"] += row.metrics.conversions_value

    # Calculate derived metrics
    totals["ctr"] = (totals["clicks"] / totals["impressions"] * 100) if totals["impressions"] > 0 else 0
    totals["avg_cpc"] = (totals["cost"] / totals["clicks"]) if totals["clicks"] > 0 else 0
    totals["cost_per_conversion"] = (totals["cost"] / totals["conversions"]) if totals["conversions"] > 0 else 0

    return totals

def print_campaign_report(campaigns, title):
    """Print formatted campaign report."""
    print("\n" + "=" * 90)
    print(f"  {title}")
    print("=" * 90)

    if not campaigns:
        print("  No campaign data found.")
        return

    print(f"\n  {'Campaign':<35} {'Spend':>12} {'Clicks':>10} {'Conv':>8} {'CPC':>10} {'CTR':>8}")
    print(f"  {'-' * 85}")

    for c in campaigns:
        name = c['name'][:34] if len(c['name']) > 34 else c['name']
        print(f"  {name:<35} ${c['cost']:>10,.2f} {c['clicks']:>10,} {c['conversions']:>8.1f} ${c['avg_cpc']:>8.2f} {c['ctr']:>7.2f}%")

def main():
    """Main entry point."""
    print("\n" + "=" * 70)
    print("  GOOGLE ADS ANALYTICS")
    print("=" * 70)

    try:
        client = get_client()
        customer_id = "3282542648"

        # 2024 data
        print("\nFetching 2024 data...")
        campaigns_2024 = get_campaigns(client, customer_id, "2024-01-01", "2024-12-31")
        summary_2024 = get_campaign_summary(client, customer_id, "2024-01-01", "2024-12-31")

        # 2025 data
        print("Fetching 2025 data...")
        campaigns_2025 = get_campaigns(client, customer_id, "2025-01-01", "2025-12-31")
        summary_2025 = get_campaign_summary(client, customer_id, "2025-01-01", "2025-12-31")

        # Print reports
        print_campaign_report(campaigns_2024, "GOOGLE ADS - 2024")
        print_campaign_report(campaigns_2025, "GOOGLE ADS - 2025")

        # Year over year comparison
        print("\n" + "=" * 70)
        print("  YEAR-OVER-YEAR COMPARISON: 2024 vs 2025")
        print("=" * 70)

        metrics = [
            ("Total Spend", "cost", "${:,.2f}"),
            ("Impressions", "impressions", "{:,}"),
            ("Clicks", "clicks", "{:,}"),
            ("CTR", "ctr", "{:.2f}%"),
            ("Avg CPC", "avg_cpc", "${:.2f}"),
            ("Conversions", "conversions", "{:.1f}"),
            ("Cost/Conversion", "cost_per_conversion", "${:.2f}"),
        ]

        print(f"\n  {'Metric':<20} {'2024':>15} {'2025':>15} {'Change':>15}")
        print(f"  {'-' * 65}")

        for label, key, fmt in metrics:
            val_2024 = summary_2024.get(key, 0)
            val_2025 = summary_2025.get(key, 0)

            if val_2024 > 0:
                change = ((val_2025 - val_2024) / val_2024) * 100
                change_str = f"{'↑' if change > 0 else '↓'} {abs(change):.1f}%"
            else:
                change_str = "N/A"

            fmt_2024 = fmt.format(val_2024)
            fmt_2025 = fmt.format(val_2025)
            print(f"  {label:<20} {fmt_2024:>15} {fmt_2025:>15} {change_str:>15}")

    except GoogleAdsException as ex:
        print(f"Google Ads API Error: {ex.failure.errors[0].message}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
