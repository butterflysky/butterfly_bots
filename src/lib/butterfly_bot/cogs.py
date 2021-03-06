#!/usr/bin/env python3
import datetime
import logging
import os
from typing import Union

from discord.ext import commands
from discord_slash import SlashContext
from discord_slash.cog_ext import cog_slash
from discord_slash.context import InteractionContext, MenuContext
from discord_slash.model import SlashCommandOptionType
from discord_slash.utils.manage_commands import create_choice, create_option

from .discord_utils import MemberNameConverter
from .openai_utils import ExchangeManager, complete_with_openai
from .options import DiscordCompletionOptions, StoryOptions
from .utils import pretty_time_delta, send_response, send_responses

logger = logging.getLogger(__name__)

GUILD_IDS = [int(guild_id) for guild_id in os.getenv("GUILD_IDS").split(",")]

DiscordContext = Union[commands.Context, SlashContext, MenuContext, InteractionContext]


async def send_openai_completion(
    options: DiscordCompletionOptions,
):
    logger.info(f"send_openai_completion called with options: {options}")
    async with options.ctx.channel.typing():
        response = await complete_with_openai(options.prompt, options.stops)

        await send_response(
            options.with_attr("paginate", True),
            response,
        )


class OpenAIBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.exchange_manager = ExchangeManager(max_size=5)
        self.member_name_converter = MemberNameConverter()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"Logged on as {self.bot.user.name}, {self.bot.user.id}")

    @cog_slash(
        name="flush_chat_history",
        guild_ids=GUILD_IDS,
        description="Clear the bot's conversation history",
    )
    async def flush_chat_history_slash(self, ctx: SlashContext):
        self.exchange_manager.clear(ctx)
        await ctx.send("I have forgotten everything we discussed.")

    @commands.command()
    async def raw_openai(self, ctx: commands.Context, prompt, *stops: str):
        """Sends a raw openai completion request given a prompt and a list of stops"""
        options = StoryOptions(ctx=ctx, prompt=prompt, stops=stops)
        await send_openai_completion(options)

    @commands.command()
    async def flush_chat_history(self, ctx):
        self.exchange_manager.clear(ctx)
        await ctx.send("_deprecated: use /flush_chat_history instead going forward")
        await ctx.send("I have forgotten everything we discussed.")

    @cog_slash(
        name="show_chat_history",
        guild_ids=GUILD_IDS,
        description="shows the bot's memory of recent chats",
        options=[
            create_option(
                name="broadcast",
                description="controls whether the history is shown to the entire channel, defaults to false",
                required=False,
                option_type=SlashCommandOptionType.BOOLEAN,
            )
        ],
    )
    async def show_chat_history_slash(self, ctx: SlashContext, broadcast=False):
        exchanges = self.exchange_manager.get(ctx)

        if len(exchanges) == 0:
            exchanges = "we haven't chatted lately"

        await ctx.send(f"```{exchanges}```", hidden=(not broadcast))

    @commands.command()
    async def show_chat_history(self, ctx):
        exchanges = self.exchange_manager.get(ctx)

        if len(exchanges) == 0:
            exchanges = "we haven't chatted lately"

        await send_responses(DiscordCompletionOptions(ctx=ctx), exchanges)

    @commands.command()
    async def story(self, ctx, *words: str):
        options = StoryOptions(ctx=ctx, prompt=" ".join(words))
        await self._story_stub(options)

    @cog_slash(
        name="story",
        guild_ids=GUILD_IDS,
        description="prompts the bot to write a short story",
        options=[
            create_option(
                name="prompt",
                description="story prompt",
                required=True,
                option_type=SlashCommandOptionType.STRING,
            ),
            create_option(
                name="prompt_prelude",
                description="this is the 'You are an author, write a story about:' prelude to the prompt",
                required=False,
                option_type=SlashCommandOptionType.STRING,
            ),
            create_option(
                name="stops",
                description="these are the tokens that cause OpenAI to stop the completion",
                required=False,
                option_type=SlashCommandOptionType.STRING,
            ),
            create_option(
                name="engine",
                description="which OpenAI completion engine to use (default: davinci-instruct-beta)",
                required=False,
                option_type=SlashCommandOptionType.STRING,
                choices=[
                    create_choice("davinci-instruct-beta", "davinci-instruct-beta"),
                    create_choice("curie-instruct-beta", "curie-instruct-beta"),
                    create_choice("davinci", "davinci"),
                    create_choice("curie", "curie"),
                    create_choice("babbage", "babbage"),
                    create_choice("ada", "ada"),
                ],
            ),
            create_option(
                name="temperature",
                description="What sampling temperature to use. Higher values means the model will take more risks.",
                required=False,
                option_type=SlashCommandOptionType.FLOAT,
            ),
            create_option(
                name="top_p",
                description="see https://beta.openai.com/docs/api-reference/completions/create#completions/create"
                "-top_p",
                required=False,
                option_type=SlashCommandOptionType.FLOAT,
            ),
            create_option(
                name="frequency_penalty",
                description="see https://beta.openai.com/docs/api-reference/completions/create"
                "-frequency_penalty",
                required=False,
                option_type=SlashCommandOptionType.FLOAT,
            ),
            create_option(
                name="presence_penalty",
                description="see https://beta.openai.com/docs/api-reference/completions/create",
                required=False,
                option_type=SlashCommandOptionType.FLOAT,
            ),
        ],
    )
    async def story_slash(self, ctx: SlashContext, **kwargs):
        await ctx.defer(hidden=False)
        await self._story_stub(StoryOptions(ctx=ctx, **kwargs))

    async def _story_stub(self, options: StoryOptions):
        """Returns a short story based on your prompt"""
        if "{prompt}" not in options.prompt_prelude:
            options.prompt_prelude += "\n{prompt}\nStory:"
        options.prompt = await self.convert_discord_refs_to_names(
            options.ctx, options.prompt
        )
        options.prompt = options.prompt_prelude.format(prompt=options.prompt)
        options.stops = ["Story:"]
        await send_openai_completion(options)

    @commands.command()
    async def tarot(self, ctx, *words: str):
        """Returns a tarot reading based on your prompt"""
        message = await self.convert_discord_refs_to_names(ctx, words)
        options = StoryOptions(
            ctx=ctx,
            stops=["Your reading:"],
            prompt=(
                f"You're a tarot reader. Give a tarot reading for the following prompt:\n\n"
                f"Prompt: {message}\n"
                f"Your reading:"
            ),
        )
        await send_openai_completion(options)

    @commands.command()
    async def code(self, ctx, language: str, *words: str):
        """Returns code based on your prompt"""
        message = await self.convert_discord_refs_to_names(ctx, words)
        if message == "":
            return
        options = StoryOptions(
            ctx=ctx,
            stops=["Your code:"],
            prompt=(
                f"Write a function in {language} that fits the following prompt:\n\n"
                f"Prompt: {message}\n"
                f"Your code:"
            ),
        )
        await send_openai_completion(options)

    @commands.command()
    async def chat(self, ctx, *words: str):
        """Sends a prompt to openai and returns the result, keeping 5 exchanges as context"""
        # sort and concatenate each of the mentioned usernames then hash the resulting string
        # as a key for the exchange cache
        stops = [
            f" {ctx.author.display_name}:",
            f" {self.bot.user.display_name}:",
            "\n",
        ]
        message = await self.convert_discord_refs_to_names(ctx, words)
        prompt = (
            f"Your name is {self.bot.user.display_name}. You're thoughtful, kind, and witty. "
            f"Continue the following conversation with your friends:\n\n"
        )

        # append previous exchanges to the prompt
        prompt += self.exchange_manager.get(ctx)

        # add new exchange prompt
        new_exchange = (
            f"{ctx.author.display_name}: {message}\n" f"{self.bot.user.display_name}:"
        )

        # todo: what happens if there's no answer?
        answer = await complete_with_openai(
            prompt + new_exchange, stops, strip_response=True
        )
        await ctx.send(answer)

        # update exchanges for next chat
        new_exchange += f" {answer}\n"
        self.exchange_manager.append(ctx, new_exchange)

    async def convert_discord_refs_to_names(self, ctx: DiscordContext, words):
        if isinstance(words, str):
            words = words.split(" ")
        message = " ".join(
            [await self.member_name_converter.convert(ctx, word) for word in words]
        )
        return message

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, exc: Exception):
        if exc.__class__ != commands.errors.CommandNotFound:
            await ctx.send(f"an exception occurred: {exc}")
            raise exc
        else:
            invoker = "chat"
            ctx.message.content = f"{ctx.invoked_with} {ctx.message.content}"
            ctx.view.index = ctx.view.previous

            ctx.invoked_with = invoker
            ctx.command = self.bot.all_commands.get(invoker)
            await self.bot.invoke(ctx)


class UtilityBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._start_time = datetime.datetime.now()

    @cog_slash(
        name="uptime",
        guild_ids=GUILD_IDS,
        description="shows how long the bot has been running since its last restart",
        options=[
            create_option(
                name="show_channel",
                description="should the response be shown to the channel, defaults to false",
                required=False,
                option_type=SlashCommandOptionType.BOOLEAN,
            )
        ],
    )
    async def uptime(self, ctx: SlashContext, show_channel: bool = False):
        uptime = datetime.datetime.now() - self._start_time
        await ctx.send(
            f"{pretty_time_delta(int(uptime.total_seconds()))}",
            hidden=(not show_channel),
        )
