import json

from prompts.planner_prompt import planner_prompt
from utils.llm import generate


def create_plan(user_request: str) -> str:
    prompt = planner_prompt(user_request)

    text = generate(prompt)

    if text.startswith("```json"):
        text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)

if __name__ == "__main__":
    plan = create_plan(
        "Create a FastAPI project called student_api"
    )

    print(json.dumps(plan, indent=2))