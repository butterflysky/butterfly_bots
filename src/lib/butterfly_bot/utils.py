from typing import Sequence

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
    if options.paginate:
        new_responses = []
        for response in responses:
            new_responses.extend(await paginate(options, response))
        responses = new_responses
    if options.respond_to is None:
        if options.ctx.message is not None:
            options.respond_to = options.ctx.message
    for part in responses:
        if options.code_block:
            part = f"```{part}```"
        if isinstance(options.ctx, InteractionContext):
            last_message = await options.ctx.send(content=part)
        else:
            last_message = await options.ctx.channel.send(
                content=part, reference=options.respond_to, mention_author=True
            )
        if options.response_target is ResponseTarget.LAST_MESSAGE:
            options.respond_to = last_message


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


async def paginate(options: PaginateOptions, response: str):
    parts = []
    while len(response) > options.split_length:
        split_point = response[: options.split_length].rfind(" ")

        if split_point == -1:
            split_point = options.split_length

        parts.append(response[:split_point])
        response = response[split_point + 1 :]  # noqa: E203
    parts.append(response)
    return parts
