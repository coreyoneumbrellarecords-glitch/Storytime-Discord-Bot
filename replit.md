# Storytime Discord Bot

A Discord bot that tells paced bedtime stories and tracks sleep logs with SQLite and OpenRouter insights.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `python3 -m pip install -r requirements.txt` — install the Python bot dependencies
- `python3 main.py` — run the Discord bot
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required secrets: `DISCORD_TOKEN`, `OPENROUTER_API_KEY`

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Python 3.13, `discord.py`, `aiohttp`, and SQLite
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `main.py` — Discord bot commands, OpenRouter integration, and SQLite persistence
- `requirements.txt` — Python runtime dependencies
- `.env.example` — environment variable template

## Architecture decisions

- Credentials are read from environment variables and are never stored in source code.
- SQLite is kept local to preserve the original bot's simple, file-based sleep log storage.
- Discord slash commands are synchronized globally in `setup_hook`.

## Product

- `/bedtimestory` generates a paced bedtime story through OpenRouter.
- `/logsleep`, `/sleepstats`, and `/aisleep` track and summarize sleep.

## User preferences

- Keep bot credentials out of committed files.

## Gotchas

- The credentials from the uploaded script should be rotated; do not reuse them.
- The bot will stop at startup with a clear error until both required secrets exist.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
