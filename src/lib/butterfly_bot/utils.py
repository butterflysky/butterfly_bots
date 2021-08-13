from enum import Enum


class ResponseTarget(Enum):
    ORIGINAL_MESSAGE = 1
    LAST_MESSAGE = 2


async def send_responses(ctx, parts, code_block=True, response_target=ResponseTarget.LAST_MESSAGE):
    respond_to = ctx.message
    if isinstance(parts, str):
        parts = [parts]
    for part in parts:
        if code_block:
            part = f"```{part}```"
        last_message = await ctx.send(content=part,
                                      reference=respond_to,
                                      mention_author=True)
        if response_target is ResponseTarget.LAST_MESSAGE:
            respond_to = last_message


def pretty_time_delta(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '%dd%dh%dm%ds' % (days, hours, minutes, seconds)
    elif hours > 0:
        return '%dh%dm%ds' % (hours, minutes, seconds)
    elif minutes > 0:
        return '%dm%ds' % (minutes, seconds)
    else:
        return '%ds' % (seconds,)
