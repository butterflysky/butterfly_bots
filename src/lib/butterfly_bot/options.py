import contextlib
import json
import logging
from typing import Any, Callable, Dict, Optional, Sequence, Union

from discord import Message
from discord.ext import commands
from discord_slash import MenuContext, SlashContext
from discord_slash.context import InteractionContext

from .response import ResponseTarget

DiscordContext = Union[commands.Context, SlashContext, MenuContext, InteractionContext]
OptionTransformers = Dict[str, Callable]

logger = logging.getLogger(__name__)


class Options:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __copy__(self):
        return self.__class__(**self.__dict__)


class OptionsConsumer:
    _transformers: Optional[OptionTransformers] = None

    class OptionError(AttributeError):
        pass

    def __init__(self, options: Optional[Options] = None, **kwargs):
        if "_transformers" in kwargs:
            logger.warning(
                "_transformers is a reserved field in Options - ignoring value passed in constructor"
            )
            del kwargs["_transformers"]

        for k, v in self._transformers.items():
            with contextlib.suppress(KeyError):
                kwargs[k] = v(kwargs[k])

        if options is None:
            options = Options()

        options.__dict__.update(kwargs)
        for k, v in options.__dict__.items():
            if not hasattr(self.__class__, k):
                raise self.OptionError("invalid option " + k)
            setattr(self, k, v)

    def __str__(self):
        return f"{self.__class__.__name__}: {self.__dict__}"

    def with_attr(self, key: str, value: Optional[Any]):
        if key in self._transformers:
            value = self._transformers[key](value)
        setattr(self, key, value)
        return self


class PaginateOptions(OptionsConsumer):
    code_block: bool = True
    paginate: bool = False
    split_length: int = 1994


class DiscordResponseOptions(PaginateOptions):
    ctx: DiscordContext = None
    respond_to: Optional[Message] = None
    response_target: ResponseTarget = ResponseTarget.LAST_MESSAGE


class CompletionOptions(OptionsConsumer):
    engine: str = ("davinci-instruct-beta",)
    strip_response: bool = (True,)
    temperature: float = (0.9,)
    max_tokens: int = (1500,)
    top_p: float = (1,)
    frequency_penalty: float = (0.2,)
    presence_penalty: float = (0.6,)
    prompt: str = ""
    stops: Sequence[str] = ["\n\n"]

    _transformers: OptionTransformers = {"stops": lambda x: json.loads(x)}


class DiscordCompletionOptions(DiscordResponseOptions, CompletionOptions):
    pass


class StoryOptions(DiscordCompletionOptions):
    prompt_prelude: str = (
        "You're a bestselling author. Write a short story about the following prompt:\n\n"
        "Prompt: {prompt}\n"
        "Story:"
    )
