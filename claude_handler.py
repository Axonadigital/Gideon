import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import anthropic
from anthropic.types import TextBlock, ToolUseBlock
from calendar_handler import CalendarHandler

class ClaudeHandler:
    """Hanterar Claude API-anrop med file access tools"""

    def __init__(self, api_key: str, workspace_path: str, model: str = "claude-sonnet-4-5-20250929", db=None, calendar=None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.workspace_path = Path(workspace_path).resolve()
        self.model = model
        self.conversation_history = []
        self.db = db  # Supabase handler för att spara leads, KPIs, etc.
        self.calendar = calendar  # Calendar handler för Google Calendar

    def _get_safe_path(self, filepath: str) -> Path:
        """Säkerställ att sökvägen är inom workspace"""
        path = Path(filepath)
        if not path.is_absolute():
            path = self.workspace_path / path
        path = path.resolve()

        # Säkerhetskoll: måste vara inom workspace
        if not str(path).startswith(str(self.workspace_path)):
            raise ValueError(f"Access denied: {path} is outside workspace")
        return path

    def _read_file(self, filepath: str) -> str:
        """Läs en fil"""
        try:
            path = self._get_safe_path(filepath)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"✅ Läste {path}:\n\n{content}"
        except Exception as e:
            return f"❌ Kunde inte läsa {filepath}: {str(e)}"

    def _write_file(self, filepath: str, content: str) -> str:
        """Skriv till en fil"""
        try:
            path = self._get_safe_path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"✅ Skrev till {path}"
        except Exception as e:
            return f"❌ Kunde inte skriva till {filepath}: {str(e)}"

    def _list_files(self, directory: str = ".") -> str:
        """Lista filer i en mapp"""
        try:
            path = self._get_safe_path(directory)
            if not path.is_dir():
                return f"❌ {directory} är inte en mapp"

            files = []
            for item in sorted(path.iterdir()):
                prefix = "📁" if item.is_dir() else "📄"
                files.append(f"{prefix} {item.name}")

            return f"✅ Filer i {path}:\n" + "\n".join(files)
        except Exception as e:
            return f"❌ Kunde inte lista {directory}: {str(e)}"

    def _run_bash(self, command: str) -> str:
        """Kör bash-kommando (begränsat för säkerhet)"""
        # Whitelist av säkra kommandon
        safe_commands = ['git', 'ls', 'pwd', 'cat', 'grep', 'find', 'tree']
        cmd_start = command.split()[0] if command.split() else ""

        if cmd_start not in safe_commands:
            return f"❌ Kommando '{cmd_start}' är inte tillåtet. Tillåtna: {', '.join(safe_commands)}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            return f"✅ Körde: {command}\n\n{output}"
        except Exception as e:
            return f"❌ Kunde inte köra kommando: {str(e)}"

    def _search_files(self, pattern: str, directory: str = ".") -> str:
        """Sök efter filer med grep"""
        try:
            path = self._get_safe_path(directory)
            result = subprocess.run(
                f"grep -r -n '{pattern}' .",
                shell=True,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.stdout:
                return f"✅ Hittade '{pattern}':\n\n{result.stdout[:2000]}"
            else:
                return f"ℹ️ Hittade inga matchningar för '{pattern}'"
        except Exception as e:
            return f"❌ Kunde inte söka: {str(e)}"

    # ==================== SUPABASE TOOLS ====================

    def _add_lead(self, företag: str, kontaktperson: str = None, status: str = "ny",
                  tjänst: str = None, anteckningar: str = None, skapad_av: str = "Gideon") -> str:
        """Lägg till nytt lead i Supabase"""
        if not self.db:
            return "❌ Supabase inte konfigurerat!"

        try:
            result = self.db.add_lead(
                företag=företag,
                kontaktperson=kontaktperson,
                status=status,
                tjänst=tjänst,
                anteckningar=anteckningar,
                skapad_av=skapad_av
            )
            return f"✅ Lead tillagt: {företag} (ID: {result['id']}, Status: {status})"
        except Exception as e:
            return f"❌ Kunde inte lägga till lead: {str(e)}"

    def _get_leads(self, status: str = None) -> str:
        """Hämta leads från Supabase"""
        if not self.db:
            return "❌ Supabase inte konfigurerat!"

        try:
            if status:
                leads = self.db.get_leads(status=status)
                title = f"Leads med status '{status}'"
            else:
                leads = self.db.get_aktiva_leads()
                title = "Aktiva leads"

            if not leads:
                return f"ℹ️ {title}: Inga hittades."

            formatted = self.db.format_lead_list(leads)
            return f"✅ {title}:\n\n{formatted}"
        except Exception as e:
            return f"❌ Kunde inte hämta leads: {str(e)}"

    def _add_kpi(self, namn: str, värde: float, enhet: str = None,
                 anteckning: str = None, skapad_av: str = "Gideon") -> str:
        """Logga KPI i Supabase"""
        if not self.db:
            return "❌ Supabase inte konfigurerat!"

        try:
            result = self.db.add_kpi(
                namn=namn,
                värde=värde,
                enhet=enhet,
                anteckning=anteckning,
                skapad_av=skapad_av
            )
            enhet_str = f" {enhet}" if enhet else ""
            return f"✅ KPI loggad: {namn} = {värde}{enhet_str}"
        except Exception as e:
            return f"❌ Kunde inte logga KPI: {str(e)}"

    def _get_kpis(self, namn: str = None, dagar: int = 7) -> str:
        """Hämta KPIs från Supabase"""
        if not self.db:
            return "❌ Supabase inte konfigurerat!"

        try:
            if dagar == 7:
                kpis = self.db.get_denna_vecka_kpis()
                period = "denna vecka"
            else:
                kpis = self.db.get_kpis(namn=namn, limit=50)
                period = f"senaste {dagar} dagarna"

            if not kpis:
                return f"ℹ️ Inga KPIs hittades för {period}."

            summary = self.db.format_kpi_summary(kpis)
            return f"✅ KPIs {period}:\n\n{summary}"
        except Exception as e:
            return f"❌ Kunde inte hämta KPIs: {str(e)}"

    def _add_reflektion(self, text: str, användare: str = "Gideon", typ: str = "daglig") -> str:
        """Spara reflektion i Supabase"""
        if not self.db:
            return "❌ Supabase inte konfigurerat!"

        try:
            result = self.db.add_reflektion(
                användare=användare,
                text=text,
                typ=typ
            )
            return f"✅ Reflektion sparad!"
        except Exception as e:
            return f"❌ Kunde inte spara reflektion: {str(e)}"

    def _reset_chat(self) -> str:
        """Rensa konversationshistorik"""
        self.conversation_history = []
        return "✅ Chatten har rensats! Vi börjar om från början."

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Kör ett tool och returnera resultat"""
        if tool_name == "read_file":
            return self._read_file(tool_input["filepath"])
        elif tool_name == "write_file":
            return self._write_file(tool_input["filepath"], tool_input["content"])
        elif tool_name == "list_files":
            return self._list_files(tool_input.get("directory", "."))
        elif tool_name == "run_bash":
            return self._run_bash(tool_input["command"])
        elif tool_name == "search_files":
            return self._search_files(tool_input["pattern"], tool_input.get("directory", "."))
        elif tool_name == "add_lead":
            return self._add_lead(
                företag=tool_input["foretag"],
                kontaktperson=tool_input.get("kontaktperson"),
                status=tool_input.get("status", "ny"),
                tjänst=tool_input.get("tjanst"),
                anteckningar=tool_input.get("anteckningar"),
                skapad_av=tool_input.get("skapad_av", "Gideon")
            )
        elif tool_name == "get_leads":
            return self._get_leads(status=tool_input.get("status"))
        elif tool_name == "add_kpi":
            return self._add_kpi(
                namn=tool_input["namn"],
                värde=tool_input["varde"],
                enhet=tool_input.get("enhet"),
                anteckning=tool_input.get("anteckning"),
                skapad_av=tool_input.get("skapad_av", "Gideon")
            )
        elif tool_name == "get_kpis":
            return self._get_kpis(
                namn=tool_input.get("namn"),
                dagar=tool_input.get("dagar", 7)
            )
        elif tool_name == "add_reflektion":
            return self._add_reflektion(
                text=tool_input["text"],
                användare=tool_input.get("anvandare", "Gideon"),
                typ=tool_input.get("typ", "daglig")
            )
        elif tool_name == "reset_chat":
            return self._reset_chat()
        elif tool_name == "add_calendar_event":
            if not self.calendar:
                return "❌ Google Calendar inte konfigurerat!"
            return self.calendar.add_event(
                summary=tool_input["summary"],
                start_time=tool_input["start_time"],
                end_time=tool_input.get("end_time"),
                description=tool_input.get("description"),
                location=tool_input.get("location"),
                attendees=tool_input.get("attendees")
            )
        elif tool_name == "get_calendar_events":
            if not self.calendar:
                return "❌ Google Calendar inte konfigurerat!"
            return self.calendar.get_events(
                days_ahead=tool_input.get("days_ahead", 7),
                max_results=tool_input.get("max_results", 10)
            )
        else:
            return f"❌ Okänt tool: {tool_name}"

    def get_tools(self) -> List[Dict]:
        """Definiera tillgängliga tools för Claude"""
        tools = [
            {
                "name": "read_file",
                "description": "Läs innehållet i en fil. Ange relativ eller absolut sökväg.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filepath": {
                            "type": "string",
                            "description": "Sökväg till filen (t.ex. 'Foretagsgrund/STATUS.md')"
                        }
                    },
                    "required": ["filepath"]
                }
            },
            {
                "name": "write_file",
                "description": "Skriv eller uppdatera en fil. Skapar nya mappar om behövs.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filepath": {
                            "type": "string",
                            "description": "Sökväg till filen"
                        },
                        "content": {
                            "type": "string",
                            "description": "Innehåll att skriva"
                        }
                    },
                    "required": ["filepath", "content"]
                }
            },
            {
                "name": "list_files",
                "description": "Lista filer och mappar i en katalog.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Mapp att lista (default: workspace root)"
                        }
                    }
                }
            },
            {
                "name": "run_bash",
                "description": "Kör bash-kommando (endast säkra kommandon: git, ls, pwd, cat, grep, find, tree).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Bash-kommando att köra"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "search_files",
                "description": "Sök efter text i filer med grep.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Sökmönster (regex)"
                        },
                        "directory": {
                            "type": "string",
                            "description": "Mapp att söka i (default: workspace root)"
                        }
                    },
                    "required": ["pattern"]
                }
            }
        ]

        # Lägg till Supabase-verktyg om databas är konfigurerad
        if self.db:
            tools.extend([
                {
                    "name": "add_lead",
                    "description": "Lägg till nytt lead (potentiell kund) i databasen. Använd när användaren nämner ett företag eller kontakt de vill hålla koll på.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "foretag": {
                                "type": "string",
                                "description": "Företagets namn"
                            },
                            "kontaktperson": {
                                "type": "string",
                                "description": "Kontaktpersonens namn (valfritt)"
                            },
                            "status": {
                                "type": "string",
                                "description": "Status: 'ny', 'kontaktad', 'intresserad', 'förhandling', 'kund', 'ej_intresserad' (default: ny)"
                            },
                            "tjanst": {
                                "type": "string",
                                "description": "Tjänst de är intresserade av: 'chatbot', 'voice_agent', 'crm', 'hemsida', etc."
                            },
                            "anteckningar": {
                                "type": "string",
                                "description": "Ytterligare anteckningar"
                            },
                            "skapad_av": {
                                "type": "string",
                                "description": "Vem som skapade leadet (default: Gideon)"
                            }
                        },
                        "required": ["foretag"]
                    }
                },
                {
                    "name": "get_leads",
                    "description": "Hämta leads från databasen. Kan filtrera på status.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": "string",
                                "description": "Filtrera på status (valfritt): 'ny', 'kontaktad', 'intresserad', etc."
                            }
                        }
                    }
                },
                {
                    "name": "add_kpi",
                    "description": "Logga en KPI (nyckeltal) som hemsidor_salda, moten_bokade, intakter, etc.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "namn": {
                                "type": "string",
                                "description": "KPI-namn (t.ex. 'hemsidor_salda', 'moten_bokade')"
                            },
                            "varde": {
                                "type": "number",
                                "description": "Värde/antal"
                            },
                            "enhet": {
                                "type": "string",
                                "description": "Enhet (t.ex. 'st', 'kr', 'tim')"
                            },
                            "anteckning": {
                                "type": "string",
                                "description": "Ytterligare kommentar"
                            },
                            "skapad_av": {
                                "type": "string",
                                "description": "Vem som loggade (default: Gideon)"
                            }
                        },
                        "required": ["namn", "varde"]
                    }
                },
                {
                    "name": "get_kpis",
                    "description": "Hämta KPIs från databasen. Visa statistik och framsteg.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "namn": {
                                "type": "string",
                                "description": "Filtrera på specifik KPI (valfritt)"
                            },
                            "dagar": {
                                "type": "integer",
                                "description": "Antal dagar bakåt att visa (default: 7)"
                            }
                        }
                    }
                },
                {
                    "name": "add_reflektion",
                    "description": "Spara en daglig reflektion eller anteckning.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Reflektionens innehåll"
                            },
                            "anvandare": {
                                "type": "string",
                                "description": "Vem reflektionen gäller (default: Gideon)"
                            },
                            "typ": {
                                "type": "string",
                                "description": "Typ av reflektion: 'daglig', 'veckovis', 'projektreflektion' (default: daglig)"
                            }
                        },
                        "required": ["text"]
                    }
                },
                {
                    "name": "reset_chat",
                    "description": "Rensa konversationshistoriken och börja om från början. Använd när användaren säger 'rensa chatten', 'börja om', 'ny konversation', eller liknande.",
                    "input_schema": {
                        "type": "object",
                        "properties": {}
                    }
                }
            ])

        # Lägg till Calendar-verktyg om konfigurerat
        if self.calendar:
            tools.extend([
                {
                    "name": "add_calendar_event",
                    "description": "Lägg till event i Google Calendar. Använd när användaren nämner möten, deadlines, påminnelser. Exempel: 'Boka möte med X', 'Påminn mig om Y'",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Event-titel (t.ex. 'Möte med kund')"
                            },
                            "start_time": {
                                "type": "string",
                                "description": "Start-tid i format YYYY-MM-DD HH:MM (t.ex. '2024-03-27 14:00')"
                            },
                            "end_time": {
                                "type": "string",
                                "description": "Slut-tid i format YYYY-MM-DD HH:MM (optional, default +1h)"
                            },
                            "description": {
                                "type": "string",
                                "description": "Beskrivning av eventet (optional)"
                            },
                            "location": {
                                "type": "string",
                                "description": "Plats/adress (optional)"
                            },
                            "attendees": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Lista med email-adresser till deltagare (optional)"
                            }
                        },
                        "required": ["summary", "start_time"]
                    }
                },
                {
                    "name": "get_calendar_events",
                    "description": "Hämta kommande events från Google Calendar. Använd när användaren frågar 'vad har jag för möten?', 'visa min kalender', etc.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "days_ahead": {
                                "type": "integer",
                                "description": "Antal dagar framåt att visa (default: 7)"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Max antal events att visa (default: 10)"
                            }
                        }
                    }
                }
            ])

        return tools

    async def ask(self, user_message: str, user_name: str = "User") -> str:
        """Skicka ett meddelande till Claude och få svar (med tool support)"""
        # Lägg till användarmeddelande i historik
        self.conversation_history.append({
            "role": "user",
            "content": f"[{user_name}]: {user_message}"
        })

        # System prompt
        db_tools_info = """
**TILLGÄNGLIGA VERKTYG:**
- add_lead: Lägg till leads (potentiella kunder)
- get_leads: Hämta och visa leads
- add_kpi: Logga KPIs (nyckeltal som 'hemsidor_salda', 'moten_bokade', etc.)
- get_kpis: Visa statistik och framsteg
- add_reflektion: Spara reflektioner och anteckningar
- reset_chat: Rensa chatten när användaren säger "rensa chatten", "börja om", "ny konversation"

**NÄR DU SKA AGERA AUTOMATISKT:**
- Någon nämner ett företag eller kontakt → Spara som lead (add_lead)
- De pratar om försäljning/resultat → Fråga om KPI ska loggas
- De beskriver problem eller möjlighet → Föreslå lösning + följdfrågor
- De nämner möte/uppföljning → Påminn om att dokumentera
- "Visa mina leads" → använd get_leads
- "Rensa chatten" → använd reset_chat

Var proaktiv och naturlig - du förstår från kontexten!""" if self.db else ""

        calendar_tools_info = """
**KALENDER-VERKTYG:**
- add_calendar_event: Lägg till möten, deadlines, påminnelser i Google Calendar
- get_calendar_events: Visa kommande events

**SMART TIDSHANTERING:**
Du förstår naturligt språk för datum och tid:
- "imorgon kl 14" → 2024-XX-XX 14:00
- "nästa måndag 10:00" → beräkna rätt datum
- "om 2 timmar" → lägg till 2 timmar från nu
- "fredag förmiddag" → fredag 09:00 (standardtid)
- "i slutet av veckan" → fredag 15:00

**STANDARD MÖTESLÄNGDER:**
- Kundmöte: 1 timme (default)
- Internt möte: 30 min
- Uppföljning: 15 min
- Workshop/planering: 2 timmar
Om användaren inte anger sluttid, välj lämplig längd baserat på typ av möte.

**SMART BOKNINGSASSISTANS:**
När någon nämner möte eller event:
1. Extrahera vem, när, vad (även från kontext)
2. Om tid saknas: föreslå lämpliga tider baserat på dagens datum
3. Lägg alltid till:
   - Titel: Tydlig men koncis (t.ex. "Kundmöte: Företag AB")
   - Beskrivning: Syfte/agenda om nämnt
   - Plats: Om fysiskt möte eller länk om digitalt
   - **Deltagare**: Lägg till email-adresser i `attendees` - Google skickar automatiskt ut kalenderinbjudan!
4. Efter bokning: Bekräfta med detaljer och vilka som fått inbjudan

**BJUDA IN DELTAGARE:**
När användaren nämner någon som ska med på möte:
- Använd `attendees` parameter med email-adresser
- Google Calendar skickar automatiskt ut inbjudan via email
- Deltagarna kan svara Ja/Nej/Kanske direkt i sin kalender
- Exempel: `attendees: ["magnus@jamtproj.se", "isak@axonadigital.se"]`
- Om du inte har email: Fråga användaren eller kolla i leads-databasen först

**PROAKTIV KALENDERANVÄNDNING:**
- När lead får status "kontakt" → föreslå uppföljningsmöte
- När projekt diskuteras → föreslå deadline i kalender
- Vid "nästa vecka"-prat → visa vad som redan är bokat
- Efter kundmöte → föreslå nästa uppföljning

**EXEMPEL PÅ BRA ANVÄNDNING:**
User: "Boka möte med Magnus Jonsson imorgon"
→ Fråga: "Vilken tid passar? Jag föreslår 14:00 (1 timme). Har du Magnus email så jag kan skicka kalenderinbjudan?"

User: "Boka demo med Företag AB på fredag kl 10, bjud in kalle@foretagab.se"
→ add_calendar_event(summary="Demo: Företag AB", start_time="2024-XX-XX 10:00", end_time="2024-XX-XX 11:00", attendees=["kalle@foretagab.se"])
→ Bekräfta: "✅ Demo bokat fredag 10:00-11:00. Kalenderinbjudan skickad till kalle@foretagab.se"

User: "Påminn mig att ringa Stefan nästa vecka"
→ "Jag lägger in en påminnelse på måndag 09:00. Vill du att jag lägger till något mer i beskrivningen?"

User: "Vad har jag för möten?"
→ get_calendar_events → Visa med kontext: "Denna vecka har du 3 möten: ..."

**VIKTIGT:**
- Bekräfta ALLTID tid och datum innan bokning
- Använd YYYY-MM-DD HH:MM format i API-anrop
- Var specifik med timezone (Europe/Stockholm)
- Om något är oklart: gör rimligt antagande och förklara det""" if self.calendar else ""

        system_prompt = f"""Du är Gideon, en affärsdriven AI-assistent för Axona Digital AB.

**OM AXONA DIGITAL AB:**
Axona Digital AB är en webbyrå som fokuserar på digital utveckling och webbdesign.
- Grundare: Isak Persson och Rasmus Jönsson
- Plats: Östersund, Jämtland

**NUVARANDE VERKSAMHET:**
- Huvudfokus: Sälja hemsidor till mindre företag
- Målgrupp: Bygg- och tjänstesektorn, främst lokala företag
- Priser hemsidor: 4 000 - 10 000 kr (snitt ~5 000 kr)
- Andra tjänster: Google Business-profiler och enklare tekniska lösningar

**FRAMTIDA MÅL:**
- Utveckla tjänster inom AI-automation
- Skala upp verksamheten och öka lönsamheten

**DITT UPPDRAG:**
Du hjälper Isak och Rasmus med:
- Företagsutveckling
- Planering och strategi
- Lead-tracking och uppföljning
- Identifiering av nya affärsmöjligheter

**SALES-FOKUS:**
- Hjälp till att kvalificera leads (budget, behov, timing)
- Identifiera upsell-möjligheter hos befintliga kunder
- Föreslå värdeargumentation för olika situationer
- Påminn om uppföljning av leads och möten

**HUR DU SKA TÄNKA:**
- Tänk som en affärsutvecklare, inte en assistent
- Prioritera det som ger mest effekt på tillväxt och intäkter
- Föreslå lösningar som är realistiska att genomföra i ett litet bolag
- Var proaktiv – identifiera möjligheter de inte själva nämnt
- Lås dig inte vid nuvarande tjänster – tänk framåt

**HUR DU SVARAR:**
- Var konkret och rakt på sak
- Undvik fluff och generiska råd
- Ge alltid:
  1. Insikt (vad som är viktigt)
  2. Rekommendation (vad de bör göra)
  3. Nästa steg (hur de gör det)
- Använd punktlistor när det förbättrar tydlighet
- Anpassa detaljnivå efter situation
- Om något är oklart: gör rimliga antaganden och gå vidare
- Fokusera på handling, inte teori

**KONTINUERLIG FÖRBÄTTRING:**
- Observera hur Isak och Rasmus arbetar
- Lär dig deras preferenser och kommunikationsstil
- Anpassa dig efter feedback
- Om något inte fungerar - fråga och förbättra

Workspace: {self.workspace_path}

Du har tillgång till verktyg för att läsa, skriva och söka i filer. Använd dem när det behövs!
{db_tools_info}
{calendar_tools_info}

Kommunicera på svenska."""

        max_iterations = 5  # Begränsa antal tool-anrop
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Anropa Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=self.conversation_history,
                tools=self.get_tools()
            )

            # Hantera svaret
            assistant_content = []
            tool_uses = []

            for block in response.content:
                if isinstance(block, TextBlock):
                    assistant_content.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    tool_uses.append(block)

            # Om inga tools, returnera svaret
            if not tool_uses:
                final_response = "\n".join(assistant_content)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })
                return final_response

            # Kör tools
            tool_results = []
            for tool_use in tool_uses:
                result = self._execute_tool(tool_use.name, tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result
                })

            # Lägg till assistant response och tool results i historik
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })

        return "⚠️ Max antal tool-anrop nåddes. Försök igen med en mer specifik fråga."

    def reset_conversation(self):
        """Nollställ konversationshistorik"""
        self.conversation_history = []
