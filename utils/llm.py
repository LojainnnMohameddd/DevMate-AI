import os
import re
import time

from dotenv import load_dotenv
from groq import (
    APITimeoutError,
    APIConnectionError,
    Groq,
    RateLimitError,
)

load_dotenv()

API_KEYS = [
    os.getenv("GROQ_API_KEY"),
    os.getenv("GROQ_API_KEY_2"),
]

API_KEYS = [key for key in API_KEYS if key]

DEFAULT_MODEL = "openai/gpt-oss-20b"


def strip_thinking(text: str) -> str:
    return re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL,
    ).strip()


def clean_response(text: str) -> str:
    """
    Remove reasoning blocks and markdown code fences.
    """

    text = strip_thinking(text)

    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines)

    return text.strip()


def generate(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
    temperature: float = 0.2,
    return_meta: bool = False,
):
    """
    Generates a response from the configured model.

    return_meta=False:
        Returns only the generated content.

    return_meta=True:
        Returns:
        {
            "content": str,
            "finish_reason": str,
            "reasoning": str | None,
        }
    """

    last_error = None

    for api_key in API_KEYS:

        client = Groq(
            api_key=api_key,
            timeout=300,
        )

        for attempt in range(3):

            try:

                create_kwargs = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    "temperature": temperature,
                }

                if max_tokens is not None:
                    create_kwargs["max_tokens"] = max_tokens

                if (
                    reasoning_effort is not None
                    and model.startswith("openai/")
                ):
                    create_kwargs["reasoning_effort"] = reasoning_effort

                response = client.chat.completions.create(
                    **create_kwargs
                )

                print("\n===== RESPONSE =====")
                print(response)
                print("====================")

                choice = response.choices[0]
                message = choice.message

                print("\n===== MESSAGE =====")
                print(message)
                print("===================")

                content = clean_response(
                    message.content or ""
                )

                if return_meta:

                    return {
                        "content": content,
                        "finish_reason": choice.finish_reason,
                        "reasoning": getattr(
                            message,
                            "reasoning",
                            None,
                        ),
                    }

                return content

            except RateLimitError as e:

                last_error = e

                if attempt < 2:

                    print(
                        f"Rate limit reached. "
                        f"Retrying in 60 seconds... "
                        f"({attempt + 1}/3)"
                    )

                    time.sleep(60)

                else:

                    print(
                        "Switching to next API key..."
                    )

            except (
                APITimeoutError,
                APIConnectionError,
            ) as e:

                last_error = e

                if attempt < 2:

                    print(
                        f"Connection timeout. "
                        f"Retrying in 10 seconds... "
                        f"({attempt + 1}/3)"
                    )

                    time.sleep(10)

                else:

                    print(
                        "Switching to next API key..."
                    )

    raise last_error