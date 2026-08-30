# Adonis Blue

Adonis Blue is a Discord bot with prefix and slash commands, OpenAI-powered chat,
stories, tarot, and code prompts, and five recent exchanges of per-channel memory.

## Run with uv

Install [uv](https://docs.astral.sh/uv/), then create `src/adonis_blue/.env`:

```dotenv
OPENAI_API_KEY=<your-api-key>
DISCORD_API_KEY=<your-bot-token>
GUILD_IDS=123456789012345678,987654321098765432
# Optional; defaults to the legacy Completions-compatible model below.
OPENAI_MODEL=gpt-3.5-turbo-instruct
# Optional: DEBUG, INFO, WARNING, ERROR, or CRITICAL. Defaults to INFO.
LOG_LEVEL=INFO
```

`GUILD_IDS` is a required comma-separated list of server IDs. The bot fails fast
when it is absent or blank; it never turns a missing value into a global command
sync. Secrets are read only from the environment and must not be committed.

Prefix commands require the privileged **Message Content Intent**. Enable it for
the bot in Discord's Developer Portal under **Bot → Privileged Gateway Intents**.
`LOG_LEVEL` applies only to Adonis Blue and its shared `butterfly_bot` code;
Discord, OpenAI, and HTTP dependency logging remains INFO or stricter so debug
mode cannot expose provider payloads or credentials.

```sh
uv sync --frozen
uv run python -m adonis_blue.adonis_blue
```

Development checks:

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

Docker remains available with `docker compose up --build -d adonis_blue`. Set
`ADONIS_BLUE_IMAGE` when an explicit registry name or tag is needed; Compose does
not duplicate the application version.
