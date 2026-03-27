# Fly.io Dockerfile för Gideon Discord Bot

FROM python:3.11-slim

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

# Skapa workspace directory (om behövs)
RUN mkdir -p /workspace

# Kör boten
CMD ["python", "bot.py"]
