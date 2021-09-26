import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import openai
from discord.ext import commands


async def build_context(channel_id="arbitrary", author="test_runner"):
    ctx: commands.Context = AsyncMock()
    ctx.message.channel.id = channel_id
    ctx.author.display_name = author
    return ctx


class OpenAIBotTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # set up a mock to intercept the create method on openai.Completion
        # and modify its return value to that of the sample fixture below
        openai_completion_create_patcher = patch.object(openai.Completion, "create")
        self.mocked_create = openai_completion_create_patcher.start()
        self.addCleanup(openai_completion_create_patcher.stop)

        fixture = (
            '{"id": "cmpl-some-long-hash", "object": "text_completion", "created": 1234567890, '
            '"model": "if-davinci-v2", "choices": [{"text": "bar", "index": 0, "logprobs": null, '
            '"finish_reason": "stop"}]}'
        )
        self.mocked_create.return_value = json.loads(fixture)

        # set up expected environment variables
        os.environ["GUILD_IDS"] = "1234567890,9876543210"

        # mock the OpenAIBot cog
        import butterfly_bot.cogs

        bot = AsyncMock(spec=commands.Bot)
        bot.user.display_name = "bot"
        self.cog = butterfly_bot.cogs.OpenAIBot(bot=bot)

    async def test_complete_with_openai(self):
        from butterfly_bot.openai_utils import complete_with_openai

        self.assertEqual(await complete_with_openai("foo", ["\n\n"]), "bar")

    async def test_chat(self):
        """Exercise the chat functionality"""
        ctx = await build_context(author="test_runner")

        # empty before any chats
        self.assertEqual(self.cog.exchange_manager.get(ctx), "")

        # contains message and response after chat exchange
        await self.cog.chat(self.cog, ctx, "hello")
        self.assertEqual(
            self.cog.exchange_manager.get(ctx), ("test_runner: hello\n" "bot: bar\n")
        )

        # second exchange gets appended
        await self.cog.chat(self.cog, ctx, "me again")
        self.assertEqual(
            self.cog.exchange_manager.get(ctx),
            (
                "test_runner: hello\n"
                "bot: bar\n"
                "\n"
                "test_runner: me again\n"
                "bot: bar\n"
            ),
        )

        # empty again after flush
        await self.cog.flush_chat_history(self.cog, ctx)
        self.assertEqual(self.cog.exchange_manager.get(ctx), "")


if __name__ == "__main__":
    unittest.main()
