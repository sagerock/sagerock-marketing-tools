# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Analytics toolkit for Alconox web properties. Aggregates data from three sources:
- **Matomo Analytics** (website traffic via API)
- **Google Ads** (paid search/video campaigns via API)
- **LinkedIn Ads** (B2B campaigns via CSV exports)

## Key Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Run Matomo analytics tool (interactive CLI)
python matomo_analyzer.py

# Generate PowerPoint-ready CSV reports for all sites
python generate_ppt_reports.py

# Export Matomo data to JSON for AI analysis
python export_for_ai.py

# Run Google Ads analyzer
python google_ads_analyzer.py

# Re-authenticate Google Ads OAuth (if token expires)
python google_ads_auth.py

# Run AI-powered analysis (requires ANTHROPIC_API_KEY)
python ai_analyzer.py
```

## Architecture

### Data Sources

| Source | Auth Method | Data Location |
|--------|-------------|---------------|
| Matomo | API token (POST `token_auth`) | API: `alconox.matomo.cloud` |
| Google Ads | OAuth2 refresh token | Config: `google_ads_config.yaml` |
| LinkedIn | Manual CSV export | Folder: `linkedin/` (UTF-16 encoded) |
| Claude API | `ANTHROPIC_API_KEY` env var | Used by `ai_analyzer.py` |

### Core Files

- `matomo_analyzer.py` - Main Matomo client (`MatomoAPI` class) and report generator
- `google_ads_analyzer.py` - Google Ads API client (uses v19)
- `generate_ppt_reports.py` - Batch report generator, outputs to `reports/`
- `export_for_ai.py` - JSON export for AI analysis workflows
- `ai_analyzer.py` - Claude API-powered multi-source analysis (Matomo + Google Ads + LinkedIn)

### Important Implementation Details

**Matomo API**: Token must be sent via POST body (`token_auth`), not query string. The `MatomoAPI._request()` method handles this.

**Google Ads**: Uses manager account (MCC) ID `3282542648` with client account `4205046148`. Config requires `use_proto_plus: True`.

**LinkedIn CSV**: Files are UTF-16 encoded. Convert before parsing:
```bash
iconv -f UTF-16 -t UTF-8 input.csv > output.csv
```

### Site IDs (Matomo)

| Site | ID |
|------|-----|
| alconox.com | 1 |
| Alconox Food Service | 3 |
| Ledizolv | 5 |
| TechNotes | 6 |

## Output Files

Reports are written to `reports/` directory as CSV files and markdown. The main analysis report is `reports/Alconox_2024_vs_2025_Analysis.md`.

## Related capability: CfA Facebook Ads access (not wired into this repo)

Noted here for cross-reference — this is **not** an Alconox source and lives in another project.
We have API access to **Center for Anthroposophy's** Meta / Facebook ad account (`act_45601263`,
owned by CfA's own Business Manager) via a permanent SageRock system-user token. The token's scopes
allow **both reporting and management**: `ads_read` (insights/reports), `ads_management`
(create/modify campaigns, ad sets, ads, budgets, pause/resume), and `leads_retrieval`.

- **Where it lives:** the `sagerock-schools` repo — a daily cron syncs campaign×day insights into
  the `meta_ads_daily` table (`scripts/meta-bootstrap.mjs` to onboard, `scripts/meta-sync.mjs` to
  sync). CfA is `client_id 22500cd6-052a-42ff-a0cb-4f3ba9125dfd` there.
- **Built today = read-only reporting.** Create/modify-campaign capability exists on the token but
  no write code exists yet. Full details in
  `/mnt/d/dev/sagerock/clients/center-for-anthroposophy/CLAUDE.md`.
