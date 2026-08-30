from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class CompletionModel(StrEnum):
    GPT_35_TURBO_INSTRUCT = "gpt-3.5-turbo-instruct"
    DAVINCI_002 = "davinci-002"
    BABBAGE_002 = "babbage-002"


DEFAULT_COMPLETION_MODEL = CompletionModel.GPT_35_TURBO_INSTRUCT


def parse_guild_ids(value: str | None) -> tuple[int, ...]:
    if value is None or not value.strip():
        raise ValueError("GUILD_IDS is required and must not be blank")
    try:
        guild_ids = tuple(int(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise ValueError(
            "GUILD_IDS must be a comma-separated list of integers"
        ) from exc
    if any(guild_id <= 0 or guild_id > 2**64 - 1 for guild_id in guild_ids):
        raise ValueError("GUILD_IDS entries must be nonzero unsigned 64-bit snowflakes")
    if len(set(guild_ids)) != len(guild_ids):
        raise ValueError("GUILD_IDS entries must be unique")
    return guild_ids


@dataclass(frozen=True)
class CompletionConfig:
    model: CompletionModel = DEFAULT_COMPLETION_MODEL
    temperature: float = 0.9
    max_tokens: int = 1500
    top_p: float = 1.0
    frequency_penalty: float = 0.2
    presence_penalty: float = 0.6
    max_concurrency: int = 2
    queue_timeout_seconds: float = 1.0
    request_timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> CompletionConfig:
        model = environ.get("OPENAI_MODEL", DEFAULT_COMPLETION_MODEL).strip()
        if not model:
            raise ValueError("OPENAI_MODEL must not be blank")
        try:
            return cls(model=CompletionModel(model))
        except ValueError as exc:
            supported = ", ".join(item.value for item in CompletionModel)
            raise ValueError(f"OPENAI_MODEL must be one of: {supported}") from exc
