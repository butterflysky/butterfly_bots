import re

from discord.ext import commands
from discord.ext.commands import MemberNotFound


class MemberNameConverter(commands.MemberConverter):
    async def convert(self, ctx, argument):
        match = re.match(r'<@!?([0-9]{15,20})>$', argument)
        if match:
            try:
                member = await super().convert(ctx, argument)
                return member.display_name
            except MemberNotFound:
                return argument
        else:
            return argument
