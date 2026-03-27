# Deployment Guide - Gideon på Fly.io

## Förberedelser

### 1. Installera Fly CLI

```bash
# Linux/WSL
curl -L https://fly.io/install.sh | sh

# Lägg till i PATH (lägg i ~/.bashrc eller ~/.zshrc)
export FLYCTL_INSTALL="/home/perssonisak1/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"

# Reload shell
source ~/.bashrc
```

### 2. Logga in på Fly.io

```bash
flyctl auth login
# Öppnar webbläsare för inloggning
```

### 3. Skapa Fly.io app (första gången)

```bash
cd ~/discord-claude-bot

# Skapa app
flyctl apps create gideon-axona

# Eller låt Fly generera namn automatiskt
flyctl launch --no-deploy
```

## Sätt upp Supabase FÖRST

Innan du deployar boten, sätt upp Supabase:

1. Gå till https://supabase.com och skapa projekt
2. Kör SQL-schemat från `database/schema.sql`
3. Hämta credentials (URL + API Key)

## Konfigurera Secrets

Lägg till alla environment variables som secrets i Fly.io:

```bash
# Discord Bot Token
flyctl secrets set DISCORD_TOKEN="din_discord_token_här"

# Anthropic API
flyctl secrets set ANTHROPIC_API_KEY="din_claude_api_key"

# Supabase
flyctl secrets set SUPABASE_URL="https://xxxxx.supabase.co"
flyctl secrets set SUPABASE_KEY="din_supabase_anon_key"

# OpenAI (för embeddings)
flyctl secrets set OPENAI_API_KEY="din_openai_key"

# Verifiera secrets
flyctl secrets list
```

## Deploya till Fly.io

```bash
# Deploy boten
flyctl deploy

# Följ deployment
flyctl logs
```

## Verifiera att boten körs

```bash
# Kolla status
flyctl status

# Se logs
flyctl logs

# Öppna Fly.io dashboard
flyctl open
```

## Botten borde nu vara live på Discord! 🎉

Testa med:
- `!info` - Visa hjälp
- `!ask Hej Gideon!` - Testa Claude
- `!lead list` - Testa Supabase

## Hantera boten

```bash
# Starta om
flyctl apps restart gideon-axona

# Stoppa (pausar, inte ta bort)
flyctl scale count 0

# Starta igen
flyctl scale count 1

# Se resurser
flyctl status

# Se live logs
flyctl logs -f

# SSH in i container (troubleshooting)
flyctl ssh console
```

## Uppdatera boten

När du gör ändringar i koden:

```bash
# 1. Commit ändringar
git add .
git commit -m "Uppdatering av Gideon"
git push

# 2. Deploya ny version
flyctl deploy

# 3. Verifiera
flyctl logs
```

## Kostnader

**Gratis tier inkluderar:**
- ✅ 3 shared-cpu-1x VMs (256MB RAM)
- ✅ 3GB persistent storage
- ✅ 160GB data transfer/månad

**Din bot använder:**
- 1 VM (256MB)
- ~100MB storage
- ~5-10GB data/månad

**= 100% GRATIS!** 🎉

## Troubleshooting

### Botten startar inte

```bash
# Kolla logs
flyctl logs

# Verifiera secrets
flyctl secrets list

# Starta om
flyctl apps restart gideon-axona
```

### Botten disconnectar från Discord

Discord-bots behöver stabil connection. Fly.io har automatisk restart om botten kraschar.

```bash
# Kolla om den körts nyligen
flyctl status

# Se crash logs
flyctl logs --since 1h
```

### Supabase connection error

Verifiera att SUPABASE_URL och SUPABASE_KEY är korrekt satta:

```bash
flyctl secrets list
```

## Backup & Säkerhet

- All data finns i Supabase (automatisk backup)
- Secrets är krypterade i Fly.io
- Kod är i GitHub
- = Inget går förlorat! ✅

## Nästa steg

- [ ] Sätt upp Supabase
- [ ] Deploya till Fly.io
- [ ] Testa alla kommandon
- [ ] Börja använda Gideon dagligen!
- [ ] Eventuellt: Sätt upp scheduled jobs för automatiska påminnelser
