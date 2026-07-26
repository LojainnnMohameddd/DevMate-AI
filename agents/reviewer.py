import json

from prompts.reviewer_prompt import reviewer_prompt
from utils.llm import generate


def review_project(user_request, plan, project, validation):

    prompt = reviewer_prompt(
        user_request,
        plan,
        project,
        validation
    )

    response = generate(prompt)

    if response.startswith("```json"):
        response = response.replace("```json", "").replace("```", "").strip()

    return json.loads(response)