import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import anthropic
from anthropic.types import TextBlock, ToolUseBlock

class ClaudeHandler:
    """Hanterar Claude API-anrop med file access tools"""

    def __init__(self, api_key: str, workspace_path: str, model: str = "claude-sonnet-4-5-20250929", db=None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.workspace_path = Path(workspace_path).resolve()
        self.model = model
        self.conversation_history = []
        self.db = db  # Supabase handler för att spara leads, KPIs, etc.

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
                företag=tool_input["företag"],
                kontaktperson=tool_input.get("kontaktperson"),
                status=tool_input.get("status", "ny"),
                tjänst=tool_input.get("tjänst"),
                anteckningar=tool_input.get("anteckningar"),
                skapad_av=tool_input.get("skapad_av", "Gideon")
            )
        elif tool_name == "get_leads":
            return self._get_leads(status=tool_input.get("status"))
        elif tool_name == "add_kpi":
            return self._add_kpi(
                namn=tool_input["namn"],
                värde=tool_input["värde"],
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
                användare=tool_input.get("användare", "Gideon"),
                typ=tool_input.get("typ", "daglig")
            )
        elif tool_name == "reset_chat":
            return self._reset_chat()
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
                            "företag": {
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
                            "tjänst": {
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
                        "required": ["företag"]
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
                    "description": "Logga en KPI (nyckeltal) som hemsidor_sålda, möten_bokade, intäkter, etc.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "namn": {
                                "type": "string",
                                "description": "KPI-namn (t.ex. 'hemsidor_sålda', 'möten_bokade')"
                            },
                            "värde": {
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
                        "required": ["namn", "värde"]
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
                            "användare": {
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
Du har också verktyg för att hantera företagets data:
- add_lead: Lägg till leads (potentiella kunder) automatiskt när användaren nämner företag eller kontakter
- get_leads: Hämta och visa leads
- add_kpi: Logga KPIs (nyckeltal som 'hemsidor_sålda', 'möten_bokade', etc.)
- get_kpis: Visa statistik och framsteg
- add_reflektion: Spara reflektioner och anteckningar
- reset_chat: Rensa chatten när användaren säger "rensa chatten", "börja om", "ny konversation"

VIKTIGT: Använd dessa verktyg AUTOMATISKT när det passar. Om användaren säger:
- "Jag pratade med Kalle på Företag AB" → använd add_lead
- "Vi sålde 2 hemsidor idag" → använd add_kpi med namn='hemsidor_sålda', värde=2
- "Visa mina leads" → använd get_leads
- "Rensa chatten" → använd reset_chat

Var proaktiv och naturlig - ingen behöver säga "lägg till lead", du förstår från kontexten!""" if self.db else ""

        system_prompt = f"""Du är Gideon, en AI-assistent för Axona Digital AB.
Du hjälper Isak Persson och Rasmus Jönsson med företagsutveckling, planering och lead-tracking.

Workspace: {self.workspace_path}

Viktiga projekt:
- ~/Foretagsgrund/ - Affärsplanering
- ~/chatbot/ - Live chatbot-lösning
- ~/personlig-assistent/ - Personligt projekt

Du har tillgång till verktyg för att läsa, skriva och söka i filer. Använd dem när det behövs!
{db_tools_info}

Kommunicera på svenska. Håll svar korta och koncisa. Var hjälpsam och proaktiv!"""

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
