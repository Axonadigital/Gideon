import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from supabase import Client

class ConversationMemory:
    """Hanterar två-lagers minne: korttidsminne (messages) och långtidsminne (summaries)"""

    def __init__(self, db: Client, user_id: str):
        """
        Args:
            db: Supabase client
            user_id: Discord user ID
        """
        self.db = db
        self.user_id = user_id
        self.session_id = None
        self.last_activity = None
        self.message_count = 0
        self.cached_summaries = None  # Cache för att undvika upprepade DB-anrop

        # Konfiguration
        self.MAX_MESSAGES = 30  # Max i korttidsminne
        self.CONTEXT_WARNING_THRESHOLD = 25  # Varna vid detta antal
        self.SESSION_TIMEOUT_MINUTES = 30  # Auto-reset efter inaktivitet

    def start_or_resume_session(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Starta ny session eller återuppta befintlig

        Returns:
            Tuple[short_term_memory, long_term_summaries]
        """
        now = datetime.now()

        # Kolla om det finns en aktiv session (senaste 30 min)
        if self.last_activity and (now - self.last_activity).seconds < self.SESSION_TIMEOUT_MINUTES * 60:
            # Fortsätt befintlig session - använd cachade summaries
            if self.cached_summaries is None:
                self.cached_summaries = self._load_summaries()
            return self._load_active_session(), self.cached_summaries

        # Sammanfatta gamla sessionen om den finns
        if self.session_id:
            self._summarize_and_close_session()

        # Starta ny session - ladda summaries EN gång
        self.session_id = uuid.uuid4()
        self.last_activity = now
        self.message_count = 0
        self.cached_summaries = self._load_summaries()

        return [], self.cached_summaries

    def add_message(self, role: str, content: str) -> Optional[str]:
        """
        Lägg till meddelande i korttidsminne

        Returns:
            Warning message om context är nästan fullt, annars None
        """
        if not self.session_id:
            self.start_or_resume_session()

        self.last_activity = datetime.now()
        self.message_count += 1

        # Spara i Supabase
        try:
            self.db.table('conversation_messages').insert({
                'user_id': self.user_id,
                'session_id': str(self.session_id),
                'role': role,
                'content': content
            }).execute()
        except Exception as e:
            print(f"⚠️ Kunde inte spara meddelande: {e}")

        # Returnera varning om context nästan fullt
        if self.message_count >= self.CONTEXT_WARNING_THRESHOLD:
            return f"⚠️ Context fylls på ({self.message_count}/{self.MAX_MESSAGES} meddelanden). Tips: Kör `!reset` för ny session!"

        return None

    def _load_active_session(self) -> List[Dict]:
        """Ladda aktiv sessions meddelanden från Supabase"""
        if not self.session_id:
            return []

        try:
            result = self.db.table('conversation_messages')\
                .select('role, content')\
                .eq('user_id', self.user_id)\
                .eq('session_id', str(self.session_id))\
                .order('created_at', desc=False)\
                .limit(self.MAX_MESSAGES)\
                .execute()

            messages = []
            for msg in result.data:
                messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })

            self.message_count = len(messages)
            return messages

        except Exception as e:
            print(f"⚠️ Kunde inte ladda session: {e}")
            return []

    def _load_summaries(self, days_back: int = 30) -> List[Dict]:
        """Ladda sammanfattningar från långtidsminne (kallas 1 gång per session)"""
        try:
            since = datetime.now() - timedelta(days=days_back)

            result = self.db.table('conversation_summaries')\
                .select('*')\
                .eq('user_id', self.user_id)\
                .gte('session_start', since.isoformat())\
                .order('session_start', desc=True)\
                .limit(5)\
                .execute()

            return result.data if result.data else []

        except Exception as e:
            print(f"⚠️ Kunde inte ladda sammanfattningar: {e}")
            return []

    def _summarize_and_close_session(self):
        """Sammanfatta session med AI och spara i långtidsminne (om meningsfull)"""
        if not self.session_id or self.message_count == 0:
            return

        # Hämta alla meddelanden från sessionen
        try:
            result = self.db.table('conversation_messages')\
                .select('role, content, created_at')\
                .eq('user_id', self.user_id)\
                .eq('session_id', str(self.session_id))\
                .order('created_at', desc=False)\
                .execute()

            if not result.data:
                return

            messages = result.data

            # Kolla om sessionen är värd att spara
            if not self._should_save_summary(messages):
                print(f"⏭️ Skippar sammanfattning - session för kort/meningslös")
                return
            session_start = messages[0]['created_at']
            session_end = messages[-1]['created_at']

            # Bygg conversation text för sammanfattning
            conversation_text = ""
            for msg in messages:
                role_label = "Användare" if msg['role'] == 'user' else "Gideon"
                conversation_text += f"{role_label}: {msg['content']}\n\n"

            # Generera sammanfattning med Claude (förenklad - borde använda Claude API)
            summary_data = self._generate_summary(conversation_text)

            # Spara sammanfattning
            self.db.table('conversation_summaries').insert({
                'user_id': self.user_id,
                'session_id': str(self.session_id),
                'session_start': session_start,
                'session_end': session_end,
                'summary': summary_data['summary'],
                'key_topics': summary_data.get('key_topics', []),
                'decisions': summary_data.get('decisions', []),
                'leads_mentioned': summary_data.get('leads_mentioned', []),
                'meetings_mentioned': summary_data.get('meetings_mentioned', []),
                'next_steps': summary_data.get('next_steps', [])
            }).execute()

            print(f"✅ Session sammanfattad och sparad: {self.session_id}")

        except Exception as e:
            print(f"⚠️ Kunde inte sammanfatta session: {e}")

    def _should_save_summary(self, messages: List[Dict]) -> bool:
        """
        Avgör om sessionen är värd att spara som långtidsminne

        Skippar:
        - Mycket korta sessioner (< 4 meddelanden)
        - Test-meddelanden ("test", "hej", "?")
        - Meningslösa chattar
        """
        if len(messages) < 4:
            return False

        # Kolla innehållet - skippa om det ser ut som bara test
        content_length = sum(len(msg.get('content', '')) for msg in messages)
        if content_length < 100:  # Mindre än 100 tecken totalt = troligen bara test
            return False

        # Kolla efter nyckelord som indikerar meningsfull konversation
        meaningful_keywords = [
            'lead', 'kund', 'möte', 'projekt', 'hemsida', 'pris', 'offert',
            'boka', 'kontakt', 'försäljning', 'strategi', 'plan', 'mål'
        ]

        combined_text = ' '.join(msg.get('content', '').lower() for msg in messages)
        has_meaningful_content = any(keyword in combined_text for keyword in meaningful_keywords)

        return has_meaningful_content

    def _generate_summary(self, conversation_text: str) -> Dict:
        """
        Generera strukturerad sammanfattning av konversation

        TODO: Använd Claude API för att generera smart sammanfattning
        För nu: extrahera nyckelord och mönster
        """
        text_lower = conversation_text.lower()

        # Enkel keyword extraction
        topics = []
        if 'hemsida' in text_lower or 'webb' in text_lower:
            topics.append('Hemsidor/Webb')
        if 'möte' in text_lower or 'boka' in text_lower:
            topics.append('Möten')
        if 'lead' in text_lower or 'kund' in text_lower:
            topics.append('Leads/Kunder')
        if 'pris' in text_lower or 'offert' in text_lower:
            topics.append('Prissättning')

        # Extrahera företagsnamn (enkelt mönster)
        # TODO: Använd Claude för bättre extraktion

        return {
            'summary': f"Diskuterade {', '.join(topics) if topics else 'diverse ämnen'} ({self.message_count} meddelanden)",
            'key_topics': topics,
            'decisions': [],
            'leads_mentioned': [],
            'meetings_mentioned': [],
            'next_steps': []
        }

    def reset_session(self) -> str:
        """
        Manuell reset - sammanfatta och starta ny session

        Returns:
            Bekräftelsemeddelande
        """
        if self.session_id and self.message_count > 0:
            self._summarize_and_close_session()
            msg = f"🔄 Session sammanfattad ({self.message_count} meddelanden). Ny session startad!"
        else:
            msg = "🔄 Ny session startad!"

        self.session_id = uuid.uuid4()
        self.last_activity = datetime.now()
        self.message_count = 0
        self.cached_summaries = self._load_summaries()  # Ladda om summaries för ny session

        return msg

    def format_context_for_claude(self, short_term: List[Dict], summaries: List[Dict]) -> str:
        """
        Formatera context för Claude's system prompt

        Returns:
            Formaterad context-sträng
        """
        context_parts = []

        # Långtidsminne (sammanfattningar)
        if summaries:
            context_parts.append("**TIDIGARE SESSIONER (Långtidsminne):**")
            for summary in summaries[:5]:  # Max 5 senaste
                start = summary['session_start'][:10]  # Datum
                context_parts.append(f"\n📅 {start}: {summary['summary']}")

                if summary.get('decisions'):
                    context_parts.append(f"  Beslut: {', '.join(summary['decisions'][:3])}")
                if summary.get('leads_mentioned'):
                    context_parts.append(f"  Leads: {', '.join(summary['leads_mentioned'][:3])}")

            context_parts.append("\n")

        return "\n".join(context_parts) if context_parts else ""
