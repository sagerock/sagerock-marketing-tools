#!/usr/bin/env python3
"""Create a LinkedIn conversion rule for the Alconox free-sample request.

Why this exists (2026-08-24): the account's three enabled rules were all useless for
measuring the thing we actually care about.

  23951594 "Conversion - Oct 6, 2025 - Key Pages"  attached to every live campaign,
           INSIGHT_TAG_WEBSITE_SIGNAL with NO url definition at all, 90d post-click AND
           90d post-view, $0 value. Every conversion figure we have ever quoted came from
           this. It means "LinkedIn thinks somebody did something on alconox.com."
  22670386 "Add to Cart"  same shape, no definition, typed QUALIFIED_LEAD.
  4298530  "Shop Now"  the only properly built rule (URL contains "merchandise", 30d/7d,
           $1). Attached to ZERO live campaigns. Last fired 2026-05-08.

Nothing tracked the free-sample request, which is the conversion the whole video program is
supposed to be judged on.

SCOPE, deliberately narrow: this CREATES a new rule and attaches it ONLY to campaign
883862684, the new Halojet campaign, which is still DRAFT and has no measurement baseline.
It does NOT touch the three live campaigns and does NOT alter 23951594's attribution
windows. Doing either before the 2026-09-16 T+30 read would change the numbers on one side
of a before/after comparison. Re-wire the live campaigns after that date.

Run with --apply to write; default is a dry run.
"""
import importlib.util, json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("lla", os.path.join(HERE, "linkedin_ads_admin.py"))
lla = importlib.util.module_from_spec(spec)
_argv, sys.argv = sys.argv, ["linkedin_ads_admin.py", "show"]
try:
    spec.loader.exec_module(lla)
except SystemExit:
    pass
sys.argv = _argv

TARGET_CAMPAIGN = 883862684

# CONTAINS rather than an exact URL: survives www/non-www and any ?utm_ suffix.
# Both confirmation URLs verified 2026-08-24 — HTTP 200, no redirect, and both carry the
# same GTM container (GTM-MZV82ND) and GA4 id (G-HHFJ30TMK0) as the rest of alconox.com,
# so the Insight Tag reaches them like any other page.
#
# $1 is a COUNTING UNIT, not a revenue estimate. It makes "conversion value" read as "number
# of conversions" and lets cost-per-sample be computed. Same convention the 2021 "Shop Now"
# rule used. Don't mistake it for what a sample or an enquiry is worth.
def rule(name, fragment):
    return {
        "account": f"urn:li:sponsoredAccount:{lla.ACCT}",
        "name": name,
        "type": "LEAD",
        "enabled": True,
        "conversionMethod": "INSIGHT_TAG_URL_MATCH_RULES",
        "postClickAttributionWindowSize": 30,
        "viewThroughAttributionWindowSize": 7,
        "attributionType": "LAST_TOUCH_BY_CAMPAIGN",
        "valueType": "FIXED",
        "value": {"currencyCode": "USD", "amount": "1"},
        "urlMatchRuleExpression": [[{"matchValue": fragment, "matchType": "CONTAINS"}]],
    }

RULES = [
    rule("Sample request (order-sample confirmation)", "sample-request-confirmation"),
    # The Ask Alconox short form only started redirecting to a confirmation page on
    # 2026-08-24, so this enquiry was never measurable before now.
    rule("Ask Alconox enquiry (confirmation page)", "ask-alconox-confirmation"),
]

apply = "--apply" in sys.argv

import urllib.request, urllib.error


def create(rule_body):
    """lla.call() hardcodes X-RestLi-Method: PARTIAL_UPDATE whenever a body is present,
    which a create rejects with "Method 'POST' is not supported". Issue this one directly."""
    req = urllib.request.Request("https://api.linkedin.com/rest/conversions",
                                 data=json.dumps(rule_body).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + lla.CFG["LINKEDIN_ADS_ACCESS_TOKEN"])
    req.add_header("LinkedIn-Version", lla.VERSION)
    req.add_header("X-Restli-Protocol-Version", "2.0.0")
    req.add_header("X-RestLi-Method", "CREATE")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return r.headers.get("x-linkedin-id") or (json.loads(raw).get("id") if raw.strip() else None)
    except urllib.error.HTTPError as e:
        print(f"  [FAIL] create HTTP {e.code}: {e.read().decode()[:300]}")
        return None


existing = lla.conversions()

for body in RULES:
    fragment = body["urlMatchRuleExpression"][0][0]["matchValue"]
    dupe = [r for r in existing.values() if fragment in json.dumps(r)]
    if dupe:
        print(f"[skip] {body['name']} — already exists as {[(r['id'], r['name']) for r in dupe]}")
        continue

    print(f"{'WOULD CREATE' if not apply else 'CREATING'}: {body['name']}  (url CONTAINS '{fragment}')")
    print(f"    30d post-click / 7d post-view, $1 counting unit, attach to {TARGET_CAMPAIGN} only")
    if not apply:
        continue

    new_id = create(body)
    if not new_id:
        continue
    print(f"  created rule {new_id}")

    # The attach occasionally returns a transient 500. Retry once; it works on the retry.
    for attempt in (1, 2):
        code, resp = lla.call(
            f"/conversions/{new_id}",
            {"patch": {"$set": {"campaigns": [f"urn:li:sponsoredCampaign:{TARGET_CAMPAIGN}"]}}},
            "POST",
        )
        if code in (200, 204):
            break
        print(f"  attach attempt {attempt}: HTTP {code} {str(resp)[:120]}")

    code, r = lla.call(f"/conversions/{new_id}")
    if code == 200 and isinstance(r, dict):
        print(f"  [OK] attached to {r.get('campaigns')}")

if not apply:
    print("\nDry run. Re-run with --apply to write.")
