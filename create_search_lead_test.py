#!/usr/bin/env python3
"""Build the Alconox Google Search lead test. Customer 4205046148.

Directed by Sage 2026-11-16: "Temporarily pause LinkedIn. Put all the money on Google Search
Ads ... till mid-December. Just don't go over her budget." (Stacy's ~$2,900/month.)
LinkedIn was paused separately the same morning (snapshots/campaigns-20261116T092238.json).

Record: sagerock/clients/alconox/ads/2026-11-16-search-lead-test.md

What it creates, and nothing else in the account:
  - a non-shared $65/day budget (see BUDGET_MICROS for why not $80)
  - campaign "Search - Lead test - Nov-Dec 2026": Google Search only (no partners, no
    Display), US presence-only, English, Maximize Clicks capped at $6 CPC,
    2026-11-16 .. 2026-12-15
  - campaign-level negatives, 6 ad groups (phrase + exact keywords), 2 RSAs each, 4 sitelinks
  - a custom conversion goal (Sample request + Ask Alconox + Purchase) set as the campaign's
    goal. Account-level primary/secondary settings are not touched.

Order: campaign is created PAUSED in one atomic request, the conversion goal is attached, then
the campaign is enabled. Re-running after a successful apply will refuse (name already exists).

    venv/bin/python create_search_lead_test.py            # dry run: validate copy, print plan
    venv/bin/python create_search_lead_test.py --apply    # build it live
    venv/bin/python create_search_lead_test.py --readback # re-read an existing build

Undo: pause campaign (status PAUSED) in the UI or API. Nothing else was changed.
"""
import sys
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.api_core import protobuf_helpers

CONFIG_PATH = "/mnt/d/dev/sagerock-marketing-tools/google_ads_config.yaml"
CUSTOMER_ID = "4205046148"
VERSION = "v24"  # v22 is blocked as of 2026-11; v24 renamed start/end_date to *_date_time

CAMPAIGN_NAME = "Search - Lead test - Nov-Dec 2026"
GOAL_NAME = "Search lead test: Sample + Ask + Purchase"
# $80/day was the brief. It doesn't fit November with margin once the email tool ($350) and
# Matomo ($42) on Stacy's invoice are counted: Nov 1-15 actual = Google $380.24 + LinkedIn
# $494.69 + $392 fixed = $1,266.93; worst case for Nov 16-30 at full budgets
# ($33 PMax + $5 Ledizolv + search) x 15 days. At $80 that is $3,036.93 (over). At $65 it is
# $2,811.93, $88 under even if PMax and Ledizolv spend their full budgets every day, which they
# haven't (PMax averaged $25/day in November; Ledizolv has spent $0 for months).
BUDGET_MICROS = 65_000_000
CPC_CAP_MICROS = 6_000_000
START = "2026-11-16 00:00:00"
END = "2026-12-15 23:59:59"
GEO_US = "geoTargetConstants/2840"   # same as PMax 18258915038 (US, presence-only)
LANG_EN = "languageConstants/1000"

GOAL_ACTIONS = [
    6767723178,  # Submit lead form (Page load /sample-request-confirmation/)  = sample request
    7732489084,  # GA4 ask_alconox_enquiry
    490714005,   # GA4 purchase
]

SITE = "https://alconox.com"
SAMPLE = f"{SITE}/order-sample/"
ASK = f"{SITE}/ask-alconox/"

# Campaign-level negatives: (text, match)
NEGATIVES = [(w, "BROAD") for w in [
    "job", "jobs", "career", "careers", "salary", "hiring", "employment", "internship", "resume",
    "dishwasher", "laundry", "car", "kitchen", "household", "homemade", "diy", "recipe",
    "jewelry", "eyeglasses", "vinyl", "pet", "urine", "odor", "carpet", "toilet", "septic",
    "msds", "sds", "walmart", "costco", "course", "courses", "training", "certification",
    "ppt", "wikipedia", "definition", "meaning", "reddit", "youtube",
]] + [
    ("free download", "PHRASE"), ("record cleaner", "PHRASE"), ("home depot", "PHRASE"),
    ("dish soap", "PHRASE"), ("car wash", "PHRASE"),
    # pure brand stays with PMax
    ("alconox", "EXACT"), ("alconox detergent", "EXACT"), ("alconox inc", "EXACT"),
    ("liquinox", "EXACT"), ("tergazyme", "EXACT"),
]

# Each ad group: name, keywords [(text, match)], two RSAs (final_url, path1, path2, headlines, descriptions)
P, E = "PHRASE", "EXACT"
SAMPLE_H = ["Request a Free Sample", "Free Sample Available"]
AD_GROUPS = [
    {
        "name": "Lab glassware detergent",
        "keywords": [(k, P) for k in [
            "lab glassware detergent", "laboratory glassware detergent", "glassware cleaning detergent",
            "lab glassware cleaner", "laboratory detergent", "lab detergent",
            "how to clean laboratory glassware", "cleaning lab glassware", "phosphate free lab detergent",
            "labware detergent"]] + [(k, E) for k in [
            "lab glassware detergent", "laboratory detergent", "lab detergent"]],
        "ads": [
            (f"{SITE}/product/alconox/", "lab", "glassware",
             ["Lab Glassware Detergent", "Alconox Powdered Detergent", "Request a Free Sample",
              "For Laboratory Equipment", "Manual and Ultrasonic Use", "Cleans Organic Residues",
              "Glass, Metal and Plastic", "Ask Our Cleaning Experts", "Alconox Lab Detergents"],
             ["Alconox powdered precision cleaner for laboratory glassware and equipment.",
              "Immersion and manual cleaner for organic and oily residues. Request a free sample.",
              "Not sure which detergent fits your residue? Ask Alconox technical support."]),
            (f"{SITE}/product/liquinox/", "lab", "liquinox",
             ["Liquinox Liquid Lab Detergent", "Phosphate-Free Concentrate", "Request a Free Sample",
              "Neutral pH Liquid Detergent", "Manual, Ultrasonic or Soak", "Lab Glassware Detergent",
              "Ask Our Cleaning Experts", "Cleans Glass and Metal"],
             ["Liquinox phosphate-free liquid concentrate for manual, ultrasonic and soak cleaning.",
              "Removes organic and oily residues from lab glassware. Request a free sample today.",
              "Questions about your residue? Ask Alconox technical support for a recommendation."]),
        ],
    },
    {
        "name": "Enzymatic protein cleaning",
        "keywords": [(k, P) for k in [
            "enzymatic detergent", "enzyme detergent for lab", "enzymatic instrument cleaner",
            "protein residue removal", "enzymatic glassware cleaner", "protease detergent",
            "remove protein residue", "biofilm removal detergent", "enzyme active detergent",
            "cleaning protein residues", "enzymatic ultrasonic cleaner"]] + [(k, E) for k in [
            "enzymatic detergent", "protein residue removal"]],
        "ads": [
            (f"{SITE}/product/tergazyme/", "enzymatic", "detergent",
             ["Enzymatic Lab Detergent", "Tergazyme Enzyme Detergent", "Request a Free Sample",
              "Removes Protein Residues", "Blood, Tissue and Biofilms", "Manual and Ultrasonic Use",
              "No Interfering Residues", "Ask Our Cleaning Experts", "Proteolytic Enzyme Formula"],
             ["Tergazyme enzyme active powdered detergent with a proteolytic enzyme.",
              "Removes proteins, tissue, biofilms, blood and body fluids with no interfering residues.",
              "For glassware, metals, plastic and ceramic. Request a free sample from Alconox."]),
            (f"{SITE}/product/tergazyme/", "protein", "residue",
             ["Protein Residue Remover", "Enzyme Active Detergent", "Free Sample Available",
              "Tergazyme by Alconox", "Cleans Proteinaceous Soils", "For Manual and Ultrasonic",
              "Ask Alconox a Question"],
             ["Concentrated anionic detergent with a proteolytic enzyme for protein soils.",
              "Manual, soak and ultrasonic cleaning of lab ware and instruments. Get a free sample.",
              "Tell us your residue and Alconox technical support will suggest a detergent."]),
        ],
    },
    {
        "name": "Cleaning validation residue testing",
        "keywords": [(k, P) for k in [
            "cleaning validation detergent", "cleaning validation residue testing",
            "detergent residue testing", "toc cleaning validation", "cleaning validation methods",
            "detergent residue detection", "swab testing cleaning validation",
            "hplc detergent residue", "cleaning validation analytical methods",
            "detergent residue analysis"]] + [(k, E) for k in [
            "cleaning validation detergent", "detergent residue testing"]],
        "ads": [
            (f"{SITE}/cleaning-validation-methods/", "cleaning", "validation",
             ["Cleaning Validation Methods", "Detergent Residue Testing", "TOC, HPLC, Conductivity",
              "Request a Free Sample", "Ask Our Cleaning Experts", "Validated Detergent Methods",
              "Residue Detection Methods", "Alconox Technical Support"],
             ["Analytical methods to detect Alconox detergent residues: TOC, HPLC, UV/Vis and more.",
              "Methods for validating cleaning on GMP pharmaceutical and medical device surfaces.",
              "Need help with a residue method? Ask Alconox technical support. Free samples too."]),
            (f"{SITE}/cleaning-validation-methods/", "residue", "testing",
             ["Validate Detergent Removal", "Residue Testing Methods", "Free Sample Available",
              "GMP Cleaning Validation", "TOC and HPLC Methods", "Ask Alconox a Question"],
             ["See detection methods for each Alconox detergent, from TOC to conductivity.",
              "Alconox technical support can provide analytical methods for residue detection.",
              "Request a free detergent sample to start your cleaning validation work."]),
        ],
    },
    {
        "name": "CIP detergent",
        "keywords": [(k, P) for k in [
            "cip detergent", "clean in place detergent", "cip cleaning chemicals",
            "low foaming cip detergent", "clean in place chemicals", "cip alkaline detergent",
            "phosphate free cip detergent", "low foam alkaline detergent", "cip cleaner",
            "clean in place cleaning solution"]] + [(k, E) for k in [
            "cip detergent", "clean in place detergent"]],
        "ads": [
            (f"{SITE}/product/solujet/", "cip", "detergent",
             ["Low-Foaming CIP Detergent", "Solujet Alkaline Detergent", "Request a Free Sample",
              "Phosphate-Free Concentrate", "For Clean-in-Place Systems", "Spray Washers and CIP",
              "Ask Our Cleaning Experts", "Alconox CIP Detergent"],
             ["Solujet low-foaming, phosphate-free alkaline liquid concentrate for clean-in-place.",
              "For CIP systems, machine washers and spray-in-air cabinets. Request a free sample.",
              "Tell Alconox about your residue and process. Technical support will recommend."]),
            (f"{SITE}/product/solujet/", "clean-in-place", "solujet",
             ["Clean-in-Place Detergent", "Low-Foam Alkaline Cleaner", "Free Sample Available",
              "Solujet by Alconox", "Removes Organic Residues", "Ask Alconox a Question"],
             ["Low-foaming phosphate-free cleaner for organic residues in clean-in-place systems.",
              "Liquid concentrate for CIP, spray washers and ultrasonic tanks. Get a free sample.",
              "Not sure about dilution or temperature? Ask Alconox technical support."]),
        ],
    },
    {
        "name": "Ultrasonic cleaning detergent",
        "keywords": [(k, P) for k in [
            "ultrasonic cleaning detergent", "ultrasonic cleaner detergent", "ultrasonic detergent",
            "ultrasonic cleaning solution concentrate", "ultrasonic parts cleaning solution",
            "detergent for ultrasonic cleaner", "ultrasonic bath detergent", "ultrasonic tank detergent",
            "lab ultrasonic cleaning solution", "ultrasonic cleaning chemicals"]] + [(k, E) for k in [
            "ultrasonic cleaning detergent", "ultrasonic detergent"]],
        "ads": [
            (f"{SITE}/applications/ultrasonics/", "ultrasonic", "detergent",
             ["Ultrasonic Cleaning Detergent", "Detergents for Ultrasonic Use", "Request a Free Sample",
              "Used and Specified for Decades", "Lab Ware, Parts and Devices", "Ask Our Cleaning Experts",
              "Alconox Ultrasonic Detergents", "Powder and Liquid Options"],
             ["Alconox ultrasonic detergents for lab ware, glassware, metal parts and ceramics.",
              "Used and specified for decades in medical device cleaning. Request a free sample.",
              "Tell us your residue and substrate. Alconox technical support will recommend one."]),
            (f"{SITE}/product/liquinox/", "ultrasonic", "liquinox",
             ["Liquid Ultrasonic Detergent", "Liquinox for Ultrasonic Tanks", "Free Sample Available",
              "Phosphate-Free Concentrate", "Removes Process Oils", "Ask Alconox a Question"],
             ["Liquinox phosphate-free liquid for manual, ultrasonic and soak cleaning.",
              "Removes oily and organic residues from glass and metal. Request a free sample.",
              "Need a different chemistry for your residue? Ask Alconox technical support."]),
        ],
    },
    {
        "name": "Precision critical cleaning",
        "keywords": [(k, P) for k in [
            "critical cleaning detergent", "precision cleaning detergent", "precision parts cleaning",
            "aqueous cleaning detergent", "aqueous parts cleaner", "precision cleaning solution",
            "aqueous precision cleaning", "medical device cleaning detergent",
            "metal parts cleaning detergent", "oxygen service cleaning"]] + [(k, E) for k in [
            "precision cleaning detergent", "critical cleaning detergent"]],
        "ads": [
            (f"{SITE}/industry/precision-manufacturing/", "precision", "cleaning",
             ["Precision Cleaning Detergents", "Aqueous Critical Cleaning", "Request a Free Sample",
              "For Precision Manufacturing", "Metal, Glass and Ceramic", "Ask Our Cleaning Experts",
              "Alconox Critical Cleaners"],
             ["Aqueous detergents from Alconox for precision and critical cleaning of parts.",
              "Manual, ultrasonic, soak and machine washer options. Request a free sample.",
              "Tell us your residue and process. Alconox technical support will recommend one."]),
            (f"{SITE}/product/liquinox/", "critical", "cleaning",
             ["Critical Cleaning Detergent", "Liquinox Liquid Concentrate", "Free Sample Available",
              "Phosphate-Free Formula", "Manual, Ultrasonic or Soak", "Ask Alconox a Question"],
             ["Liquinox critical cleaning liquid detergent for glass and metal substrates.",
              "Phosphate-free concentrate for oily and organic residues. Request a free sample.",
              "Questions about your residue? Ask Alconox technical support for a recommendation."]),
        ],
    },
]

SITELINKS = [
    ("Request a Free Sample", SAMPLE, "Try an Alconox detergent", "Free sample request form"),
    ("Ask Alconox", ASK, "Send us a cleaning question", "Technical support answers"),
    ("Cleaning Validation", f"{SITE}/cleaning-validation-methods/", "Residue detection methods",
     "TOC, HPLC, conductivity"),
    ("Clean Lab Glassware", f"{SITE}/videos/how-to-clean-laboratory-glassware/",
     "How-to video", "Step-by-step glassware cleaning"),
]


def validate():
    errs = []
    for g in AD_GROUPS:
        n = len(g["keywords"])
        if not 8 <= n <= 15:
            errs.append(f"{g['name']}: {n} keywords")
        for url, p1, p2, hs, ds in g["ads"]:
            if len(hs) < 3 or len(ds) < 2:
                errs.append(f"{g['name']}: too few assets")
            if len(set(hs)) != len(hs):
                errs.append(f"{g['name']}: duplicate headline")
            errs += [f"H>30 ({len(h)}): {h}" for h in hs if len(h) > 30]
            errs += [f"D>90 ({len(d)}): {d}" for d in ds if len(d) > 90]
            errs += [f"path>15: {p}" for p in (p1, p2) if len(p) > 15]
    for t, u, d1, d2 in SITELINKS:
        if len(t) > 25 or len(d1) > 35 or len(d2) > 35:
            errs.append(f"sitelink too long: {t}")
    return errs


def mutate(client, ops, label):
    svc = client.get_service("GoogleAdsService")
    try:
        resp = svc.mutate(customer_id=CUSTOMER_ID, mutate_operations=ops)
    except GoogleAdsException as ex:
        print(f"FAILED at {label}:")
        for e in ex.failure.errors:
            print("  ", e.error_code, e.message, e.location)
        sys.exit(1)
    return resp


def build(client):
    ga = client.get_service("GoogleAdsService")
    E = client.enums
    tmp = iter(range(-1, -10000, -1))
    rn = lambda kind, i: f"customers/{CUSTOMER_ID}/{kind}/{i}"
    ops = []

    def op(field):
        m = client.get_type("MutateOperation")
        return m, getattr(m, field).create

    b_id = next(tmp); m, b = op("campaign_budget_operation")
    b.resource_name = rn("campaignBudgets", b_id)
    b.name = f"{CAMPAIGN_NAME} budget"
    b.amount_micros = BUDGET_MICROS
    b.delivery_method = E.BudgetDeliveryMethodEnum.STANDARD
    b.explicitly_shared = False
    ops.append(m)

    c_id = next(tmp); m, c = op("campaign_operation")
    camp_rn = rn("campaigns", c_id)
    c.resource_name = camp_rn
    c.name = CAMPAIGN_NAME
    c.status = E.CampaignStatusEnum.PAUSED  # enabled after the goal is attached
    c.advertising_channel_type = E.AdvertisingChannelTypeEnum.SEARCH
    c.campaign_budget = b.resource_name
    c.target_spend.cpc_bid_ceiling_micros = CPC_CAP_MICROS
    c.network_settings.target_google_search = True
    c.network_settings.target_search_network = False
    c.network_settings.target_content_network = False
    c.network_settings.target_partner_search_network = False
    c.geo_target_type_setting.positive_geo_target_type = E.PositiveGeoTargetTypeEnum.PRESENCE
    c.geo_target_type_setting.negative_geo_target_type = E.NegativeGeoTargetTypeEnum.PRESENCE
    c.start_date_time = START
    c.end_date_time = END
    c.contains_eu_political_advertising = (
        E.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
    ops.append(m)

    m, cc = op("campaign_criterion_operation"); cc.campaign = camp_rn
    cc.location.geo_target_constant = GEO_US; ops.append(m)
    m, cc = op("campaign_criterion_operation"); cc.campaign = camp_rn
    cc.language.language_constant = LANG_EN; ops.append(m)
    for text, match in NEGATIVES:
        m, cc = op("campaign_criterion_operation"); cc.campaign = camp_rn; cc.negative = True
        cc.keyword.text = text; cc.keyword.match_type = getattr(E.KeywordMatchTypeEnum, match)
        ops.append(m)

    for g in AD_GROUPS:
        ag_id = next(tmp); m, ag = op("ad_group_operation")
        ag.resource_name = rn("adGroups", ag_id); ag.name = g["name"]; ag.campaign = camp_rn
        ag.status = E.AdGroupStatusEnum.ENABLED; ag.type_ = E.AdGroupTypeEnum.SEARCH_STANDARD
        ag.cpc_bid_micros = CPC_CAP_MICROS
        ops.append(m)
        for text, match in g["keywords"]:
            m, k = op("ad_group_criterion_operation"); k.ad_group = ag.resource_name
            k.status = E.AdGroupCriterionStatusEnum.ENABLED
            k.keyword.text = text; k.keyword.match_type = getattr(E.KeywordMatchTypeEnum, match)
            ops.append(m)
        for url, p1, p2, hs, ds in g["ads"]:
            m, a = op("ad_group_ad_operation"); a.ad_group = ag.resource_name
            a.status = E.AdGroupAdStatusEnum.ENABLED
            a.ad.final_urls.append(url)
            rsa = a.ad.responsive_search_ad
            rsa.path1, rsa.path2 = p1, p2
            for h in hs:
                t = client.get_type("AdTextAsset"); t.text = h; rsa.headlines.append(t)
            for d in ds:
                t = client.get_type("AdTextAsset"); t.text = d; rsa.descriptions.append(t)
            ops.append(m)

    for text, url, d1, d2 in SITELINKS:
        a_id = next(tmp); m, a = op("asset_operation")
        a.resource_name = rn("assets", a_id)
        a.final_urls.append(url)
        a.sitelink_asset.link_text = text
        a.sitelink_asset.description1 = d1; a.sitelink_asset.description2 = d2
        ops.append(m)
        m, ca = op("campaign_asset_operation")
        ca.campaign = camp_rn; ca.asset = a.resource_name
        ca.field_type = E.AssetFieldTypeEnum.SITELINK
        ops.append(m)

    print(f"step 1: {len(ops)} operations (atomic)")
    resp = mutate(client, ops, "build")
    camp = next(r.campaign_result.resource_name for r in resp.mutate_operation_responses
                if r.campaign_result.resource_name)
    print("campaign:", camp)

    # step 2: custom goal + attach at campaign level
    m = client.get_type("MutateOperation")
    g = m.custom_conversion_goal_operation.create
    g.name = GOAL_NAME
    g.status = E.CustomConversionGoalStatusEnum.ENABLED
    for a in GOAL_ACTIONS:
        g.conversion_actions.append(f"customers/{CUSTOMER_ID}/conversionActions/{a}")
    resp = mutate(client, [m], "custom goal")
    goal_rn = resp.mutate_operation_responses[0].custom_conversion_goal_result.resource_name
    print("custom goal:", goal_rn)

    cid = camp.split("/")[-1]
    m = client.get_type("MutateOperation")
    u = m.conversion_goal_campaign_config_operation.update
    u.resource_name = f"customers/{CUSTOMER_ID}/conversionGoalCampaignConfigs/{cid}"
    u.goal_config_level = E.GoalConfigLevelEnum.CAMPAIGN
    u.custom_conversion_goal = goal_rn
    client.copy_from(m.conversion_goal_campaign_config_operation.update_mask,
                     protobuf_helpers.field_mask(None, u._pb))
    mutate(client, [m], "campaign goal config")
    print("goal attached at campaign level")

    # step 3: enable
    m = client.get_type("MutateOperation")
    u = m.campaign_operation.update
    u.resource_name = camp
    u.status = E.CampaignStatusEnum.ENABLED
    client.copy_from(m.campaign_operation.update_mask, protobuf_helpers.field_mask(None, u._pb))
    mutate(client, [m], "enable")
    print("campaign ENABLED")
    return cid


def readback(client, cid=None):
    ga = client.get_service("GoogleAdsService")
    def q(s):
        for b in ga.search_stream(customer_id=CUSTOMER_ID, query=s):
            yield from b.results
    where = f"campaign.id = {cid}" if cid else f"campaign.name = '{CAMPAIGN_NAME}'"
    for r in q(f"""SELECT campaign.id, campaign.status, campaign.serving_status,
        campaign.primary_status, campaign.start_date_time, campaign.end_date_time,
        campaign.bidding_strategy_type, campaign.target_spend.cpc_bid_ceiling_micros,
        campaign.network_settings.target_google_search, campaign.network_settings.target_search_network,
        campaign.network_settings.target_content_network, campaign.network_settings.target_partner_search_network,
        campaign.geo_target_type_setting.positive_geo_target_type, campaign_budget.amount_micros,
        campaign_budget.explicitly_shared FROM campaign WHERE {where}"""):
        c = r.campaign; cid = c.id
        print(f"campaign {c.id} status={c.status.name} serving={c.serving_status.name} primary={c.primary_status.name}")
        print(f"  dates {c.start_date_time} -> {c.end_date_time}")
        print(f"  budget ${r.campaign_budget.amount_micros/1e6:.2f}/day shared={r.campaign_budget.explicitly_shared}")
        print(f"  bidding {c.bidding_strategy_type.name} cap ${c.target_spend.cpc_bid_ceiling_micros/1e6:.2f}")
        ns = c.network_settings
        print(f"  google_search={ns.target_google_search} search_partners={ns.target_search_network} "
              f"display={ns.target_content_network} partner_search={ns.target_partner_search_network}")
        print(f"  geo type {c.geo_target_type_setting.positive_geo_target_type.name}")
    for r in q(f"""SELECT campaign_criterion.type, campaign_criterion.negative,
        campaign_criterion.location.geo_target_constant, campaign_criterion.language.language_constant
        FROM campaign_criterion WHERE campaign.id = {cid}"""):
        cc = r.campaign_criterion
        if cc.type_.name in ("LOCATION", "LANGUAGE"):
            print(f"  {cc.type_.name} {cc.location.geo_target_constant or cc.language.language_constant}")
    neg = sum(1 for r in q(f"""SELECT campaign_criterion.criterion_id FROM campaign_criterion
        WHERE campaign.id = {cid} AND campaign_criterion.type = 'KEYWORD' AND campaign_criterion.negative = TRUE"""))
    print(f"  negative keywords: {neg}")
    for r in q(f"""SELECT conversion_goal_campaign_config.goal_config_level,
        conversion_goal_campaign_config.custom_conversion_goal FROM conversion_goal_campaign_config
        WHERE campaign.id = {cid}"""):
        g = r.conversion_goal_campaign_config
        print(f"  goal level {g.goal_config_level.name} custom goal {g.custom_conversion_goal}")
        if g.custom_conversion_goal:
            for r2 in q(f"""SELECT custom_conversion_goal.id, custom_conversion_goal.name,
                custom_conversion_goal.conversion_actions, custom_conversion_goal.status
                FROM custom_conversion_goal WHERE custom_conversion_goal.resource_name = '{g.custom_conversion_goal}'"""):
                cg = r2.custom_conversion_goal
                print(f"    {cg.id} '{cg.name}' {cg.status.name} actions={[a.split('/')[-1] for a in cg.conversion_actions]}")
    for r in q(f"""SELECT ad_group.id, ad_group.name, ad_group.status FROM ad_group WHERE campaign.id = {cid}"""):
        ag = r.ad_group
        kws = list(q(f"""SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
            ad_group_criterion.approval_status FROM ad_group_criterion WHERE ad_group.id = {ag.id}
            AND ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE"""))
        kw_appr = sorted({k.ad_group_criterion.approval_status.name for k in kws})
        print(f"  ad group {ag.id} '{ag.name}' {ag.status.name}: {len(kws)} keywords (approval {kw_appr})")
        for r2 in q(f"""SELECT ad_group_ad.ad.id, ad_group_ad.status, ad_group_ad.ad.final_urls,
            ad_group_ad.policy_summary.approval_status, ad_group_ad.policy_summary.review_status,
            ad_group_ad.policy_summary.policy_topic_entries FROM ad_group_ad WHERE ad_group.id = {ag.id}"""):
            a = r2.ad_group_ad; ps = a.policy_summary
            topics = [t.topic for t in ps.policy_topic_entries]
            print(f"    ad {a.ad.id} {a.status.name} {list(a.ad.final_urls)} approval={ps.approval_status.name} "
                  f"review={ps.review_status.name} {topics or ''}")
    for r in q(f"""SELECT campaign.id, asset.id, asset.sitelink_asset.link_text, campaign_asset.status
        FROM campaign_asset WHERE campaign.id = {cid} AND campaign_asset.field_type = 'SITELINK'"""):
        print(f"  sitelink {r.asset.id} '{r.asset.sitelink_asset.link_text}' {r.campaign_asset.status.name}")


def main():
    errs = validate()
    if errs:
        print("\n".join(errs)); sys.exit("copy validation failed")
    n_kw = sum(len(g["keywords"]) for g in AD_GROUPS)
    print(f"copy OK: {len(AD_GROUPS)} ad groups, {n_kw} keywords, {2*len(AD_GROUPS)} RSAs, "
          f"{len(NEGATIVES)} negatives, budget ${BUDGET_MICROS/1e6:.0f}/day, {START} -> {END}")
    client = GoogleAdsClient.load_from_storage(CONFIG_PATH, version=VERSION)
    if "--readback" in sys.argv:
        readback(client); return
    ga = client.get_service("GoogleAdsService")
    existing = [r for b in ga.search_stream(customer_id=CUSTOMER_ID, query=
        f"SELECT campaign.id FROM campaign WHERE campaign.name = '{CAMPAIGN_NAME}' AND campaign.status != 'REMOVED'")
        for r in b.results]
    if existing:
        sys.exit(f"campaign already exists: {existing[0].campaign.id}. Use --readback.")
    if "--apply" not in sys.argv:
        print("dry run; pass --apply to build"); return
    cid = build(client)
    readback(client, cid)


if __name__ == "__main__":
    main()
