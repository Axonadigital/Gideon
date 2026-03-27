# Supabase Setup - Gideon

## Steg 1: Skapa Supabase-projekt

1. Gå till https://supabase.com
2. Logga in / Skapa konto (gratis)
3. Klicka **"New Project"**
4. Fyll i:
   - **Name:** `gideon-axona`
   - **Database Password:** (välj ett starkt lösenord, spara det!)
   - **Region:** `Europe West (Ireland)` (närmast Sverige)
   - **Pricing Plan:** `Free` ✅
5. Klicka **"Create new project"** (tar ~2 min)

## Steg 2: Kör SQL-schema

1. I Supabase-dashboard, gå till **SQL Editor** (vänstra menyn)
2. Klicka **"New Query"**
3. Kopiera innehållet från `schema.sql`
4. Klistra in i SQL-editorn
5. Klicka **"Run"** (nere till höger)
6. ✅ Du bör se: "Success. No rows returned"

## Steg 3: Hämta credentials

1. Gå till **Settings** → **API** (vänstra menyn)
2. Kopiera dessa värden:

```
Project URL:        https://xxxxx.supabase.co
API Key (anon):     eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

3. Lägg till i `.env`:

```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Steg 4: Verifiera tabeller

1. Gå till **Table Editor** (vänstra menyn)
2. Du bör se 4 tabeller:
   - ✅ `leads`
   - ✅ `reflektioner`
   - ✅ `kpis`
   - ✅ `minnen`

## Steg 5: Testa (valfritt)

Kör denna SQL för att testa:

```sql
-- Se exempeldata
SELECT * FROM leads;

-- Lägg till en testreflektion
INSERT INTO reflektioner (användare, text, typ)
VALUES ('isak', 'Testreflektion från Supabase!', 'daglig');

-- Kolla att det funkar
SELECT * FROM reflektioner;
```

## Nästa steg

När Supabase är uppsatt, gå tillbaka till Discord-boten och kör:

```bash
cd ~/discord-claude-bot
pip install supabase
```

Sedan är ni redo att köra Gideon med persistent databas! 🚀
