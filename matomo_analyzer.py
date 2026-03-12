#!/usr/bin/env python3
"""
Alconox Website Analytics Tool
Fetches data from Matomo API and generates PowerPoint-ready reports.
"""

import requests
import json
import csv
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import os

# Configuration
MATOMO_URL = "https://alconox.matomo.cloud"
API_TOKEN = os.environ.get("MATOMO_API_TOKEN", "")


@dataclass
class DateRange:
    """Represents a date range for analytics queries."""
    start: str
    end: str
    label: str

    @classmethod
    def last_7_days(cls) -> "DateRange":
        end = datetime.now()
        start = end - timedelta(days=7)
        return cls(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), "Last 7 Days")

    @classmethod
    def last_30_days(cls) -> "DateRange":
        end = datetime.now()
        start = end - timedelta(days=30)
        return cls(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), "Last 30 Days")

    @classmethod
    def last_90_days(cls) -> "DateRange":
        end = datetime.now()
        start = end - timedelta(days=90)
        return cls(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), "Last 90 Days")

    @classmethod
    def this_month(cls) -> "DateRange":
        now = datetime.now()
        start = now.replace(day=1)
        return cls(start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"), "This Month")

    @classmethod
    def last_month(cls) -> "DateRange":
        now = datetime.now()
        first_this_month = now.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return cls(last_month_start.strftime("%Y-%m-%d"), last_month_end.strftime("%Y-%m-%d"), "Last Month")

    @classmethod
    def this_year(cls) -> "DateRange":
        now = datetime.now()
        start = now.replace(month=1, day=1)
        return cls(start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"), "This Year")


class MatomoAPI:
    """Client for interacting with Matomo Analytics API."""

    def __init__(self, base_url: str = MATOMO_URL, token: str = API_TOKEN):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.api_url = f"{self.base_url}/index.php"

    def _request(self, method: str, params: Optional[Dict] = None) -> Any:
        """Make a request to the Matomo API using POST for token authentication."""
        query_params = {
            "module": "API",
            "method": method,
            "format": "json",
        }
        if params:
            query_params.update(params)

        # Send token as POST data for security (required by Matomo Cloud)
        post_data = {"token_auth": self.token}

        response = requests.post(self.api_url, params=query_params, data=post_data)
        response.raise_for_status()
        return response.json()

    def get_sites(self) -> List[Dict]:
        """Get all sites accessible with this API token."""
        return self._request("SitesManager.getSitesWithAtLeastViewAccess")

    def get_site_info(self, site_id: int) -> Dict:
        """Get information about a specific site."""
        result = self._request("SitesManager.getSiteFromId", {"idSite": site_id})
        return result[0] if isinstance(result, list) and result else result

    # ==================== TRAFFIC OVERVIEW ====================

    def get_visits_summary(self, site_id: int, period: str = "day",
                          date: str = "last30") -> Dict:
        """Get visit summary statistics."""
        return self._request("VisitsSummary.get", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_visits_over_time(self, site_id: int, period: str = "day",
                            date: str = "last30") -> Dict:
        """Get visits over time for charting."""
        return self._request("VisitsSummary.getVisits", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_pageviews_over_time(self, site_id: int, period: str = "day",
                                date: str = "last30") -> Dict:
        """Get pageviews over time for charting."""
        return self._request("VisitsSummary.getActions", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_bounce_rate(self, site_id: int, period: str = "day",
                       date: str = "last30") -> Dict:
        """Get bounce rate over time."""
        return self._request("VisitsSummary.getBounceCount", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    # ==================== ACQUISITION / REFERRERS ====================

    def get_referrer_types(self, site_id: int, period: str = "range",
                          date: str = "last30") -> List[Dict]:
        """Get traffic sources breakdown (direct, search, social, etc.)."""
        return self._request("Referrers.getReferrerType", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_search_engines(self, site_id: int, period: str = "range",
                          date: str = "last30") -> List[Dict]:
        """Get search engine traffic breakdown."""
        return self._request("Referrers.getSearchEngines", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_websites(self, site_id: int, period: str = "range",
                    date: str = "last30") -> List[Dict]:
        """Get referring websites."""
        return self._request("Referrers.getWebsites", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_social_networks(self, site_id: int, period: str = "range",
                           date: str = "last30") -> List[Dict]:
        """Get social network referrals."""
        return self._request("Referrers.getSocials", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_campaigns(self, site_id: int, period: str = "range",
                     date: str = "last30") -> List[Dict]:
        """Get campaign traffic."""
        return self._request("Referrers.getCampaigns", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_keywords(self, site_id: int, period: str = "range",
                    date: str = "last30") -> List[Dict]:
        """Get search keywords (limited due to search engine privacy)."""
        return self._request("Referrers.getKeywords", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    # ==================== CONTENT / PAGES ====================

    def get_page_urls(self, site_id: int, period: str = "range",
                     date: str = "last30", limit: int = 50) -> List[Dict]:
        """Get top pages by URL."""
        return self._request("Actions.getPageUrls", {
            "idSite": site_id,
            "period": period,
            "date": date,
            "filter_limit": limit,
            "flat": 1,
        })

    def get_page_titles(self, site_id: int, period: str = "range",
                       date: str = "last30", limit: int = 50) -> List[Dict]:
        """Get top pages by title."""
        return self._request("Actions.getPageTitles", {
            "idSite": site_id,
            "period": period,
            "date": date,
            "filter_limit": limit,
        })

    def get_entry_pages(self, site_id: int, period: str = "range",
                       date: str = "last30", limit: int = 20) -> List[Dict]:
        """Get top entry (landing) pages."""
        return self._request("Actions.getEntryPageUrls", {
            "idSite": site_id,
            "period": period,
            "date": date,
            "filter_limit": limit,
            "flat": 1,
        })

    def get_exit_pages(self, site_id: int, period: str = "range",
                      date: str = "last30", limit: int = 20) -> List[Dict]:
        """Get top exit pages."""
        return self._request("Actions.getExitPageUrls", {
            "idSite": site_id,
            "period": period,
            "date": date,
            "filter_limit": limit,
            "flat": 1,
        })

    def get_downloads(self, site_id: int, period: str = "range",
                     date: str = "last30", limit: int = 20) -> List[Dict]:
        """Get file downloads."""
        return self._request("Actions.getDownloads", {
            "idSite": site_id,
            "period": period,
            "date": date,
            "filter_limit": limit,
            "flat": 1,
        })

    def get_outlinks(self, site_id: int, period: str = "range",
                    date: str = "last30", limit: int = 20) -> List[Dict]:
        """Get outbound link clicks."""
        return self._request("Actions.getOutlinks", {
            "idSite": site_id,
            "period": period,
            "date": date,
            "filter_limit": limit,
            "flat": 1,
        })

    # ==================== VISITORS ====================

    def get_devices(self, site_id: int, period: str = "range",
                   date: str = "last30") -> List[Dict]:
        """Get device type breakdown."""
        return self._request("DevicesDetection.getType", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_browsers(self, site_id: int, period: str = "range",
                    date: str = "last30") -> List[Dict]:
        """Get browser breakdown."""
        return self._request("DevicesDetection.getBrowsers", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_operating_systems(self, site_id: int, period: str = "range",
                              date: str = "last30") -> List[Dict]:
        """Get OS breakdown."""
        return self._request("DevicesDetection.getOsVersions", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_countries(self, site_id: int, period: str = "range",
                     date: str = "last30") -> List[Dict]:
        """Get visitor countries."""
        return self._request("UserCountry.getCountry", {
            "idSite": site_id,
            "period": period,
            "date": date,
        })

    def get_cities(self, site_id: int, period: str = "range",
                  date: str = "last30", limit: int = 20) -> List[Dict]:
        """Get visitor cities."""
        return self._request("UserCountry.getCity", {
            "idSite": site_id,
            "period": period,
            "date": date,
            "filter_limit": limit,
        })

    # ==================== GOALS & CONVERSIONS ====================

    def get_goals(self, site_id: int) -> List[Dict]:
        """Get configured goals for a site."""
        return self._request("Goals.getGoals", {"idSite": site_id})

    def get_goal_conversions(self, site_id: int, period: str = "range",
                            date: str = "last30", goal_id: Optional[int] = None) -> Dict:
        """Get goal conversion data."""
        params = {
            "idSite": site_id,
            "period": period,
            "date": date,
        }
        if goal_id:
            params["idGoal"] = goal_id
        return self._request("Goals.get", params)


class ReportGenerator:
    """Generates PowerPoint-ready reports from Matomo data."""

    def __init__(self, api: MatomoAPI):
        self.api = api

    def format_number(self, num: Any) -> str:
        """Format numbers for display."""
        if num is None:
            return "N/A"
        if isinstance(num, float):
            if num == int(num):
                return f"{int(num):,}"
            return f"{num:,.2f}"
        if isinstance(num, int):
            return f"{num:,}"
        return str(num)

    def format_percentage(self, num: Any) -> str:
        """Format percentages for display."""
        if num is None:
            return "N/A"
        if isinstance(num, str):
            return num
        return f"{num:.1f}%"

    def format_time(self, seconds: Any) -> str:
        """Format seconds to mm:ss."""
        if seconds is None:
            return "N/A"
        if isinstance(seconds, str):
            return seconds
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{mins}:{secs:02d}"

    def generate_traffic_summary(self, site_id: int, date_range: DateRange) -> Dict:
        """Generate traffic overview summary."""
        date_str = f"{date_range.start},{date_range.end}"
        data = self.api.get_visits_summary(site_id, period="range", date=date_str)

        return {
            "title": f"Traffic Summary - {date_range.label}",
            "metrics": {
                "Total Visits": self.format_number(data.get("nb_visits")),
                "Unique Visitors": self.format_number(data.get("nb_uniq_visitors")),
                "Pageviews": self.format_number(data.get("nb_actions")),
                "Pages per Visit": self.format_number(data.get("nb_actions_per_visit")),
                "Avg. Visit Duration": self.format_time(data.get("avg_time_on_site")),
                "Bounce Rate": self.format_percentage(data.get("bounce_rate")),
            },
            "raw_data": data,
        }

    def generate_traffic_sources_report(self, site_id: int, date_range: DateRange) -> Dict:
        """Generate traffic sources breakdown."""
        date_str = f"{date_range.start},{date_range.end}"
        data = self.api.get_referrer_types(site_id, period="range", date=date_str)

        sources = []
        for item in data:
            sources.append({
                "Source": item.get("label", "Unknown"),
                "Visits": self.format_number(item.get("nb_visits")),
                "Pageviews": self.format_number(item.get("nb_actions")),
                "Bounce Rate": self.format_percentage(item.get("bounce_rate")),
            })

        return {
            "title": f"Traffic Sources - {date_range.label}",
            "columns": ["Source", "Visits", "Pageviews", "Bounce Rate"],
            "data": sources,
            "raw_data": data,
        }

    def generate_top_pages_report(self, site_id: int, date_range: DateRange,
                                  limit: int = 20) -> Dict:
        """Generate top pages report."""
        date_str = f"{date_range.start},{date_range.end}"
        data = self.api.get_page_urls(site_id, period="range", date=date_str, limit=limit)

        pages = []
        for item in data:
            pages.append({
                "Page URL": item.get("label", "Unknown"),
                "Pageviews": self.format_number(item.get("nb_hits")),
                "Unique Pageviews": self.format_number(item.get("nb_visits")),
                "Avg. Time on Page": self.format_time(item.get("avg_time_on_page")),
                "Bounce Rate": self.format_percentage(item.get("bounce_rate")),
                "Exit Rate": self.format_percentage(item.get("exit_rate")),
            })

        return {
            "title": f"Top Pages - {date_range.label}",
            "columns": ["Page URL", "Pageviews", "Unique Pageviews", "Avg. Time on Page", "Bounce Rate", "Exit Rate"],
            "data": pages,
            "raw_data": data,
        }

    def generate_search_engines_report(self, site_id: int, date_range: DateRange) -> Dict:
        """Generate search engine traffic report."""
        date_str = f"{date_range.start},{date_range.end}"
        data = self.api.get_search_engines(site_id, period="range", date=date_str)

        engines = []
        for item in data:
            engines.append({
                "Search Engine": item.get("label", "Unknown"),
                "Visits": self.format_number(item.get("nb_visits")),
                "Pageviews": self.format_number(item.get("nb_actions")),
                "Bounce Rate": self.format_percentage(item.get("bounce_rate")),
            })

        return {
            "title": f"Search Engine Traffic - {date_range.label}",
            "columns": ["Search Engine", "Visits", "Pageviews", "Bounce Rate"],
            "data": engines,
            "raw_data": data,
        }

    def generate_devices_report(self, site_id: int, date_range: DateRange) -> Dict:
        """Generate device breakdown report."""
        date_str = f"{date_range.start},{date_range.end}"
        data = self.api.get_devices(site_id, period="range", date=date_str)

        devices = []
        for item in data:
            devices.append({
                "Device Type": item.get("label", "Unknown"),
                "Visits": self.format_number(item.get("nb_visits")),
                "Pageviews": self.format_number(item.get("nb_actions")),
                "Bounce Rate": self.format_percentage(item.get("bounce_rate")),
            })

        return {
            "title": f"Device Breakdown - {date_range.label}",
            "columns": ["Device Type", "Visits", "Pageviews", "Bounce Rate"],
            "data": devices,
            "raw_data": data,
        }

    def generate_countries_report(self, site_id: int, date_range: DateRange,
                                  limit: int = 15) -> Dict:
        """Generate country breakdown report."""
        date_str = f"{date_range.start},{date_range.end}"
        data = self.api.get_countries(site_id, period="range", date=date_str)

        countries = []
        for item in data[:limit]:
            countries.append({
                "Country": item.get("label", "Unknown"),
                "Visits": self.format_number(item.get("nb_visits")),
                "Pageviews": self.format_number(item.get("nb_actions")),
                "Bounce Rate": self.format_percentage(item.get("bounce_rate")),
            })

        return {
            "title": f"Top Countries - {date_range.label}",
            "columns": ["Country", "Visits", "Pageviews", "Bounce Rate"],
            "data": countries,
            "raw_data": data,
        }

    def generate_referrers_report(self, site_id: int, date_range: DateRange,
                                  limit: int = 15) -> Dict:
        """Generate referring websites report."""
        date_str = f"{date_range.start},{date_range.end}"
        data = self.api.get_websites(site_id, period="range", date=date_str)

        referrers = []
        for item in data[:limit]:
            referrers.append({
                "Referring Website": item.get("label", "Unknown"),
                "Visits": self.format_number(item.get("nb_visits")),
                "Pageviews": self.format_number(item.get("nb_actions")),
                "Bounce Rate": self.format_percentage(item.get("bounce_rate")),
            })

        return {
            "title": f"Top Referring Websites - {date_range.label}",
            "columns": ["Referring Website", "Visits", "Pageviews", "Bounce Rate"],
            "data": referrers,
            "raw_data": data,
        }

    def generate_social_report(self, site_id: int, date_range: DateRange) -> Dict:
        """Generate social network traffic report."""
        date_str = f"{date_range.start},{date_range.end}"
        data = self.api.get_social_networks(site_id, period="range", date=date_str)

        social = []
        for item in data:
            social.append({
                "Social Network": item.get("label", "Unknown"),
                "Visits": self.format_number(item.get("nb_visits")),
                "Pageviews": self.format_number(item.get("nb_actions")),
                "Bounce Rate": self.format_percentage(item.get("bounce_rate")),
            })

        return {
            "title": f"Social Network Traffic - {date_range.label}",
            "columns": ["Social Network", "Visits", "Pageviews", "Bounce Rate"],
            "data": social,
            "raw_data": data,
        }

    def generate_full_report(self, site_id: int, date_range: DateRange) -> Dict:
        """Generate a complete report with all sections."""
        return {
            "site_id": site_id,
            "date_range": date_range.label,
            "generated_at": datetime.now().isoformat(),
            "sections": {
                "traffic_summary": self.generate_traffic_summary(site_id, date_range),
                "traffic_sources": self.generate_traffic_sources_report(site_id, date_range),
                "top_pages": self.generate_top_pages_report(site_id, date_range),
                "search_engines": self.generate_search_engines_report(site_id, date_range),
                "devices": self.generate_devices_report(site_id, date_range),
                "countries": self.generate_countries_report(site_id, date_range),
                "referrers": self.generate_referrers_report(site_id, date_range),
                "social": self.generate_social_report(site_id, date_range),
            }
        }


def print_table(report: Dict) -> None:
    """Print a report section as a formatted table."""
    print(f"\n{'='*60}")
    print(f"  {report['title']}")
    print(f"{'='*60}\n")

    if "metrics" in report:
        # Summary format
        for key, value in report["metrics"].items():
            print(f"  {key}: {value}")
    elif "data" in report:
        # Table format
        if not report["data"]:
            print("  No data available")
            return

        columns = report["columns"]
        col_widths = {col: len(col) for col in columns}

        for row in report["data"]:
            for col in columns:
                col_widths[col] = max(col_widths[col], len(str(row.get(col, ""))))

        # Print header
        header = " | ".join(col.ljust(col_widths[col]) for col in columns)
        print(f"  {header}")
        print(f"  {'-' * len(header)}")

        # Print rows
        for row in report["data"]:
            row_str = " | ".join(str(row.get(col, "")).ljust(col_widths[col]) for col in columns)
            print(f"  {row_str}")

    print()


def export_to_csv(report: Dict, filename: str) -> None:
    """Export a report section to CSV."""
    if "data" not in report or not report["data"]:
        print(f"No data to export for {report.get('title', 'Unknown')}")
        return

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=report["columns"])
        writer.writeheader()
        writer.writerows(report["data"])

    print(f"Exported to {filename}")


def main():
    """Main entry point for the analytics tool."""
    print("\n" + "="*60)
    print("  ALCONOX WEBSITE ANALYTICS TOOL")
    print("="*60)

    api = MatomoAPI()

    # Get available sites
    print("\nFetching available sites...")
    try:
        sites = api.get_sites()
        if not sites:
            print("No sites found. Check your API token permissions.")
            return

        print(f"\nFound {len(sites)} site(s):\n")
        for i, site in enumerate(sites, 1):
            print(f"  {i}. {site.get('name', 'Unknown')} (ID: {site.get('idsite')})")
            print(f"     URL: {site.get('main_url', 'N/A')}")

    except Exception as e:
        print(f"Error connecting to Matomo: {e}")
        return

    # Interactive menu
    print("\n" + "-"*60)
    print("OPTIONS:")
    print("-"*60)
    print("  1. Generate full report (Last 30 days)")
    print("  2. Generate full report (Last 7 days)")
    print("  3. Generate full report (This month)")
    print("  4. Generate full report (Last month)")
    print("  5. Export all reports to CSV")
    print("  6. Interactive data exploration")
    print("  7. Exit")

    while True:
        try:
            choice = input("\nSelect option (1-7): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "7":
            print("Goodbye!")
            break

        if not sites:
            print("No sites available.")
            continue

        site_id = int(sites[0].get("idsite", 1))

        if choice in ["1", "2", "3", "4", "5"]:
            reporter = ReportGenerator(api)

            date_ranges = {
                "1": DateRange.last_30_days(),
                "2": DateRange.last_7_days(),
                "3": DateRange.this_month(),
                "4": DateRange.last_month(),
                "5": DateRange.last_30_days(),
            }
            date_range = date_ranges.get(choice, DateRange.last_30_days())

            print(f"\nGenerating report for {date_range.label}...")

            try:
                if choice == "5":
                    # Export to CSV
                    reports = [
                        ("traffic_sources", reporter.generate_traffic_sources_report(site_id, date_range)),
                        ("top_pages", reporter.generate_top_pages_report(site_id, date_range)),
                        ("search_engines", reporter.generate_search_engines_report(site_id, date_range)),
                        ("devices", reporter.generate_devices_report(site_id, date_range)),
                        ("countries", reporter.generate_countries_report(site_id, date_range)),
                        ("referrers", reporter.generate_referrers_report(site_id, date_range)),
                        ("social", reporter.generate_social_report(site_id, date_range)),
                    ]
                    for name, report in reports:
                        export_to_csv(report, f"{name}_{date_range.start}_{date_range.end}.csv")
                else:
                    # Print reports
                    summary = reporter.generate_traffic_summary(site_id, date_range)
                    print_table(summary)

                    sources = reporter.generate_traffic_sources_report(site_id, date_range)
                    print_table(sources)

                    pages = reporter.generate_top_pages_report(site_id, date_range)
                    print_table(pages)

                    devices = reporter.generate_devices_report(site_id, date_range)
                    print_table(devices)

            except Exception as e:
                print(f"Error generating report: {e}")

        elif choice == "6":
            print("\n" + "="*60)
            print("  INTERACTIVE DATA EXPLORATION")
            print("="*60)
            print("\nAvailable commands:")
            print("  visits     - Get visit summary")
            print("  pages      - Top pages")
            print("  sources    - Traffic sources")
            print("  countries  - Visitor countries")
            print("  devices    - Device breakdown")
            print("  search     - Search engine traffic")
            print("  social     - Social network traffic")
            print("  referrers  - Referring websites")
            print("  raw <method> - Raw API call")
            print("  back       - Return to main menu")

            reporter = ReportGenerator(api)
            date_range = DateRange.last_30_days()

            while True:
                try:
                    cmd = input("\n> ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    break

                if cmd == "back":
                    break

                try:
                    if cmd == "visits":
                        report = reporter.generate_traffic_summary(site_id, date_range)
                        print_table(report)
                    elif cmd == "pages":
                        report = reporter.generate_top_pages_report(site_id, date_range)
                        print_table(report)
                    elif cmd == "sources":
                        report = reporter.generate_traffic_sources_report(site_id, date_range)
                        print_table(report)
                    elif cmd == "countries":
                        report = reporter.generate_countries_report(site_id, date_range)
                        print_table(report)
                    elif cmd == "devices":
                        report = reporter.generate_devices_report(site_id, date_range)
                        print_table(report)
                    elif cmd == "search":
                        report = reporter.generate_search_engines_report(site_id, date_range)
                        print_table(report)
                    elif cmd == "social":
                        report = reporter.generate_social_report(site_id, date_range)
                        print_table(report)
                    elif cmd == "referrers":
                        report = reporter.generate_referrers_report(site_id, date_range)
                        print_table(report)
                    elif cmd.startswith("raw "):
                        method = cmd[4:].strip()
                        result = api._request(method, {"idSite": site_id, "period": "range",
                                                       "date": f"{date_range.start},{date_range.end}"})
                        print(json.dumps(result, indent=2))
                    else:
                        print("Unknown command. Type 'back' to return to main menu.")
                except Exception as e:
                    print(f"Error: {e}")

        else:
            print("Invalid option. Please select 1-7.")


if __name__ == "__main__":
    main()
