#!/usr/bin/env python3
"""Dates on which Alconox measurement changed, so reports spanning them aren't misread.

Several Alconox numbers fall off a cliff in 2026 because WHAT GETS COUNTED changed, not
because performance did. A quarterly or half-year report crossing one of these dates shows
an apparent collapse that is nothing of the sort.

Michael and Stacy don't open the ad platforms — they ask for periodic overview reports. So
the risk is not that they see a confusing graph, it's that WE build the report and forget.
This module exists so the tooling says it out loud instead of relying on anybody's memory.

The prose version, with full before/after numbers, is the source of record:
    /mnt/d/dev/sagerock/clients/alconox/MEASUREMENT-CHANGELOG.md
Add an entry there AND here whenever measurement changes.

Usage:
    from measurement_breaks import warnings_for, as_prompt_block, as_markdown
    hits = warnings_for("2026-07-01", "2026-09-30")

    python3 measurement_breaks.py 2026-07-01 2026-09-30
"""
from datetime import date

CHANGELOG = "clients/alconox/MEASUREMENT-CHANGELOG.md (in the sagerock repo)"

# date, platform, what a reader will SEE, why, and whether it was deliberate
BREAKS = [
    {
        "date": "2026-07-27",
        "platform": "GA4",
        "symptom": "Page views roughly halve.",
        "cause": "A GTM tagging fault had been double-counting page views since June 2024. "
                 "Fixed 2026-07-27. The OLD numbers were wrong; the new ones are right.",
        "deliberate": True,
        "affects": ["pageviews", "sessions", "GA4"],
    },
    {
        "date": "2026-08-17",
        "platform": "LinkedIn Ads",
        "symptom": "Impressions fall ~97%, CPM rises ~8x, reported conversions fall to "
                   "near zero.",
        "cause": "LinkedIn Audience Network turned off, deliberately. 99.9% of delivery had "
                 "been cheap offsite inventory (1,107,576 offsite impressions vs 79 on "
                 "LinkedIn itself in 30 days). The old conversions were 90-day view-through "
                 "credit against those junk impressions.",
        "deliberate": True,
        "affects": ["impressions", "CPM", "CTR", "conversions", "LinkedIn"],
    },
    {
        "date": "2026-08-24",
        "platform": "Google Ads",
        "symptom": "Reported conversions drop from 400+/quarter to single digits.",
        "cause": "`file_download` demoted from primary to secondary, deliberately. It was "
                 "firing 402x per 90 days, ~25x every other primary action combined, so "
                 "bidding was optimising toward PDF downloads instead of leads. Real lead "
                 "volume is unchanged. Still recorded as a secondary action.",
        "deliberate": True,
        "affects": ["conversions", "Google Ads", "cost per conversion"],
    },
    {
        "date": "2026-08-24",
        "platform": "Google Ads / GA4",
        "symptom": "A new conversion appears: Ask Alconox enquiries.",
        "cause": "GA4 key event `ask_alconox_enquiry` created and enabled as a primary "
                 "Google Ads conversion. Never tracked before. Not retroactive, so it reads "
                 "zero for every period before 2026-08-24.",
        "deliberate": True,
        "affects": ["conversions", "Google Ads", "GA4"],
    },
    {
        "date": "2026-08-24",
        "platform": "Matomo / website",
        "symptom": "Goal 7 'Ask Alconox' reads 0 for August 2026, then resumes.",
        "cause": "The Ask Alconox short form stopped redirecting to a confirmation page, so "
                 "nothing counted the submissions. The enquiries still arrived. Redirect to "
                 "/ask-alconox-confirmation/ restored 2026-08-24.",
        "deliberate": False,
        "affects": ["goals", "Matomo", "Ask Alconox"],
    },
    {
        "date": "2026-08-31",
        "platform": "Athena weekly brief / Matomo ecommerce",
        "symptom": "The brief's store yr/yr deltas disappear until ~Dec 2026; order "
                   "counts shift ~1% against prior briefs.",
        "cause": "Order source switched from Matomo ecommerce tracking to the synced "
                 "WooCommerce order records, deliberately. Matomo's Aug-2025 baseline was "
                 "phantom — 84 orders in a month the store was shut (2025 suspension). "
                 "Matomo ecommerce figures for Jun-Dec 2025 should not be trusted anywhere.",
        "deliberate": True,
        "affects": ["orders", "revenue", "ecommerce", "Matomo", "yr/yr"],
    },
    {
        "date": "2026-09-16",
        "platform": "LinkedIn Ads",
        "symptom": "Reported conversions reset to real Sample Request and Ask Alconox "
                   "leads and may fall to near zero.",
        "cause": "Legacy 90-day Key Pages and Add to Cart rules were detached from the "
                 "two continuing campaigns. Real Sample Request and Ask Alconox rules "
                 "were attached instead. The active campaign mix also changed: Lab People "
                 "and Retargeting paused; Ethan retained with expansion off; Halojet launched.",
        "deliberate": True,
        "affects": ["conversions", "LinkedIn", "cost per conversion", "campaign mix"],
    },
]


def warnings_for(start, end):
    """Breaks falling inside [start, end]. Accepts 'YYYY-MM-DD' strings or dates."""
    def d(v):
        return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])
    lo, hi = d(start), d(end)
    return [b for b in BREAKS if lo <= d(b["date"]) <= hi]


def as_markdown(start, end):
    hits = warnings_for(start, end)
    if not hits:
        return ""
    out = ["> ## ⚠️ Measurement changed during this period",
           ">",
           "> Some numbers below fall sharply because **what gets counted changed**, not "
           "because performance did. Do not report these as declines.",
           ">"]
    for b in hits:
        tag = "deliberate" if b["deliberate"] else "a bug, since fixed"
        out.append(f"> **{b['date']} — {b['platform']}** ({tag})  ")
        out.append(f"> {b['symptom']} {b['cause']}")
        out.append(">")
    out.append(f"> Full detail: `{CHANGELOG}`")
    return "\n".join(out)


def as_prompt_block(start, end):
    """Injected into the analyst prompt so the narrative accounts for these."""
    hits = warnings_for(start, end)
    if not hits:
        return ""
    lines = [
        "=== CRITICAL: MEASUREMENT CHANGES INSIDE THIS REPORTING PERIOD ===",
        "The following are changes to HOW THINGS ARE COUNTED, not changes in performance.",
        "You MUST NOT describe these as declines, drops in performance, or problems.",
        "Where a metric below moves, say plainly that the measurement changed and why.",
        "",
    ]
    for b in hits:
        tag = "deliberate change" if b["deliberate"] else "a tracking bug, since fixed"
        lines.append(f"* {b['date']} — {b['platform']} ({tag})")
        lines.append(f"  What a reader sees: {b['symptom']}")
        lines.append(f"  Why: {b['cause']}")
        lines.append("")
    lines.append("=== END MEASUREMENT CHANGES ===")
    return "\n".join(lines)


def console_warning(start, end):
    hits = warnings_for(start, end)
    if not hits:
        return
    bar = "!" * 78
    print(f"\n{bar}")
    print(f"  {len(hits)} MEASUREMENT CHANGE(S) FALL INSIDE {start} .. {end}")
    print("  Numbers will move for reasons that are not performance. Do not report")
    print("  them as declines. Detail is being included in the report.")
    for b in hits:
        print(f"    - {b['date']}  {b['platform']}: {b['symptom']}")
    print(f"  Source of record: {CHANGELOG}")
    print(f"{bar}\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        sys.exit("usage: measurement_breaks.py <start YYYY-MM-DD> <end YYYY-MM-DD>")
    s, e = sys.argv[1], sys.argv[2]
    console_warning(s, e)
    md = as_markdown(s, e)
    print(md if md else f"No measurement changes between {s} and {e}.")
