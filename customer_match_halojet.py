#!/usr/bin/env python3
"""Build and upload Alconox's Halojet Customer Match audience.

The script is dry-run by default. It reads contacts directly from Supabase,
filters them in memory, and never writes or prints raw email addresses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import requests
from dotenv import dotenv_values
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException


CLIENT_ID = "ea7f1422-2d20-4299-85a7-c1201e953409"
CUSTOMER_ID = "4205046148"
LIST_NAME = "Halojet - Cosmetics + Sample + Ask - 2026-09"
LIST_DESCRIPTION = (
    "Eligible Alconox contacts in Cosmetics, tagged Sample Request, or tagged "
    "Ask Alconox; built 2026-09-16. Raw addresses are not exported."
)
DEFAULT_CONTACT_ENV = Path("/mnt/d/dev/email-marketing-tool-1/.env")
DEFAULT_GOOGLE_CONFIG = Path(__file__).with_name("google_ads_config.yaml")
DATA_MANAGER_TOKEN = Path.home() / ".config/sagerock-marketing-tools/data-manager-token.json"
DATA_MANAGER_SCOPE = "https://www.googleapis.com/auth/datamanager"
DATA_MANAGER_ENDPOINT = "https://datamanager.googleapis.com/v1/audienceMembers:ingest"
REDIRECT_URI = "http://localhost"
PAGE_SIZE = 1_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create/reuse the Google Ads list and upload through Data Manager.",
    )
    parser.add_argument(
        "--auth-url",
        action="store_true",
        help="Print the one-time Data Manager authorization URL.",
    )
    parser.add_argument(
        "--auth-code",
        metavar="CODE_OR_URL",
        help="Exchange the returned OAuth code and save the Data Manager token.",
    )
    parser.add_argument(
        "--status",
        metavar="REQUEST_ID",
        help="Read Data Manager processing diagnostics for an upload request.",
    )
    parser.add_argument(
        "--contact-env",
        type=Path,
        default=DEFAULT_CONTACT_ENV,
        help="Path to the email tool's Supabase environment file.",
    )
    parser.add_argument(
        "--google-config",
        type=Path,
        default=DEFAULT_GOOGLE_CONFIG,
        help="Path to google-ads.yaml-compatible credentials.",
    )
    return parser.parse_args()


def google_config_values(config_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def print_auth_url(config_path: Path) -> None:
    config = google_config_values(config_path)
    client_id = config.get("client_id")
    if not client_id:
        raise RuntimeError(f"client_id is missing from {config_path}")
    url = "https://accounts.google.com/o/oauth2/auth?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": DATA_MANAGER_SCOPE,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    print("Open this URL and approve with the Google account that manages Alconox Ads:")
    print(url)
    print("Google will redirect to a localhost URL that may not load; copy that full URL.")
    print("Then run: customer_match_halojet.py --auth-code '<copied URL>'")


def exchange_auth_code(config_path: Path, pasted: str) -> None:
    config = google_config_values(config_path)
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    if not client_id or not client_secret:
        raise RuntimeError(f"OAuth client credentials are missing from {config_path}")
    if pasted == "-":
        pasted = sys.stdin.readline()
    code = pasted.strip()
    if code.startswith("http"):
        query = parse_qs(urlparse(code).query)
        if query.get("error"):
            raise RuntimeError(f"OAuth returned: {query['error'][0]}")
        code = query.get("code", [""])[0]
    else:
        match = re.search(r"[?&]code=([^&]+)", code)
        if match:
            code = unquote(match.group(1))
    if not code:
        raise RuntimeError("No OAuth code was supplied.")
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=60,
    )
    response.raise_for_status()
    tokens = response.json()
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Google did not return a refresh token; re-run --auth-url.")
    DATA_MANAGER_TOKEN.parent.mkdir(parents=True, exist_ok=True)
    DATA_MANAGER_TOKEN.write_text(
        json.dumps({"refresh_token": refresh_token}, indent=2) + "\n",
        encoding="utf-8",
    )
    DATA_MANAGER_TOKEN.chmod(0o600)
    print(f"Saved Data Manager authorization to {DATA_MANAGER_TOKEN}")


def data_manager_access_token(config_path: Path) -> str:
    if not DATA_MANAGER_TOKEN.exists():
        raise RuntimeError("Data Manager is not authorized. Run with --auth-url first.")
    config = google_config_values(config_path)
    stored = json.loads(DATA_MANAGER_TOKEN.read_text(encoding="utf-8"))
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": config.get("client_id"),
            "client_secret": config.get("client_secret"),
            "refresh_token": stored.get("refresh_token"),
            "grant_type": "refresh_token",
        },
        timeout=60,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Google did not return a Data Manager access token.")
    return token


def print_request_status(config_path: Path, request_id: str) -> None:
    access_token = data_manager_access_token(config_path)
    response = requests.get(
        "https://datamanager.googleapis.com/v1/requestStatus:retrieve",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"requestId": request_id},
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(
            f"Data Manager status failed ({response.status_code}): "
            f"{safe_api_error(response)}"
        )
    destinations = response.json().get("requestStatusPerDestination", [])
    if not destinations:
        print("No destination status has been returned yet.")
        return
    for item in destinations:
        destination = item.get("destination", {})
        ingestion = item.get("audienceMembersIngestionStatus", {})
        composite = ingestion.get("compositeDataIngestionStatus", {})
        print(f"request_status: {item.get('requestStatus', 'UNKNOWN')}")
        print(f"destination_list_id: {destination.get('productDestinationId', 'unknown')}")
        print(f"record_count: {composite.get('recordCount', 'unknown')}")
        for data_type in composite.get("dataTypeCounts", []):
            print(
                f"{str(data_type.get('type', 'identifier')).lower()}_count: "
                f"{data_type.get('count', 'unknown')}"
            )
        if item.get("errors"):
            print(f"error_count: {len(item['errors'])}")


def load_supabase_credentials(env_path: Path) -> tuple[str, str]:
    values = {**dotenv_values(env_path), **os.environ}
    url = values.get("VITE_SUPABASE_URL") or values.get("SUPABASE_URL")
    key = values.get("SUPABASE_SERVICE_KEY") or values.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(f"Supabase credentials are missing from {env_path}")
    return str(url).rstrip("/"), str(key)


def fetch_contacts(url: str, key: str) -> list[dict[str, Any]]:
    endpoint = f"{url}/rest/v1/contacts"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    params = {
        "client_id": f"eq.{CLIENT_ID}",
        "select": "email,industry,tags,unsubscribed,bounce_status",
        "order": "id.asc",
    }
    contacts: list[dict[str, Any]] = []
    offset = 0
    with requests.Session() as session:
        while True:
            response = session.get(
                endpoint,
                headers={**headers, "Range": f"{offset}-{offset + PAGE_SIZE - 1}"},
                params=params,
                timeout=60,
            )
            response.raise_for_status()
            page = response.json()
            contacts.extend(page)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    return contacts


def text_values(value: Any) -> Iterable[str]:
    if value is None:
        return ()
    if isinstance(value, list):
        return (str(item) for item in value)
    if isinstance(value, dict):
        return (str(item) for item in value.values())
    return (str(value),)


def is_source_contact(contact: dict[str, Any]) -> bool:
    industry = str(contact.get("industry") or "").strip().lower()
    tags = {
        value.strip().lower()
        for value in text_values(contact.get("tags"))
    }
    return (
        industry == "cosmetics"
        or "cosmetics" in tags
        or "sample request" in tags
        or "ask alconox" in tags
    )


def normalize_email(value: Any) -> str | None:
    email = str(value or "").strip().lower()
    if not email or "@" not in email:
        return None
    return email


def eligible_hashes(contacts: list[dict[str, Any]]) -> tuple[set[str], dict[str, int]]:
    source_rows = [contact for contact in contacts if is_source_contact(contact)]
    source_emails = {
        email
        for contact in source_rows
        if (email := normalize_email(contact.get("email")))
    }
    eligible_emails = {
        email
        for contact in source_rows
        if not bool(contact.get("unsubscribed"))
        and str(contact.get("bounce_status") or "").strip().lower() != "hard"
        and (email := normalize_email(contact.get("email")))
    }
    hashes = {
        hashlib.sha256(email.encode("utf-8")).hexdigest()
        for email in eligible_emails
    }
    counts = {
        "contacts_read": len(contacts),
        "source_rows": len(source_rows),
        "source_unique_emails": len(source_emails),
        "eligible_unique_emails": len(eligible_emails),
        "excluded_unique_emails": len(source_emails - eligible_emails),
    }
    return hashes, counts


def find_user_list(client: GoogleAdsClient) -> str | None:
    service = client.get_service("GoogleAdsService")
    escaped_name = LIST_NAME.replace("\\", "\\\\").replace("'", "\\'")
    query = f"""
        SELECT user_list.resource_name, user_list.name
        FROM user_list
        WHERE user_list.name = '{escaped_name}'
          AND user_list.membership_status != 'CLOSED'
        LIMIT 1
    """
    for row in service.search(customer_id=CUSTOMER_ID, query=query):
        return row.user_list.resource_name
    return None


def create_user_list(client: GoogleAdsClient) -> str:
    service = client.get_service("UserListService")
    operation = client.get_type("UserListOperation")
    user_list = operation.create
    user_list.name = LIST_NAME
    user_list.description = LIST_DESCRIPTION
    user_list.membership_life_span = 540
    user_list.crm_based_user_list.upload_key_type = (
        client.enums.CustomerMatchUploadKeyTypeEnum.CONTACT_INFO
    )
    response = service.mutate_user_lists(
        customer_id=CUSTOMER_ID,
        operations=[operation],
    )
    return response.results[0].resource_name


def upload_hashes_data_manager(
    config_path: Path,
    user_list_resource: str,
    hashes: set[str],
) -> str:
    config = google_config_values(config_path)
    access_token = data_manager_access_token(config_path)
    list_id = user_list_resource.rsplit("/", 1)[-1]
    destination: dict[str, Any] = {
        "operatingAccount": {
            "accountType": "GOOGLE_ADS",
            "accountId": CUSTOMER_ID,
        },
        "productDestinationId": list_id,
    }
    login_customer_id = config.get("login_customer_id", "").replace("-", "")
    if login_customer_id:
        destination["loginAccount"] = {
            "accountType": "GOOGLE_ADS",
            "accountId": login_customer_id,
        }
    members = [
        {
            "compositeData": {
                "userData": {
                    "userIdentifiers": [{"emailAddress": email_hash}],
                }
            }
        }
        for email_hash in sorted(hashes)
    ]
    base_payload: dict[str, Any] = {
        "destinations": [destination],
        "audienceMembers": members,
        "encoding": "HEX",
        "termsOfService": {"customerMatchTermsOfServiceStatus": "ACCEPTED"},
    }
    # Consent is intentionally omitted. The source has no per-contact ad-user-data
    # or ad-personalization consent fields, so this integration must not claim GRANTED.
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    validation = requests.post(
        DATA_MANAGER_ENDPOINT,
        headers=headers,
        json={**base_payload, "validateOnly": True},
        timeout=120,
    )
    if not validation.ok:
        raise RuntimeError(
            f"Data Manager validation failed ({validation.status_code}): "
            f"{safe_api_error(validation)}"
        )
    response = requests.post(
        DATA_MANAGER_ENDPOINT,
        headers=headers,
        json={**base_payload, "validateOnly": False},
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(
            f"Data Manager upload failed ({response.status_code}): "
            f"{safe_api_error(response)}"
        )
    result = response.json()
    return str(result.get("requestId") or "submitted-without-request-id")


def safe_api_error(response: requests.Response) -> str:
    try:
        error = response.json().get("error", {})
        status = error.get("status", "UNKNOWN")
        message = error.get("message", "No message returned")
        return f"{status}: {message}"
    except (ValueError, AttributeError):
        return "Google returned a non-JSON error response"


def google_error_summary(exc: GoogleAdsException) -> str:
    parts = []
    for error in exc.failure.errors:
        code = error.error_code
        active_code = next(
            (
                field.name
                for field, value in code._pb.ListFields()
                if value
            ),
            "unknown",
        )
        parts.append(f"{active_code}: {error.message}")
    return "; ".join(parts) or str(exc)


def main() -> int:
    args = parse_args()
    try:
        modes = sum(
            bool(value)
            for value in (args.apply, args.auth_url, args.auth_code, args.status)
        )
        if modes > 1:
            raise RuntimeError(
                "Choose only one of --apply, --auth-url, --auth-code, or --status."
            )
        if args.auth_url:
            print_auth_url(args.google_config)
            return 0
        if args.auth_code:
            exchange_auth_code(args.google_config, args.auth_code)
            return 0
        if args.status:
            print_request_status(args.google_config, args.status)
            return 0

        url, key = load_supabase_credentials(args.contact_env)
        contacts = fetch_contacts(url, key)
        hashes, counts = eligible_hashes(contacts)
        print("Halojet Customer Match source summary")
        for label, value in counts.items():
            print(f"  {label}: {value:,}")
        print("  raw addresses written or printed: 0")

        if not args.apply:
            print("Dry run only. Re-run with --apply to create and upload the list.")
            return 0
        if not hashes:
            raise RuntimeError("No eligible identifiers were found; refusing to upload.")

        client = GoogleAdsClient.load_from_storage(str(args.google_config))
        user_list = find_user_list(client)
        if user_list:
            print(f"Reusing existing list: {user_list}")
        else:
            user_list = create_user_list(client)
            print(f"Created list: {user_list}")
        request_id = upload_hashes_data_manager(args.google_config, user_list, hashes)
        print(f"Submitted Data Manager request: {request_id}")
        print("Google will populate size and match-rate fields asynchronously.")
        return 0
    except GoogleAdsException as exc:
        print(f"Google Ads API error: {google_error_summary(exc)}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
