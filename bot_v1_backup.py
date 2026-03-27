import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from claude_handler import ClaudeHandler

# Ladda environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
WORKSPACE_PATH = os.getenv("WORKSPACE_PATH", os.path.expanduser("~"))
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

# Skapa bot med intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Claude handler (en per användare för att hålla konversationshistorik separat)
claude_sessions = {}

def get_claude_session(user_id: str) -> ClaudeHandler:
    """Hämta eller skapa Claude-session för användare"""
    if user_id not in claude_sessions:
        claude_sessions[user_id] = ClaudeHandler(
            api_key=ANTHROPIC_API_KEY,
            workspace_path=WORKSPACE_PATH,
            model=CLAUDE_MODEL
        )
    return claude_sessions[user_id]

@bot.event
async def on_ready():
    """När botten är online"""
    print(f"✅ Bot online som {bot.user}")
    print(f"📁 Workspace: {WORKSPACE_PATH}")
    print(f"🤖 Claude Model: {CLAUDE_MODEL}")
    print("\nTillgängliga kommandon:")
    print("  !ask <prompt>      - Fråga Claude något")
    print("  !read <filepath>   - Läs en fil")
    print("  !list [directory]  - Lista filer")
    print("  !reset             - Nollställ konversation")
    print("  !info              - Visa hjälp")

@bot.command(name="ask")
async def ask_claude(ctx, *, prompt: str):
    """Fråga Claude något - den kan använda verktyg för filaccess"""
    async with ctx.typing():
        try:
            claude = get_claude_session(str(ctx.author.id))
            response = await claude.ask(prompt, user_name=ctx.author.display_name)

            # Splitta långa svar (Discord limit: 2000 tecken)
            if len(response) <= 2000:
                await ctx.reply(response)
            else:
                # Skicka i chunks
                chunks = [response[i:i+1990] for i in range(0, len(response), 1990)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await ctx.reply(f"📄 Del {i+1}/{len(chunks)}:\n{chunk}")
                    else:
                        await ctx.send(f"📄 Del {i+1}/{len(chunks)}:\n{chunk}")

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

            # Splitta långa svar
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

@bot.command(name="info")
async def info_command(ctx):
    """Visa hjälptext"""
    help_text = """
🤖 **Axona Digital Claude Bot**

**Kommandon:**
`!ask <prompt>` - Fråga Claude något (kan automatiskt läsa/skriva filer om behövs)
`!read <filepath>` - Läs en fil
`!list [directory]` - Lista filer i en mapp
`!reset` - Nollställ konversationshistorik
`!info` - Visa denna hjälp

**Exempel:**
`!ask Vad finns i Foretagsgrund-mappen?`
`!ask Skapa en ny fil test.txt med texten "Hello World"`
`!ask Läs STATUS.md i chatbot-projektet`
`!read Foretagsgrund/STATUS.md`
`!list chatbot`

**Tips:**
- Claude kommer ihåg konversationen tills du kör `!reset`
- Varje användare har sin egen konversationshistorik
- Claude har tillgång till: {workspace}
    """.format(workspace=WORKSPACE_PATH)

    await ctx.reply(help_text)

@bot.event
async def on_message(message):
    """Hantera meddelanden"""
    # Ignorera bot's egna meddelanden
    if message.author == bot.user:
        return

    # Tillåt @ mentions som alternativ till !ask
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        # Ta bort @mention från meddelandet
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        if content:
            # Simulera !ask command
            ctx = await bot.get_context(message)
            await ask_claude(ctx, prompt=content)
            return

    # Processa vanliga kommandon
    await bot.process_commands(message)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN saknas i .env!")
        exit(1)
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY saknas i .env!")
        exit(1)

    print("🚀 Startar bot...")
    bot.run(DISCORD_TOKEN)
