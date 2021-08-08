import logging
import os

import openai

logger = logging.getLogger(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")


class NoOpenAIResponse(Exception):
    pass


def complete(prompt: str, stops: list[str], strip=True):
    try:
        logger.info(f"sending the following prompt: {prompt}")

        if stops is None or len(stops) == 0:
            stops = ["\n\n"]

        response = openai.Completion.create(
            engine="davinci-instruct-beta",
            prompt=prompt,
            temperature=0.9,
            max_tokens=1500,
            top_p=1,
            frequency_penalty=0.2,
            presence_penalty=0.6,
            stop=stops,
        )

        logger.info(f"got the following response: {response}")

        if response["choices"][0]["text"]:
            answer = response["choices"][0]["text"]
            if strip:
                return f"{answer.strip()}"
            else:
                return f"{answer}"
        else:
            raise NoOpenAIResponse("openai response didn't include answer:\n\n{response}")
    except Exception as e:
        error = f"<error> something went wrong: {e}"
        logger.error(error)
        return error


async def get_openai_completion(prompt, stops, strip=True, split_length=1994):
    response = complete(prompt, stops, strip)

    parts = []

    while len(response) > split_length:
        split_point = response[:split_length].rfind(" ")

        if split_point == -1:
            split_point = split_length

        parts.append(response[:split_point])
        response = response[split_point:]

    parts.append(response)
    return parts
