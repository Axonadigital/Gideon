import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class CalendarHandler:
    """Hanterar Google Calendar-operationer med OAuth 2.0"""

    def __init__(self, refresh_token: str, client_id: str, client_secret: str):
        """
        Initiera Calendar handler med OAuth credentials

        Args:
            refresh_token: OAuth refresh token
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
        """
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Autentisera med Google Calendar API"""
        try:
            creds = Credentials(
                None,  # token (vi använder refresh_token)
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            self.service = build('calendar', 'v3', credentials=creds)
        except Exception as e:
            print(f"❌ Kunde inte autentisera med Google Calendar: {str(e)}")
            self.service = None

    def add_event(
        self,
        summary: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None
    ) -> str:
        """
        Lägg till event i kalendern

        Args:
            summary: Event-titel (t.ex. "Möte med kund")
            start_time: Start-tid (ISO format eller naturligt språk som "2024-03-27 14:00")
            end_time: Slut-tid (optional, default +1h)
            description: Beskrivning
            location: Plats
            attendees: Lista med email-adresser

        Returns:
            Resultat-meddelande
        """
        if not self.service:
            return "❌ Google Calendar inte konfigurerat!"

        try:
            # Parsa start_time
            start_dt = self._parse_datetime(start_time)
            if not start_dt:
                return f"❌ Kunde inte parsa start-tid: {start_time}"

            # Parsa eller beräkna end_time
            if end_time:
                end_dt = self._parse_datetime(end_time)
                if not end_dt:
                    return f"❌ Kunde inte parsa slut-tid: {end_time}"
            else:
                end_dt = start_dt + timedelta(hours=1)

            # Skapa event
            event = {
                'summary': summary,
                'description': description or '',
                'location': location or '',
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': 'Europe/Stockholm',
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': 'Europe/Stockholm',
                },
            }

            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]

            # Lägg till i kalendern
            result = self.service.events().insert(calendarId='primary', body=event).execute()

            event_link = result.get('htmlLink', '')
            return f"✅ Event tillagt: {summary}\n📅 {start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%H:%M')}\n🔗 {event_link}"

        except HttpError as error:
            return f"❌ Google Calendar API-fel: {error}"
        except Exception as e:
            return f"❌ Kunde inte lägga till event: {str(e)}"

    def get_events(
        self,
        days_ahead: int = 7,
        max_results: int = 10
    ) -> str:
        """
        Hämta kommande events

        Args:
            days_ahead: Antal dagar framåt att visa
            max_results: Max antal events att returnera

        Returns:
            Formaterad lista med events
        """
        if not self.service:
            return "❌ Google Calendar inte konfigurerat!"

        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            if not events:
                return f"📅 Inga events kommande {days_ahead} dagar."

            result = [f"📅 **Kommande events ({days_ahead} dagar):**\n"]
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                summary = event.get('summary', 'Ingen titel')

                # Parsa datum
                try:
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    formatted_time = start

                location = event.get('location', '')
                loc_str = f" 📍 {location}" if location else ""

                result.append(f"• {formatted_time} - {summary}{loc_str}")

            return "\n".join(result)

        except HttpError as error:
            return f"❌ Google Calendar API-fel: {error}"
        except Exception as e:
            return f"❌ Kunde inte hämta events: {str(e)}"

    def _parse_datetime(self, dt_string: str) -> Optional[datetime]:
        """
        Parsa datetime-sträng till datetime-objekt
        Stödjer ISO format och enklare format som "2024-03-27 14:00"
        """
        formats = [
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%dT%H:%M:%S',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(dt_string, fmt)
            except ValueError:
                continue

        # Försök med ISO format
        try:
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        except:
            return None
