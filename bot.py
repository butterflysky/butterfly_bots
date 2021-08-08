#!/usr/bin/env python3
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import butterfly_bot.cogs


load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('adonis_blue')

intents = discord.Intents.default()
intents.members = True
intents.typing = False
intents.presences = False

description = "butterfly bot alpha"
adonis_blue = commands.Bot(command_prefix=commands.when_mentioned_or('!'), description=description, intents=intents,
                           strip_after_prefix=True)

adonis_blue.add_cog(butterfly_bot.cogs.OpenAIBot(adonis_blue))
adonis_blue.run(os.getenv('DISCORD_API_KEY'))
