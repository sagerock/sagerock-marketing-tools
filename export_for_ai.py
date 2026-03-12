#!/usr/bin/env python3
"""
Export Matomo analytics data to JSON format for AI analysis.
This creates a comprehensive data dump that can be used with AI tools.
"""

import json
import sys
from datetime import datetime
from matomo_analyzer import MatomoAPI, ReportGenerator, DateRange


def export_comprehensive_data(site_id: int, date_range: DateRange, output_file: str = None) -> dict:
    """
    Export all available analytics data for AI analysis.
    Returns a comprehensive JSON structure with all metrics.
    """
    api = MatomoAPI()
    reporter = ReportGenerator(api)

    print(f"Fetching data for {date_range.label}...")

    # Build comprehensive data structure
    data = {
        "metadata": {
            "site_id": site_id,
            "date_range": {
                "label": date_range.label,
                "start": date_range.start,
                "end": date_range.end,
            },
            "generated_at": datetime.now().isoformat(),
            "data_source": "Matomo Analytics",
        },
        "summary": {},
        "traffic_sources": {},
        "content_performance": {},
        "audience": {},
        "raw_api_data": {},
    }

    date_str = f"{date_range.start},{date_range.end}"

    # Traffic Summary
    print("  - Fetching traffic summary...")
    try:
        summary = api.get_visits_summary(site_id, period="range", date=date_str)
        data["summary"]["overview"] = summary
        data["raw_api_data"]["visits_summary"] = summary
    except Exception as e:
        print(f"    Warning: Could not fetch traffic summary: {e}")

    # Traffic over time (for trends)
    print("  - Fetching traffic trends...")
    try:
        visits_daily = api.get_visits_over_time(site_id, period="day", date="last30")
        data["summary"]["daily_visits"] = visits_daily
        data["raw_api_data"]["visits_daily"] = visits_daily
    except Exception as e:
        print(f"    Warning: Could not fetch daily visits: {e}")

    try:
        pageviews_daily = api.get_pageviews_over_time(site_id, period="day", date="last30")
        data["summary"]["daily_pageviews"] = pageviews_daily
        data["raw_api_data"]["pageviews_daily"] = pageviews_daily
    except Exception as e:
        print(f"    Warning: Could not fetch daily pageviews: {e}")

    # Traffic Sources
    print("  - Fetching traffic sources...")
    try:
        data["traffic_sources"]["by_type"] = api.get_referrer_types(site_id, period="range", date=date_str)
        data["raw_api_data"]["referrer_types"] = data["traffic_sources"]["by_type"]
    except Exception as e:
        print(f"    Warning: Could not fetch referrer types: {e}")

    try:
        data["traffic_sources"]["search_engines"] = api.get_search_engines(site_id, period="range", date=date_str)
        data["raw_api_data"]["search_engines"] = data["traffic_sources"]["search_engines"]
    except Exception as e:
        print(f"    Warning: Could not fetch search engines: {e}")

    try:
        data["traffic_sources"]["referring_websites"] = api.get_websites(site_id, period="range", date=date_str)
        data["raw_api_data"]["websites"] = data["traffic_sources"]["referring_websites"]
    except Exception as e:
        print(f"    Warning: Could not fetch referring websites: {e}")

    try:
        data["traffic_sources"]["social_networks"] = api.get_social_networks(site_id, period="range", date=date_str)
        data["raw_api_data"]["social_networks"] = data["traffic_sources"]["social_networks"]
    except Exception as e:
        print(f"    Warning: Could not fetch social networks: {e}")

    try:
        data["traffic_sources"]["campaigns"] = api.get_campaigns(site_id, period="range", date=date_str)
        data["raw_api_data"]["campaigns"] = data["traffic_sources"]["campaigns"]
    except Exception as e:
        print(f"    Warning: Could not fetch campaigns: {e}")

    try:
        data["traffic_sources"]["keywords"] = api.get_keywords(site_id, period="range", date=date_str)
        data["raw_api_data"]["keywords"] = data["traffic_sources"]["keywords"]
    except Exception as e:
        print(f"    Warning: Could not fetch keywords: {e}")

    # Content Performance
    print("  - Fetching content performance...")
    try:
        data["content_performance"]["top_pages"] = api.get_page_urls(site_id, period="range", date=date_str, limit=50)
        data["raw_api_data"]["page_urls"] = data["content_performance"]["top_pages"]
    except Exception as e:
        print(f"    Warning: Could not fetch top pages: {e}")

    try:
        data["content_performance"]["page_titles"] = api.get_page_titles(site_id, period="range", date=date_str, limit=50)
        data["raw_api_data"]["page_titles"] = data["content_performance"]["page_titles"]
    except Exception as e:
        print(f"    Warning: Could not fetch page titles: {e}")

    try:
        data["content_performance"]["entry_pages"] = api.get_entry_pages(site_id, period="range", date=date_str)
        data["raw_api_data"]["entry_pages"] = data["content_performance"]["entry_pages"]
    except Exception as e:
        print(f"    Warning: Could not fetch entry pages: {e}")

    try:
        data["content_performance"]["exit_pages"] = api.get_exit_pages(site_id, period="range", date=date_str)
        data["raw_api_data"]["exit_pages"] = data["content_performance"]["exit_pages"]
    except Exception as e:
        print(f"    Warning: Could not fetch exit pages: {e}")

    try:
        data["content_performance"]["downloads"] = api.get_downloads(site_id, period="range", date=date_str)
        data["raw_api_data"]["downloads"] = data["content_performance"]["downloads"]
    except Exception as e:
        print(f"    Warning: Could not fetch downloads: {e}")

    try:
        data["content_performance"]["outlinks"] = api.get_outlinks(site_id, period="range", date=date_str)
        data["raw_api_data"]["outlinks"] = data["content_performance"]["outlinks"]
    except Exception as e:
        print(f"    Warning: Could not fetch outlinks: {e}")

    # Audience Data
    print("  - Fetching audience data...")
    try:
        data["audience"]["devices"] = api.get_devices(site_id, period="range", date=date_str)
        data["raw_api_data"]["devices"] = data["audience"]["devices"]
    except Exception as e:
        print(f"    Warning: Could not fetch devices: {e}")

    try:
        data["audience"]["browsers"] = api.get_browsers(site_id, period="range", date=date_str)
        data["raw_api_data"]["browsers"] = data["audience"]["browsers"]
    except Exception as e:
        print(f"    Warning: Could not fetch browsers: {e}")

    try:
        data["audience"]["operating_systems"] = api.get_operating_systems(site_id, period="range", date=date_str)
        data["raw_api_data"]["operating_systems"] = data["audience"]["operating_systems"]
    except Exception as e:
        print(f"    Warning: Could not fetch operating systems: {e}")

    try:
        data["audience"]["countries"] = api.get_countries(site_id, period="range", date=date_str)
        data["raw_api_data"]["countries"] = data["audience"]["countries"]
    except Exception as e:
        print(f"    Warning: Could not fetch countries: {e}")

    try:
        data["audience"]["cities"] = api.get_cities(site_id, period="range", date=date_str)
        data["raw_api_data"]["cities"] = data["audience"]["cities"]
    except Exception as e:
        print(f"    Warning: Could not fetch cities: {e}")

    # Goals
    print("  - Fetching goals...")
    try:
        goals = api.get_goals(site_id)
        data["goals"] = {
            "configured_goals": goals,
        }
        if goals:
            conversions = api.get_goal_conversions(site_id, period="range", date=date_str)
            data["goals"]["conversions"] = conversions
            data["raw_api_data"]["goals"] = goals
            data["raw_api_data"]["goal_conversions"] = conversions
    except Exception as e:
        print(f"    Warning: Could not fetch goals: {e}")

    # Save to file
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"\nData exported to: {output_file}")

    return data


def generate_ai_prompt(data: dict) -> str:
    """Generate a prompt for AI analysis of the data."""
    summary = data.get("summary", {}).get("overview", {})

    prompt = f"""
I have website analytics data for the period {data['metadata']['date_range']['label']}
({data['metadata']['date_range']['start']} to {data['metadata']['date_range']['end']}).

Key metrics:
- Total Visits: {summary.get('nb_visits', 'N/A')}
- Unique Visitors: {summary.get('nb_uniq_visitors', 'N/A')}
- Pageviews: {summary.get('nb_actions', 'N/A')}
- Pages per Visit: {summary.get('nb_actions_per_visit', 'N/A')}
- Avg Visit Duration: {summary.get('avg_time_on_site', 'N/A')} seconds
- Bounce Rate: {summary.get('bounce_rate', 'N/A')}

Please analyze this data and provide:
1. Key insights and trends
2. Areas of concern or opportunity
3. Recommendations for improvement
4. Comparison benchmarks (if relevant)

The full data is attached as JSON for deeper analysis.
"""
    return prompt


def main():
    """Main entry point."""
    api = MatomoAPI()

    print("\n" + "="*60)
    print("  MATOMO DATA EXPORT FOR AI ANALYSIS")
    print("="*60)

    # Get sites
    try:
        sites = api.get_sites()
        if not sites:
            print("No sites found.")
            return

        print(f"\nAvailable sites:")
        for site in sites:
            print(f"  - {site.get('name')} (ID: {site.get('idsite')})")

        site_id = int(sites[0].get("idsite", 1))
        site_name = sites[0].get("name", "unknown").replace(" ", "_").lower()

    except Exception as e:
        print(f"Error: {e}")
        return

    # Export options
    print("\nSelect date range:")
    print("  1. Last 7 days")
    print("  2. Last 30 days")
    print("  3. Last 90 days")
    print("  4. This month")
    print("  5. Last month")
    print("  6. This year")

    try:
        choice = input("\nChoice (1-6): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting...")
        return

    date_ranges = {
        "1": DateRange.last_7_days(),
        "2": DateRange.last_30_days(),
        "3": DateRange.last_90_days(),
        "4": DateRange.this_month(),
        "5": DateRange.last_month(),
        "6": DateRange.this_year(),
    }

    date_range = date_ranges.get(choice, DateRange.last_30_days())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"analytics_export_{site_name}_{timestamp}.json"

    data = export_comprehensive_data(site_id, date_range, output_file)

    # Generate AI prompt
    prompt = generate_ai_prompt(data)
    prompt_file = f"ai_analysis_prompt_{timestamp}.txt"
    with open(prompt_file, "w") as f:
        f.write(prompt)
    print(f"AI prompt saved to: {prompt_file}")

    print("\n" + "="*60)
    print("  NEXT STEPS")
    print("="*60)
    print(f"""
1. Open {output_file} to view the raw data
2. Use {prompt_file} as a starting prompt for AI analysis
3. Upload the JSON file to Claude, ChatGPT, or another AI tool
4. Ask follow-up questions about specific metrics

Example questions for AI:
- "What are the top performing pages and why?"
- "How does our traffic source mix compare to industry standards?"
- "What opportunities exist to improve bounce rate?"
- "Create a summary suitable for an executive presentation"
""")


if __name__ == "__main__":
    main()
