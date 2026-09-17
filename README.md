# Storytime Discord Bot

A Discord bot with cozy bedtime stories, sleep logging, sleep statistics, and AI-assisted sleep trend insights.

## Setup

1. Install the Python dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

2. Add these as Replit Secrets:

   - `DISCORD_TOKEN` — a token for the Discord bot application.
   - `OPENROUTER_API_KEY` — an OpenRouter API key.

   Optional environment variables are documented in `.env.example`.

3. Start the bot:

   ```bash
   python3 main.py
   ```

## Discord commands

- `/bedtimestory` — generates and sends a paced bedtime story.
- `/logsleep` — records sleep duration, naps, awakenings, mood, and notes.
- `/sleepstats` — shows averages from the latest 14 entries.
- `/aisleep` — asks OpenRouter for gentle observations from the latest 10 entries.

Sleep logs are stored locally in `storytime_bot.db`.

The credentials that were included in the uploaded script should be rotated and should not be reused.