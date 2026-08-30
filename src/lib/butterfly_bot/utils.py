from collections.abc import Iterable, Sequence
from typing import Any

from discord import Interaction

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
    ctx = options.ctx
    if ctx is None:
        raise RuntimeError("Discord response has no context")
    if options.respond_to is None and getattr(ctx, "message", None) is not None:
        options.respond_to = ctx.message
    async for part in paginate(options, responses):
        last_message = await send_message(options, part)
        if options.response_target is ResponseTarget.LAST_MESSAGE:
            options.respond_to = last_message


async def send_message(options: DiscordResponseOptions, content: str) -> Any:
    """sends a Discord message according to the underlying API's context semantics"""
    ctx = options.ctx
    if ctx is None:
        raise RuntimeError("Discord response has no context")
    last_message: Any
    if isinstance(ctx, Interaction):
        if ctx.response.is_done():
            last_message = await ctx.followup.send(content=content, wait=True)
        else:
            await ctx.response.send_message(content=content)
            last_message = await ctx.original_response()
    else:
        kwargs: dict[str, Any] = {"content": content, "mention_author": True}
        if options.respond_to is not None:
            kwargs["reference"] = options.respond_to
        last_message = await ctx.channel.send(**kwargs)
    return last_message


def pretty_time_delta(seconds: int):
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return f"{days}d{hours}h{minutes}m{seconds}s"
    elif hours > 0:
        return f"{hours}h{minutes}m{seconds}s"
    elif minutes > 0:
        return f"{minutes}m{seconds}s"
    else:
        return f"{seconds}s"


def split_string(string: str, length: int) -> tuple[str, str]:
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
