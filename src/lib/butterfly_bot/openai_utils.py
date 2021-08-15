import hashlib
import logging
import os
from enum import Enum

import openai

from collections import deque

logger = logging.getLogger(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")


class NoOpenAIResponse(Exception):
    pass


class ExchangeKey(Enum):
    CHANNEL = 1
    MENTIONS = 2


class ExchangeBuffer:
    def __init__(self, max_size: int = 5, joiner: str = "\n"):
        self.exchanges = deque()
        self.max_size = max_size
        self.joiner = joiner

    def append(self, exchange: str):
        if len(self.exchanges) == self.max_size:
            self.exchanges.popleft()
        self.exchanges.append(exchange)

    def clear(self):
        self.exchanges.clear()

    def __iter__(self):
        return self.exchanges

    def __str__(self):
        if len(self.exchanges) == 0:
            return ""
        else:
            return self.joiner.join(self.exchanges)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"max_size: {self.max_size},"
            f"joiner: {self.joiner,}"
            f"exchanges: {self.exchanges}"
        )


def _hash_ctx(ctx, exchange_key: ExchangeKey = ExchangeKey.CHANNEL):
    if exchange_key == ExchangeKey.CHANNEL:
        return frozenset([1])

    deduped_participants = [ctx.message.author.id]
    for m in ctx.message.mentions:
        if m.id != ctx.bot.user.id:
            deduped_participants.append(m.id)
    logger.info(f"deduped_participants: {deduped_participants}")
    return frozenset(sorted(deduped_participants))


class ExchangeManager:
    def __init__(self, max_size: int = 5):
        self.max_size = max_size
        self._exchanges = {}

    def get_channel_exchanges(self, ctx):
        return self._exchanges.setdefault(ctx.message.channel.id, {})

    def get(self, ctx):
        return str(
            self.get_channel_exchanges(ctx).setdefault(
                _hash_ctx(ctx), ExchangeBuffer(max_size=self.max_size)
            )
        )

    def append(self, ctx, exchange: str):
        self.get_channel_exchanges(ctx).setdefault(
            _hash_ctx(ctx), ExchangeBuffer(max_size=self.max_size)
        ).append(exchange)

    def clear(self, ctx):
        key = _hash_ctx(ctx)
        if key in self.get_channel_exchanges(ctx).keys():
            del self.get_channel_exchanges()[key]


async def complete_with_openai(
    prompt: str,
    stops: list[str],
    strip=True,
    temperature=0.9,
    max_tokens=1500,
    top_p=1,
    frequency_penalty=0.2,
    presence_penalty=0.6,
):
    try:
        logger.info(f"sending the following prompt: {prompt}")

        if stops is None or len(stops) == 0:
            stops = ["\n\n"]

        response = openai.Completion.create(
            engine="davinci-instruct-beta",
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
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
            raise NoOpenAIResponse(
                "openai response didn't include answer:\n\n{response}"
            )
    except Exception as e:
        error = f"<error> something went wrong: {e}"
        logger.error(error)
        return error
