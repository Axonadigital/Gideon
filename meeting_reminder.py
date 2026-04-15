"""
Meeting Reminder System
- Skickar email-påminnelse 24h innan möte
- Skickar Discord-påminnelse med SMS-förslag 4h innan möte
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import anthropic

class MeetingReminder:
    """Hanterar automatiska mötes-påminnelser"""

    def __init__(self, calendar_handler, claude_api_key: str):
        self.calendar = calendar_handler
        self.claude_client = anthropic.Anthropic(api_key=claude_api_key)

        # Email-konfiguration (SMTP)
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_from = os.getenv("EMAIL_FROM")  # t.ex. isak@axonadigital.se
        self.email_password = os.getenv("EMAIL_PASSWORD")  # App-specific password

    def _is_relevant_meeting(self, event_summary: str) -> bool:
        """
        Kolla om mötet är relevant för påminnelser

        Nyckelord: möte, demo, demosida, uppföljning
        """
        summary_lower = event_summary.lower()
        keywords = ['möte', 'demo', 'demosida', 'demo hemsida', 'uppföljning']

        return any(keyword in summary_lower for keyword in keywords)

    def get_upcoming_meetings(self, hours_ahead: int = 48) -> List[Dict]:
        """
        Hämta kommande möten från Google Calendar

        Args:
            hours_ahead: Hur många timmar framåt att kolla

        Returns:
            Lista med möten (filtrerat på relevanta nyckelord)
        """
        if not self.calendar:
            return []

        try:
            # Hämta rå events från kalendern
            days = int(hours_ahead / 24) + 1
            print(f"🔍 DEBUG: Hämtar events {days} dagar framåt...")
            events = self.calendar.get_events_raw(
                days_ahead=days,
                max_results=50
            )
            print(f"🔍 DEBUG: Fick {len(events)} events från kalendern")

            # Filtrera på relevanta möten
            relevant_meetings = []
            for event in events:
                print(f"🔍 DEBUG: Kollar event: {event.get('summary', 'Ingen titel')}")
                summary = event.get('summary', '')

                if not self._is_relevant_meeting(summary):
                    continue

                # Parsa start-tid
                start = event['start'].get('dateTime', event['start'].get('date'))
                try:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                except:
                    continue

                # Extrahera företagsnamn (ord efter nyckelord)
                company = self._extract_company_name(summary)

                # Extrahera deltagare
                attendees = []
                for attendee in event.get('attendees', []):
                    email = attendee.get('email', '')
                    if email and '@axonadigital.se' not in email:
                        attendees.append(email)

                # Extrahera videolänk
                meeting_link = self._extract_meeting_link(event)

                relevant_meetings.append({
                    'id': event.get('id'),
                    'summary': summary,
                    'start': start_dt,
                    'company': company,
                    'attendees': attendees,
                    'link': meeting_link,
                    'description': event.get('description', '')
                })

            return relevant_meetings

        except Exception as e:
            print(f"❌ Kunde inte hämta möten: {e}")
            return []

    def _extract_company_name(self, summary: str) -> str:
        """Extrahera företagsnamn från mötes-titel"""
        # Ta bort nyckelord och hämta resten
        keywords = ['möte', 'demo', 'demosida', 'demo hemsida', 'uppföljning']

        summary_lower = summary.lower()
        for keyword in keywords:
            if keyword in summary_lower:
                # Ta text efter nyckelordet
                parts = summary.split(keyword, 1)
                if len(parts) > 1:
                    company = parts[1].strip(' -:,')
                    return company if company else 'Kunden'

        return 'Kunden'

    def _extract_meeting_link(self, event: Dict) -> str:
        """Extrahera Google Meet/Zoom-länk från event"""
        # Kolla hangoutLink (Google Meet)
        if 'hangoutLink' in event:
            return event['hangoutLink']

        # Kolla beskrivning för Zoom/Teams-länkar
        description = event.get('description', '')
        import re

        # Zoom
        zoom_match = re.search(r'https://[\w-]*\.?zoom\.us/j/[\d\w?=-]+', description)
        if zoom_match:
            return zoom_match.group(0)

        # Teams
        teams_match = re.search(r'https://teams\.microsoft\.com/l/meetup-join/[\w\d%/.-]+', description)
        if teams_match:
            return teams_match.group(0)

        # Google Meet i beskrivning
        meet_match = re.search(r'https://meet\.google\.com/[\w-]+', description)
        if meet_match:
            return meet_match.group(0)

        return event.get('htmlLink', 'Ingen länk hittades')

    def _generate_email_reminder(self, meeting_info: Dict) -> str:
        """
        Generera trevlig email-påminnelse med Claude

        Args:
            meeting_info: Dict med mötesinformation (summary, start, link, attendees)

        Returns:
            Email-text
        """
        # Använd Claude för att generera personlig email
        prompt = f"""Generera en trevlig och avslappnad email-påminnelse för ett kundmöte.

Mötesinformation:
- Titel: {meeting_info.get('summary', 'Möte')}
- Tid: {meeting_info.get('start', 'imorgon')}
- Videolänk: {meeting_info.get('link', 'Kommer skickas separat')}

Stil:
- Trevlig och avslappnad
- Kort och koncis
- Svensk ton
- Exempel: "Här kommer en påminnelse och videolänken på nytt: [länk]. Allt gott..."

Skriv bara email-texten (utan ämnesrad), max 3-4 meningar."""

        try:
            response = self.claude_client.messages.create(
                model="claude-haiku-4-5-20251001",  # Snabbare och billigare för email
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            return response.content[0].text.strip()
        except Exception as e:
            print(f"⚠️ Kunde inte generera email med Claude: {e}")
            # Fallback till enkel template
            return f"""Hej!

Här kommer en påminnelse om vårt möte {meeting_info.get('start', 'imorgon')}.

Videolänk: {meeting_info.get('link', 'Kommer skickas separat')}

Allt gott!

Mvh,
Axona Digital"""

    def _generate_sms_suggestion(self, meeting_info: Dict) -> str:
        """
        Generera förslag på SMS-text med Claude

        Args:
            meeting_info: Dict med mötesinformation

        Returns:
            SMS-förslag
        """
        prompt = f"""Generera ett kort och trevligt SMS för att påminna kund om möte.

Mötesinformation:
- Titel: {meeting_info.get('summary', 'Möte')}
- Tid: {meeting_info.get('start', 'idag')}
- Företag: {meeting_info.get('company', 'kunden')}

Krav:
- Max 160 tecken (SMS-längd)
- Trevlig och professionell ton
- Inkludera tid
- Avsluta med "/Isak, Axona Digital" eller "/[Namn], Axona Digital"

Skriv bara SMS-texten."""

        try:
            response = self.claude_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            return response.content[0].text.strip()
        except Exception as e:
            print(f"⚠️ Kunde inte generera SMS med Claude: {e}")
            # Fallback till enkel template
            return f"Hej! Påminnelse om vårt möte {meeting_info.get('start', 'idag')}. Ser fram emot att prata! /Isak, Axona Digital"

    async def send_email_reminder(self, to_email: str, meeting_info: Dict) -> bool:
        """
        Skicka email-påminnelse till kund

        Args:
            to_email: Mottagarens email
            meeting_info: Mötesinformation

        Returns:
            True om email skickades, False annars
        """
        if not self.email_from or not self.email_password:
            print("❌ Email inte konfigurerat (EMAIL_FROM/EMAIL_PASSWORD saknas)")
            return False

        try:
            # Generera email-text
            body = self._generate_email_reminder(meeting_info)

            # Skapa email
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"Påminnelse: {meeting_info.get('summary', 'Möte')} {meeting_info.get('start', 'imorgon')}"

            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Skicka via SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)

            print(f"✅ Email-påminnelse skickad till {to_email}")
            return True

        except Exception as e:
            print(f"❌ Kunde inte skicka email: {e}")
            return False

    def generate_discord_reminder(self, meeting_info: Dict) -> str:
        """
        Generera Discord-meddelande med SMS-förslag

        Args:
            meeting_info: Mötesinformation

        Returns:
            Formaterat Discord-meddelande
        """
        sms_suggestion = self._generate_sms_suggestion(meeting_info)

        # Formatera Discord-meddelande
        time_str = meeting_info.get('start', 'idag')
        company = meeting_info.get('company', 'kunden')
        attendees = meeting_info.get('attendees', [])

        message = f"""🔔 **Påminnelse: Möte om 4 timmar**

**Möte:** {meeting_info.get('summary', 'Okänt möte')}
**Tid:** {time_str}
**Företag:** {company}
"""

        if attendees:
            message += f"**Deltagare:** {', '.join(attendees)}\n"

        message += f"""
📱 **Förslag på SMS till kund:**

_{sms_suggestion}_

Kopiera texten och skicka manuellt!"""

        return message
