import asyncio
from datetime import datetime
import os
import random
import sqlite3
import time
import traceback
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

# Configuration
def required_secret(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment secret: {name}")
    return value


DISCORD_TOKEN = required_secret("DISCORD_TOKEN")
OPENROUTER_API_KEY = required_secret("OPENROUTER_API_KEY")
DB_NAME = "storytime_bot.db"

# Reliable low cost paid models on OpenRouter
MODELS_TO_TRY = [
    "meta-llama/llama-3.3-70b-instruct",
    "openai/gpt-4o-mini",
    "anthropic/claude-3-haiku"
]

# Track active stories for cancellation
active_stories = {}

# Database Setup
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sleep_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date_logged TEXT,
            sleep_time TEXT,
            wake_time TEXT,
            sleep_hours REAL,
            nap_minutes INTEGER,
            awakenings INTEGER,
            mood INTEGER,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Discord Client Setup
class StorytimeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced globally.")
        if not self.health_check.is_running():
            self.health_check.start()

    async def on_ready(self):
        print(f"Logged in as Storytime Bot: {self.user} (ID: {self.user.id})")

    async def on_disconnect(self):
        print("Discord connection lost; discord.py will attempt to reconnect.")

    async def on_resumed(self):
        print("Discord connection resumed.")

    async def on_error(self, event_method, *args, **kwargs):
        print(f"Unhandled Discord event error in {event_method}:")
        traceback.print_exc()

    @tasks.loop(minutes=5)
    async def health_check(self):
        try:
            latency_ms = self.latency * 1000
            print(
                f"[health] bot_running=true discord_ready={self.is_ready()} "
                f"latency_ms={latency_ms:.0f}"
            )
        except Exception:
            print("Health check failed:")
            traceback.print_exc()

    @health_check.before_loop
    async def before_health_check(self):
        await self.wait_until_ready()

    @health_check.error
    async def health_check_error(self, error):
        print(f"Health-check loop error: {error!r}")
        traceback.print_exception(type(error), error, error.__traceback__)

bot = StorytimeBot()

# Helper Function for OpenRouter with Fallback Handling and Timeout
async def query_openrouter(system_prompt: str, user_prompt: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://discord.com",
        "X-Title": "StorytimeBot"
    }

    last_error = "Unknown error"
    timeout = aiohttp.ClientTimeout(total=30)

    for model_name in MODELS_TO_TRY:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        last_error = await response.text()
                        print(f"Endpoint {model_name} returned status {response.status}. Trying next available fallback...")
        except asyncio.TimeoutError:
            last_error = f"Endpoint {model_name} timed out."
            print(last_error)
        except Exception as exc:
            last_error = str(exc)
            print(f"Request error with {model_name}: {last_error}")

    return f"API Error: All model endpoints failed. Details: {last_error}"

# Slash Commands: Bedtime Stories

@bot.tree.command(
    name="bedtimestory",
    description="Tells a cozy bedtime story line by line with typing indicators."
)
@app_commands.describe(
    theme="What should the story be about? (e.g., quiet snowy cabin, cozy cafe in the rain)",
    pacing="Pacing speed between sentences"
)
@app_commands.choices(pacing=[
    app_commands.Choice(name="Fast (9.5 to 13 second pauses)", value="fast"),
    app_commands.Choice(name="Normal (20 to 25 second pauses)", value="normal"),
    app_commands.Choice(name="Slow (33 to 40 second pauses)", value="slow")
])
async def bedtime_story(
    interaction: discord.Interaction,
    theme: str = "a warm, quiet cabin by a foggy pine forest with a glowing fireplace",
    pacing: app_commands.Choice[str] = None
):
    user_id = interaction.user.id
    selected_pacing = pacing.value if pacing else "normal"
    await interaction.response.defer()

    system_prompt = (
        "You are Storytime Bot, a calming, quiet storyteller crafting cozy, relaxing bedtime tales. "
        "Your tone must be gentle, atmospheric, and soothing to help someone drift off to sleep. "
        "Write a continuous story made up of 20 to 25 individual, short sentences. "
        "Do not write blocky paragraphs. "
        "Crucial formatting requirement: Separate EVERY SINGLE SENTENCE strictly with the exact token '===SPLIT===' "
        "and nothing else between them. Do not include markdown headers, titles, or numbered lists."
    )
    user_prompt = f"Tell me a peaceful bedtime story about: {theme}"

    try:
        raw_story = await query_openrouter(system_prompt, user_prompt)
    except Exception as e:
        await interaction.followup.send(f"Error communicating with AI service: {e}")
        return

    if "API Error" in raw_story:
        await interaction.followup.send(f"Couldn't generate the story right now: {raw_story}")
        return

    sentences = [s.strip() for s in raw_story.split("===SPLIT===") if s.strip()]

    if len(sentences) <= 1:
        sentences = [s.strip() for s in raw_story.replace(". ", ".\n").split("\n") if s.strip()]

    delay_ranges = {
        "fast": (9.5, 13.0),
        "normal": (20.0, 25.0),
        "slow": (33.0, 40.0)
    }
    min_delay, max_delay = delay_ranges.get(selected_pacing, (20.0, 25.0))

    intro_embed = discord.Embed(
        title="Storytime Bot Bedtime Story",
        description=f"Theme: *{theme}*\nGet cozy and relax...",
        color=discord.Color.dark_purple()
    )
    await interaction.followup.send(embed=intro_embed)

    channel = interaction.channel
    if channel is None:
        await interaction.followup.send(
            "I couldn't find a channel to send the story to. Please try again."
        )
        return

    active_stories[user_id] = True

    try:
        for sentence in sentences:
            if not active_stories.get(user_id, True):
                break

            natural_delay = random.uniform(min_delay, max_delay)

            async with channel.typing():
                await asyncio.sleep(natural_delay)

            if not active_stories.get(user_id, True):
                break

            try:
                await channel.send(sentence)
            except discord.HTTPException as exc:
                print(f"Story message failed to send: {exc}")
                break

        if active_stories.get(user_id, True):
            async with channel.typing():
                await asyncio.sleep(2.5)
            
            closing_embed = discord.Embed(
                description="Rest well and sweet dreams.",
                color=discord.Color.dark_teal()
            )
            await channel.send(embed=closing_embed)
    finally:
        active_stories.pop(user_id, None)

@bot.tree.command(
    name="stop",
    description="Stops an ongoing bedtime story."
)
async def stop_story(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in active_stories:
        active_stories[user_id] = False
        await interaction.response.send_message("Stopping the story now...", ephemeral=True)
    else:
        await interaction.response.send_message("You don't have an active story playing right now.", ephemeral=True)

# Slash Commands: Sleep Tracking

@bot.tree.command(
    name="logsleep",
    description="Log your sleep, naps, and morning mood."
)
@app_commands.describe(
    sleep_time="When did you fall asleep? (e.g., 4:30 AM)",
    wake_time="When did you wake up? (e.g., 1:00 PM)",
    sleep_hours="Total hours slept (e.g., 8.5)",
    nap_minutes="Total nap minutes taken during the day (e.g., 60)",
    awakenings="How many times did you wake up in the night?",
    mood="How exhausted/heavy do you feel? (1 = Awful, 5 = Great)",
    notes="Any notes (e.g., headache, bad dreams, room was hot)"
)
async def log_sleep(
    interaction: discord.Interaction,
    sleep_time: str,
    wake_time: str,
    sleep_hours: float,
    nap_minutes: int = 0,
    awakenings: int = 0,
    mood: int = 3,
    notes: str = ""
):
    user_id = interaction.user.id
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sleep_logs (user_id, date_logged, sleep_time, wake_time, sleep_hours, nap_minutes, awakenings, mood, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, today, sleep_time, wake_time, sleep_hours, nap_minutes, awakenings, mood, notes))
    conn.commit()
    conn.close()

    embed = discord.Embed(
        title="Sleep Logged",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Window", value=f"{sleep_time} to {wake_time}", inline=True)
    embed.add_field(name="Duration", value=f"{sleep_hours} hrs", inline=True)
    embed.add_field(name="Daytime Nap", value=f"{nap_minutes} mins", inline=True)
    embed.add_field(name="Awakenings", value=str(awakenings), inline=True)
    embed.add_field(name="Mood Score", value=f"{mood}/5", inline=True)
    if notes:
        embed.add_field(name="Notes", value=notes, inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="sleepstats",
    description="View raw numbers and averages."
)
async def sleep_stats(interaction: discord.Interaction):
    user_id = interaction.user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sleep_hours, nap_minutes, awakenings, mood
        FROM sleep_logs
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 14
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("No sleep logs found yet. Use `/logsleep` first.", ephemeral=True)
        return

    total_logs = len(rows)
    avg_sleep = sum(r[0] for r in rows) / total_logs
    avg_naps = sum(r[1] for r in rows) / total_logs
    avg_wakeups = sum(r[2] for r in rows) / total_logs
    avg_mood = sum(r[3] for r in rows) / total_logs

    embed = discord.Embed(
        title=f"Storytime Bot: Sleep Overview (Last {total_logs} Entries)",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Average Nightly Sleep", value=f"{avg_sleep:.1f} hours", inline=True)
    embed.add_field(name="Average Daily Nap", value=f"{avg_naps:.0f} mins", inline=True)
    embed.add_field(name="Average Night Wakeups", value=f"{avg_wakeups:.1f}", inline=True)
    embed.add_field(name="Average Mood Rating", value=f"{avg_mood:.1f} / 5", inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="aisleep",
    description="Get an AI breakdown of your sleep trends and gentle advice."
)
async def ai_sleep(interaction: discord.Interaction):
    user_id = interaction.user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date_logged, sleep_time, wake_time, sleep_hours, nap_minutes, awakenings, mood, notes
        FROM sleep_logs
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 10
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("No logs found to analyze. Add a few entries using `/logsleep` first.", ephemeral=True)
        return

    await interaction.response.defer()

    log_summary_lines = []
    for r in reversed(rows):
        log_summary_lines.append(
            f"Date: {r[0]} | Slept: {r[1]} to {r[2]} ({r[3]} hrs) | Nap: {r[4]}m | Awakenings: {r[5]} | Morning Mood: {r[6]}/5 | Notes: {r[7]}"
        )
    formatted_logs = "\n".join(log_summary_lines)

    system_prompt = (
        "You are Storytime Bot, a supportive, insightful sleep and circadian rhythm helper. "
        "Analyze the provided sleep log entries. Be empathetic, low pressure, "
        "and practical. Avoid sounding like a stiff medical lecture. "
        "Identify patterns between nap length, wake times, nighttime awakenings, "
        "and mood. Offer 2 or 3 tiny, painless adjustments she can test. "
        "Keep your total output under 1500 characters so it fits cleanly in Discord."
    )
    user_prompt = (
        f"Here are my recent sleep logs from the past few days:\n\n"
        f"{formatted_logs}\n\n"
        f"What patterns do you notice, and what small steps can I take to make waking up less exhausting?"
    )

    try:
        ai_response = await query_openrouter(system_prompt, user_prompt)
    except Exception as e:
        ai_response = f"Failed to retrieve insights: {e}"

    embed = discord.Embed(
        title="Storytime Bot: Sleep Pattern Insights",
        description=ai_response,
        color=discord.Color.purple(),
        timestamp=datetime.now()
    )
    embed.set_footer(text="Engine: OpenRouter Paid Pool")

    await interaction.followup.send(embed=embed)


def run_bot_forever():
    reconnect_delay = 5
    while True:
        try:
            bot.run(DISCORD_TOKEN, reconnect=True)
            print("Bot run loop ended normally.")
            return
        except KeyboardInterrupt:
            print("Bot stopped by request.")
            return
        except Exception:
            print(
                f"Bot process stopped unexpectedly; restarting in "
                f"{reconnect_delay} seconds."
            )
            traceback.print_exc()
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 300)


if __name__ == "__main__":
    run_bot_forever()
