from enum import Enum


class ResponseTarget(Enum):
    ORIGINAL_MESSAGE = 1
    LAST_MESSAGE = 2


async def send_responses(ctx, parts, code_block=True, response_target=ResponseTarget.LAST_MESSAGE):
    respond_to = ctx.message
    for part in parts:
        if code_block:
            part = f"```{part}```"
        last_message = await ctx.send(content=part,
                                      reference=respond_to,
                                      mention_author=True)
        if response_target is ResponseTarget.LAST_MESSAGE:
            respond_to = last_message
