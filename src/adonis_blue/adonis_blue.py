#!/usr/bin/env python3
import logging
import os

import butterfly_bot.cogs
import discord
from butterfly_bot.env_utils import load_environment
from discord.ext import commands
from discord_slash import SlashCommand
from version import get_bot_version

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("adonis_blue")

load_environment()

intents = discord.Intents.default()
intents.members = True
intents.typing = False
intents.presences = False

description = "butterfly bot alpha"
adonis_blue = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    description=description,
    intents=intents,
    strip_after_prefix=True,
)
slash = SlashCommand(adonis_blue, sync_commands=True, sync_on_cog_reload=True)


@adonis_blue.command()
async def version(ctx):
    await ctx.send(get_bot_version())


adonis_blue.add_cog(butterfly_bot.cogs.OpenAIBot(adonis_blue))
adonis_blue.add_cog(butterfly_bot.cogs.UtilityBot(adonis_blue))
adonis_blue.run(os.getenv("DISCORD_API_KEY"))
