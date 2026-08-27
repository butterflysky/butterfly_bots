import asyncio
import importlib
import logging
import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from butterfly_bot.cogs import OpenAIBot
from butterfly_bot.config import CompletionConfig, parse_guild_ids
from butterfly_bot.openai_utils import (
    CompletionGate,
    CompletionOverloaded,
    CompletionTimedOut,
    complete_with_openai,
)
from discord.ext import commands
from openai import AsyncOpenAI


def context(channel_id: int = 42, author: str = "test_runner") -> SimpleNamespace:
    channel = SimpleNamespace(id=channel_id, send=AsyncMock())
    message = SimpleNamespace(channel=channel)
    return SimpleNamespace(
        message=message,
        channel=channel,
        author=SimpleNamespace(display_name=author),
        send=AsyncMock(),
    )


def client_with_text(text: str = "bar") -> MagicMock:
    client = MagicMock()
    client.completions.create = AsyncMock(
        return_value=SimpleNamespace(choices=[SimpleNamespace(text=text)])
    )
    return client


@pytest.mark.asyncio
async def test_completion_uses_exact_model_and_parameters() -> None:
    client = client_with_text(" bar ")
    config = CompletionConfig()

    result = await complete_with_openai(
        client, CompletionGate(config), config, "foo", ["STOP"]
    )

    assert result == "bar"
    client.completions.create.assert_awaited_once_with(
        model="gpt-3.5-turbo-instruct",
        prompt="foo",
        temperature=0.9,
        max_tokens=1500,
        top_p=1.0,
        frequency_penalty=0.2,
        presence_penalty=0.6,
        stop=["STOP"],
    )


@pytest.mark.asyncio
async def test_chat_preserves_five_exchange_channel_memory() -> None:
    bot = MagicMock(spec=commands.Bot)
    bot.user.display_name = "bot"
    cog = OpenAIBot(bot, client_with_text(), CompletionConfig())
    ctx = context()

    for number in range(6):
        await cog.chat.callback(cog, ctx, f"message-{number}")

    history = cog.exchange_manager.get(ctx)
    assert "message-0" not in history
    assert history.count("test_runner:") == 5
    assert "message-5" in history


@pytest.mark.asyncio
async def test_prefix_history_sends_one_complete_response() -> None:
    bot = MagicMock(spec=commands.Bot)
    bot.user.display_name = "bot"
    cog = OpenAIBot(bot, client_with_text(), CompletionConfig())
    ctx = context()
    cog.exchange_manager.append(ctx, "test_runner: hello\nbot: bar\n")

    with patch("butterfly_bot.cogs.send_response", new=AsyncMock()) as sender:
        await cog.show_chat_history.callback(cog, ctx)

    sender.assert_awaited_once()
    assert sender.await_args.args[1] == "test_runner: hello\nbot: bar\n"


def test_config_parsing_and_model_override() -> None:
    assert parse_guild_ids("123, 456") == (123, 456)
    assert parse_guild_ids(str(2**64 - 1)) == (2**64 - 1,)
    assert CompletionConfig.from_env({}).model == "gpt-3.5-turbo-instruct"
    assert CompletionConfig.from_env({"OPENAI_MODEL": "davinci-002"}).model == (
        "davinci-002"
    )
    with pytest.raises(ValueError, match="must be one of"):
        CompletionConfig.from_env({"OPENAI_MODEL": "gpt-4o"})
    with pytest.raises(ValueError, match="comma-separated"):
        parse_guild_ids("[123,456]")
    with pytest.raises(ValueError, match="required"):
        parse_guild_ids(None)
    with pytest.raises(ValueError, match="required"):
        parse_guild_ids("  ")
    with pytest.raises(ValueError, match="nonzero unsigned 64-bit"):
        parse_guild_ids("0")
    with pytest.raises(ValueError, match="nonzero unsigned 64-bit"):
        parse_guild_ids("-1")
    with pytest.raises(ValueError, match="nonzero unsigned 64-bit"):
        parse_guild_ids(str(2**64))
    with pytest.raises(ValueError, match="unique"):
        parse_guild_ids("123,123")


def test_bot_rejects_programmatic_global_sync() -> None:
    from adonis_blue.adonis_blue import build_bot

    with pytest.raises(ValueError, match="at least one guild"):
        build_bot(client_with_text(), CompletionConfig(), ())


def test_import_is_logging_inert_and_startup_enables_info() -> None:
    import adonis_blue.adonis_blue as app

    app.logger.setLevel(logging.WARNING)
    with patch.object(logging, "basicConfig") as basic_config:
        importlib.reload(app)
        basic_config.assert_not_called()
        assert app.logger.level == logging.WARNING

        app.logger.setLevel(logging.NOTSET)
        app.configure_logging({})

    basic_config.assert_called_once_with(level=logging.INFO)
    assert app.logger.getEffectiveLevel() == logging.INFO


def test_startup_logging_level_is_validated() -> None:
    import adonis_blue.adonis_blue as app

    with patch.object(logging, "basicConfig") as basic_config:
        app.configure_logging({"LOG_LEVEL": "debug"})
    basic_config.assert_called_once_with(level=logging.INFO)
    assert app.logger.getEffectiveLevel() == logging.DEBUG
    with pytest.raises(ValueError, match="invalid LOG_LEVEL"):
        app.configure_logging({"LOG_LEVEL": "verbose-ish"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "level_name", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
)
async def test_log_levels_never_expose_provider_payloads_or_api_keys(
    level_name, caplog
) -> None:
    import adonis_blue.adonis_blue as app

    prompt_sentinel = "PRIVATE-PROMPT-SENTINEL"
    key_sentinel = "sk-private-api-key-sentinel"

    def completion_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "cmpl-test",
                "object": "text_completion",
                "created": 0,
                "model": "gpt-3.5-turbo-instruct",
                "choices": [
                    {
                        "text": "PRIVATE-RESPONSE-SENTINEL",
                        "index": 0,
                        "logprobs": None,
                        "finish_reason": "stop",
                    }
                ],
            },
            request=request,
        )

    transport = httpx.MockTransport(completion_response)
    http_client = httpx.AsyncClient(transport=transport)
    client = AsyncOpenAI(api_key=key_sentinel, http_client=http_client)
    config = CompletionConfig()
    caplog.clear()
    app.configure_logging({"LOG_LEVEL": level_name})
    app.logger.debug("owned debug receipt")
    try:
        await complete_with_openai(
            client,
            CompletionGate(config),
            config,
            prompt_sentinel,
            ["STOP"],
        )
    finally:
        await client.close()

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert prompt_sentinel not in messages
    assert "PRIVATE-RESPONSE-SENTINEL" not in messages
    assert key_sentinel not in messages
    assert ("owned debug receipt" in messages) is (level_name == "DEBUG")
    assert logging.getLogger().level >= logging.INFO
    for namespace in app.DEPENDENCY_LOGGERS:
        assert logging.getLogger(namespace).level >= logging.INFO


@pytest.mark.asyncio
async def test_production_entrypoint_wires_prefix_and_slash_commands() -> None:
    from adonis_blue.adonis_blue import build_bot, version_command

    client = client_with_text()
    bot = build_bot(client, CompletionConfig(), (123,))
    bot.tree.sync = AsyncMock()
    await bot.setup_hook()

    assert {"chat", "story", "tarot", "code", "show_chat_history", "version"} <= set(
        bot.all_commands
    )
    assert {command.name for command in bot.tree.get_commands()} >= {
        "story",
        "show_chat_history",
        "flush_chat_history",
    }
    assert bot.intents.message_content is True
    bot.tree.sync.assert_awaited_once()
    version_context = SimpleNamespace(send=AsyncMock())
    await version_command.callback(version_context)
    project = tomllib.loads(Path("pyproject.toml").read_text())
    version_context.send.assert_awaited_once_with(project["project"]["version"])
    await bot.close()


@pytest.mark.asyncio
async def test_entrypoint_closes_clients_when_discord_fails(monkeypatch) -> None:
    import adonis_blue.adonis_blue as app

    monkeypatch.setenv("DISCORD_API_KEY", "discord-test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-token")
    monkeypatch.setenv("GUILD_IDS", "123")
    fake_client = MagicMock(close=AsyncMock())
    fake_bot = MagicMock(
        start=AsyncMock(side_effect=RuntimeError("Discord unavailable")),
        close=AsyncMock(),
    )

    with (
        patch.object(app, "AsyncOpenAI", return_value=fake_client) as client_factory,
        patch.object(app, "build_bot", return_value=fake_bot),
    ):
        with pytest.raises(RuntimeError, match="Discord unavailable"):
            await app.run()

    client_factory.assert_called_once_with(
        api_key="openai-test-token", timeout=60.0, max_retries=2
    )
    fake_bot.close.assert_awaited_once_with()
    fake_client.close.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "close_error", [RuntimeError("bot close failed"), asyncio.CancelledError()]
)
async def test_cleanup_always_closes_openai_when_bot_close_fails(close_error) -> None:
    from adonis_blue.adonis_blue import run_with_cleanup

    fake_bot = MagicMock(start=AsyncMock(), close=AsyncMock(side_effect=close_error))
    fake_client = MagicMock(close=AsyncMock())

    with pytest.raises(type(close_error)):
        await run_with_cleanup(fake_bot, fake_client, "discord-test-token")

    fake_client.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_original_run_error_wins_over_cleanup_errors() -> None:
    from adonis_blue.adonis_blue import run_with_cleanup

    original = RuntimeError("Discord failed")
    fake_bot = MagicMock(
        start=AsyncMock(side_effect=original),
        close=AsyncMock(side_effect=ValueError("bot close failed")),
    )
    fake_client = MagicMock(close=AsyncMock(side_effect=OSError("client close failed")))

    with pytest.raises(RuntimeError, match="Discord failed") as raised:
        await run_with_cleanup(fake_bot, fake_client, "discord-test-token")

    assert raised.value is original
    fake_bot.close.assert_awaited_once_with()
    fake_client.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_completion_gate_rejects_overload_and_releases_on_cancellation() -> None:
    entered = asyncio.Event()
    blocker = asyncio.Event()

    async def blocked_create(**kwargs):
        entered.set()
        await blocker.wait()

    client = MagicMock()
    client.completions.create = AsyncMock(side_effect=blocked_create)
    config = CompletionConfig(max_concurrency=1, queue_timeout_seconds=0.01)
    gate = CompletionGate(config)
    first = asyncio.create_task(
        complete_with_openai(client, gate, config, "first", ["STOP"])
    )
    await entered.wait()

    with pytest.raises(CompletionOverloaded):
        await complete_with_openai(client, gate, config, "second", ["STOP"])

    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    client.completions.create = AsyncMock(
        return_value=SimpleNamespace(choices=[SimpleNamespace(text="recovered")])
    )
    assert (
        await complete_with_openai(client, gate, config, "third", ["STOP"])
        == "recovered"
    )


@pytest.mark.asyncio
async def test_deferred_story_failure_gets_terminal_response() -> None:
    bot = MagicMock(spec=commands.Bot)
    cog = OpenAIBot(bot, client_with_text(), CompletionConfig())
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    cog._story_stub = AsyncMock(side_effect=CompletionTimedOut("timeout"))

    await cog.story_slash.callback(cog, interaction, "a lighthouse")

    interaction.response.defer.assert_awaited_once_with()
    interaction.followup.send.assert_awaited_once_with(
        "I couldn't finish that story request. Please try again shortly.",
        ephemeral=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"stops": "not-json"}, "bad stops"),
        ({"prompt_prelude": "Story about {missing}"}, "bad prelude"),
        ({"prompt_prelude": "Story {}"}, "positional prelude"),
    ],
)
async def test_deferred_story_local_prompt_errors_get_terminal_response(
    kwargs, message
) -> None:
    bot = MagicMock(spec=commands.Bot)
    cog = OpenAIBot(bot, client_with_text(), CompletionConfig())
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    await cog.story_slash.callback(cog, interaction, message, **kwargs)

    interaction.response.defer.assert_awaited_once_with()
    interaction.followup.send.assert_awaited_once_with(
        "I couldn't finish that story request. Please try again shortly.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_deferred_story_preserves_cancellation() -> None:
    bot = MagicMock(spec=commands.Bot)
    cog = OpenAIBot(bot, client_with_text(), CompletionConfig())
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    cog._story_stub = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await cog.story_slash.callback(cog, interaction, "a lighthouse")
    interaction.followup.send.assert_not_awaited()


def test_container_context_and_version_have_single_safe_authority() -> None:
    dockerignore = Path(".dockerignore").read_text().splitlines()
    dockerfile = Path("Dockerfile").read_text()
    compose = Path("docker-compose.yml").read_text()
    project = tomllib.loads(Path("pyproject.toml").read_text())

    assert "**/.env" in dockerignore
    assert ".git" in dockerignore
    assert "COPY src/adonis_blue ." not in dockerfile
    assert "COPY src/adonis_blue/.env" not in dockerfile
    assert "--no-install-project" in dockerfile
    assert "chown -R" not in dockerfile
    docker_lines = dockerfile.splitlines()
    dependency_sync = docker_lines.index(
        "RUN uv sync --frozen --no-dev --no-install-project"
    )
    app_init_copy = docker_lines.index(
        "COPY src/adonis_blue/__init__.py ./src/adonis_blue/__init__.py"
    )
    app_main_copy = docker_lines.index(
        "COPY src/adonis_blue/adonis_blue.py ./src/adonis_blue/adonis_blue.py"
    )
    project_sync = docker_lines.index("RUN uv sync --frozen --no-dev")
    read_only = docker_lines.index(
        "RUN useradd --create-home adonis_blue && chmod -R a-w /app"
    )
    assert dependency_sync < app_init_copy <= app_main_copy < project_sync < read_only
    assert docker_lines[-1] == (
        'ENTRYPOINT ["/app/.venv/bin/python", "-m", "adonis_blue.adonis_blue"]'
    )
    assert project["project"]["version"] not in compose
