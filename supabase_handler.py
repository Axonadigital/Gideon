import os
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
import json

class SupabaseHandler:
    """Hanterar all databasinteraktion med Supabase"""

    def __init__(self, url: str, key: str):
        self.client: Client = create_client(url, key)

    # ==================== LEADS ====================

    def add_lead(
        self,
        företag: str,
        kontaktperson: Optional[str] = None,
        email: Optional[str] = None,
        telefon: Optional[str] = None,
        status: str = "ny",
        tjänst: Optional[str] = None,
        anteckningar: Optional[str] = None,
        skapad_av: Optional[str] = None
    ) -> Dict:
        """Lägg till ny lead"""
        data = {
            "företag": företag,
            "kontaktperson": kontaktperson,
            "email": email,
            "telefon": telefon,
            "status": status,
            "tjänst": tjänst,
            "anteckningar": anteckningar,
            "skapad_av": skapad_av
        }
        # Ta bort None-värden
        data = {k: v for k, v in data.items() if v is not None}

        response = self.client.table("leads").insert(data).execute()
        return response.data[0] if response.data else {}

    def get_leads(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Hämta leads (filtrerat på status om angivet)"""
        query = self.client.table("leads").select("*").order("uppdaterad_datum", desc=True).limit(limit)

        if status:
            query = query.eq("status", status)

        response = query.execute()
        return response.data

    def update_lead(self, lead_id: str, **kwargs) -> Dict:
        """Uppdatera en lead"""
        response = self.client.table("leads").update(kwargs).eq("id", lead_id).execute()
        return response.data[0] if response.data else {}

    def get_aktiva_leads(self) -> List[Dict]:
        """Hämta alla aktiva leads (ej kund eller ej_intresserad)"""
        response = self.client.table("aktiva_leads").select("*").execute()
        return response.data

    # ==================== REFLEKTIONER ====================

    def add_reflektion(
        self,
        användare: str,
        text: str,
        typ: str = "daglig",
        lärdomar: Optional[List[str]] = None,
        nästa_steg: Optional[List[str]] = None,
        datum: Optional[date] = None
    ) -> Dict:
        """Logga en reflektion"""
        data = {
            "användare": användare,
            "text": text,
            "typ": typ,
            "datum": datum.isoformat() if datum else date.today().isoformat()
        }

        if lärdomar:
            data["lärdomar"] = lärdomar
        if nästa_steg:
            data["nästa_steg"] = nästa_steg

        response = self.client.table("reflektioner").insert(data).execute()
        return response.data[0] if response.data else {}

    def get_reflektioner(
        self,
        användare: Optional[str] = None,
        typ: Optional[str] = None,
        limit: int = 30
    ) -> List[Dict]:
        """Hämta reflektioner"""
        query = self.client.table("reflektioner").select("*").order("datum", desc=True).limit(limit)

        if användare:
            query = query.eq("användare", användare)
        if typ:
            query = query.eq("typ", typ)

        response = query.execute()
        return response.data

    def get_veckoreflektion(self, användare: Optional[str] = None) -> List[Dict]:
        """Hämta reflektioner från senaste veckan"""
        from datetime import timedelta
        en_vecka_sedan = (date.today() - timedelta(days=7)).isoformat()

        query = self.client.table("reflektioner")\
            .select("*")\
            .gte("datum", en_vecka_sedan)\
            .order("datum", desc=True)

        if användare:
            query = query.eq("användare", användare)

        response = query.execute()
        return response.data

    # ==================== KPIs ====================

    def add_kpi(
        self,
        namn: str,
        värde: float,
        enhet: Optional[str] = None,
        kategori: Optional[str] = None,
        anteckning: Optional[str] = None,
        skapad_av: Optional[str] = None,
        datum: Optional[date] = None
    ) -> Dict:
        """Logga en KPI"""
        data = {
            "namn": namn,
            "värde": värde,
            "enhet": enhet,
            "kategori": kategori,
            "anteckning": anteckning,
            "skapad_av": skapad_av,
            "datum": datum.isoformat() if datum else date.today().isoformat()
        }
        # Ta bort None-värden
        data = {k: v for k, v in data.items() if v is not None}

        response = self.client.table("kpis").insert(data).execute()
        return response.data[0] if response.data else {}

    def get_kpis(
        self,
        namn: Optional[str] = None,
        kategori: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Hämta KPIs"""
        query = self.client.table("kpis").select("*").order("datum", desc=True).limit(limit)

        if namn:
            query = query.eq("namn", namn)
        if kategori:
            query = query.eq("kategori", kategori)

        response = query.execute()
        return response.data

    def get_kpi_summa(self, namn: str, dagar: int = 30) -> float:
        """Räkna summa av en KPI över X dagar"""
        from datetime import timedelta
        start_datum = (date.today() - timedelta(days=dagar)).isoformat()

        response = self.client.table("kpis")\
            .select("värde")\
            .eq("namn", namn)\
            .gte("datum", start_datum)\
            .execute()

        return sum(item["värde"] for item in response.data)

    def get_denna_vecka_kpis(self) -> List[Dict]:
        """Hämta alla KPIs från denna vecka"""
        response = self.client.table("denna_vecka_kpis").select("*").execute()
        return response.data

    # ==================== TODOS ====================

    def add_todo(
        self,
        uppgift: str,
        kategori: str = "backlog",
        prioritet: str = "normal",
        skapad_av: Optional[str] = None,
        deadline: Optional[date] = None,
        anteckning: Optional[str] = None
    ) -> Dict:
        """Lägg till ny todo"""
        data = {
            "uppgift": uppgift,
            "kategori": kategori,
            "prioritet": prioritet,
            "status": "öppen",
            "skapad_av": skapad_av,
            "deadline": deadline.isoformat() if deadline else None,
            "anteckning": anteckning
        }
        # Ta bort None-värden
        data = {k: v for k, v in data.items() if v is not None}

        response = self.client.table("todos").insert(data).execute()
        return response.data[0] if response.data else {}

    def get_todos(
        self,
        kategori: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Hämta todos (filtrerat om angivet)"""
        query = self.client.table("todos").select("*").order("skapad_datum", desc=True).limit(limit)

        if kategori:
            query = query.eq("kategori", kategori)
        if status:
            query = query.eq("status", status)

        response = query.execute()
        return response.data

    def get_öppna_todos(self) -> List[Dict]:
        """Hämta alla öppna todos (status = öppen eller påbörjad)"""
        response = self.client.table("öppna_todos").select("*").execute()
        return response.data

    def get_dagens_todos(self) -> List[Dict]:
        """Hämta dagens todos (kategori = idag, status öppen/påbörjad)"""
        response = self.client.table("dagens_todos").select("*").execute()
        return response.data

    def update_todo(self, todo_id: str, **kwargs) -> Dict:
        """Uppdatera en todo"""
        # Om status ändras till 'klar', sätt klar_datum
        if kwargs.get("status") == "klar" and "klar_datum" not in kwargs:
            kwargs["klar_datum"] = datetime.now().isoformat()

        response = self.client.table("todos").update(kwargs).eq("id", todo_id).execute()
        return response.data[0] if response.data else {}

    def markera_todo_klar(self, todo_id: str) -> Dict:
        """Markera en todo som klar"""
        return self.update_todo(todo_id, status="klar", klar_datum=datetime.now().isoformat())

    def radera_todo(self, todo_id: str) -> bool:
        """Ta bort en todo"""
        response = self.client.table("todos").delete().eq("id", todo_id).execute()
        return len(response.data) > 0

    # ==================== MINNEN (pgvector) ====================

    def add_minne(
        self,
        användare: str,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Spara ett minne med embedding för senare sökning"""
        data = {
            "användare": användare,
            "text": text,
            "embedding": embedding,
            "metadata": metadata or {}
        }

        response = self.client.table("minnen").insert(data).execute()
        return response.data[0] if response.data else {}

    def search_minnen(
        self,
        query_embedding: List[float],
        användare: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        Sök efter relevanta minnen med vektor-likhet
        OBS: Kräver custom RPC-funktion i Supabase (se nedan)
        """
        # Detta kräver en RPC-funktion i Supabase
        # För nu returnerar vi senaste minnen som fallback
        query = self.client.table("minnen").select("*").order("skapad_datum", desc=True).limit(limit)

        if användare:
            query = query.eq("användare", användare)

        response = query.execute()
        return response.data

    # ==================== HJÄLPFUNKTIONER ====================

    def format_lead_list(self, leads: List[Dict]) -> str:
        """Formatera leads till läsbar text"""
        if not leads:
            return "Inga leads hittades."

        result = []
        for lead in leads:
            result.append(
                f"🏢 **{lead['företag']}**\n"
                f"   Status: {lead['status']}\n"
                f"   Kontakt: {lead.get('kontaktperson', 'Okänd')}\n"
                f"   Tjänst: {lead.get('tjänst', '-')}\n"
                f"   Senast uppdaterad: {lead['uppdaterad_datum'][:10]}\n"
            )
        return "\n".join(result)

    def format_kpi_summary(self, kpis: List[Dict]) -> str:
        """Formatera KPIs till läsbar sammanfattning"""
        if not kpis:
            return "Inga KPIs hittades."

        # Gruppera per namn
        grouped = {}
        for kpi in kpis:
            namn = kpi['namn']
            if namn not in grouped:
                grouped[namn] = []
            grouped[namn].append(kpi)

        result = []
        for namn, items in grouped.items():
            total = sum(item['värde'] for item in items)
            enhet = items[0].get('enhet', '')
            result.append(f"📊 **{namn}**: {total} {enhet}")

        return "\n".join(result)

    def format_todo_list(self, todos: List[Dict]) -> str:
        """Formatera todos till läsbar lista"""
        if not todos:
            return "Inga todos hittades."

        # Gruppera per kategori
        grouped = {}
        for todo in todos:
            kategori = todo.get('kategori', 'backlog')
            if kategori not in grouped:
                grouped[kategori] = []
            grouped[kategori].append(todo)

        kategori_emoji = {
            'idag': '📅',
            'ai': '🤖',
            'tech': '🤖',
            'träning': '💪',
            'hälsa': '💪',
            'praktiskt': '📦',
            'innehåll': '🎥',
            'backlog': '📋'
        }

        result = []
        for kategori, items in grouped.items():
            emoji = kategori_emoji.get(kategori, '📋')
            result.append(f"\n{emoji} **{kategori.capitalize()}** ({len(items)} st)")

            for todo in items:
                status_emoji = {
                    'öppen': '⬜',
                    'påbörjad': '🔄',
                    'klar': '✅',
                    'avbruten': '❌'
                }.get(todo['status'], '⬜')

                prioritet = todo.get('prioritet', 'normal')
                prio_marker = '🔴 ' if prioritet == 'hög' else ''

                uppgift = todo['uppgift']
                deadline_str = f" (deadline: {todo['deadline']})" if todo.get('deadline') else ''

                result.append(f"  {status_emoji} {prio_marker}{uppgift}{deadline_str}")

        return "\n".join(result)
