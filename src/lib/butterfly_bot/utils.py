from typing import Iterable, Optional, Sequence, Tuple

from discord import Message
from discord_slash.context import InteractionContext

from .options import DiscordResponseOptions, PaginateOptions
from .response import ResponseTarget


async def send_response(
    options: DiscordResponseOptions,
    response: str,
) -> None:
    await send_responses(options, [response])


async def send_responses(
    options: DiscordResponseOptions,
    responses: Sequence[str],
) -> None:
    if options.respond_to is None and options.ctx.message is not None:
        options.respond_to = options.ctx.message
    async for part in paginate(options, responses):
        last_message = await send_message(options, part)
        if options.response_target is ResponseTarget.LAST_MESSAGE:
            options.respond_to = last_message


async def send_message(
    options: DiscordResponseOptions, content: str
) -> Optional[Message]:
    """sends a Discord message according to the underlying API's context semantics"""
    if isinstance(options.ctx, InteractionContext):
        last_message = await options.ctx.send(content=content)
    else:
        last_message = await options.ctx.channel.send(
            content=content, reference=options.respond_to, mention_author=True
        )
    return last_message


def pretty_time_delta(seconds: int):
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return "%dd%dh%dm%ds" % (days, hours, minutes, seconds)
    elif hours > 0:
        return "%dh%dm%ds" % (hours, minutes, seconds)
    elif minutes > 0:
        return "%dm%ds" % (minutes, seconds)
    else:
        return "%ds" % (seconds,)


def split_string(string: str, length: int) -> Tuple[str, str]:
    """splits a string on the word boundary right before the specified length"""
    split_point = string[:length].rfind(" ")

    if split_point == -1:
        split_point = length

    return string[:split_point], string[split_point + 1 :]  # noqa: E203


def get_splits(options: PaginateOptions, responses: Sequence[str]) -> Iterable[str]:
    for string in responses:
        while options.paginate and len(string) > options.split_length:
            part, string = split_string(string, options.split_length)
            yield part
        yield string


async def paginate(options: PaginateOptions, responses: Sequence[str]):
    for split in get_splits(options, responses):
        if options.code_block:
            yield f"```{split}```"
        else:
            yield split
