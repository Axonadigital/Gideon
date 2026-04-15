import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from claude_handler import ClaudeHandler
from supabase_handler import SupabaseHandler
from calendar_handler import CalendarHandler
from tts_handler import TTSHandler
from crm_handler import CRMHandler, CRMError
from http_api import GideonHTTPAPI
from datetime import date, datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from meeting_reminder import MeetingReminder

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

# CRM-integration
CRM_EDGE_FUNCTION_URL = os.getenv("CRM_EDGE_FUNCTION_URL")
CRM_BOT_SECRET = os.getenv("CRM_BOT_SECRET")
CRM_ALERTS_CHANNEL_ID = os.getenv("CRM_ALERTS_CHANNEL_ID")   # Dagliga påminnelser
CRM_REPORTS_CHANNEL_ID = os.getenv("CRM_REPORTS_CHANNEL_ID") # Veckoapporter + AI-analys

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

# CRM handler
crm = None
if CRM_EDGE_FUNCTION_URL and CRM_BOT_SECRET:
    crm = CRMHandler(url=CRM_EDGE_FUNCTION_URL, secret=CRM_BOT_SECRET)

# Meeting Reminder handler
meeting_reminder = None
MEETING_ALERTS_CHANNEL_ID = os.getenv("MEETING_ALERTS_CHANNEL_ID")  # Discord-kanal för påminnelser
if calendar and ANTHROPIC_API_KEY:
    meeting_reminder = MeetingReminder(calendar, ANTHROPIC_API_KEY)

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
    print(f"🏢 CRM: {'✅ Connected' if crm else '❌ Not configured (CRM_EDGE_FUNCTION_URL/CRM_BOT_SECRET saknas)'}")

    # Starta CRM-scheduler om CRM är konfigurerat
    if crm:
        _start_crm_scheduler()

    # Starta mötes-påminnelse-scheduler om konfigurerat
    if meeting_reminder and MEETING_ALERTS_CHANNEL_ID:
        _start_meeting_reminder_scheduler()
        print(f"📅 Meeting Reminders: ✅ Connected (kanal: {MEETING_ALERTS_CHANNEL_ID})")
    else:
        missing = []
        if not meeting_reminder:
            missing.append("Calendar/Claude API")
        if not MEETING_ALERTS_CHANNEL_ID:
            missing.append("MEETING_ALERTS_CHANNEL_ID")
        print(f"📅 Meeting Reminders: ❌ Not configured ({', '.join(missing)} saknas)")

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
    print("  !crm pipeline       - CRM pipeline-status")
    print("  !crm rapport        - Veckans CRM-rapport")
    print("  !crm analys         - AI-säljanalys")

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

            # CRM-kontext: detektera intent och hämta relevant data
            crm_context = ""
            if crm:
                try:
                    actions = _detect_crm_actions(message.content)
                    if actions:
                        crm_context = await asyncio.wait_for(_fetch_crm_context(actions), timeout=20.0)
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

            prompt = message.content
            if crm_context:
                prompt = f"{message.content}\n\n{crm_context}"

            claude = get_claude_session(str(message.author.id))

            # Använd timeout för att förhindra att Discord heartbeat blockeras
            try:
                response = await asyncio.wait_for(
                    claude.ask(prompt, user_name=message.author.display_name),
                    timeout=120.0  # Max 2 minuter
                )
            except asyncio.TimeoutError:
                await message.reply("⏱️ Timeout - svaret tog för lång tid. Försök med en enklare fråga!")
                return

            await send_long(message.channel, response, reply_to=message)

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

            await send_long(ctx, response, reply_to=ctx)

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

            await send_long(ctx, f"📦 **Avslutar dagen för {ctx.author.display_name}**\n\n{response}", reply_to=ctx)

        except Exception as e:
            await ctx.reply(f"❌ Fel vid avslut: {str(e)}")

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

**CRM (eller skriv fritt – Gideon förstår):**
`!crm pipeline` - Pipeline per stage
`!crm rapport` - Veckans aktivitet
`!crm analys` - AI-säljanalys
`!crm deals [stage]` - Lista deals
`!crm tasks` - Försenade tasks
`!crm followups` - Försenade followups
`!crm performance` - Säljprestanda per person

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

# ==================== DISCORD HJÄLPFUNKTIONER ====================

async def send_long(ctx_or_channel, text: str, reply_to=None):
    """Skicka ett meddelande och dela upp det om det överstiger 2000 tecken."""
    CHUNK = 1950  # Marginal för "📄 Del X/Y:\n"-prefix
    if len(text) <= 2000:
        if reply_to:
            await reply_to.reply(text)
        else:
            await ctx_or_channel.send(text)
        return

    chunks = [text[i:i+CHUNK] for i in range(0, len(text), CHUNK)]
    for i, chunk in enumerate(chunks):
        content = f"📄 Del {i+1}/{len(chunks)}:\n{chunk}"
        if i == 0 and reply_to:
            await reply_to.reply(content)
        else:
            await ctx_or_channel.send(content)


# ==================== CRM NATURLIG SPRÅKFÖRSTÅELSE ====================

# Breda nyckelordsmatcher – träffar alla vanliga säljrelaterade frågor på svenska
# get_ai_sales_analysis exkluderas – för tung för auto-fetch (10-15s), använd !crm analys
_CRM_KEYWORDS = {
    "get_pipeline_summary": [
        "pipeline", "deal", "affär", "försälj", "lead", "kund", "kontakta",
        "prioriter", "prio", "status", "läge", "hur går", "hur ser", "vad har vi",
        "potential", "prospect", "möjlighet", "analys", "fokus", "fokusera",
    ],
    "list_followups": [
        "ringa", "ring", "followup", "follow up", "uppföljning", "callback",
        "återring", "kontakt idag", "vem ska vi", "ta kontakt",
    ],
    "list_tasks_due": [
        "task", "uppgift", "att göra", "todo", "försenad", "akut",
    ],
    "get_weekly_report": [
        "veckorapport", "hur gick veckan", "sammanfatta veckan", "veckans rapport",
    ],
}

def _detect_crm_actions(message: str) -> list[str]:
    """Matcha meddelandet mot CRM-nyckelord och returnera relevanta actions."""
    text = message.lower()
    matched = []
    for action, keywords in _CRM_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            matched.append(action)

    # Om pipeline matchas, ta alltid med followups (vanligtvis intressant ihop)
    if "get_pipeline_summary" in matched and "list_followups" not in matched:
        matched.append("list_followups")

    return matched


async def _fetch_crm_context(actions: list[str]) -> str:
    """Hämta CRM-data parallellt och formatera som kontext-sträng."""
    if not crm or not actions:
        return ""

    results = await asyncio.gather(
        *[crm.call_action(action) for action in actions],
        return_exceptions=True
    )

    parts = []
    formatters = {
        "get_pipeline_summary": crm.format_pipeline,
        "get_weekly_report": crm.format_weekly_report,
        "list_followups": crm.format_followups,
        "list_tasks_due": crm.format_tasks,
        "get_sales_performance": crm.format_performance,
        "get_ai_sales_analysis": crm.format_ai_analysis,
    }

    for action, result in zip(actions, results):
        if isinstance(result, Exception):
            continue
        formatter = formatters.get(action)
        if formatter:
            try:
                parts.append(formatter(result))
            except Exception:
                pass

    if not parts:
        return ""
    return "\n\n**Aktuell CRM-data:**\n" + "\n\n".join(parts)


# ==================== CRM-SCHEDULER ====================

def _start_crm_scheduler():
    """Starta schemalagda CRM-jobb."""
    scheduler = AsyncIOScheduler(timezone="Europe/Stockholm")

    # Varje dag 08:00 – försenade tasks + followups
    scheduler.add_job(
        _post_daily_reminders,
        CronTrigger(hour=8, minute=0),
        id="crm_daily_reminders",
        replace_existing=True,
    )

    # Måndag 09:00 – veckorapport
    scheduler.add_job(
        _post_weekly_report,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="crm_weekly_report",
        replace_existing=True,
    )

    # Fredag 15:00 – AI-säljanalys
    scheduler.add_job(
        _post_ai_analysis,
        CronTrigger(day_of_week="fri", hour=15, minute=0),
        id="crm_ai_analysis",
        replace_existing=True,
    )

    scheduler.start()
    print("⏰ CRM-scheduler startad (dagliga påminnelser + veckoapporter)")


async def _post_daily_reminders():
    """Posta försenade tasks och followups i alerts-kanalen."""
    if not crm or not CRM_ALERTS_CHANNEL_ID:
        return
    channel = bot.get_channel(int(CRM_ALERTS_CHANNEL_ID))
    if not channel:
        print(f"⚠️ CRM: alerts-kanal {CRM_ALERTS_CHANNEL_ID} hittades inte")
        return
    try:
        tasks, followups = await asyncio.gather(
            crm.call_action("list_tasks_due"),
            crm.call_action("list_followups"),
        )
        if tasks:
            await send_long(channel, crm.format_tasks(tasks))
        if followups:
            await send_long(channel, crm.format_followups(followups))
    except CRMError as e:
        print(f"⚠️ CRM daily reminders fel: {e}")


async def _post_weekly_report():
    """Posta veckorapport i reports-kanalen."""
    if not crm or not CRM_REPORTS_CHANNEL_ID:
        return
    channel = bot.get_channel(int(CRM_REPORTS_CHANNEL_ID))
    if not channel:
        print(f"⚠️ CRM: reports-kanal {CRM_REPORTS_CHANNEL_ID} hittades inte")
        return
    try:
        data = await crm.call_action("get_weekly_report")
        await send_long(channel, crm.format_weekly_report(data))
    except CRMError as e:
        print(f"⚠️ CRM weekly report fel: {e}")


async def _post_ai_analysis():
    """Posta AI-säljanalys i reports-kanalen."""
    if not crm or not CRM_REPORTS_CHANNEL_ID:
        return
    channel = bot.get_channel(int(CRM_REPORTS_CHANNEL_ID))
    if not channel:
        print(f"⚠️ CRM: reports-kanal {CRM_REPORTS_CHANNEL_ID} hittades inte")
        return
    try:
        data = await crm.call_action("get_ai_sales_analysis")
        await send_long(channel, "**🤖 Fredagsanalys från Gideon**\n" + crm.format_ai_analysis(data))
    except CRMError as e:
        print(f"⚠️ CRM AI analysis fel: {e}")


# ==================== MÖTES-PÅMINNELSER ====================

def _start_meeting_reminder_scheduler():
    """Starta schemalagd koll av mötes-påminnelser."""
    scheduler = AsyncIOScheduler(timezone="Europe/Stockholm")

    # Kolla möten varje timme
    scheduler.add_job(
        _check_meeting_reminders,
        IntervalTrigger(hours=1),
        id="meeting_reminders_check",
        replace_existing=True,
    )

    scheduler.start()
    print("⏰ Mötes-påminnelse-scheduler startad (kollar varje timme)")


async def _check_meeting_reminders():
    """Kolla om det finns möten som behöver påminnelser (24h email / 4h Discord)."""
    if not meeting_reminder or not MEETING_ALERTS_CHANNEL_ID:
        return

    channel = bot.get_channel(int(MEETING_ALERTS_CHANNEL_ID))
    if not channel:
        print(f"⚠️ Meeting: alerts-kanal {MEETING_ALERTS_CHANNEL_ID} hittades inte")
        return

    try:
        # Hämta kommande möten (48h framåt)
        print("🔍 DEBUG: Hämtar möten från kalendern...")
        meetings = meeting_reminder.get_upcoming_meetings(hours_ahead=48)
        print(f"🔍 DEBUG: Hittade {len(meetings)} relevanta möten")

        if not meetings:
            print("ℹ️ Inga relevanta möten hittades")
            return

        now = datetime.now()

        for meeting in meetings:
            time_until_meeting = meeting['start'] - now

            # 24h email-påminnelse (TEST-MODE: visar bara förslag, skickar inte)
            if timedelta(hours=23) < time_until_meeting < timedelta(hours=25):
                # Generera email-förslag (skickar INTE)
                if meeting['attendees']:
                    # Generera email-text
                    email_body = meeting_reminder._generate_email_reminder(meeting)

                    for attendee_email in meeting['attendees']:
                        # Skicka FÖRSLAG i Discord (skickar INTE email)
                        await channel.send(
                            f"📧 **Email-påminnelse REDO** (24h innan möte)\n\n"
                            f"**Till:** {attendee_email}\n"
                            f"**Möte:** {meeting['summary']}\n"
                            f"**Tid:** {meeting['start'].strftime('%Y-%m-%d %H:%M')}\n"
                            f"**Företag:** {meeting['company']}\n\n"
                            f"**📝 Förslag på email-text:**\n"
                            f"```\n{email_body}\n```\n\n"
                            f"**Videolänk:** {meeting['link']}\n\n"
                            f"⚠️ **TEST-MODE:** Email skickas INTE automatiskt.\n"
                            f"Kopiera texten och skicka manuellt från info@axonadigital.se"
                        )

            # 4h SMS-påminnelse (Discord med förslag)
            elif timedelta(hours=3, minutes=30) < time_until_meeting < timedelta(hours=4, minutes=30):
                # Skicka Discord-påminnelse med SMS-förslag
                reminder_message = meeting_reminder.generate_discord_reminder(meeting)
                await channel.send(reminder_message)

    except Exception as e:
        print(f"❌ Meeting reminder fel: {e}")


# ==================== CRM-KOMMANDON ====================

@bot.group(name="crm", invoke_without_command=True)
async def crm_group(ctx):
    """CRM-kommandon – se !crm help"""
    await ctx.reply(
        "**CRM-kommandon:**\n"
        "`!crm pipeline`     – Pipeline-sammanfattning\n"
        "`!crm rapport`      – Veckans rapport\n"
        "`!crm deals`        – Lista aktiva deals\n"
        "`!crm tasks`        – Försenade tasks\n"
        "`!crm followups`    – Försenade followups\n"
        "`!crm performance`  – Säljprestanda per person\n"
        "`!crm analys`       – AI-säljanalys (tar ~10s)"
    )


@bot.command(name="test-påminnelse")
async def test_meeting_reminder(ctx):
    """TEST: Kör mötes-påminnelse-check manuellt (istället för att vänta på scheduler)"""
    if not meeting_reminder or not MEETING_ALERTS_CHANNEL_ID:
        await ctx.reply("❌ Meeting Reminders inte konfigurerat")
        return

    async with ctx.typing():
        await ctx.reply("🔍 Kollar kalendern efter möten som behöver påminnelser...")
        try:
            await _check_meeting_reminders()
            await ctx.reply("✅ Koll klar! Om det finns möten som matchar ser du dem i <#1493857026319712316>")
        except Exception as e:
            await ctx.reply(f"❌ Fel: {e}")


@crm_group.command(name="pipeline")
async def crm_pipeline(ctx):
    """Visa pipeline-sammanfattning"""
    if not crm:
        await ctx.reply("❌ CRM inte konfigurerat (CRM_EDGE_FUNCTION_URL saknas)")
        return
    async with ctx.typing():
        try:
            data = await crm.call_action("get_pipeline_summary")
            await ctx.reply(crm.format_pipeline(data))
        except CRMError as e:
            await ctx.reply(f"❌ CRM-fel: {e}")


@crm_group.command(name="rapport")
async def crm_rapport(ctx):
    """Visa veckans CRM-rapport"""
    if not crm:
        await ctx.reply("❌ CRM inte konfigurerat")
        return
    async with ctx.typing():
        try:
            data = await crm.call_action("get_weekly_report")
            await ctx.reply(crm.format_weekly_report(data))
        except CRMError as e:
            await ctx.reply(f"❌ CRM-fel: {e}")


@crm_group.command(name="deals")
async def crm_deals(ctx, stage: str = None):
    """Lista aktiva deals: !crm deals [stage]"""
    if not crm:
        await ctx.reply("❌ CRM inte konfigurerat")
        return
    async with ctx.typing():
        try:
            kwargs = {"stage": stage} if stage else {}
            data = await crm.call_action("list_deals", **kwargs)
            if not data:
                await ctx.reply("Inga deals hittades.")
                return
            lines = [f"💼 **Deals{f' ({stage})' if stage else ''}**"]
            for d in data[:20]:
                amount = f"{d.get('amount') or 0:,.0f} kr".replace(",", " ")
                company = (d.get("companies") or {}).get("name", "")
                lines.append(f"  • **{d['name']}** {f'({company}) ' if company else ''}– `{d['stage']}` · {amount}")
            if len(data) > 20:
                lines.append(f"  _…och {len(data) - 20} till_")
            await ctx.reply("\n".join(lines))
        except CRMError as e:
            await ctx.reply(f"❌ CRM-fel: {e}")


@crm_group.command(name="tasks")
async def crm_tasks(ctx):
    """Visa försenade tasks"""
    if not crm:
        await ctx.reply("❌ CRM inte konfigurerat")
        return
    async with ctx.typing():
        try:
            data = await crm.call_action("list_tasks_due")
            await ctx.reply(crm.format_tasks(data))
        except CRMError as e:
            await ctx.reply(f"❌ CRM-fel: {e}")


@crm_group.command(name="followups")
async def crm_followups(ctx):
    """Visa försenade followups"""
    if not crm:
        await ctx.reply("❌ CRM inte konfigurerat")
        return
    async with ctx.typing():
        try:
            data = await crm.call_action("list_followups")
            await ctx.reply(crm.format_followups(data))
        except CRMError as e:
            await ctx.reply(f"❌ CRM-fel: {e}")


@crm_group.command(name="performance")
async def crm_performance(ctx):
    """Visa säljprestanda per person (30 dagar)"""
    if not crm:
        await ctx.reply("❌ CRM inte konfigurerat")
        return
    async with ctx.typing():
        try:
            data = await crm.call_action("get_sales_performance")
            await ctx.reply(crm.format_performance(data))
        except CRMError as e:
            await ctx.reply(f"❌ CRM-fel: {e}")


@crm_group.command(name="analys")
async def crm_analys(ctx):
    """AI-analys av säljprocessen (tar ~10 sekunder)"""
    if not crm:
        await ctx.reply("❌ CRM inte konfigurerat")
        return
    async with ctx.typing():
        try:
            data = await crm.call_action("get_ai_sales_analysis")
            text = crm.format_ai_analysis(data)
            await send_long(ctx, text, reply_to=ctx)
        except CRMError as e:
            await ctx.reply(f"❌ CRM-fel: {e}")


# ==================== MAIN ====================

async def start_services():
    """Starta både Discord bot och HTTP API parallellt"""
    tasks = []

    # Lägg till HTTP API task om API key finns
    if GIDEON_API_KEY:
        async def run_http_api():
            http_api = GideonHTTPAPI(get_claude_session, GIDEON_API_KEY)
            await http_api.start(port=8080)
            print("🌐 HTTP API aktiverad för Siri Shortcuts")
            # Håll HTTP servern igång
            await asyncio.Future()  # Kör för alltid

        tasks.append(run_http_api())
    else:
        print("⚠️ GIDEON_API_KEY saknas - HTTP API inaktiverad")

    # Lägg till Discord bot task
    async def run_discord_bot():
        async with bot:
            await bot.start(DISCORD_TOKEN)

    tasks.append(run_discord_bot())

    # Kör alla tasks parallellt
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN saknas i .env!")
        exit(1)
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY saknas i .env!")
        exit(1)

    print("🚀 Startar Gideon...")
    asyncio.run(start_services())
