# Gideon hosting-migration: Fly.io → Hetzner-VPS

**Status**: PLAN. Ingen migration har utförts. Detta dokument beskriver rekommenderat tillvägagångssätt för att flytta Gideon från Fly.io till samma Hetzner-VPS som redan kör axona-brain crons.

## Rekommendation

**Option A — flytta till Hetzner.**

### Skäl
- `axona-brain`-vaulten är redan utcheckad på `/home/axona/axona-brain` med deploy-key i `axona`-userens `~/.ssh`. Filesystem-direkt-läsning från Gideon = ingen pull-loop, inga race-conditions mellan två kloner.
- En SSH-key som äger både brain-läsning (för Gideon) och brain-skrivning (för cron-runner). Inget duplicerat.
- VPS:en kör redan andra always-on-tjänster (cron-runner, DocuSeal). En Python-process till är försumbar overhead.
- `systemd` ger tydlig process-supervision (`Restart=on-failure`, `journalctl`). Inget Docker-overhead.
- Fly.io-kostnad försvinner (i runda slängar 5 USD/mån för en alltid-på Python-process).

## Pre-requisites

- Hetzner-VPS (`204.168.215.207`, kör redan brain).
- Linux-user `axona` med:
  - `~/.ssh/id_ed25519` deploy-key som har read+write till `Axona-Digital/axona-brain` och read till `Axona-Digital/Gideon`.
  - Tillgång att klona Gideon-repot.
- Python 3.11+ på VPS:en.
- Caddy redan installerad och kör för andra subdomains.

## Steg

### 1. Förbered .env på Hetzner

På din lokala maskin:
```bash
flyctl secrets list -a gideon                 # se vilka som finns
flyctl ssh console -a gideon -C 'env'         # exportera nuvarande värden
```
SCP:a en .env-fil till `/home/axona/gideon/.env` med:
```
DISCORD_TOKEN=…
ANTHROPIC_API_KEY=…
SUPABASE_URL=…
SUPABASE_KEY=…
OPENAI_API_KEY=…
GIDEON_API_KEY=…
GOOGLE_CALENDAR_REFRESH_TOKEN=…
GOOGLE_CLIENT_ID=…
GOOGLE_CLIENT_SECRET=…
CRM_EDGE_FUNCTION_URL=…
CRM_BOT_SECRET=…
CRM_ALERTS_CHANNEL_ID=…
CRM_REPORTS_CHANNEL_ID=…
MEETING_ALERTS_CHANNEL_ID=…
WORKSPACE_PATH=/home/axona/workspace
BRAIN_PATH=/home/axona/axona-brain
CLAUDE_MODEL=claude-sonnet-4-6
```

### 2. Klona och installera

```bash
ssh axona@204.168.215.207
git clone git@github.com:Axona-Digital/Gideon.git /home/axona/gideon
cd /home/axona/gideon
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p /home/axona/workspace
```

### 3. systemd-unit

`/etc/systemd/system/gideon.service` (kräver sudo):
```ini
[Unit]
Description=Gideon Discord bot
After=network.target

[Service]
Type=simple
User=axona
Group=axona
WorkingDirectory=/home/axona/gideon
EnvironmentFile=/home/axona/gideon/.env
ExecStart=/home/axona/gideon/.venv/bin/python bot_v2.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Aktivera:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gideon
journalctl -u gideon -f
```

### 4. HTTP API (Siri Shortcuts) via Caddy reverse-proxy

`http_api.py` lyssnar på port 8080 lokalt. DocuSeal äger redan port 80/443 så vi exponerar Gideon på en subdomain.

Lägg till i `/etc/caddy/Caddyfile`:
```
gideon.axonadigital.se {
    reverse_proxy localhost:8080
}
```

DNS: skapa CNAME `gideon` → vps-host. Caddy hanterar TLS automatiskt via Let's Encrypt.

`sudo systemctl reload caddy`.

Verifiera: `curl https://gideon.axonadigital.se/health` (om http_api.py har health-endpoint, annars en känd endpoint).

Uppdatera Siri Shortcut för att peka på den nya URL:en.

**Alternativ utan DNS-ändring**: Cloudflare Tunnel — `cloudflared tunnel` med `gideon.axonadigital.se` mappad till `localhost:8080`. Mer setup men kräver inga DNS-ändringar.

### 5. Verifiera Hetzner-deployen

- Discord: skicka `!info` i bot-kanalen → ska få svar.
- Discord: skicka `!ask vem är Roddar VVS?` → Claude ska referera brain-data (kunden finns i `entities/clients/roddar-vvs.md`).
- Discord: skicka `!flush` på en kort konversation → verifiera att fil dyker upp i `axona-brain/sources/discord-YYYY-MM-DD-...md` och att commit har prefix `ingest: gideon - `.
- HTTP API: `curl https://gideon.axonadigital.se/<known-endpoint>` med korrekt `GIDEON_API_KEY`.

### 6. Stäng av Fly.io

ENDAST efter att Hetzner kört grön i 24h:
```bash
flyctl apps destroy gideon --yes
```

Behåll Fly-appen som rollback-target tills dess.

## Rollback

Om Hetzner-deployen havererar: starta om Fly-appen (den rörs inte i denna migration). Inget Hetzner-tillstånd behöver rensas — `systemctl stop gideon` räcker.

## Backup-plan: option B (behåll på Fly.io)

Mer komplext, dubbel-klon-risk:
1. Lägg till deploy-key för axona-brain i Fly secrets (`fly secrets set BRAIN_DEPLOY_KEY=...`).
2. I `Dockerfile`: `git clone git@github.com:Axona-Digital/axona-brain.git /workspace/axona-brain` vid container-start.
3. I `bot_v2.py`: starta en bakgrunds-task som kör `git -C /workspace/axona-brain pull --rebase` var 5:e minut för att få in nya ingest-commits från GH Actions.
4. Risk: race-condition om Gideon-container pushar samtidigt som GH Actions ingest pushar. Mitigeras av `pull --rebase` + retry-logik i `brain_handler.write_session_summary` men ger tysta race-buggar i extremfall.
5. Två kloner kan divergera om en push misslyckas tyst.

Acceptabelt om Hetzner inte är ett alternativ, men inte rekommenderat.
