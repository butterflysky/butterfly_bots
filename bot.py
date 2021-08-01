#!/usr/bin/env python3
import logging
import os

import discord
import openai
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


class NoOpenAIResponse(Exception):
    pass


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('adonis_blue')

intents = discord.Intents.default()
intents.members = True
intents.typing = False
intents.presences = False

ignored_users = ['buckybot#2514']

botname = 'Adonis Blue'

description = "butterfly bot alpha"
bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'), description=description, intents=intents,
                   strip_after_prefix=True)

openai.api_key = os.getenv('OPENAI_API_KEY')


def openai_complete(prompt: str, stops: list[str], strip=True):
    try:
        logger.info(f"sending the following prompt: {prompt}")

        response = openai.Completion.create(
            engine="davinci-instruct-beta",
            prompt=prompt,
            temperature=0.9,
            max_tokens=1500,
            top_p=1,
            frequency_penalty=0.0,
            presence_penalty=0.6,
            stop=stops,
        )

        logger.info(f"got the following response: {response}")

        if response["choices"][0]["text"]:
            answer = response["choices"][0]["text"]
            if strip:
                return f"{answer.strip()}"
            else:
                return f"{answer}"
        else:
            raise NoOpenAIResponse("openai response didn't include answer:\n\n{response}")
    except Exception as e:
        error = f"<error> something went wrong: {e}"
        logger.error(error)
        return error


async def get_and_send_openai_response(ctx, prompt, stops, strip=True):
    response = openai_complete(prompt, stops, strip)

    parts = []
    split_length = 1994

    while len(response) > split_length:
        split_point = response[:split_length].rfind(" ")

        if split_point == -1:
            split_point = split_length

        parts.append(response[:split_point])
        response = response[split_point:]

    parts.append(response)

    respond_to = ctx.message
    for part in parts:
        respond_to = await ctx.send(content=f"```{part}```",
                                    reference=respond_to,
                                    mention_author=True)


# dictionary to look up context based on user
exchanges = {}


@bot.event
async def on_ready():
    logger.info(f'Logged on as {bot.user.name}, {bot.user.id}')


@bot.command(description='Echoes the message back for testing purposes')
async def echo(ctx, message: str):
    """Echoes the message back to the channel"""
    await ctx.send(message)


@bot.command()
async def raw_openai(ctx, prompt, *stops: str):
    """Sends a raw openai completion request given a prompt and a list of stops"""
    await get_and_send_openai_response(ctx, prompt, list(stops))


@bot.command()
async def show_chat_history(ctx):
    history = ""
    for previous_exchange in exchanges.setdefault(ctx.author, []):
        history += previous_exchange

    if len(history) == 0:
        history = "we haven't chatted lately" \
                  ""
    await ctx.send(content=f"```{history}```",
                   reference=ctx.message,
                   mention_author=True)


@bot.command()
async def story(ctx, *words: str):
    """Returns a short story based on your prompt"""
    message = ' '.join(words)
    prompt = (
        "You're a bestselling author of transhumanist stories. Write a short story about the following prompt:\n\n"
        f"Prompt: {message}\n"
        "Your story:"
    )
    await get_and_send_openai_response(ctx, prompt, [" Your story:"])


@bot.command()
async def tarot(ctx, *words: str):
    """Returns a tarot reading based on your prompt"""
    message = ' '.join(words)
    prompt = (
        f"You're a tarot reader. Give a tarot reading for the following prompt:\n\n"
        f"Prompt: {message}\n"
        f"Your reading:"
    )
    await get_and_send_openai_response(ctx, prompt, [" Your reading:"])


@bot.command()
async def code(ctx, language: str, *words: str):
    """Returns code based on your prompt"""
    message = ' '.join(words)
    if message == '':
        return
    prompt = (
        f"Write a function in {language} that fits the following prompt:\n\n"
        f"Prompt: {message}\n"
        f"Your code:"
    )
    await get_and_send_openai_response(ctx, prompt, [" Your code:"], strip=False)


@bot.command()
async def chat(ctx, *words: str):
    """Sends a prompt to openai and returns the result, keeping 5 exchanges as context"""
    stops = ["\n", f" {ctx.author}:", f" {bot.user.name}:"]
    message = ' '.join(words)
    prompt = f"You're a witty, polite, insightful, and very kind conversationalist. In up to a few sentences, " \
             f"continue the following conversation with your friend {ctx.author}\n\n "

    for previous_exchange in exchanges.setdefault(ctx.author, []):
        prompt += previous_exchange

    new_exchange = (
        f"{ctx.author}: {message}\n"
        f"{bot.user.name}:"
    )

    prompt += new_exchange

    answer = openai_complete(prompt, stops, strip=True)
    await ctx.send(answer)

    # update exchanges for next chat
    new_exchange += f" {answer}\n"
    exchanges[ctx.author].append(new_exchange)
    if len(exchanges[ctx.author]) > 5:
        exchanges[ctx.author] = exchanges[ctx.author][1:]


@bot.event
async def on_command_error(ctx, exc):
    if exc.__class__ == commands.errors.CommandNotFound:
        invoker = 'chat'
        ctx.message.content = f"{ctx.invoked_with} {ctx.message.content}"
        ctx.view.index = ctx.view.previous

        ctx.invoked_with = invoker
        ctx.command = bot.all_commands.get(invoker)
        await bot.invoke(ctx)


bot.run(os.getenv('DISCORD_API_KEY'))
