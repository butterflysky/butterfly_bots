import asyncio
import logging
from collections import deque
from collections.abc import Sequence
from enum import Enum
from typing import Any

from openai import AsyncOpenAI

from .config import CompletionConfig

logger = logging.getLogger(__name__)


class NoOpenAIResponse(Exception):
    pass


class CompletionOverloaded(Exception):
    pass


class CompletionTimedOut(Exception):
    pass


class CompletionGate:
    def __init__(self, config: CompletionConfig) -> None:
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._queue_timeout = config.queue_timeout_seconds
        self._request_timeout = config.request_timeout_seconds

    async def create(self, client: AsyncOpenAI, **kwargs: Any) -> Any:
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(), timeout=self._queue_timeout
            )
        except TimeoutError as exc:
            raise CompletionOverloaded("completion capacity is busy") from exc
        try:
            async with asyncio.timeout(self._request_timeout):
                return await client.completions.create(**kwargs)
        except TimeoutError as exc:
            raise CompletionTimedOut("completion request timed out") from exc
        finally:
            self._semaphore.release()


class ExchangeKey(Enum):
    CHANNEL = 1
    MENTIONS = 2


class ExchangeBuffer:
    def __init__(self, max_size: int = 5, joiner: str = "\n"):
        self.exchanges: deque[str] = deque()
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
            f"joiner: {(self.joiner,)}"
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
        self._exchanges: dict[int, dict[frozenset[int], ExchangeBuffer]] = {}

    def get_channel_exchanges(self, ctx):
        if ctx.message:
            return self._exchanges.setdefault(ctx.message.channel.id, {})
        if ctx.channel:
            return self._exchanges.setdefault(ctx.channel.id, {})

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
        if key in self.get_channel_exchanges(ctx):
            del self.get_channel_exchanges(ctx)[key]


async def complete_with_openai(
    client: AsyncOpenAI,
    gate: CompletionGate,
    config: CompletionConfig,
    prompt: str,
    stops: Sequence[str],
    strip_response=True,
):
    logger.debug(
        "sending completion with model=%s prompt_chars=%d", config.model, len(prompt)
    )

    if stops is None or len(stops) == 0:
        stops = ["\n\n"]

    response: Any = await gate.create(
        client,
        model=config.model,
        prompt=prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        top_p=config.top_p,
        frequency_penalty=config.frequency_penalty,
        presence_penalty=config.presence_penalty,
        stop=list(stops),
    )

    logger.debug("completion received with model=%s", config.model)

    if response.choices and response.choices[0].text:
        answer = response.choices[0].text
        if strip_response:
            return f"{answer.strip()}"
        else:
            return f"{answer}"
    else:
        raise NoOpenAIResponse("OpenAI response did not include completion text")
