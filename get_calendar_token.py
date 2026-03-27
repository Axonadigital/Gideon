#!/usr/bin/env python3
"""
OAuth 2.0 flow för att få Google Calendar refresh token.
Kör detta script EN gång för att autentisera och få refresh token.
"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Scopes - vad Gideon behöver kunna göra
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_credentials():
    """Kör OAuth flow och returnera credentials med refresh token"""
    creds = None

    # Kolla om vi redan har token
    if os.path.exists('token.pickle'):
        print("📂 Hittade befintlig token.pickle...")
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # Om inga (giltiga) credentials finns, låt användaren logga in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Uppdaterar token...")
            creds.refresh(Request())
        else:
            print("🔐 Startar OAuth flow...")
            print("Din webbläsare kommer öppnas - logga in med ditt Google-konto!")

            # Hitta credentials-filen
            credentials_file = None
            for f in os.listdir('.'):
                if f.startswith('client_secret_') and f.endswith('.json'):
                    credentials_file = f
                    break

            if not credentials_file:
                print("❌ Kunde inte hitta client_secret_xxx.json fil!")
                print("Ladda ner den från Google Cloud Console och lägg i denna mapp.")
                return None

            print(f"📄 Använder credentials: {credentials_file}")

            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Spara credentials för framtida körningar
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

        print("✅ Token sparad i token.pickle")

    return creds

def main():
    print("🚀 Google Calendar OAuth Setup för Gideon\n")

    creds = get_calendar_credentials()

    if creds:
        print("\n" + "="*60)
        print("✅ OAUTH LYCKADES!")
        print("="*60)
        print("\n📋 Refresh Token (spara denna som Fly.io secret):\n")
        print(f"GOOGLE_CALENDAR_REFRESH_TOKEN={creds.refresh_token}")
        print("\n📋 Client ID och Secret (från din credentials.json):\n")

        # Läs client ID och secret från credentials-filen
        credentials_file = None
        for f in os.listdir('.'):
            if f.startswith('client_secret_') and f.endswith('.json'):
                credentials_file = f
                break

        if credentials_file:
            with open(credentials_file, 'r') as f:
                client_config = json.load(f)
                installed = client_config.get('installed', client_config.get('web', {}))
                print(f"GOOGLE_CLIENT_ID={installed.get('client_id')}")
                print(f"GOOGLE_CLIENT_SECRET={installed.get('client_secret')}")

        print("\n" + "="*60)
        print("📝 NÄSTA STEG:")
        print("="*60)
        print("1. Kopiera dessa 3 secrets")
        print("2. Sätt dem på Fly.io med:")
        print("   flyctl secrets set GOOGLE_CALENDAR_REFRESH_TOKEN='...' \\")
        print("                       GOOGLE_CLIENT_ID='...' \\")
        print("                       GOOGLE_CLIENT_SECRET='...'")
        print("="*60)

        # Spara också till en fil för backup
        with open('calendar_secrets.txt', 'w') as f:
            f.write(f"GOOGLE_CALENDAR_REFRESH_TOKEN={creds.refresh_token}\n")
            if credentials_file:
                with open(credentials_file, 'r') as cf:
                    client_config = json.load(cf)
                    installed = client_config.get('installed', client_config.get('web', {}))
                    f.write(f"GOOGLE_CLIENT_ID={installed.get('client_id')}\n")
                    f.write(f"GOOGLE_CLIENT_SECRET={installed.get('client_secret')}\n")

        print("\n💾 Secrets också sparade i: calendar_secrets.txt")
    else:
        print("❌ Något gick fel!")

if __name__ == '__main__':
    main()
