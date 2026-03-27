# Gideon 2.0 - AI-Assistent för Axona Digital AB

Discord-bot med Claude AI, persistent databas och avancerade features för företagsledning.

## 🚀 Features

### Grundfunktioner
- 🤖 **Claude AI-integration** - Avancerad konversation med filaccess
- 💬 **Discord-kommandon** - Enkla commands för allt
- 📁 **Filhantering** - Läs/skriv filer i workspace
- 🔒 **Säker bash-exec** - Kör git och andra kommandon

### Nya features (v2.0)
- 💾 **Persistent minne** - Supabase + pgvector för långtidsminne
- 📊 **Lead-tracking** - Håll koll på potentiella kunder
- 💭 **Reflektionslogg** - Dagliga/veckovisa reflektioner
- 📈 **KPI-tracking** - Följ viktiga nyckeltal
- 🤖 **AI-assistans** - Veckorapporter och prioriteringshjälp
- 👥 **Multi-user** - Separata sessions per användare

## 📋 Kommandon

### Grundläggande
```
!ask <fråga>           - Fråga Claude något
!read <filepath>       - Läs en fil
!list [directory]      - Lista filer
!reset                 - Nollställ konversation
!info                  - Visa hjälp
```

### Lead-hantering
```
!lead add "Företag AB" kontakt:Kalle status:ny tjänst:chatbot
!lead list [status]    - Visa alla leads (eller filtrera på status)
```

### Reflektioner
```
!reflektion Idag gick bra med försäljning, lärde mig XYZ
```

### KPIs
```
!kpi add hemsidor_sålda 2 st
!kpi show [dagar]      - Visa KPIs (default: 7 dagar)
```

### AI-Assistans
```
!veckorapport          - AI sammanfattar veckan
!prioritera            - AI hjälper prioritera dagens todos
!avsluta-dag           - Git commit + push
```

## 🛠️ Setup

### 1. Klona eller uppdatera repo

```bash
cd ~/discord-claude-bot
git pull  # Om redan klonat
```

### 2. Installera dependencies

```bash
pip install -r requirements.txt
```

### 3. Sätt upp Supabase

Följ steg i `database/SETUP.md`:
1. Skapa Supabase-projekt (gratis)
2. Kör SQL-schema
3. Hämta credentials

### 4. Konfigurera environment

Kopiera `.env.example` till `.env` och fyll i:

```bash
cp .env.example .env
nano .env
```

Fyll i alla nycklar:
- `DISCORD_TOKEN` - Från Discord Developer Portal
- `ANTHROPIC_API_KEY` - Från console.anthropic.com
- `SUPABASE_URL` - Från Supabase project settings
- `SUPABASE_KEY` - Anon/public key från Supabase
- `OPENAI_API_KEY` - Från platform.openai.com (för embeddings)

### 5. Byt till ny bot-fil

```bash
# Backup gammal version
cp bot.py bot_v1_backup.py

# Använd nya versionen
cp bot_v2.py bot.py
```

### 6. Testa lokalt

```bash
python bot.py
```

Botten borde nu starta och vara online på Discord!

## 🌐 Deployment (Fly.io - GRATIS)

Följ `DEPLOYMENT.md` för fullständig guide.

**TL;DR:**

```bash
# Installera Fly CLI
curl -L https://fly.io/install.sh | sh

# Logga in
flyctl auth login

# Skapa app
flyctl launch --no-deploy

# Sätt secrets
flyctl secrets set DISCORD_TOKEN="..."
flyctl secrets set ANTHROPIC_API_KEY="..."
flyctl secrets set SUPABASE_URL="..."
flyctl secrets set SUPABASE_KEY="..."
flyctl secrets set OPENAI_API_KEY="..."

# Deploya
flyctl deploy

# Kolla logs
flyctl logs
```

## 📂 Projektstruktur

```
discord-claude-bot/
├── bot.py                  # Huvudfil (ny version)
├── claude_handler.py       # Claude API-integration
├── supabase_handler.py     # Supabase databas-integration
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (ej committat)
├── .env.example            # Template för .env
├── Dockerfile              # För Fly.io deployment
├── fly.toml                # Fly.io config
├── database/
│   ├── schema.sql          # Supabase SQL-schema
│   └── SETUP.md            # Supabase setup-guide
├── DEPLOYMENT.md           # Deployment-guide
└── README.md               # Detta dokument
```

## 🎯 Användningsexempel

### Lead-tracking
```
!lead add "Restaurang Italia" kontakt:Luca status:ny tjänst:chatbot
!lead list intresserad
```

### Daglig rutin
```
!prioritera
# Jobba...
!reflektion Idag sålde vi 2 hemsidor, lärde mig att följa upp snabbare
!kpi add hemsidor_sålda 2 st
!avsluta-dag
```

### Veckouppföljning
```
!veckorapport
!kpi show 7
```

## 🔧 Teknisk stack

- **Discord.py** - Discord bot framework
- **Claude AI** (Anthropic) - AI-konversation
- **Supabase** - PostgreSQL databas + pgvector
- **OpenAI Embeddings** - För långtidsminne
- **Fly.io** - Hosting (gratis tier)

## 📊 Databas-schema

### Tabeller
- `leads` - Potentiella kunder
- `reflektioner` - Dagliga/veckovisa reflektioner
- `kpis` - Nyckeltal (försäljning, intäkter, etc)
- `minnen` - Långtidsminne med pgvector

## 🚀 Nästa steg

- [ ] Sätt upp Supabase
- [ ] Konfigurera .env
- [ ] Testa lokalt
- [ ] Deploya till Fly.io
- [ ] Börja använda dagligen!

## 📝 Licens

Privat projekt för Axona Digital AB.

## 🤝 Support

Frågor? Fråga Gideon! 😉
```
!ask Hur använder jag dig bäst?
```
