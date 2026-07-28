#!/usr/bin/env python3
"""
Google Ads OAuth2 re-auth — mints a FRESH refresh token.

The old google_ads_auth.py used Google's `oob` redirect, which Google disabled
in 2022. This uses the manual loopback flow, which works even over SSH and in
non-interactive runners (no input() — driven entirely by command args).

Two steps:
  1) python3 google_ads_reauth.py url
       Prints a consent URL. Open it on ANY device, sign in with a Google
       account that can access MCC 3282542648, and approve. The browser then
       tries to load 'http://localhost/?code=...' and FAILS to load — expected.
       Copy the `code=` value (or the whole localhost URL) from the address bar.
  2) python3 google_ads_reauth.py code "<paste code or full localhost URL>"
       Exchanges it and writes the new refresh_token back into
       google_ads_config.yaml. Secrets are never printed.
"""
import sys
import urllib.parse
import urllib.request
import json
import re

CONFIG = "google_ads_config.yaml"
REDIRECT_URI = "http://localhost"  # allowed for Desktop-type OAuth clients
SCOPE = "https://www.googleapis.com/auth/adwords"


def read_config():
    lines = open(CONFIG, encoding="utf-8-sig", errors="replace").read().splitlines()
    cfg = {}
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or ":" not in s:
            continue
        k, _, v = s.partition(":")
        cfg[k.strip()] = v.strip().strip('"').strip("'")
    return lines, cfg


def write_refresh_token(lines, new_token):
    out = []
    replaced = False
    for line in lines:
        if re.match(r"^\s*refresh_token\s*:", line):
            out.append(f'refresh_token: "{new_token}"')
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f'refresh_token: "{new_token}"')
    open(CONFIG, "w", encoding="utf-8").write("\n".join(out) + "\n")


def print_url(client_id):
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",  # force a fresh refresh_token
    })
    print("\nOpen this URL (any device), sign in with the Google account that")
    print("can access MCC 3282542648, and approve:\n")
    print(auth_url)
    print("\nThe browser will then try to load 'http://localhost/?code=...' and")
    print("FAIL to load — that's expected. Copy the whole address-bar URL (or just")
    print("the code=... value) and run:\n")
    print('  python3 google_ads_reauth.py code "<paste here>"\n')
    sys.stdout.flush()


def main():
    _, cfg = read_config()
    client_id = cfg.get("client_id", "")
    client_secret = cfg.get("client_secret", "")
    if not client_id or not client_secret:
        print("ERROR: client_id / client_secret missing from", CONFIG)
        sys.exit(1)

    mode = sys.argv[1] if len(sys.argv) > 1 else "url"

    if mode == "url":
        print_url(client_id)
        return

    if mode != "code":
        print(f"Unknown command '{mode}'. Use:  url  |  code \"<value>\"")
        sys.exit(1)

    code = sys.argv[2].strip() if len(sys.argv) > 2 else ""
    # Tolerate a pasted full localhost URL
    m = re.search(r"[?&]code=([^&]+)", code)
    if m:
        code = urllib.parse.unquote(m.group(1))
    if not code:
        print('No code provided. Run:  python3 google_ads_reauth.py code "<value>"')
        sys.exit(1)

    data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    try:
        resp = urllib.request.urlopen(urllib.request.Request(
            "https://oauth2.googleapis.com/token", data=data))
        tokens = json.load(resp)
    except urllib.error.HTTPError as e:
        print("\nToken exchange FAILED:", e.read().decode()[:300])
        sys.exit(1)

    rt = tokens.get("refresh_token")
    if not rt:
        print("\nNo refresh_token returned. Response keys:", list(tokens.keys()))
        print("(If you only got an access_token, revoke prior access at")
        print(" https://myaccount.google.com/permissions and retry — `prompt=consent`")
        print(" should force a refresh token.)")
        sys.exit(1)

    _, cfg2 = read_config()  # re-read to preserve current file
    lines, _ = read_config()
    write_refresh_token(lines, rt)
    print("\nSUCCESS — new refresh_token written to", CONFIG)
    print("(", len(rt), "chars; value not shown). You can now re-run the validation.")


if __name__ == "__main__":
    main()
