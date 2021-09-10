import json
from typing import Dict, Union, Sequence, Optional, Any

from discord import Message
from discord.ext import commands
from discord_slash import SlashContext, MenuContext
from discord_slash.context import InteractionContext

from .response import ResponseTarget

DiscordContext = Union[commands.Context, SlashContext, MenuContext, InteractionContext]


class Options:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __copy__(self):
        return self.__class__(**self.__dict__)


class OptionsConsumer:
    class OptionError(AttributeError):
        pass

    def __init__(self, opt: Options = Options(), **kwargs):
        self.init_options(opt, kwargs)

    def init_options(self, options: Options, kwargs: Dict):
        options.__dict__.update(kwargs)
        for k, v in options.__dict__.items():
            if not hasattr(self.__class__, k):
                raise self.OptionError("invalid option " + k)
            setattr(self, k, v)

    def with_attr(self, key: str, value: Optional[Any]):
        setattr(self, key, value)
        return self


class CompletionOptions(OptionsConsumer):
    engine: str = ("davinci-instruct-beta",)
    strip_response: bool = (True,)
    temperature: float = (0.9,)
    max_tokens: int = (1500,)
    top_p: float = (1,)
    frequency_penalty: float = (0.2,)
    presence_penalty: float = (0.6,)


class PaginateOptions(OptionsConsumer):
    code_block: bool = True
    split_length: int = 1994


class ResponseOptions(PaginateOptions):
    ctx: DiscordContext = None
    respond_to: Optional[Message] = None
    response_target: ResponseTarget = ResponseTarget.LAST_MESSAGE
    paginate: bool = False


def get_default_story_prompt_prelude():
    return (
        "You're a bestselling author. Write a short story about the following prompt:\n\n"
        "Prompt: {prompt}\n"
        "Story:"
    )


class StoryOptions(CompletionOptions, ResponseOptions):
    ctx: DiscordContext = None
    prompt: str = ""
    prompt_prelude: str = get_default_story_prompt_prelude()
    stops: Sequence[str] = ["\n\n"]

    def __init__(self, opt: Options = Options(), **kwargs):
        def process_str_arg(key: str, transform=(lambda x: x)):
            arg = kwargs.get(key)
            if arg is not None and len(arg) > 0:
                kwargs[key] = transform(arg)

        process_str_arg("stops", lambda x: json.loads(x))

        super().__init__(opt, **kwargs)
