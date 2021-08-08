#!/usr/bin/env python3
import logging
import butterfly_bot.openai_utils as openai_utils
import butterfly_bot.utils
from discord.ext import commands


logger = logging.getLogger(__name__)


class OpenAIBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # dictionary to look up chat context based on user
        self._exchanges = {}

    async def send_openai_completion(self, ctx, prompt, stops,
                                     response_target=butterfly_bot.utils.ResponseTarget.LAST_MESSAGE):
        await butterfly_bot.utils.send_responses(
            ctx,
            await openai_utils.get_openai_completion(prompt, list(stops)),
            response_target = response_target)

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'Logged on as {self.bot.user.name}, {self.bot.user.id}')

    @commands.command(description='Echoes the message back for testing purposes')
    async def echo(self, ctx, message: str):
        """Echoes the message back to the channel"""
        await butterfly_bot.utils.send_responses(ctx, (message), code_block = False)

    @commands.command()
    async def raw_openai(self, ctx, prompt, *stops: str):
        """Sends a raw openai completion request given a prompt and a list of stops"""
        await self.send_openai_completion(ctx, prompt, stops)

    @commands.command()
    async def flush_chat_history(self, ctx):
        self._exchanges.setdefault(ctx.author, []).clear()
        await ctx.send("I have forgotten everything we discussed.")

    @commands.command()
    async def show_chat_history(self, ctx):
        history = []
        for previous_exchange in self._exchanges.setdefault(ctx.author, []):
            history.append(previous_exchange)

        if len(history) == 0:
            history.append("we haven't chatted lately")

        await butterfly_bot.utils.send_responses(ctx, history)

    @commands.command()
    async def story(self, ctx, *words: str):
        """Returns a short story based on your prompt"""
        message = ' '.join(words)
        prompt = (
            "You're a bestselling author. Write a short story about the following prompt:\n\n"
            f"Prompt: {message}\n"
            "Your story:"
        )
        await self.send_openai_completion(ctx, prompt, ["Your story:"])

    @commands.command()
    async def tarot(self, ctx, *words: str):
        """Returns a tarot reading based on your prompt"""
        message = ' '.join(words)
        prompt = (
            f"You're a tarot reader. Give a tarot reading for the following prompt:\n\n"
            f"Prompt: {message}\n"
            f"Your reading:"
        )
        await self.send_openai_completion(ctx, prompt, ["Your reading:"])

    @commands.command()
    async def code(self, ctx, language: str, *words: str):
        """Returns code based on your prompt"""
        message = ' '.join(words)
        if message == '':
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
        stops = ["\n", f" {ctx.author}:", f" {self.bot.user.name}:"]
        message = ' '.join(words)
        prompt = f"You're a witty, polite, insightful, and very kind conversationalist. In up to a few sentences, " \
                 f"continue the following conversation with your friend {ctx.author}\n\n "

        for previous_exchange in self._exchanges.setdefault(ctx.author, []):
            prompt += previous_exchange

        new_exchange = (
            f"{ctx.author}: {message}\n"
            f"{self.bot.user.name}:"
        )

        prompt += new_exchange

        answer = openai_utils.complete(prompt, stops, strip=True)
        await ctx.send(answer)

        # update exchanges for next chat
        new_exchange += f" {answer}\n"
        self._exchanges[ctx.author].append(new_exchange)
        if len(self._exchanges[ctx.author]) > 5:
            self._exchanges[ctx.author] = self._exchanges[ctx.author][1:]

    @commands.Cog.listener()
    async def on_command_error(self, ctx, exc):
        if exc.__class__ == commands.errors.CommandNotFound:
            invoker = 'chat'
            ctx.message.content = f"{ctx.invoked_with} {ctx.message.content}"
            ctx.view.index = ctx.view.previous

            ctx.invoked_with = invoker
            ctx.command = self.bot.all_commands.get(invoker)
            await self.bot.invoke(ctx)
        else:
            raise exc
