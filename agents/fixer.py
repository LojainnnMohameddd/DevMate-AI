import json

from prompts.fixer_prompt import (
    fixer_diagnosis_prompt,
    fixer_file_prompt,
)
from utils.llm import generate
from utils.repetition import find_repetition_loop


FIXER_MODEL = "openai/gpt-oss-120b"


def _strip_code_fences(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines)

    return text.strip()


def _strip_json_fences(text: str) -> str:
    text = text.strip()

    if text.startswith("```json"):
        text = (
            text
            .removeprefix("```json")
            .removesuffix("```")
            .strip()
        )

    elif text.startswith("```"):
        text = (
            text
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )

    return text


def _diagnose(
    user_request,
    plan,
    project,
    review,
    execution,
    max_retries: int = 2,
) -> dict:

    tokens = 3000
    temperature = 0

    for attempt in range(max_retries + 1):

        prompt = fixer_diagnosis_prompt(
            user_request,
            plan,
            project,
            review,
            execution,
        )

        result = generate(
            prompt,
            model=FIXER_MODEL,
            max_tokens=tokens,
            reasoning_effort="medium",
            temperature=temperature,
            return_meta=True,
        )

        text = _strip_json_fences(result["content"])
        finish_reason = result["finish_reason"]

        print("\n========== DIAGNOSIS ==========\n")
        print(text)
        print(
            f"finish_reason={finish_reason}, "
            f"tokens_budget={tokens}, "
            f"temperature={temperature}"
        )
        print("================================\n")

        if finish_reason == "length":

            loop_offset = find_repetition_loop(text)

            if loop_offset is not None:

                print(
                    "[fixer] Diagnosis entered a repetition loop. "
                    "Retrying with higher temperature..."
                )

                temperature = min(temperature + 0.4, 0.8)
                continue

            print(
                "[fixer] Diagnosis truncated. "
                "Retrying with more tokens..."
            )

            tokens = int(tokens * 1.75)
            continue

        try:
            return json.loads(text)

        except json.JSONDecodeError:

            print(
                "[fixer] Invalid diagnosis JSON. "
                "Retrying..."
            )

            continue

    raise RuntimeError(
        "Fixer diagnosis failed after "
        f"{max_retries + 1} attempts."
    )


def fix_project(
    user_request,
    plan,
    project,
    review,
    execution,
    max_retries: int = 2,
):

    diagnosis = _diagnose(
        user_request,
        plan,
        project,
        review,
        execution,
        max_retries=max_retries,
    )

    root_cause = diagnosis.get("root_cause", "")
    affected_files = diagnosis.get("affected_files", [])

    content_by_path = {
        f["path"]: f["content"]
        for f in project["files"]
    }

    fixed_files = []

    for file_path in affected_files:

        current_content = content_by_path.get(file_path, "")

        related_files = []

        file_dir = "/".join(file_path.split("/")[:-1])

        for path, content in content_by_path.items():

            if path == file_path:
                continue

            if path.startswith(file_dir):

                related_files.append({
                    "path": path,
                    "content": content,
                })

        content = ""
        finish_reason = None
        tokens = 1500

        for attempt in range(max_retries + 1):

            prompt = fixer_file_prompt(
                user_request=user_request,
                root_cause=root_cause,
                file_path=file_path,
                current_content=current_content,
                related_files=related_files,
                execution=execution,
            )

            result = generate(
                prompt,
                model=FIXER_MODEL,
                max_tokens=tokens,
                reasoning_effort="medium",
                temperature=0,
                return_meta=True,
            )

            content = _strip_code_fences(
                result["content"]
            )

            finish_reason = result["finish_reason"]

            print(
                f"\n===== FIXING: {file_path} "
                f"(attempt {attempt + 1}) ====="
            )

            print(
                f"finish_reason={finish_reason}, "
                f"tokens_budget={tokens}"
            )

            print("=" * 60)

            if finish_reason == "length":

                loop_offset = find_repetition_loop(content)

                if loop_offset is not None:

                    content = (
                        content[:loop_offset]
                        .rstrip()
                    )

                    print(
                        f"[fixer] '{file_path}' "
                        "entered a repetition loop. "
                        "Using truncated result."
                    )

                    finish_reason = "stop"
                    break

                print(
                    f"[fixer] '{file_path}' "
                    "truncated. Retrying..."
                )

                tokens = int(tokens * 1.75)
                continue

            if not content:

                print(
                    f"[fixer] '{file_path}' "
                    "returned empty content."
                )

                continue

            break

        else:

            raise RuntimeError(
                f"Fixer failed to repair '{file_path}' "
                f"after {max_retries + 1} attempts."
            )

        fixed_files.append({
            "path": file_path,
            "content": content,
        })

    return {
        "files": fixed_files
    }