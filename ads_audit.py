#!/usr/bin/env python3
"""
Google Ads Audit Tool
Pulls ad-level detail (ad copy, keywords, search terms, quality scores)
to identify optimization opportunities.
"""

import json
import os
from datetime import datetime, timedelta
from google.ads.googleads.client import GoogleAdsClient

CUSTOMER_ID = "4205046148"
CONFIG_PATH = "google_ads_config.yaml"


def get_client():
    return GoogleAdsClient.load_from_storage(CONFIG_PATH, version="v22")


def get_ad_group_performance(client, customer_id, start_date, end_date):
    """Get ad group level performance."""
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            ad_group.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM ad_group
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 50
    """
    response = ga_service.search_stream(customer_id=customer_id, query=query)
    results = []
    for batch in response:
        for row in batch.results:
            results.append({
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "status": row.ad_group.status.name,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": round(row.metrics.cost_micros / 1_000_000, 2),
                "conversions": round(row.metrics.conversions, 1),
                "ctr": round(row.metrics.ctr * 100, 2),
                "avg_cpc": round(row.metrics.average_cpc / 1_000_000, 2) if row.metrics.average_cpc else 0,
            })
    return results


def get_ad_copy_performance(client, customer_id, start_date, end_date):
    """Get responsive search ad headlines and descriptions with performance."""
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            ad_group_ad.ad.responsive_search_ad.headlines,
            ad_group_ad.ad.responsive_search_ad.descriptions,
            ad_group_ad.ad.final_urls,
            ad_group_ad.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM ad_group_ad
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'
            AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 30
    """
    response = ga_service.search_stream(customer_id=customer_id, query=query)
    results = []
    for batch in response:
        for row in batch.results:
            ad = row.ad_group_ad.ad
            headlines = [h.text for h in ad.responsive_search_ad.headlines] if ad.responsive_search_ad.headlines else []
            descriptions = [d.text for d in ad.responsive_search_ad.descriptions] if ad.responsive_search_ad.descriptions else []
            final_urls = list(ad.final_urls) if ad.final_urls else []

            results.append({
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "status": row.ad_group_ad.status.name,
                "headlines": headlines,
                "descriptions": descriptions,
                "final_urls": final_urls,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": round(row.metrics.cost_micros / 1_000_000, 2),
                "conversions": round(row.metrics.conversions, 1),
                "ctr": round(row.metrics.ctr * 100, 2),
                "avg_cpc": round(row.metrics.average_cpc / 1_000_000, 2) if row.metrics.average_cpc else 0,
            })
    return results


def get_keyword_performance(client, customer_id, start_date, end_date):
    """Get keyword-level performance with quality scores."""
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.quality_info.quality_score,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM keyword_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """
    response = ga_service.search_stream(customer_id=customer_id, query=query)
    results = []
    for batch in response:
        for row in batch.results:
            results.append({
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "keyword": row.ad_group_criterion.keyword.text,
                "match_type": row.ad_group_criterion.keyword.match_type.name,
                "quality_score": row.ad_group_criterion.quality_info.quality_score or None,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": round(row.metrics.cost_micros / 1_000_000, 2),
                "conversions": round(row.metrics.conversions, 1),
                "ctr": round(row.metrics.ctr * 100, 2),
                "avg_cpc": round(row.metrics.average_cpc / 1_000_000, 2) if row.metrics.average_cpc else 0,
            })
    return results


def get_search_terms(client, customer_id, start_date, end_date):
    """Get actual search terms that triggered ads."""
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            search_term_view.search_term,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr
        FROM search_term_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND metrics.impressions > 10
        ORDER BY metrics.impressions DESC
        LIMIT 100
    """
    response = ga_service.search_stream(customer_id=customer_id, query=query)
    results = []
    for batch in response:
        for row in batch.results:
            results.append({
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "search_term": row.search_term_view.search_term,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": round(row.metrics.cost_micros / 1_000_000, 2),
                "conversions": round(row.metrics.conversions, 1),
                "ctr": round(row.metrics.ctr * 100, 2),
            })
    return results


def main():
    # Full 2025 + 2026 YTD
    start_date = "2025-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"  GOOGLE ADS AUDIT: {start_date} to {end_date}")
    print(f"{'='*60}")

    client = get_client()
    customer_id = CUSTOMER_ID

    print("\nFetching ad group performance...")
    ad_groups = get_ad_group_performance(client, customer_id, start_date, end_date)
    print(f"  Found {len(ad_groups)} ad groups")

    print("Fetching ad copy...")
    ads = get_ad_copy_performance(client, customer_id, start_date, end_date)
    print(f"  Found {len(ads)} ads")

    print("Fetching keyword performance...")
    keywords = get_keyword_performance(client, customer_id, start_date, end_date)
    print(f"  Found {len(keywords)} keywords")

    print("Fetching search terms...")
    search_terms = get_search_terms(client, customer_id, start_date, end_date)
    print(f"  Found {len(search_terms)} search terms")

    # Save raw data for analysis
    audit_data = {
        "date_range": {"start": start_date, "end": end_date},
        "ad_groups": ad_groups,
        "ads": ads,
        "keywords": keywords,
        "search_terms": search_terms,
    }

    os.makedirs("reports", exist_ok=True)
    output_file = "reports/ads_audit_data.json"
    with open(output_file, "w") as f:
        json.dump(audit_data, f, indent=2, default=str)
    print(f"\nRaw data saved to {output_file}")

    # Print summary
    print(f"\n{'='*60}")
    print("  AD COPY REVIEW")
    print(f"{'='*60}")
    for ad in ads[:10]:
        print(f"\n  Campaign: {ad['campaign']}")
        print(f"  Ad Group: {ad['ad_group']}")
        print(f"  CTR: {ad['ctr']}% | Clicks: {ad['clicks']} | Conv: {ad['conversions']} | CPC: ${ad['avg_cpc']}")
        print(f"  Headlines: {' | '.join(ad['headlines'][:5])}")
        print(f"  Descriptions: {ad['descriptions'][:2]}")
        print(f"  URL: {ad['final_urls']}")

    print(f"\n{'='*60}")
    print("  TOP KEYWORDS (by spend)")
    print(f"{'='*60}")
    print(f"\n  {'Keyword':<35} {'Match':<10} {'QS':>4} {'Clicks':>8} {'CTR':>7} {'CPC':>8} {'Conv':>6}")
    print(f"  {'-'*80}")
    for kw in keywords[:25]:
        qs = str(kw['quality_score']) if kw['quality_score'] else '-'
        name = kw['keyword'][:34]
        print(f"  {name:<35} {kw['match_type']:<10} {qs:>4} {kw['clicks']:>8} {kw['ctr']:>6.1f}% ${kw['avg_cpc']:>6.2f} {kw['conversions']:>6.1f}")

    print(f"\n{'='*60}")
    print("  TOP SEARCH TERMS (what people actually searched)")
    print(f"{'='*60}")
    print(f"\n  {'Search Term':<45} {'Impr':>8} {'Clicks':>8} {'CTR':>7} {'Conv':>6}")
    print(f"  {'-'*76}")
    for st in search_terms[:25]:
        term = st['search_term'][:44]
        print(f"  {term:<45} {st['impressions']:>8} {st['clicks']:>8} {st['ctr']:>6.1f}% {st['conversions']:>6.1f}")

    # Flag issues
    print(f"\n{'='*60}")
    print("  POTENTIAL ISSUES")
    print(f"{'='*60}")

    # Low quality score keywords
    low_qs = [kw for kw in keywords if kw['quality_score'] and kw['quality_score'] <= 5]
    if low_qs:
        print(f"\n  Low Quality Score Keywords ({len(low_qs)}):")
        for kw in low_qs[:10]:
            print(f"    QS={kw['quality_score']}: {kw['keyword']} (${kw['cost']} spent)")

    # High spend, no conversions
    wasted = [kw for kw in keywords if kw['cost'] > 10 and kw['conversions'] == 0]
    if wasted:
        print(f"\n  High Spend, Zero Conversions ({len(wasted)} keywords):")
        for kw in wasted[:10]:
            print(f"    ${kw['cost']:.2f}: {kw['keyword']} ({kw['clicks']} clicks)")

    # Low CTR ads
    low_ctr = [ad for ad in ads if ad['ctr'] < 2.0 and ad['impressions'] > 100]
    if low_ctr:
        print(f"\n  Low CTR Ads (<2%, {len(low_ctr)} ads):")
        for ad in low_ctr[:5]:
            print(f"    CTR={ad['ctr']}%: {ad['ad_group']} in {ad['campaign']}")

    print()


if __name__ == "__main__":
    main()
