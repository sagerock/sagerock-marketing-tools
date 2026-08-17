#!/usr/bin/env python3
"""
matomo_linkedin_quality.py — compare the QUALITY of LinkedIn-referred sessions on
alconox.com across two date ranges.

Built for the T+30 check after LinkedIn Audience Network was turned off on 2026-08-17
(see /mnt/d/dev/ai-collab/2026-08-04-alconox-linkedin-ads-overhaul.md §4 Phase 2).

The question this answers: LAN-off buys fewer, more expensive, on-LinkedIn impressions.
Did the visitors who actually arrive behave better? Volume is EXPECTED to fall. The test
is bounce rate, pages per session, session length, and goal conversions.

WHY NOT SEGMENTS
  Matomo Cloud refuses on-the-fly segments ("must be created in the Segment Editor").
  But Referrers.getCampaigns is pre-archived and already carries bounce_count,
  sum_visit_length, nb_actions and goals per campaign — everything needed. So this reads
  the campaign report directly and does the arithmetic here. No segment setup required.

HOW LINKEDIN TRAFFIC IS IDENTIFIED
  Alconox's LinkedIn ads tag their landing URLs with UTM campaign names, so the traffic
  lands in Matomo as CAMPAIGNS, not as the "LinkedIn" social referrer. As of 2026-08-17
  the live tags are:
      linkedin, linkedin-video-shorts, linkedin-video-shorts-lab-people
  Rather than hard-code them, this matches any campaign label containing "linkedin"
  (override with --match), so new tags are picked up automatically. The handful of
  organic "LinkedIn" social referrals are a different thing and are excluded on purpose.

USAGE
  python3 matomo_linkedin_quality.py
      # defaults to the T+30 comparison: 2026-08-17..2026-09-16 vs 2026-07-17..2026-08-16

  python3 matomo_linkedin_quality.py --after 2026-08-17,2026-09-16 \
                                     --before 2026-07-17,2026-08-16
  python3 matomo_linkedin_quality.py --match linkedin --json
"""
import argparse
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, ".env")
MATOMO_URL = "https://alconox.matomo.cloud"
SITE_ID = 1  # alconox.com

# The change this script exists to measure.
LAN_OFF_DATE = "2026-08-17"
DEFAULT_AFTER = "2026-08-17,2026-09-16"
DEFAULT_BEFORE = "2026-07-17,2026-08-16"


def load_token():
    token = os.environ.get("MATOMO_API_TOKEN")
    if token:
        return token
    try:
        with open(ENV) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("MATOMO_API_TOKEN=") and "=" in line:
                    return line.split("=", 1)[1]
    except FileNotFoundError:
        pass
    sys.exit(f"MATOMO_API_TOKEN not in environment or {ENV}")


TOKEN = load_token()


def api(method, date, **params):
    """Matomo sends the token as POST data — Matomo Cloud requires it."""
    query = {
        "module": "API",
        "method": method,
        "format": "json",
        "idSite": SITE_ID,
        "period": "range",
        "date": date,
    }
    query.update(params)
    r = requests.post(f"{MATOMO_URL}/index.php", params=query, data={"token_auth": TOKEN})
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("result") == "error":
        sys.exit(f"Matomo error on {method}: {data.get('message')}")
    return data


def quality(rows):
    """Collapse campaign rows into the quality metrics we actually care about."""
    visits = sum(r.get("nb_visits", 0) for r in rows)
    actions = sum(r.get("nb_actions", 0) for r in rows)
    bounces = sum(r.get("bounce_count", 0) for r in rows)
    seconds = sum(r.get("sum_visit_length", 0) for r in rows)
    conversions = sum(r.get("nb_conversions", 0) for r in rows)
    revenue = sum(float(r.get("revenue", 0) or 0) for r in rows)
    return {
        "visits": visits,
        "bounce_rate": bounces / visits * 100 if visits else 0.0,
        "actions_per_visit": actions / visits if visits else 0.0,
        "avg_seconds": seconds / visits if visits else 0.0,
        "conversions": conversions,
        "conv_rate": conversions / visits * 100 if visits else 0.0,
        "revenue": revenue,
    }


def sitewide(date):
    """Site-wide control. Tells you whether a movement is LinkedIn-specific or global."""
    d = api("VisitsSummary.get", date)
    visits = d.get("nb_visits", 0)
    # Goals live in a separate call — VisitsSummary carries no goal data.
    g = api("Goals.get", date)
    conversions = g.get("nb_conversions", 0) if isinstance(g, dict) else 0
    return {
        "visits": visits,
        "bounce_rate": d.get("bounce_count", 0) / visits * 100 if visits else 0.0,
        "actions_per_visit": d.get("nb_actions", 0) / visits if visits else 0.0,
        "avg_seconds": d.get("avg_time_on_site", 0),
        "conversions": conversions,
        "conv_rate": conversions / visits * 100 if visits else 0.0,
        "revenue": float(g.get("revenue", 0) or 0) if isinstance(g, dict) else 0.0,
    }


def linkedin_rows(date, match):
    rows = api("Referrers.getCampaigns", date)
    if not isinstance(rows, list):
        return []
    return [r for r in rows if match in str(r.get("label", "")).lower()]


def fmt_delta(before, after, unit="", lower_is_better=False):
    if before == 0:
        return "     n/a"
    pct = (after - before) / before * 100
    arrow = "+" if pct >= 0 else ""
    good = (pct < 0) if lower_is_better else (pct > 0)
    mark = "  better" if good and abs(pct) >= 1 else ("  worse" if not good and abs(pct) >= 1 else "")
    return f"{arrow}{pct:.1f}%{unit}{mark}"


METRICS = [
    # (key, label, format, lower_is_better)
    ("visits", "Sessions", "{:,.0f}", False),
    ("bounce_rate", "Bounce rate", "{:.1f}%", True),
    ("actions_per_visit", "Pages / session", "{:.2f}", False),
    ("avg_seconds", "Avg session (sec)", "{:.0f}", False),
    ("conversions", "Goal conversions", "{:,.0f}", False),
    ("conv_rate", "Conversion rate", "{:.2f}%", False),
]


def print_block(title, before, after, note=None):
    print(f"\n{title}")
    print("-" * 78)
    print(f"{'metric':<22}{'before':>14}{'after':>14}{'change':>28}")
    for key, label, fmt, lower_better in METRICS:
        b, a = before[key], after[key]
        print(f"{label:<22}{fmt.format(b):>14}{fmt.format(a):>14}"
              f"{fmt_delta(b, a, lower_is_better=lower_better):>28}")
    if note:
        print(f"\n  {note}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--after", default=DEFAULT_AFTER,
                   help=f"post-change range YYYY-MM-DD,YYYY-MM-DD (default {DEFAULT_AFTER})")
    p.add_argument("--before", default=DEFAULT_BEFORE,
                   help=f"pre-change range YYYY-MM-DD,YYYY-MM-DD (default {DEFAULT_BEFORE})")
    p.add_argument("--match", default="linkedin",
                   help="substring matched against campaign labels (default: linkedin)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = p.parse_args()

    before_rows = linkedin_rows(args.before, args.match.lower())
    after_rows = linkedin_rows(args.after, args.match.lower())

    before, after = quality(before_rows), quality(after_rows)
    site_before, site_after = sitewide(args.before), sitewide(args.after)

    if args.json:
        print(json.dumps({
            "lan_off_date": LAN_OFF_DATE,
            "before": {"range": args.before, "linkedin": before, "sitewide": site_before,
                       "campaigns": {r["label"]: r.get("nb_visits", 0) for r in before_rows}},
            "after": {"range": args.after, "linkedin": after, "sitewide": site_after,
                      "campaigns": {r["label"]: r.get("nb_visits", 0) for r in after_rows}},
        }, indent=2))
        return

    print("=" * 78)
    print("  ALCONOX — LinkedIn session quality, before vs after Audience Network off")
    print(f"  LAN turned off {LAN_OFF_DATE}")
    print(f"  before: {args.before}   after: {args.after}")
    print("=" * 78)

    if not before_rows and not after_rows:
        print(f"\nNo campaigns matching {args.match!r} in either range. Check the UTM tags — "
              "run Referrers.getCampaigns and look at the labels.")
        return

    print_block("LINKEDIN CAMPAIGN TRAFFIC", before, after)

    print_block("SITE-WIDE (control — is the movement LinkedIn-specific or global?)",
                site_before, site_after)

    print("\nPER-CAMPAIGN SESSIONS")
    print("-" * 78)
    labels = sorted({r["label"] for r in before_rows} | {r["label"] for r in after_rows})
    bmap = {r["label"]: r for r in before_rows}
    amap = {r["label"]: r for r in after_rows}
    print(f"{'campaign':<44}{'before':>10}{'after':>10}{'bounce b/a':>14}")
    for lbl in labels:
        b, a = bmap.get(lbl, {}), amap.get(lbl, {})
        bq, aq = quality([b]) if b else quality([]), quality([a]) if a else quality([])
        print(f"{lbl[:43]:<44}{bq['visits']:>10,}{aq['visits']:>10,}"
              f"{bq['bounce_rate']:>7.0f}%{aq['bounce_rate']:>6.0f}%")

    print("\n" + "=" * 78)
    print("HOW TO READ THIS")
    print("=" * 78)
    print("""
  Sessions falling is EXPECTED and is not the finding. Audience Network was ~99.9% of
  delivery, so volume had to drop. The finding is whether bounce rate came down and
  pages/session and session length went up.

  Check the site-wide block before concluding anything. If site-wide moved the same way,
  something else changed (season, a site release, tracking) and it is not about LinkedIn.

  CAVEAT — Matomo sessions have consistently run several times LinkedIn's own reported
  landing-page clicks (2,163 vs 336 in Jul 18 - Aug 16). The two systems count different
  things and the gap is not explained. Use this script to compare LinkedIn traffic to
  ITSELF across time, which is valid. Do not treat a Matomo session as one LinkedIn click.
""")


if __name__ == "__main__":
    main()
