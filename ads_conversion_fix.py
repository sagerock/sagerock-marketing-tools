#!/usr/bin/env python3
"""Re-point Google Ads conversion tracking at outcomes that matter. Alconox 4205046148.

Authorised by Sage 2026-08-24 off the back of ads_conversion_audit.py.

The account's tracking was never broken; it was aimed at the wrong thing. `file_download`
was PRIMARY and fired 402 times in 90 days, roughly 25x everything else combined, so Smart
Bidding was being told the goal of Alconox advertising is getting people to download PDFs.
The sample-request lead form, the outcome the business actually cares about, contributed
about 0.4% of the primary signal.

REPORTED CONVERSIONS WILL FALL SHARPLY after this, from 400+ per quarter to single digits,
and nothing will have got worse. That is the point of the change, and it is why
clients/alconox/MEASUREMENT-CHANGELOG.md exists. Read that before comparing any report
across 2026-08-24.

Run with --apply to write; default is a dry run.
"""
import sys
from google.ads.googleads.client import GoogleAdsClient
# FieldMask is not a Google Ads type -- client.get_type('FieldMask') raises.
# And DON'T derive it with protobuf_helpers.field_mask(): setting a bool to False looks
# identical to unset, so the field is silently dropped from the mask and the mutate
# reports success while changing nothing. Build the mask explicitly from the fields dict.
from google.protobuf import field_mask_pb2

CONFIG_PATH = "/mnt/d/dev/sagerock-marketing-tools/google_ads_config.yaml"
CUSTOMER_ID = "4205046148"
VERSION = "v22"

# (id, {field: value}, why)
CHANGES = [
    (490714224, {"primary_for_goal": False},
     "file_download: PRIMARY -> secondary. Stop bidding toward PDF downloads. Still "
     "recorded, just no longer a bidding target."),
    (7732489084, {"status": "ENABLED", "primary_for_goal": True},
     "ask_alconox_enquiry: HIDDEN/secondary -> ENABLED/PRIMARY. Auto-imported from the GA4 "
     "key event created 2026-08-24. Nothing tracked Ask Alconox before today."),
    # 7732488958 sample_request -- the orphan Google Ads auto-imported from a GA4 key event
    # that was deleted minutes later as a duplicate. It can never fire. Left alone on
    # purpose: the API rejects setting a conversion action to REMOVED ("Enum value 'REMOVED'
    # cannot be used"), and HIDDEN is Google's retire state, which it is already in. Sample
    # requests are covered by 6767723178 "Submit lead form (Page load
    # .../sample-request-confirmation/)".
]


def main():
    client = GoogleAdsClient.load_from_storage(CONFIG_PATH, version=VERSION)
    svc = client.get_service("GoogleAdsService")
    ca_svc = client.get_service("ConversionActionService")
    apply = "--apply" in sys.argv

    ids = ",".join(str(c[0]) for c in CHANGES)
    q = (f"SELECT conversion_action.id, conversion_action.name, conversion_action.status, "
         f"conversion_action.primary_for_goal FROM conversion_action "
         f"WHERE conversion_action.id IN ({ids})")
    before = {}
    for b in svc.search_stream(customer_id=CUSTOMER_ID, query=q):
        for r in b.results:
            a = r.conversion_action
            before[a.id] = {"name": a.name, "status": a.status.name,
                            "primary_for_goal": a.primary_for_goal}

    ops = []
    for cid, fields, why in CHANGES:
        cur = before.get(cid)
        if not cur:
            print(f"[SKIP] {cid} not found")
            continue
        print(f"\n{cid}  {cur['name'][:60]}")
        print(f"   {why}")
        for f, v in fields.items():
            print(f"   {f}: {cur[f]}  ->  {v}")
        if not apply:
            continue

        op = client.get_type("ConversionActionOperation")
        upd = op.update
        upd.resource_name = ca_svc.conversion_action_path(CUSTOMER_ID, cid)
        for f, v in fields.items():
            if f == "status":
                upd.status = client.enums.ConversionActionStatusEnum[v]
            else:
                setattr(upd, f, v)
        client.copy_from(op.update_mask,
                         field_mask_pb2.FieldMask(paths=list(fields.keys())))
        ops.append(op)

    if not apply:
        print("\nDry run. Re-run with --apply to write.")
        return

    resp = ca_svc.mutate_conversion_actions(customer_id=CUSTOMER_ID, operations=ops)
    print(f"\napplied {len(resp.results)} change(s)")

    print("\nVERIFY")
    for b in svc.search_stream(customer_id=CUSTOMER_ID, query=q):
        for r in b.results:
            a = r.conversion_action
            print(f"  {a.id:<12}{a.status.name:<9}"
                  f"{'PRIMARY' if a.primary_for_goal else 'secondary':<10}{a.name[:56]}")


if __name__ == "__main__":
    sys.exit(main())
