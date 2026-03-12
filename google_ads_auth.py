#!/usr/bin/env python3
"""
Google Ads OAuth2 Authentication Helper
Generates a refresh token for Google Ads API access.
Manual flow for systems without a browser.
"""

import os
import urllib.parse
import requests

# OAuth credentials - load from environment variables
CLIENT_ID = os.environ.get("GOOGLE_ADS_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "")
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
SCOPE = "https://www.googleapis.com/auth/adwords"

def main():
    print("=" * 70)
    print("  GOOGLE ADS OAUTH2 AUTHENTICATION")
    print("=" * 70)

    # Build authorization URL
    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(auth_params)

    print("\n1. Open this URL in your browser:\n")
    print(auth_url)
    print("\n2. Sign in and authorize the app")
    print("3. Copy the authorization code and paste it below\n")

    auth_code = input("Enter the authorization code: ").strip()

    if not auth_code:
        print("No code entered. Exiting.")
        return None

    # Exchange code for tokens
    print("\nExchanging code for tokens...")

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    response = requests.post(token_url, data=token_data)
    tokens = response.json()

    if "error" in tokens:
        print(f"\nError: {tokens.get('error_description', tokens.get('error'))}")
        return None

    refresh_token = tokens.get("refresh_token")

    print("\n" + "=" * 70)
    print("  SUCCESS! Here's your refresh token:")
    print("=" * 70)
    print(f"\n{refresh_token}\n")
    print("=" * 70)

    return refresh_token

if __name__ == "__main__":
    main()
