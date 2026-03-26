# Gideon - Discord Claude Bot

AI-assistent för Axona Digital AB via Discord.

## Funktioner

- 🤖 Claude AI-integration med filaccess
- 💬 Discord-kommandon (`!ask`, `!read`, `!list`, etc.)
- 📁 Läs/skriv filer i workspace
- 🔒 Säker bash-kommandohantering
- 👥 Separata konversationer per användare

## Kommandon

- `!ask <fråga>` - Fråga Claude något
- `!read <filepath>` - Läs en fil
- `!list [directory]` - Lista filer
- `!reset` - Nollställ konversation
- `!avsluta-dag` - Commit och push till GitHub
- `!info` - Visa hjälp

## Environment Variables

```
DISCORD_TOKEN=din_discord_bot_token
ANTHROPIC_API_KEY=din_claude_api_nyckel
WORKSPACE_PATH=/path/to/workspace
CLAUDE_MODEL=claude-sonnet-4-5-20250929
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
