# Fly.io Dockerfile för Gideon Discord Bot

FROM python:3.11-slim

# Installera git (krävs för brain_handler att pulla axona-brain)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Sätt working directory
WORKDIR /app

# Kopiera requirements först (för bättre caching)
COPY requirements.txt .

# Installera dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Kopiera bot-kod
COPY bot_v2.py bot.py
COPY claude_handler.py .
COPY supabase_handler.py .
COPY calendar_handler.py .
COPY tts_handler.py .
COPY conversation_memory.py .
COPY http_api.py .
COPY crm_handler.py .
COPY meeting_reminder.py .
COPY brain_handler.py .

# Skapa workspace och audio directories
RUN mkdir -p /workspace /tmp/gideon_audio

# Brain-vaulten klonas vid uppstart via entrypoint, inte vid build
# (kräver runtime secrets för deploy key)
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Kör boten
CMD ["/app/entrypoint.sh"]
