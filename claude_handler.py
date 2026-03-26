import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import anthropic
from anthropic.types import TextBlock, ToolUseBlock

class ClaudeHandler:
    """Hanterar Claude API-anrop med file access tools"""

    def __init__(self, api_key: str, workspace_path: str, model: str = "claude-sonnet-4-5-20250929"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.workspace_path = Path(workspace_path).resolve()
        self.model = model
        self.conversation_history = []

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
        else:
            return f"❌ Okänt tool: {tool_name}"

    def get_tools(self) -> List[Dict]:
        """Definiera tillgängliga tools för Claude"""
        return [
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

    async def ask(self, user_message: str, user_name: str = "User") -> str:
        """Skicka ett meddelande till Claude och få svar (med tool support)"""
        # Lägg till användarmeddelande i historik
        self.conversation_history.append({
            "role": "user",
            "content": f"[{user_name}]: {user_message}"
        })

        # System prompt
        system_prompt = f"""Du är en AI-assistent för Axona Digital AB.
Du hjälper Isak Persson och Rasmus Jönsson med företagsutveckling, planering och kodning.

Workspace: {self.workspace_path}

Viktiga projekt:
- ~/Foretagsgrund/ - Affärsplanering
- ~/chatbot/ - Live chatbot-lösning
- ~/personlig-assistent/ - Personligt projekt

Du har tillgång till verktyg för att läsa, skriva och söka i filer. Använd dem när det behövs!

Kommunicera på svenska. Håll svar korta och koncisa."""

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
