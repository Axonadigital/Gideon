import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from claude_handler import ClaudeHandler
from supabase_handler import SupabaseHandler
from calendar_handler import CalendarHandler
from tts_handler import TTSHandler
from http_api import GideonHTTPAPI
from datetime import date

# Ladda environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GIDEON_API_KEY = os.getenv("GIDEON_API_KEY")  # För Siri Shortcuts
WORKSPACE_PATH = os.getenv("WORKSPACE_PATH", os.path.expanduser("~"))
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_CALENDAR_REFRESH_TOKEN = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Skapa bot med intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Claude handler (en per användare för att hålla konversationshistorik separat)
claude_sessions = {}

# Supabase handler (delad för alla)
db = None
if SUPABASE_URL and SUPABASE_KEY:
    db = SupabaseHandler(SUPABASE_URL, SUPABASE_KEY)

# Calendar handler (delad för alla)
calendar = None
if GOOGLE_CALENDAR_REFRESH_TOKEN and GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    calendar = CalendarHandler(
        refresh_token=GOOGLE_CALENDAR_REFRESH_TOKEN,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )

# TTS handler (delad för alla)
tts = None
if OPENAI_API_KEY:
    tts = TTSHandler(api_key=OPENAI_API_KEY)

def get_claude_session(user_id: str) -> ClaudeHandler:
    """Hämta eller skapa Claude-session för användare"""
    if user_id not in claude_sessions:
        claude_sessions[user_id] = ClaudeHandler(
            api_key=ANTHROPIC_API_KEY,
            workspace_path=WORKSPACE_PATH,
            model=CLAUDE_MODEL,
            db=db,  # Skicka in Supabase så Claude kan använda den
            calendar=calendar,  # Skicka in Calendar så Claude kan använda den
            user_id=user_id  # Skicka in user_id för minnesystemet
        )
    return claude_sessions[user_id]

@bot.event
async def on_ready():
    """När botten är online"""
    print(f"✅ Bot online som {bot.user}")
    print(f"📁 Workspace: {WORKSPACE_PATH}")
    print(f"🤖 Claude Model: {CLAUDE_MODEL}")
    print(f"💾 Supabase: {'✅ Connected' if db else '❌ Not configured'}")
    print(f"📅 Google Calendar: {'✅ Connected' if calendar else '❌ Not configured'}")
    print(f"🎤 TTS (Voice): {'✅ Connected' if tts else '❌ Not configured'}")
    print("\nTillgängliga kommandon:")
    print("  !ask <prompt>       - Fråga Claude något")
    print("  !read <filepath>    - Läs en fil")
    print("  !list [directory]   - Lista filer")
    print("  !reset              - Nollställ konversation")
    print("  !lead add           - Lägg till lead")
    print("  !lead list          - Visa alla leads")
    print("  !reflektion <text>  - Logga daglig reflektion")
    print("  !kpi add            - Logga KPI")
    print("  !kpi show           - Visa KPIs")
    print("  !veckorapport       - AI-sammanfattning av veckan")
    print("  !prioritera         - AI-hjälp med prioritering")
    print("  !avsluta-dag        - Git commit + push")
    print("  !info               - Visa hjälp")

@bot.event
async def on_message(message):
    """Lyssna på alla meddelanden och svara automatiskt (utom på kommandon)"""
    # Ignorera meddelanden från bottar
    if message.author.bot:
        return

    # Om meddelandet börjar med ! så är det ett kommando - låt command handler ta hand om det
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    # Svara automatiskt på alla andra meddelanden
    async with message.channel.typing():
        try:
            # Kolla om användaren vill ha röst-svar
            want_voice = any(phrase in message.content.lower() for phrase in ["svara med röst", "röst-svar", "röstmeddelande"])

            claude = get_claude_session(str(message.author.id))

            # Använd timeout för att förhindra att Discord heartbeat blockeras
            try:
                response = await asyncio.wait_for(
                    claude.ask(message.content, user_name=message.author.display_name),
                    timeout=120.0  # Max 2 minuter
                )
            except asyncio.TimeoutError:
                await message.reply("⏱️ Timeout - svaret tog för lång tid. Försök med en enklare fråga!")
                return

            # Splitta långa svar (Discord limit: 2000 tecken)
            if len(response) <= 2000:
                await message.reply(response)
            else:
                chunks = [response[i:i+1990] for i in range(0, len(response), 1990)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await message.reply(f"📄 Del {i+1}/{len(chunks)}:\n{chunk}")
                    else:
                        await message.channel.send(f"📄 Del {i+1}/{len(chunks)}:\n{chunk}")

            # Generera röst-svar om begärt
            if want_voice and tts:
                try:
                    # Ta bort markdown och formatering för TTS
                    clean_text = response.replace("**", "").replace("*", "").replace("#", "").replace("`", "")

                    # Generera ljudfil
                    audio_path = tts.generate_speech(clean_text, voice="nova")

                    # Skicka ljudfil
                    await message.channel.send("🎤 Röst-svar:", file=discord.File(audio_path))

                    # Cleanup
                    tts.cleanup_old_files()
                except Exception as e:
                    await message.channel.send(f"⚠️ Kunde inte generera röst: {e}")

        except Exception as e:
            await message.reply(f"❌ Fel: {e}")

    # Viktigt: Detta krävs för att kommandon ska fungera
    await bot.process_commands(message)

# ==================== BEFINTLIGA KOMMANDON ====================

@bot.command(name="ask")
async def ask_claude(ctx, *, prompt: str):
    """Fråga Claude något - den kan använda verktyg för filaccess"""
    async with ctx.typing():
        try:
            # Kolla om användaren vill ha röst-svar
            want_voice = any(phrase in prompt.lower() for phrase in ["svara med röst", "röst-svar", "röstmeddelande"])

            claude = get_claude_session(str(ctx.author.id))

            # Använd timeout för att förhindra att Discord heartbeat blockeras
            try:
                response = await asyncio.wait_for(
                    claude.ask(prompt, user_name=ctx.author.display_name),
                    timeout=120.0  # Max 2 minuter
                )
            except asyncio.TimeoutError:
                await ctx.reply("⏱️ Timeout - svaret tog för lång tid. Försök med en enklare fråga!")
                return

            # Splitta långa svar (Discord limit: 2000 tecken)
            if len(response) <= 2000:
                await ctx.reply(response)
            else:
                chunks = [response[i:i+1990] for i in range(0, len(response), 1990)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await ctx.reply(f"📄 Del {i+1}/{len(chunks)}:\n{chunk}")
                    else:
                        await ctx.send(f"📄 Del {i+1}/{len(chunks)}:\n{chunk}")

            # Generera röst-svar om begärt och TTS är konfigurerat
            if want_voice and tts:
                try:
                    # Rensa bort markdown och specialtecken för bättre TTS
                    clean_text = response.replace("**", "").replace("*", "").replace("#", "")

                    # Generera audio
                    audio_path = tts.generate_speech(clean_text, voice="nova")

                    # Skicka audio-fil
                    await ctx.send("🎤 Röst-svar:", file=discord.File(audio_path))

                    # Rensa gamla filer
                    tts.cleanup_old_files()

                except Exception as e:
                    await ctx.send(f"⚠️ Kunde inte generera röst-svar: {str(e)}")

        except Exception as e:
            await ctx.reply(f"❌ Fel: {str(e)}")

@bot.command(name="read")
async def read_file(ctx, *, filepath: str):
    """Snabbkommando för att läsa en fil"""
    await ask_claude(ctx, prompt=f"Läs filen: {filepath}")

@bot.command(name="list")
async def list_files(ctx, directory: str = "."):
    """Snabbkommando för att lista filer"""
    await ask_claude(ctx, prompt=f"Lista filer i: {directory}")

@bot.command(name="reset")
async def reset_conversation(ctx):
    """Nollställ konversationshistorik"""
    claude = get_claude_session(str(ctx.author.id))
    claude.reset_conversation()
    await ctx.reply("🔄 Konversation nollställd!")

@bot.command(name="avsluta-dag")
async def avsluta_dag(ctx):
    """Avsluta arbetsdagen - commit och push ändringar till GitHub"""
    async with ctx.typing():
        try:
            prompt = """Jag ska avsluta arbetsdagen. Gör följande:

1. Kör 'git status' för att se vad som ändrats
2. Om det finns ändringar:
   - Kör 'git diff --stat' för översikt
   - Generera ett kort, tydligt commit-meddelande som sammanfattar ändringarna
   - Kör: git add .
   - Kör: git commit -m "ditt_meddelande"
   - Kör: git push
3. Om inga ändringar: Säg att allt redan är synkat

Var tydlig med vad som sparades och pushades!"""

            claude = get_claude_session(str(ctx.author.id))
            response = await claude.ask(prompt, user_name=ctx.author.display_name)

            if len(response) <= 2000:
                await ctx.reply(f"📦 **Avslutar dagen för {ctx.author.display_name}**\n\n{response}")
            else:
                chunks = [response[i:i+1990] for i in range(0, len(response), 1990)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await ctx.reply(f"📦 **Avslutar dagen** (Del {i+1}/{len(chunks)})\n\n{chunk}")
                    else:
                        await ctx.send(f"📄 Del {i+1}/{len(chunks)}:\n{chunk}")

        except Exception as e:
            await ctx.reply(f"❌ Fel vid avslut: {str(e)}")

# ==================== NYA KOMMANDON: LEADS ====================

@bot.group(name="lead", invoke_without_command=True)
async def lead(ctx):
    """Lead-hantering - använd !lead add eller !lead list"""
    await ctx.reply("Använd `!lead add` eller `!lead list` eller `!lead update`")

@lead.command(name="add")
async def lead_add(ctx, företag: str, *, info: str = ""):
    """Lägg till ny lead: !lead add "Företag AB" kontakt:Kalle status:ny tjänst:chatbot"""
    if not db:
        await ctx.reply("❌ Supabase inte konfigurerat!")
        return

    try:
        # Parsa info-strängen
        kontakt = None
        status = "ny"
        tjänst = None
        anteckningar = None

        if info:
            parts = info.split()
            for part in parts:
                if ":" in part:
                    key, value = part.split(":", 1)
                    if key == "kontakt":
                        kontakt = value
                    elif key == "status":
                        status = value
                    elif key == "tjänst":
                        tjänst = value
                else:
                    anteckningar = (anteckningar or "") + " " + part

        # Lägg till i databas
        lead_data = db.add_lead(
            företag=företag,
            kontaktperson=kontakt,
            status=status,
            tjänst=tjänst,
            anteckningar=anteckningar.strip() if anteckningar else None,
            skapad_av=ctx.author.display_name
        )

        await ctx.reply(f"✅ Lead tillagd: **{företag}**\nStatus: {status}\nID: {lead_data['id']}")

    except Exception as e:
        await ctx.reply(f"❌ Kunde inte lägga till lead: {str(e)}")

@lead.command(name="list")
async def lead_list(ctx, status: str = None):
    """Visa leads: !lead list [status]"""
    if not db:
        await ctx.reply("❌ Supabase inte konfigurerat!")
        return

    try:
        if status:
            leads = db.get_leads(status=status)
            title = f"📋 Leads med status '{status}'"
        else:
            leads = db.get_aktiva_leads()
            title = "📋 Aktiva leads"

        if not leads:
            await ctx.reply(f"{title}: Inga hittades.")
            return

        formatted = db.format_lead_list(leads)
        await ctx.reply(f"{title}:\n\n{formatted}")

    except Exception as e:
        await ctx.reply(f"❌ Fel: {str(e)}")

# ==================== NYA KOMMANDON: REFLEKTIONER ====================

@bot.command(name="reflektion")
async def reflektion(ctx, *, text: str):
    """Logga daglig reflektion: !reflektion Idag gick bra med försäljning"""
    if not db:
        await ctx.reply("❌ Supabase inte konfigurerat!")
        return

    try:
        result = db.add_reflektion(
            användare=ctx.author.display_name,
            text=text,
            typ="daglig"
        )

        await ctx.reply(f"✅ Reflektion sparad för {date.today().isoformat()}!\n\n💭 _{text[:100]}..._" if len(text) > 100 else f"✅ Reflektion sparad!\n\n💭 _{text}_")

    except Exception as e:
        await ctx.reply(f"❌ Kunde inte spara reflektion: {str(e)}")

# ==================== NYA KOMMANDON: KPIs ====================

@bot.group(name="kpi", invoke_without_command=True)
async def kpi(ctx):
    """KPI-hantering - använd !kpi add eller !kpi show"""
    await ctx.reply("Använd `!kpi add` eller `!kpi show`")

@kpi.command(name="add")
async def kpi_add(ctx, namn: str, värde: float, enhet: str = "", *, anteckning: str = ""):
    """Logga KPI: !kpi add hemsidor_sålda 2 st Sålde till företag X och Y"""
    if not db:
        await ctx.reply("❌ Supabase inte konfigurerat!")
        return

    try:
        result = db.add_kpi(
            namn=namn,
            värde=värde,
            enhet=enhet if enhet else None,
            anteckning=anteckning if anteckning else None,
            skapad_av=ctx.author.display_name
        )

        await ctx.reply(f"✅ KPI loggad: **{namn}** = {värde} {enhet}")

    except Exception as e:
        await ctx.reply(f"❌ Kunde inte logga KPI: {str(e)}")

@kpi.command(name="show")
async def kpi_show(ctx, dagar: int = 7):
    """Visa KPIs: !kpi show [antal dagar]"""
    if not db:
        await ctx.reply("❌ Supabase inte konfigurerat!")
        return

    try:
        kpis = db.get_denna_vecka_kpis() if dagar == 7 else db.get_kpis(limit=50)

        if not kpis:
            await ctx.reply("📊 Inga KPIs hittades.")
            return

        summary = db.format_kpi_summary(kpis)
        await ctx.reply(f"📊 **KPIs senaste {dagar} dagarna:**\n\n{summary}")

    except Exception as e:
        await ctx.reply(f"❌ Fel: {str(e)}")

# ==================== NYA KOMMANDON: AI-ASSISTANS ====================

@bot.command(name="veckorapport")
async def veckorapport(ctx):
    """AI sammanfattar veckan baserat på reflektioner och KPIs"""
    if not db:
        await ctx.reply("❌ Supabase inte konfigurerat!")
        return

    async with ctx.typing():
        try:
            # Hämta data från veckan
            reflektioner = db.get_veckoreflektion(användare=ctx.author.display_name)
            kpis = db.get_denna_vecka_kpis()

            # Skapa prompt till Claude
            prompt = f"""Skapa en veckorapport baserat på denna data:

**Reflektioner denna vecka:**
{chr(10).join([f"- {r['datum']}: {r['text']}" for r in reflektioner])}

**KPIs denna vecka:**
{db.format_kpi_summary(kpis)}

Analysera och sammanfatta:
1. Vad gick bra?
2. Vad kan förbättras?
3. Viktiga lärdomar
4. Rekommendationer för nästa vecka

Håll det kort och actionable!"""

            claude = get_claude_session(str(ctx.author.id))
            response = await claude.ask(prompt, user_name=ctx.author.display_name)

            await ctx.reply(f"📊 **Veckorapport för {ctx.author.display_name}**\n\n{response}")

        except Exception as e:
            await ctx.reply(f"❌ Fel: {str(e)}")

@bot.command(name="prioritera")
async def prioritera(ctx):
    """AI hjälper dig prioritera dagens uppgifter"""
    async with ctx.typing():
        try:
            prompt = """Baserat på mina mål och nuvarande situation, hjälp mig prioritera dagens uppgifter.

Läs:
- ~/personlig-assistent/todos/idag.md
- ~/personlig-assistent/mål/veckomål.md

Ge mig:
1. Top 3 prioriteringar för idag
2. Vad ska jag INTE göra (distraktion)
3. Rekommenderad ordning

Kom ihåg deadline: April 2026!"""

            claude = get_claude_session(str(ctx.author.id))
            response = await claude.ask(prompt, user_name=ctx.author.display_name)

            await ctx.reply(f"🎯 **Prioriteringar för {ctx.author.display_name}**\n\n{response}")

        except Exception as e:
            await ctx.reply(f"❌ Fel: {str(e)}")

# ==================== INFO & HJÄLP ====================

@bot.command(name="info")
async def info_command(ctx):
    """Visa hjälptext"""
    help_text = """
🤖 **Gideon - Axona Digital AI-Assistent**

**Grundläggande:**
`!ask <prompt>` - Fråga Claude något
`!read <filepath>` - Läs en fil
`!list [directory]` - Lista filer
`!reset` - Nollställ konversation

**Lead-tracking:**
`!lead add "Företag" kontakt:Namn status:ny tjänst:chatbot` - Ny lead
`!lead list [status]` - Visa leads

**Reflektioner:**
`!reflektion <text>` - Logga daglig reflektion

**KPIs:**
`!kpi add <namn> <värde> [enhet]` - Logga KPI
`!kpi show [dagar]` - Visa KPIs

**AI-assistans:**
`!veckorapport` - AI-sammanfattning av veckan
`!prioritera` - AI-hjälp med dagens prioriteringar

**Övrigt:**
`!avsluta-dag` - Git commit + push
`!info` - Visa denna hjälp

**Workspace:** {workspace}
    """.format(workspace=WORKSPACE_PATH)

    await ctx.reply(help_text)

# ==================== MAIN ====================

async def start_services():
    """Starta både Discord bot och HTTP API"""
    # Starta HTTP API om API key finns
    http_runner = None
    if GIDEON_API_KEY:
        http_api = GideonHTTPAPI(get_claude_session, GIDEON_API_KEY)
        http_runner = await http_api.start(port=8080)
        print("🌐 HTTP API aktiverad för Siri Shortcuts")
    else:
        print("⚠️ GIDEON_API_KEY saknas - HTTP API inaktiverad")

    # Starta Discord bot
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN saknas i .env!")
        exit(1)
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY saknas i .env!")
        exit(1)

    print("🚀 Startar Gideon...")
    asyncio.run(start_services())
