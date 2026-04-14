# Conversation Memory Database

Detta är minnesystemet för Gideon Discord-botten.

## Arkitektur

**Två-lagers minne:**
1. **Korttidsminne** (`conversation_messages`) - Senaste 30 meddelandena i RAM + Supabase
2. **Långtidsminne** (`conversation_summaries`) - AI-genererade sammanfattningar

## Installation

### Metod 1: Supabase Dashboard (Rekommenderat)

1. Gå till Supabase Dashboard: https://supabase.com/dashboard
2. Välj ditt projekt
3. Gå till **SQL Editor** (vänster meny)
4. Kopiera innehållet från `conversation_schema.sql`
5. Klistra in och klicka **Run**

### Metod 2: Migrations-script

```bash
cd database
python3 run_migration.py
```

Detta visar SQL-koden som du behöver köra manuellt (Supabase Python-klienten stödjer inte raw SQL).

## Funktioner

✅ **Auto-reset efter inaktivitet**: Session sammanfattas efter 30 min
✅ **Smart filtrering**: Skippar test-meddelanden och meningslösa chattar
✅ **Context warning**: Varnar vid 25/30 meddelanden
✅ **Strukturerade sammanfattningar**: Sparar topics, beslut, leads, möten, next steps
✅ **Långtidsminne**: Behåller kontext över sessioner utan att fylla RAM

## Schema

### conversation_messages
- Korttidsminne - detaljerade meddelanden
- Auto-cleanup: Radera efter 7 dagar (sammanfattningar finns kvar)

### conversation_summaries
- Långtidsminne - AI-genererade sammanfattningar
- Behåller struktur: topics, decisions, leads, meetings, next_steps
- Auto-cleanup: Radera efter 90 dagar

## Användning

Botten hanterar minnet automatiskt. Användaren kan:
- `!reset` - Manuellt sammanfatta och starta ny session
- System varnar automatiskt vid 25/30 meddelanden
- Auto-reset efter 30 min inaktivitet

## Cleanup-policies

Kör regelbundet (manuellt eller med cron):

```sql
-- Radera messages äldre än 7 dagar
DELETE FROM conversation_messages WHERE created_at < NOW() - INTERVAL '7 days';

-- Radera summaries äldre än 90 dagar
DELETE FROM conversation_summaries WHERE created_at < NOW() - INTERVAL '90 days';
```
