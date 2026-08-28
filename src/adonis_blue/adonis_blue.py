#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from importlib.metadata import version

import discord
from butterfly_bot.cogs import OpenAIBot, UtilityBot
from butterfly_bot.config import CompletionConfig, parse_guild_ids
from discord.ext import commands
from dotenv import load_dotenv
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
OWNED_LOGGERS = ("adonis_blue", "butterfly_bot")
DEPENDENCY_LOGGERS = ("discord", "httpcore", "httpx", "openai")
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging(environ: Mapping[str, str] = os.environ) -> None:
    level_name = environ.get("LOG_LEVEL", "INFO").strip().upper()
    level = LOG_LEVELS.get(level_name)
    if level is None:
        raise ValueError(f"invalid LOG_LEVEL: {level_name}")
    logging.basicConfig(level=logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    for namespace in DEPENDENCY_LOGGERS:
        logging.getLogger(namespace).setLevel(logging.INFO)
    for namespace in OWNED_LOGGERS:
        logging.getLogger(namespace).setLevel(level)


class AdonisBlue(commands.Bot):
    def __init__(
        self, client: AsyncOpenAI, config: CompletionConfig, guild_ids: tuple[int, ...]
    ):
        if not guild_ids:
            raise ValueError("at least one guild ID is required")
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.typing = False
        intents.presences = False
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            description="butterfly bot alpha",
            intents=intents,
            strip_after_prefix=True,
        )
        self.openai_client = client
        self.completion_config = config
        self.guild_ids = guild_ids

    async def process_commands(self, message: discord.Message, /) -> None:
        """Process human and peer-bot commands while ignoring our own messages."""
        user = self.user
        if user is not None and message.author.id == user.id:
            return

        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def setup_hook(self) -> None:
        await self.add_cog(OpenAIBot(self, self.openai_client, self.completion_config))
        await self.add_cog(UtilityBot(self))
        for guild_id in self.guild_ids:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)


@commands.command(name="version")
async def version_command(ctx: commands.Context) -> None:
    await ctx.send(version("adonis-blue"))


def build_bot(
    client: AsyncOpenAI, config: CompletionConfig, guild_ids: tuple[int, ...]
) -> AdonisBlue:
    bot = AdonisBlue(client, config, guild_ids)
    bot.add_command(version_command)
    return bot


async def run_with_cleanup(
    bot: AdonisBlue, client: AsyncOpenAI, discord_token: str
) -> None:
    primary_error: BaseException | None = None
    try:
        await bot.start(discord_token)
    except BaseException as exc:
        primary_error = exc

    for resource_name, close in (
        ("Discord bot", bot.close),
        ("OpenAI client", client.close),
    ):
        try:
            await close()
        except BaseException as exc:
            if primary_error is None:
                primary_error = exc
            else:
                logger.warning(
                    "%s cleanup failed after an earlier error: %s",
                    resource_name,
                    type(exc).__name__,
                )

    if primary_error is not None:
        raise primary_error.with_traceback(primary_error.__traceback__)


async def run() -> None:
    load_dotenv()
    configure_logging()
    discord_token = os.environ.get("DISCORD_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not discord_token:
        raise RuntimeError("DISCORD_API_KEY is required")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    completion_config = CompletionConfig.from_env()
    guild_ids = parse_guild_ids(os.environ.get("GUILD_IDS"))
    client = AsyncOpenAI(
        api_key=openai_key,
        timeout=completion_config.request_timeout_seconds,
        max_retries=2,
    )
    bot = build_bot(
        client,
        completion_config,
        guild_ids,
    )
    await run_with_cleanup(bot, client, discord_token)


if __name__ == "__main__":
    asyncio.run(run())
