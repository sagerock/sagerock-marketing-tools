#!/usr/bin/env python3
"""
Weekly Google Ads Review
Pulls performance data from all accounts under the MCC,
flags issues, and generates a summary report.
"""

import json
import os
from datetime import datetime, timedelta
from google.ads.googleads.client import GoogleAdsClient

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_ads_config.yaml")
MCC_ID = "3282542648"


def get_client():
    return GoogleAdsClient.load_from_storage(CONFIG_PATH, version="v22")


def get_client_accounts(client):
    """Get all client accounts under the MCC."""
    ga_service = client.get_service("GoogleAdsService")
    query = """
        SELECT
            customer_client.id,
            customer_client.descriptive_name,
            customer_client.status,
            customer_client.manager
        FROM customer_client
        WHERE customer_client.status = 'ENABLED'
            AND customer_client.manager = false
    """
    response = ga_service.search(customer_id=MCC_ID, query=query)
    accounts = []
    for row in response:
        accounts.append({
            "id": str(row.customer_client.id),
            "name": row.customer_client.descriptive_name,
        })
    return accounts


def get_campaign_performance(client, customer_id, start_date, end_date):
    """Get campaign performance for a date range."""
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
    """
    try:
        response = ga_service.search(customer_id=customer_id, query=query)
        campaigns = []
        for row in response:
            campaigns.append({
                "name": row.campaign.name,
                "status": row.campaign.status.name,
                "type": row.campaign.advertising_channel_type.name,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": round(row.metrics.cost_micros / 1_000_000, 2),
                "conversions": round(row.metrics.conversions, 1),
                "ctr": round(row.metrics.ctr * 100, 2),
                "avg_cpc": round(row.metrics.average_cpc / 1_000_000, 2) if row.metrics.average_cpc else 0,
            })
        return campaigns
    except Exception as e:
        return [{"error": str(e)[:200]}]


def get_account_summary(campaigns):
    """Summarize campaign data for an account."""
    total_cost = sum(c.get("cost", 0) for c in campaigns if "error" not in c)
    total_clicks = sum(c.get("clicks", 0) for c in campaigns if "error" not in c)
    total_impressions = sum(c.get("impressions", 0) for c in campaigns if "error" not in c)
    total_conversions = sum(c.get("conversions", 0) for c in campaigns if "error" not in c)
    return {
        "cost": total_cost,
        "clicks": total_clicks,
        "impressions": total_impressions,
        "conversions": total_conversions,
        "ctr": round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0,
        "avg_cpc": round(total_cost / total_clicks, 2) if total_clicks > 0 else 0,
        "cost_per_conv": round(total_cost / total_conversions, 2) if total_conversions > 0 else 0,
    }


def flag_issues(campaigns, account_name):
    """Flag potential issues in campaign data."""
    issues = []
    for c in campaigns:
        if "error" in c:
            continue
        # High spend, no conversions
        if c["cost"] > 20 and c["conversions"] == 0:
            issues.append(f"⚠️ **{c['name']}**: ${c['cost']:.2f} spent, 0 conversions ({c['clicks']} clicks)")
        # Very low CTR
        if c["ctr"] < 1.0 and c["impressions"] > 500 and c["type"] == "SEARCH":
            issues.append(f"📉 **{c['name']}**: Low CTR {c['ctr']}% on search ({c['impressions']:,} impressions)")
        # High CPC
        if c["avg_cpc"] > 10 and c["clicks"] > 5:
            issues.append(f"💰 **{c['name']}**: High CPC ${c['avg_cpc']:.2f} ({c['clicks']} clicks)")
        # Video with no conversions and high spend
        if c["type"] == "VIDEO" and c["cost"] > 50 and c["conversions"] == 0:
            issues.append(f"🎬 **{c['name']}**: Video campaign ${c['cost']:.2f} spent, 0 conversions")
    return issues


def pct_change(current, previous):
    """Calculate percentage change."""
    if previous == 0:
        return "N/A" if current == 0 else "+∞"
    change = ((current - previous) / previous) * 100
    if change > 0:
        return f"+{change:.0f}%"
    return f"{change:.0f}%"


def generate_report():
    """Generate the full weekly report."""
    client = get_client()
    accounts = get_client_accounts(client)

    # Date ranges
    today = datetime.now()
    this_week_end = today.strftime("%Y-%m-%d")
    this_week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    last_week_end = (today - timedelta(days=8)).strftime("%Y-%m-%d")
    last_week_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")

    report_lines = []
    report_lines.append(f"# Weekly Google Ads Review")
    report_lines.append(f"**Week of {this_week_start} to {this_week_end}**\n")
    report_lines.append("---\n")

    all_issues = []
    total_spend_this = 0
    total_spend_last = 0

    for account in accounts:
        cid = account["id"]
        name = account["name"]

        this_week = get_campaign_performance(client, cid, this_week_start, this_week_end)
        last_week = get_campaign_performance(client, cid, last_week_start, last_week_end)

        # Skip if errors on both
        if this_week and "error" in this_week[0] and last_week and "error" in last_week[0]:
            report_lines.append(f"## {name}\n")
            report_lines.append(f"⚠️ Error fetching data: {this_week[0]['error'][:100]}\n")
            continue

        summary_this = get_account_summary(this_week)
        summary_last = get_account_summary(last_week)

        total_spend_this += summary_this["cost"]
        total_spend_last += summary_last["cost"]

        report_lines.append(f"## {name}")
        report_lines.append(f"| Metric | This Week | Last Week | Change |")
        report_lines.append(f"|--------|-----------|-----------|--------|")
        report_lines.append(f"| Spend | ${summary_this['cost']:,.2f} | ${summary_last['cost']:,.2f} | {pct_change(summary_this['cost'], summary_last['cost'])} |")
        report_lines.append(f"| Clicks | {summary_this['clicks']:,} | {summary_last['clicks']:,} | {pct_change(summary_this['clicks'], summary_last['clicks'])} |")
        report_lines.append(f"| Impressions | {summary_this['impressions']:,} | {summary_last['impressions']:,} | {pct_change(summary_this['impressions'], summary_last['impressions'])} |")
        report_lines.append(f"| CTR | {summary_this['ctr']}% | {summary_last['ctr']}% | {pct_change(summary_this['ctr'], summary_last['ctr'])} |")
        report_lines.append(f"| Conversions | {summary_this['conversions']} | {summary_last['conversions']} | {pct_change(summary_this['conversions'], summary_last['conversions'])} |")
        report_lines.append(f"| Avg CPC | ${summary_this['avg_cpc']:.2f} | ${summary_last['avg_cpc']:.2f} | {pct_change(summary_this['avg_cpc'], summary_last['avg_cpc'])} |")
        report_lines.append("")

        # Active campaigns detail
        active = [c for c in this_week if "error" not in c and c["cost"] > 0]
        if active:
            report_lines.append("**Active campaigns:**")
            for c in active:
                conv_str = f", {c['conversions']} conv" if c['conversions'] > 0 else ""
                report_lines.append(f"- {c['name']} ({c['type']}): ${c['cost']:.2f}, {c['clicks']} clicks, {c['ctr']}% CTR{conv_str}")
            report_lines.append("")

        # Issues
        issues = flag_issues(this_week, name)
        if issues:
            all_issues.append(f"**{name}:**")
            all_issues.extend(issues)
            all_issues.append("")

    # Executive summary at top
    header = []
    header.append(f"## Executive Summary\n")
    header.append(f"**Total spend this week:** ${total_spend_this:,.2f} ({pct_change(total_spend_this, total_spend_last)} vs last week)")
    header.append(f"**Total spend last week:** ${total_spend_last:,.2f}\n")

    if all_issues:
        header.append("### Issues to Review\n")
        header.extend(all_issues)
    else:
        header.append("✅ No issues flagged this week.\n")

    header.append("---\n")

    # Insert header after the title
    report_lines = report_lines[:3] + header + report_lines[3:]

    return "\n".join(report_lines)


def main():
    """Generate and print the weekly report."""
    print("Generating weekly Google Ads review...")
    report = generate_report()

    # Save report
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"reports/weekly_ads_review_{timestamp}.md"
    with open(filename, "w") as f:
        f.write(report)
    print(f"Report saved to {filename}")

    # Print report
    print("\n" + report)

    return report


if __name__ == "__main__":
    main()
