from groq import Groq
import json

from prompts.fixer_prompt import fixer_prompt

client = Groq()


def fix_project(
    user_request,
    plan,
    project,
    review,
    execution,
):

    prompt = fixer_prompt(
        user_request,
        plan,
        project,
        review,
        execution,
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0
    )

    text = response.choices[0].message.content

    print("\n========== FIX RESPONSE ==========\n")
    print(text)
    print("\n==================================\n")

    text = text.strip()

    if text.startswith("```json"):
        text = (
            text
            .removeprefix("```json")
            .removesuffix("```")
            .strip()
        )

    return json.loads(text)