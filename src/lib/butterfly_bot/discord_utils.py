import contextlib
import re

from discord.ext import commands
from discord.ext.commands import MemberNotFound


class MemberNameConverter(commands.MemberConverter):
    async def convert(self, ctx, argument):
        if re.match(r"<@!?([0-9]{15,20})>$", argument):
            with contextlib.suppress(MemberNotFound):
                member = await super().convert(ctx, argument)
                return member.display_name
        return argument
