#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import datetime
import logging
from dataclasses import replace
from typing import Any, TypeAlias, cast

import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI, OpenAIError

from .config import CompletionConfig
from .discord_utils import MemberNameConverter
from .openai_utils import (
    CompletionGate,
    CompletionOverloaded,
    CompletionTimedOut,
    ExchangeManager,
    NoOpenAIResponse,
    complete_with_openai,
)
from .options import DiscordCompletionOptions, StoryOptions
from .utils import pretty_time_delta, send_response

logger = logging.getLogger(__name__)
DiscordContext: TypeAlias = commands.Context | discord.Interaction


async def send_openai_completion(
    client: AsyncOpenAI,
    gate: CompletionGate,
    config: CompletionConfig,
    options: DiscordCompletionOptions,
) -> None:
    logger.info("requesting completion with model=%s", config.model)
    ctx = options.ctx
    if ctx is None or ctx.channel is None:
        raise RuntimeError("Discord context has no channel")
    channel = cast(Any, ctx.channel)
    async with channel.typing():
        request_config = replace(
            config,
            temperature=options.temperature,
            max_tokens=options.max_tokens,
            top_p=options.top_p,
            frequency_penalty=options.frequency_penalty,
            presence_penalty=options.presence_penalty,
        )
        response = await complete_with_openai(
            client,
            gate,
            request_config,
            options.prompt,
            options.stops,
            options.strip_response,
        )
        await send_response(options.with_attr("paginate", True), response)


class OpenAIBot(commands.Cog):
    def __init__(
        self, bot: commands.Bot, client: AsyncOpenAI, config: CompletionConfig
    ):
        self.bot = bot
        self.client = client
        self.config = config
        self.completion_gate = CompletionGate(config)
        self.exchange_manager = ExchangeManager(max_size=5)
        self.member_name_converter = MemberNameConverter()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        user = self.bot.user
        if user is not None:
            logger.info("Logged on as %s, %s", user.name, user.id)

    @app_commands.command(
        name="flush_chat_history", description="Clear conversation history"
    )
    async def flush_chat_history_slash(self, interaction: discord.Interaction) -> None:
        self.exchange_manager.clear(interaction)
        await interaction.response.send_message(
            "I have forgotten everything we discussed."
        )

    @commands.command()
    async def raw_openai(self, ctx: commands.Context, prompt: str, *stops: str) -> None:
        await send_openai_completion(
            self.client,
            self.completion_gate,
            self.config,
            StoryOptions(ctx=ctx, prompt=prompt, stops=stops),
        )

    @commands.command()
    async def flush_chat_history(self, ctx: commands.Context) -> None:
        self.exchange_manager.clear(ctx)
        await ctx.send("_deprecated: use /flush_chat_history instead going forward")
        await ctx.send("I have forgotten everything we discussed.")

    @app_commands.command(
        name="show_chat_history", description="Show recent chat memory"
    )
    @app_commands.describe(broadcast="Show history to the channel")
    async def show_chat_history_slash(
        self, interaction: discord.Interaction, broadcast: bool = False
    ) -> None:
        exchanges = (
            self.exchange_manager.get(interaction) or "we haven't chatted lately"
        )
        await interaction.response.send_message(
            f"```{exchanges}```", ephemeral=not broadcast
        )

    @commands.command()
    async def show_chat_history(self, ctx: commands.Context) -> None:
        exchanges = self.exchange_manager.get(ctx) or "we haven't chatted lately"
        await send_response(DiscordCompletionOptions(ctx=ctx), exchanges)

    @commands.command()
    async def story(self, ctx: commands.Context, *words: str) -> None:
        await self._story_stub(StoryOptions(ctx=ctx, prompt=" ".join(words)))

    @app_commands.command(name="story", description="Write a short story")
    @app_commands.describe(
        prompt="Story prompt",
        prompt_prelude="Prelude containing an optional {prompt} placeholder",
        stops="JSON list of stop tokens",
        temperature="Sampling temperature",
        top_p="Nucleus sampling probability",
        frequency_penalty="Frequency penalty",
        presence_penalty="Presence penalty",
    )
    async def story_slash(
        self,
        interaction: discord.Interaction,
        prompt: str,
        prompt_prelude: str | None = None,
        stops: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
    ) -> None:
        await interaction.response.defer()
        kwargs: dict[str, object] = {"ctx": interaction, "prompt": prompt}
        for key, value in {
            "prompt_prelude": prompt_prelude,
            "stops": stops,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
        }.items():
            if value is not None:
                kwargs[key] = value
        try:
            await self._story_stub(StoryOptions(**cast(Any, kwargs)))
        except (
            CompletionOverloaded,
            CompletionTimedOut,
            NoOpenAIResponse,
            OpenAIError,
            IndexError,
            KeyError,
            ValueError,
        ):
            logger.warning("slash story completion failed")
            async with asyncio.timeout(10):
                await interaction.followup.send(
                    "I couldn't finish that story request. Please try again shortly.",
                    ephemeral=True,
                )

    async def _story_stub(self, options: StoryOptions) -> None:
        if options.ctx is None:
            raise RuntimeError("Story request has no Discord context")
        if "{prompt}" not in options.prompt_prelude:
            options.prompt_prelude += "\n{prompt}\nStory:"
        options.prompt = await self.convert_discord_refs_to_names(
            options.ctx, options.prompt
        )
        options.prompt = options.prompt_prelude.format(prompt=options.prompt)
        options.stops = ["Story:"]
        await send_openai_completion(
            self.client, self.completion_gate, self.config, options
        )

    @commands.command()
    async def tarot(self, ctx: commands.Context, *words: str) -> None:
        message = await self.convert_discord_refs_to_names(ctx, words)
        await send_openai_completion(
            self.client,
            self.completion_gate,
            self.config,
            StoryOptions(
                ctx=ctx,
                stops=["Your reading:"],
                prompt="You're a tarot reader. Give a tarot reading for the following "
                "prompt:\n\n"
                f"Prompt: {message}\nYour reading:",
            ),
        )

    @commands.command()
    async def code(self, ctx: commands.Context, language: str, *words: str) -> None:
        message = await self.convert_discord_refs_to_names(ctx, words)
        if not message:
            return
        await send_openai_completion(
            self.client,
            self.completion_gate,
            self.config,
            StoryOptions(
                ctx=ctx,
                stops=["Your code:"],
                prompt=f"Write a function in {language} that fits the following "
                "prompt:\n\n"
                f"Prompt: {message}\nYour code:",
            ),
        )

    @commands.command()
    async def chat(self, ctx: commands.Context, *words: str) -> None:
        user = self.bot.user
        if user is None:
            raise RuntimeError("Discord client user is unavailable")
        stops = [
            f" {ctx.author.display_name}:",
            f" {user.display_name}:",
            "\n",
        ]
        message = await self.convert_discord_refs_to_names(ctx, words)
        prompt = (
            f"Your name is {user.display_name}. You're thoughtful, kind, "
            "and witty. "
            "Continue the following conversation with your friends:\n\n"
            + self.exchange_manager.get(ctx)
        )
        new_exchange = f"{ctx.author.display_name}: {message}\n{user.display_name}:"
        answer = await complete_with_openai(
            self.client,
            self.completion_gate,
            self.config,
            prompt + new_exchange,
            stops,
            True,
        )
        await ctx.send(answer)
        self.exchange_manager.append(ctx, new_exchange + f" {answer}\n")

    async def convert_discord_refs_to_names(
        self, ctx: DiscordContext, words: str | tuple[str, ...]
    ) -> str:
        if isinstance(words, str):
            words = tuple(words.split(" "))
        return " ".join(
            [await self.member_name_converter.convert(ctx, word) for word in words]
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, exc: Exception) -> None:
        if not isinstance(exc, commands.CommandNotFound):
            await ctx.send(f"an exception occurred: {exc}")
            raise exc
        ctx.message.content = f"{ctx.invoked_with} {ctx.message.content}"
        ctx.view.index = ctx.view.previous
        ctx.invoked_with = "chat"
        ctx.command = self.bot.all_commands.get("chat")
        await self.bot.invoke(ctx)


class UtilityBot(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._start_time = datetime.datetime.now()

    @app_commands.command(name="uptime", description="Show bot uptime")
    @app_commands.describe(show_channel="Show the response to the whole channel")
    async def uptime(
        self, interaction: discord.Interaction, show_channel: bool = False
    ) -> None:
        uptime = datetime.datetime.now() - self._start_time
        await interaction.response.send_message(
            pretty_time_delta(int(uptime.total_seconds())), ephemeral=not show_channel
        )
