import json

from prompts.coder_prompt import coder_prompt
from utils.llm import generate


def generate_project(user_request: str, plan: list) -> dict:
    prompt = coder_prompt(
        user_request=user_request,
        plan=plan
    )

    response = generate(prompt)

    print("\n========== RAW RESPONSE ==========\n")
    print(response)
    print("\n==================================\n")

    response = response.strip()

    # Remove markdown fences if present
    if response.startswith("```json"):
        response = (
            response
            .removeprefix("```json")
            .removesuffix("```")
            .strip()
        )

    # Escape raw newlines inside JSON strings
    response = response.replace("\r\n", "\n")

    if response.startswith("```json"):
        response = (
            response
            .removeprefix("```json")
            .removesuffix("```")
            .strip()
        )

    try:
        return json.loads(response)

    except json.JSONDecodeError as e:
        print("=" * 80)
        print("JSON ERROR:")
        print(e)
        print("=" * 80)

        pos = e.pos

        start = max(0, pos - 300)
        end = min(len(response), pos + 300)

        print(response[start:end])

        raise


if __name__ == "__main__":

    sample_plan = [
        {
            "tool": "create_file",
            "args": {
                "file_path": "app/main.py"
            }
        },
        {
            "tool": "create_file",
            "args": {
                "file_path": "requirements.txt"
            }
        }
    ]

    project = generate_project(
        "Create a FastAPI CRUD API for students",
        sample_plan
    )

    print(json.dumps(project, indent=2))