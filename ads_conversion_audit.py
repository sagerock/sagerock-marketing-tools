#!/usr/bin/env python3
"""Audit Google Ads conversion actions for Alconox. Read-only.

Written 2026-08-24. Reported conversions on this account fell from 5,865 in 2023 to 239 in
2024 to 15.6 in 2025, which looked like a tracking collapse. This works out what is actually
configured, what still fires, and what counts toward the "Conversions" column, before any
decision to spend on YouTube.

The column that matters is PRIMARY. Only actions marked primary-for-goal feed the bidding
"Conversions" metric; secondary ones are recorded but ignored by bid strategies and by the
headline number.
"""
import sys
from collections import defaultdict
from google.ads.googleads.client import GoogleAdsClient

CONFIG_PATH = "/mnt/d/dev/sagerock-marketing-tools/google_ads_config.yaml"
CUSTOMER_ID = "4205046148"
VERSION = "v22"


def main():
    client = GoogleAdsClient.load_from_storage(CONFIG_PATH, version=VERSION)
    svc = client.get_service("GoogleAdsService")

    q = """
        SELECT conversion_action.id, conversion_action.name, conversion_action.status,
               conversion_action.type, conversion_action.category,
               conversion_action.origin, conversion_action.primary_for_goal,
               conversion_action.counting_type,
               conversion_action.click_through_lookback_window_days,
               conversion_action.view_through_lookback_window_days,
               conversion_action.value_settings.default_value,
               conversion_action.value_settings.always_use_default_value
        FROM conversion_action
        ORDER BY conversion_action.status, conversion_action.name
    """
    actions = {}
    for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=q):
        for row in batch.results:
            a = row.conversion_action
            actions[str(a.id)] = {
                "name": a.name, "status": a.status.name, "type": a.type_.name,
                "category": a.category.name, "origin": a.origin.name,
                "primary": a.primary_for_goal, "counting": a.counting_type.name,
                "click_win": a.click_through_lookback_window_days,
                "view_win": a.view_through_lookback_window_days,
                "default_value": a.value_settings.default_value,
                "always_default": a.value_settings.always_use_default_value,
                "conv_90d": 0.0,
            }

    # Which of them actually fired recently. Explicit dates: the DURING operator rejects
    # LAST_90_DAYS ("Invalid date literal"), it only knows the shorter presets.
    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=90)
    q2 = f"""
        SELECT segments.conversion_action, metrics.all_conversions
        FROM customer
        WHERE segments.date BETWEEN '{start:%Y-%m-%d}' AND '{end:%Y-%m-%d}'
    """
    fired = defaultdict(float)
    for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=q2):
        for row in batch.results:
            fired[row.segments.conversion_action.split("/")[-1]] += row.metrics.all_conversions
    for cid, n in fired.items():
        if cid in actions:
            actions[cid]["conv_90d"] = n

    enabled = {k: v for k, v in actions.items() if v["status"] == "ENABLED"}
    other = {k: v for k, v in actions.items() if v["status"] != "ENABLED"}

    print(f"Google Ads account {CUSTOMER_ID} — {len(actions)} conversion actions "
          f"({len(enabled)} enabled)\n")

    print("ENABLED")
    print(f"  {'id':<12}{'PRIMARY':<9}{'90d':>8}  {'origin':<18}{'category':<20}"
          f"{'windows':<10}name")
    for cid, a in sorted(enabled.items(), key=lambda kv: (-kv[1]["primary"], -kv[1]["conv_90d"])):
        print(f"  {cid:<12}{'PRIMARY' if a['primary'] else 'secondary':<9}"
              f"{a['conv_90d']:>8.1f}  {a['origin'][:17]:<18}{a['category'][:19]:<20}"
              f"{str(a['click_win']) + '/' + str(a['view_win']):<10}{a['name'][:44]}")

    if other:
        print("\nNOT ENABLED")
        for cid, a in sorted(other.items(), key=lambda kv: kv[1]["name"]):
            print(f"  {cid:<12}{a['status']:<12}{a['conv_90d']:>8.1f}  {a['name'][:52]}")

    prim = [a for a in enabled.values() if a["primary"]]
    live = [a for a in enabled.values() if a["conv_90d"] > 0]
    print(f"\nSUMMARY")
    print(f"  primary (feed the Conversions column / bidding): {len(prim)}")
    print(f"  fired at all in the last 90 days:                {len(live)}")
    print(f"  primary AND firing:                              "
          f"{len([a for a in prim if a['conv_90d'] > 0])}")


if __name__ == "__main__":
    sys.exit(main())
