# Gideon - Discord Claude Bot

AI-assistent för Axona Digital AB via Discord. **Agent-lagret** i den
tre-skiktade arkitekturen (Second Brain läser, **Gideon agerar**, Mission
Control visar). Se `axona-brain/SYSTEM.md` för helheten.

## Funktioner

- 🤖 Claude AI-integration med tool-användning
- 💬 Discord-kommandon (`!ask`, `!read`, `!list`, etc.)
- 📁 Läs/skriv filer i workspace + Supabase + Google Calendar + CRM
- 🧠 **Brain-integration** — läser `axona-brain` för kund-kontext, sparar
  Discord-konversationer som nya `sources/` (triggar GitHub Actions ingest)
- 🎤 OpenAI TTS för röstmeddelanden
- 👥 Per-användare conversation memory (kort- + långtidsminne)

## Kommandon

- `!ask <fråga>` - Fråga Claude något
- `!read <filepath>` - Läs en fil
- `!list [directory]` - Lista filer
- `!reset` - Nollställ konversation
- `!avsluta-dag` - Commit och push till GitHub
- `!info` - Visa hjälp

## Brain-frågor (när BRAIN_PATH är konfigurerad)

Ställ fritt i Discord — Gideon väljer rätt brain-tool automatiskt:

- *"Vad vet vi om EMP Bygg?"* → `find_client('EMP Bygg')` → läser entities/clients/emp-bygg-ab.md
- *"Visa mig alla möten med Norrlandsbetong"* → `search_brain('Norrlandsbetong')`
- *"Spara detta: vi pratade med Lejda Entreprenad om offerten, de behöver svar i veckan"* → `save_to_brain(...)` → ny `sources/YYYY-MM-DD-discord-lejda-offert.md`

## Environment Variables

Kärna:
```
DISCORD_TOKEN=din_discord_bot_token
ANTHROPIC_API_KEY=din_claude_api_nyckel
WORKSPACE_PATH=/workspace
CLAUDE_MODEL=claude-haiku-4-5-20251001
```

Brain-integration (axona-brain vault):
```
BRAIN_PATH=/workspace/axona-brain
BRAIN_GIT_KEY_B64=<base64-kodad SSH private key med write-access till repo>
```

För att skapa BRAIN_GIT_KEY_B64:
1. Generera ett deploy key: `ssh-keygen -t ed25519 -f gideon_brain_key -N ""`
2. Lägg till `gideon_brain_key.pub` på GitHub: repo → Settings → Deploy keys → Add deploy key (markera "Allow write access")
3. Encoda private key: `base64 -w0 gideon_brain_key`
4. Sätt resultatet som BRAIN_GIT_KEY_B64 i Fly secrets:
   `fly secrets set BRAIN_GIT_KEY_B64="<base64-strängen>"`

Övriga (valfria) integrationer:
```
SUPABASE_URL=...
SUPABASE_KEY=...
GOOGLE_CALENDAR_REFRESH_TOKEN=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
OPENAI_API_KEY=...
CRM_EDGE_FUNCTION_URL=...
CRM_BOT_SECRET=...
```

## Deployment (Render)

1. Skapa ett nytt **Background Worker** på Render
2. Koppla till GitHub-repo: `Axonadigital/Gideon`
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python bot.py`
5. Lägg till environment variables

## Lokal körning

```bash
# Installera dependencies
pip install -r requirements.txt

# Skapa .env från exempel
cp .env.example .env
# Fyll i dina nycklar i .env

# Kör boten
python bot.py
```
