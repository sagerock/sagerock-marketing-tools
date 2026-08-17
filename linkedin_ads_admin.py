#!/usr/bin/env python3
"""
linkedin_ads_admin.py — read and modify Alconox's LinkedIn ad account from the CLI.

Account 508285222 "Alconox 2020" (Alconox, LLC), under Business Manager 7166843588310466560.
Credentials come from ./.env (LINKEDIN_ADS_*). See the `linkedin-ads-api` memory for gotchas.

SAFETY MODEL
  - `plan` (default) is READ-ONLY. It prints current state and the diff that `apply` would make.
  - `apply` writes, but ALWAYS snapshots current state to snapshots/ first.
  - `revert <snapshot>` restores campaign settings from a snapshot file.
  - Nothing here activates a paused campaign or creates new spend. The current phase only
    pauses campaigns. Activation stays a human decision.

USAGE
  python3 linkedin_ads_admin.py plan
  python3 linkedin_ads_admin.py apply
  python3 linkedin_ads_admin.py revert snapshots/campaigns-<timestamp>.json
  python3 linkedin_ads_admin.py show          # current account state, no changes
  python3 linkedin_ads_admin.py placements [YYYY-MM-DD]  # LAN/on-site video breakdown

The CHANGES list below is the declarative change set. Edit it, run `plan`, then `apply`.
"""
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, ".env")
SNAPDIR = os.path.join(HERE, "snapshots")
VERSION = "202607"   # newest ACTIVE LinkedIn-Version as of 2026-08-04; probe upward on HTTP 426

# ---------------------------------------------------------------- change set
# Phase 2 ratified by Sage 2026-08-17: turn LinkedIn Audience Network OFF on the three
# primary video campaigns. The objective question from the 2026-08-04 audit (§3.1) was
# decided in favour of LinkedIn-feed exposure over cheap offsite modeled reach.
# Rationale + expected effects: /mnt/d/dev/ai-collab/2026-08-04-alconox-linkedin-ads-overhaul.md
#
# Phase 1 (both pauses, applied 2026-08-04) is done and verified; its entries were retired
# from this list. Snapshot: snapshots/campaigns-20260804T100257.json.
CHANGES = [
    # (campaign_id, {fields}, human label)
    (427658604, {"offsiteDeliveryEnabled": False}, "Video views - Lab People: LAN ON -> OFF"),
    (427628234, {"offsiteDeliveryEnabled": False}, "Video Shorts with Ethan's Targeting: LAN ON -> OFF"),
    (431005354, {"offsiteDeliveryEnabled": False}, "Video views Marketing Cloud Retargeting: LAN ON -> OFF"),
]
# Conversion-rule changes: (rule_id, {fields}, label)
CONVERSION_CHANGES = []

PRIMARY_VIDEO_CAMPAIGNS = (427658604, 427628234, 431005354)
PLACEMENT_FIELDS = (
    "impressions,clicks,landingPageClicks,costInLocalCurrency,videoStarts,videoViews,"
    "videoFirstQuartileCompletions,videoMidpointCompletions,"
    "videoThirdQuartileCompletions,videoCompletions,pivotValues"
)

# ---------------------------------------------------------------- plumbing
def load_env():
    cfg = {}
    with open(ENV) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("LINKEDIN_ADS_") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k] = v
    missing = [k for k in ("LINKEDIN_ADS_ACCESS_TOKEN", "LINKEDIN_ADS_ACCOUNT_ID") if k not in cfg]
    if missing:
        sys.exit(f"missing {missing} in {ENV}")
    return cfg

CFG = load_env()
ACCT = CFG["LINKEDIN_ADS_ACCOUNT_ID"]

def call(path, body=None, method="GET"):
    req = urllib.request.Request("https://api.linkedin.com/rest" + path, method=method)
    req.add_header("Authorization", "Bearer " + CFG["LINKEDIN_ADS_ACCESS_TOKEN"])
    req.add_header("LinkedIn-Version", VERSION)
    req.add_header("X-Restli-Protocol-Version", "2.0.0")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("X-RestLi-Method", "PARTIAL_UPDATE")
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        if e.code == 426:
            detail += "\n  -> LinkedIn-Version is stale. Probe upward (202608, 202609, ...)."
        return e.code, detail

def campaigns():
    code, d = call(f"/adAccounts/{ACCT}/adCampaigns?q=search&count=100")
    if code != 200:
        sys.exit(f"cannot read campaigns (HTTP {code}): {d}")
    return {c["id"]: c for c in d.get("elements", [])}

def conversions():
    code, d = call(f"/conversions?q=account&account=urn%3Ali%3AsponsoredAccount%3A{ACCT}&count=100")
    if code != 200:
        sys.exit(f"cannot read conversions (HTTP {code}): {d}")
    return {e["id"]: e for e in d.get("elements", [])}

def current_value(obj, field):
    v = obj.get(field)
    if field == "dailyBudget" and isinstance(v, dict):
        return f"${v.get('amount')}"
    return v

def monthly_estimate(camps):
    total = 0.0
    for c in camps.values():
        if c.get("status") == "ACTIVE":
            amt = c.get("dailyBudget", {}).get("amount")
            if amt:
                total += float(amt)
    return total, total * 30.44

def placement_analytics(pivot, start_date):
    try:
        year, month, day = (int(part) for part in start_date.split("-"))
    except ValueError:
        sys.exit("start date must use YYYY-MM-DD")
    campaign_urns = ",".join(
        f"urn%3Ali%3AsponsoredCampaign%3A{cid}" for cid in PRIMARY_VIDEO_CAMPAIGNS
    )
    path = (
        f"/adAnalytics?q=analytics&pivot={pivot}&timeGranularity=ALL"
        f"&dateRange=(start:(year:{year},month:{month},day:{day}))"
        f"&campaigns=List({campaign_urns})&fields={PLACEMENT_FIELDS}"
    )
    code, data = call(path)
    if code != 200:
        sys.exit(f"cannot read {pivot} analytics (HTTP {code}): {data}")
    return data.get("elements", [])

# ---------------------------------------------------------------- commands
def cmd_show():
    camps = campaigns()
    print(f"{'id':>10} {'status':<9} {'LAN':<6} {'audExp':<7} {'daily':>7}  name")
    for cid, c in sorted(camps.items(), key=lambda x: (x[1].get("status",""), -x[0])):
        if c.get("status") in ("ARCHIVED", "COMPLETED", "DRAFT"):
            continue
        print(f"{cid:>10} {c.get('status',''):<9} {str(c.get('offsiteDeliveryEnabled')):<6} "
              f"{str(c.get('audienceExpansionEnabled')):<7} "
              f"{current_value(c,'dailyBudget') or '-':>7}  {c.get('name','')[:46]}")
    d, m = monthly_estimate(camps)
    print(f"\nactive daily budget total: ${d:.2f}/day  ~${m:,.0f}/month")
    print("\nconversion rules:")
    for rid, r in conversions().items():
        print(f"  {rid} {r.get('name')!r} postClick={r.get('postClickAttributionWindowSize')}d "
              f"postView={r.get('viewThroughAttributionWindowSize')}d "
              f"{'ENABLED' if r.get('enabled') else 'disabled'}")

def cmd_plan():
    camps, convs = campaigns(), conversions()
    print("PLANNED CHANGES (nothing written)\n")
    n = 0
    for cid, fields, label in CHANGES:
        c = camps.get(cid)
        if not c:
            print(f"  [SKIP] {cid} not found — {label}")
            continue
        for f, want in fields.items():
            now = current_value(c, f)
            wantv = f"${want['amount']}" if f == "dailyBudget" else want
            if str(now) == str(wantv):
                print(f"  [no-op] {label}  (already {now})")
            else:
                print(f"  [change] {label}\n           {f}: {now}  ->  {wantv}")
                n += 1
    for rid, fields, label in CONVERSION_CHANGES:
        r = convs.get(rid)
        if not r:
            print(f"  [SKIP] conversion rule {rid} not found — {label}")
            continue
        for f, want in fields.items():
            now = r.get(f)
            if str(now) == str(want):
                print(f"  [no-op] {label}  (already {now})")
            else:
                print(f"  [change] {label}\n           {f}: {now}  ->  {want}")
                n += 1
    d, m = monthly_estimate(camps)
    print(f"\ncurrent active budget: ${d:.2f}/day (~${m:,.0f}/mo)")
    after = d
    for cid, fields, _ in CHANGES:
        c = camps.get(cid, {})
        if "status" in fields and fields["status"] == "PAUSED" and c.get("status") == "ACTIVE":
            amt = c.get("dailyBudget", {}).get("amount")
            if amt:
                after -= float(amt)
        if "dailyBudget" in fields and c.get("status") == "ACTIVE":
            old = float(c.get("dailyBudget", {}).get("amount") or 0)
            after += float(fields["dailyBudget"]["amount"]) - old
    print(f"after changes:         ${after:.2f}/day (~${after*30.44:,.0f}/mo)")
    if n:
        print(f"\n{n} field(s) would change. Run `apply` to execute.")
    else:
        print("\nNo fields would change.")

def cmd_placements(start_date="2024-01-01"):
    print(f"Primary video campaigns, {start_date} through present")
    for pivot in ("SERVING_LOCATION", "PLACEMENT_NAME"):
        print(f"\n{pivot}")
        print(f"{'location':<20} {'spend':>10} {'impressions':>13} {'views':>11} "
              f"{'complete':>10} {'LP clicks':>10} {'CPV':>9} {'view rate':>10} {'comp rate':>10}")
        for row in placement_analytics(pivot, start_date):
            impressions = int(row.get("impressions", 0))
            views = int(row.get("videoViews", 0))
            completions = int(row.get("videoCompletions", 0))
            spend = float(row.get("costInLocalCurrency", 0))
            cpv = spend / views if views else 0
            view_rate = views / impressions * 100 if impressions else 0
            completion_rate = completions / views * 100 if views else 0
            location = ",".join(row.get("pivotValues", []))
            print(f"{location:<20} ${spend:>9,.2f} {impressions:>13,} {views:>11,} "
                  f"{completions:>10,} {int(row.get('landingPageClicks', 0)):>10,} "
                  f"${cpv:>8.4f} {view_rate:>9.2f}% {completion_rate:>9.2f}%")

def snapshot(camps, convs):
    os.makedirs(SNAPDIR, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    path = os.path.join(SNAPDIR, f"campaigns-{ts}.json")
    json.dump({"campaigns": camps, "conversions": convs}, open(path, "w"), indent=1)
    return path

def cmd_apply():
    camps, convs = campaigns(), conversions()
    snap = snapshot(camps, convs)
    print(f"snapshot written: {snap}\n")
    ok = fail = 0
    for cid, fields, label in CHANGES:
        c = camps.get(cid)
        if not c:
            print(f"  [SKIP] {cid} not found — {label}"); continue
        if all(str(current_value(c, f)) == str(f"${v['amount']}" if f == "dailyBudget" else v)
               for f, v in fields.items()):
            print(f"  [no-op] {label}"); continue
        code, resp = call(f"/adAccounts/{ACCT}/adCampaigns/{cid}", {"patch": {"$set": fields}}, "POST")
        if code in (200, 204):
            print(f"  [OK]   {label}"); ok += 1
        else:
            print(f"  [FAIL] {label}  HTTP {code}\n         {resp}"); fail += 1
    for rid, fields, label in CONVERSION_CHANGES:
        if rid not in convs:
            print(f"  [SKIP] conversion rule {rid} not found"); continue
        if all(str(convs[rid].get(f)) == str(v) for f, v in fields.items()):
            print(f"  [no-op] {label}"); continue
        code, resp = call(f"/conversions/{rid}", {"patch": {"$set": fields}}, "POST")
        if code in (200, 204):
            print(f"  [OK]   {label}"); ok += 1
        else:
            print(f"  [FAIL] {label}  HTTP {code}\n         {resp}"); fail += 1
    print(f"\n{ok} applied, {fail} failed. Verifying...\n")
    cmd_show()
    if fail:
        print(f"\n!! {fail} change(s) failed. Revert with:\n   python3 {sys.argv[0]} revert {snap}")

def cmd_revert(path):
    snap = json.load(open(path))
    old = {int(k): v for k, v in snap["campaigns"].items()}
    now = campaigns()
    restored = 0
    for cid, fields, label in CHANGES:
        if cid not in old or cid not in now:
            continue
        sets = {}
        for f in fields:
            prev = old[cid].get(f)
            if prev is not None and str(prev) != str(now[cid].get(f)):
                sets[f] = prev
        if not sets:
            continue
        code, resp = call(f"/adAccounts/{ACCT}/adCampaigns/{cid}", {"patch": {"$set": sets}}, "POST")
        print(f"  [{'OK' if code in (200,204) else 'FAIL'}] restore {cid} {list(sets)}"
              + ("" if code in (200,204) else f"  {resp}"))
        restored += 1
    oldc = {int(k): v for k, v in snap.get("conversions", {}).items()}
    for rid, fields, label in CONVERSION_CHANGES:
        if rid in oldc:
            sets = {f: oldc[rid].get(f) for f in fields if oldc[rid].get(f) is not None}
            if sets:
                code, _ = call(f"/conversions/{rid}", {"patch": {"$set": sets}}, "POST")
                print(f"  [{'OK' if code in (200,204) else 'FAIL'}] restore conversion {rid} {sets}")
                restored += 1
    print(f"\n{restored} restore call(s) made.")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "plan":     cmd_plan()
    elif cmd == "show":   cmd_show()
    elif cmd == "placements": cmd_placements(sys.argv[2] if len(sys.argv) > 2 else "2024-01-01")
    elif cmd == "apply":  cmd_apply()
    elif cmd == "revert": cmd_revert(sys.argv[2])
    else: sys.exit(__doc__)
