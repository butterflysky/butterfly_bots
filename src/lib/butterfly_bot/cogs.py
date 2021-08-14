#!/usr/bin/env python3
import asyncio
import datetime
import logging

from discord.ext import commands

from .discord_utils import MemberNameConverter

from .openai_utils import (
    ExchangeManager,
    complete_with_openai,
)

from .utils import (
    ResponseTarget,
    pretty_time_delta,
    send_responses, paginate,
)


logger = logging.getLogger(__name__)


class OpenAIBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.exchange_manager = ExchangeManager(max_size=5)
        self.member_name_converter = MemberNameConverter()

    async def send_openai_completion(
        self,
        ctx,
        prompt,
        stops,
        response_target=ResponseTarget.LAST_MESSAGE,
    ):
        async with ctx.typing():
            response = await complete_with_openai(prompt, stops)

            await send_responses(
                ctx,
                await paginate(response),
                response_target=response_target,
            )

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"Logged on as {self.bot.user.name}, {self.bot.user.id}")

    @commands.command(description="Echoes the message back for testing purposes")
    async def echo(self, ctx, *words):
        """Echoes the message back to the channel"""
        message = await self.preprocess_message(ctx, words)
        await send_responses(ctx, message, code_block=False)

    @commands.command()
    async def raw_openai(self, ctx, prompt, *stops: str):
        """Sends a raw openai completion request given a prompt and a list of stops"""
        await self.send_openai_completion(ctx, prompt, stops)

    @commands.command()
    async def flush_chat_history(self, ctx):
        self.exchange_manager.clear(ctx)
        await ctx.send("I have forgotten everything we discussed.")

    @commands.command()
    async def show_chat_history(self, ctx):
        exchanges = self.exchange_manager.get(ctx)

        if len(exchanges) == 0:
            exchanges = "we haven't chatted lately"

        await send_responses(ctx, exchanges)

    @commands.command()
    async def story(self, ctx, *words: str):
        """Returns a short story based on your prompt"""
        message = await self.preprocess_message(ctx, words)
        prompt = (
            "You're a bestselling author. Write a short story about the following prompt:\n\n"
            f"Prompt: {message}\n"
            "Your story:"
        )
        await self.send_openai_completion(ctx, prompt, ["Your story:"])

    @commands.command()
    async def tarot(self, ctx, *words: str):
        """Returns a tarot reading based on your prompt"""
        message = await self.preprocess_message(ctx, words)
        prompt = (
            f"You're a tarot reader. Give a tarot reading for the following prompt:\n\n"
            f"Prompt: {message}\n"
            f"Your reading:"
        )
        await self.send_openai_completion(ctx, prompt, ["Your reading:"])

    @commands.command()
    async def code(self, ctx, language: str, *words: str):
        """Returns code based on your prompt"""
        message = await self.preprocess_message(ctx, words)
        if message == "":
            return
        prompt = (
            f"Write a function in {language} that fits the following prompt:\n\n"
            f"Prompt: {message}\n"
            f"Your code:"
        )
        await self.send_openai_completion(ctx, prompt, ["Your code:"])

    @commands.command()
    async def chat(self, ctx, *words: str):
        """Sends a prompt to openai and returns the result, keeping 5 exchanges as context"""
        # sort and concatenate each of the mentioned usernames then hash the resulting string
        # as a key for the exchange cache
        stops = [f"\n{ctx.author.display_name}:", f"\n{self.bot.user.display_name}:", "\n"]
        message = await self.preprocess_message(ctx, words)
        prompt = (
            f"Your name is {self.bot.user.display_name}. You're having a polite conversation with one or more friends. "
            f"Continue the following conversation with your friends:\n\n"
        )

        # append previous exchanges to the prompt
        prompt += self.exchange_manager.get(ctx)

        # add new exchange prompt
        new_exchange = f"{ctx.author.display_name}: {message}\n" f"{self.bot.user.display_name}:"

        # todo: what happens if there's no answer?
        answer = await complete_with_openai(prompt + new_exchange, stops, strip=True)
        await ctx.send(answer)

        # update exchanges for next chat
        new_exchange += f" {answer}\n"
        self.exchange_manager.append(ctx, new_exchange)

    async def preprocess_message(self, ctx, words):
        message = " ".join([await self.member_name_converter.convert(ctx, word) for word in words])
        return message

    @commands.Cog.listener()
    async def on_command_error(self, ctx, exc):
        if exc.__class__ == commands.errors.CommandNotFound:
            invoker = "chat"
            ctx.message.content = f"{ctx.invoked_with} {ctx.message.content}"
            ctx.view.index = ctx.view.previous

            ctx.invoked_with = invoker
            ctx.command = self.bot.all_commands.get(invoker)
            await self.bot.invoke(ctx)
        else:
            raise exc


class UtilityBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def uptime(self, ctx):
        logger.debug("running uptime command asynchronously")
        proc = await asyncio.create_subprocess_shell(
            'stat --printf="%X" /proc/1/cmdline',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if stdout:
            stdout = stdout.decode()
            start_time = datetime.datetime.fromtimestamp(float(stdout))
            logger.debug(f"[stdout]: {stdout}")
            uptime = datetime.datetime.now() - start_time
            await ctx.send(
                f"{pretty_time_delta(uptime.total_seconds())}"
            )
        if stderr:
            stderr = stderr.decode()
            logger.debug(f"[stderr]: {stderr}")
            await ctx.send(f"process exited with {proc.returncode}\n[stderr]: {stderr}")
