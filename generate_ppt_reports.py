#!/usr/bin/env python3
"""
Generate PowerPoint-ready reports for all Alconox web properties.
Outputs formatted text and CSV files that can be easily copied into presentations.
"""

import csv
import os
from datetime import datetime
from matomo_analyzer import MatomoAPI, ReportGenerator, DateRange


def generate_all_reports(output_dir: str = "reports"):
    """Generate comprehensive reports for all sites."""
    api = MatomoAPI()
    reporter = ReportGenerator(api)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Get all sites
    sites = api.get_sites()
    print(f"Found {len(sites)} sites")

    # Date ranges to generate
    date_ranges = [
        DateRange.last_30_days(),
        DateRange.last_7_days(),
        DateRange.this_month(),
    ]

    for site in sites:
        site_id = int(site.get("idsite"))
        site_name = site.get("name", "Unknown").replace(" ", "_").replace("/", "_")

        print(f"\nGenerating reports for: {site.get('name')}")

        for date_range in date_ranges:
            date_label = date_range.label.replace(" ", "_")
            prefix = f"{output_dir}/{site_name}_{date_label}"

            print(f"  - {date_range.label}...")

            try:
                # Traffic Summary (text format for easy copying)
                summary = reporter.generate_traffic_summary(site_id, date_range)
                with open(f"{prefix}_summary.txt", "w") as f:
                    f.write(f"{summary['title']}\n")
                    f.write("=" * 50 + "\n\n")
                    for key, value in summary["metrics"].items():
                        f.write(f"{key}: {value}\n")

                # Traffic Sources
                sources = reporter.generate_traffic_sources_report(site_id, date_range)
                write_report_csv(sources, f"{prefix}_traffic_sources.csv")

                # Top Pages
                pages = reporter.generate_top_pages_report(site_id, date_range)
                write_report_csv(pages, f"{prefix}_top_pages.csv")

                # Devices
                devices = reporter.generate_devices_report(site_id, date_range)
                write_report_csv(devices, f"{prefix}_devices.csv")

                # Countries
                countries = reporter.generate_countries_report(site_id, date_range)
                write_report_csv(countries, f"{prefix}_countries.csv")

                # Search Engines
                search = reporter.generate_search_engines_report(site_id, date_range)
                write_report_csv(search, f"{prefix}_search_engines.csv")

                # Social Networks
                social = reporter.generate_social_report(site_id, date_range)
                write_report_csv(social, f"{prefix}_social.csv")

                # Referrers
                referrers = reporter.generate_referrers_report(site_id, date_range)
                write_report_csv(referrers, f"{prefix}_referrers.csv")

            except Exception as e:
                print(f"    Error: {e}")

    # Generate combined executive summary
    generate_executive_summary(api, reporter, output_dir)

    print(f"\nReports saved to: {output_dir}/")
    print("\nGenerated files can be opened in Excel and copied to PowerPoint.")


def write_report_csv(report: dict, filename: str):
    """Write a report to CSV format."""
    if "data" not in report or not report["data"]:
        return

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=report["columns"])
        writer.writeheader()
        writer.writerows(report["data"])


def generate_executive_summary(api: MatomoAPI, reporter: ReportGenerator, output_dir: str):
    """Generate an executive summary comparing all sites."""
    sites = api.get_sites()
    date_range = DateRange.last_30_days()

    summary_data = []
    for site in sites:
        site_id = int(site.get("idsite"))
        site_name = site.get("name")

        try:
            date_str = f"{date_range.start},{date_range.end}"
            data = api.get_visits_summary(site_id, period="range", date=date_str)

            summary_data.append({
                "Site": site_name,
                "URL": site.get("main_url", ""),
                "Visits": reporter.format_number(data.get("nb_visits")),
                "Pageviews": reporter.format_number(data.get("nb_actions")),
                "Pages/Visit": reporter.format_number(data.get("nb_actions_per_visit")),
                "Avg Duration": reporter.format_time(data.get("avg_time_on_site")),
                "Bounce Rate": reporter.format_percentage(data.get("bounce_rate")),
            })
        except Exception as e:
            print(f"  Error getting summary for {site_name}: {e}")

    # Write executive summary
    filename = f"{output_dir}/EXECUTIVE_SUMMARY_{date_range.label.replace(' ', '_')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        if summary_data:
            writer = csv.DictWriter(f, fieldnames=summary_data[0].keys())
            writer.writeheader()
            writer.writerows(summary_data)

    # Also write as formatted text
    txt_filename = f"{output_dir}/EXECUTIVE_SUMMARY_{date_range.label.replace(' ', '_')}.txt"
    with open(txt_filename, "w") as f:
        f.write(f"ALCONOX WEB PROPERTIES - EXECUTIVE SUMMARY\n")
        f.write(f"Period: {date_range.label} ({date_range.start} to {date_range.end})\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 70 + "\n\n")

        for site in summary_data:
            f.write(f"{site['Site']}\n")
            f.write(f"  URL: {site['URL']}\n")
            f.write(f"  Visits: {site['Visits']} | Pageviews: {site['Pageviews']}\n")
            f.write(f"  Pages/Visit: {site['Pages/Visit']} | Avg Duration: {site['Avg Duration']}\n")
            f.write(f"  Bounce Rate: {site['Bounce Rate']}\n")
            f.write("\n")

    print(f"  Executive summary saved")


if __name__ == "__main__":
    generate_all_reports()
