import json

from prompts.reviewer_prompt import reviewer_prompt
from utils.llm import generate
from utils.repetition import find_repetition_loop

REVIEW_MODEL = "openai/gpt-oss-120b"


def _strip_json_fences(text: str):
    text = text.strip()

    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()

    return text


def summarize_project(project):
    files = []

    for file in project["files"]:
        files.append({
            "path": file["path"],
            "lines": len(file["content"].splitlines()),
            "imports": [
                line.strip()
                for line in file["content"].splitlines()
                if line.startswith(("import ", "from "))
            ],
        })

    return {"files": files}


def review_project(user_request, plan, project, validation, max_retries: int = 3):

    prompt = reviewer_prompt(
        user_request,
        plan,
        summarize_project(project),
        validation
    )

    tokens = 1024
    temperature = 0

    for attempt in range(max_retries + 1):

        result = generate(
            prompt,
            model=REVIEW_MODEL,
            max_tokens=tokens,
            reasoning_effort="low",
            temperature=temperature,
            return_meta=True,
        )

        content = result["content"].strip()
        content = _strip_json_fences(content)

        finish_reason = result["finish_reason"]
        reasoning = result.get("reasoning") or ""

        print(f"\n===== REVIEW (attempt {attempt + 1}) =====")
        print(
            f"finish_reason={finish_reason}, "
            f"tokens_budget={tokens}, "
            f"temperature={temperature}"
        )
        print(f"content_len={len(content)}")
        print("=" * 60)

        if finish_reason == "length" and not content:
            loop_detected = find_repetition_loop(reasoning) is not None

            print(
                f"[reviewer] Empty content after reasoning exhausted "
                f"tokens (repetition_loop_detected={loop_detected}). "
                f"Retrying with higher temperature..."
            )

            temperature = min(temperature + 0.3, 0.9)
            tokens = int(tokens * 1.3)
            continue

        try:
            return json.loads(content)

        except json.JSONDecodeError:

            print("[reviewer] Invalid JSON returned, retrying...")

            temperature = min(temperature + 0.2, 0.9)

            continue

    raise RuntimeError(
        f"Reviewer failed to produce a valid review after {max_retries + 1} attempts."
    )