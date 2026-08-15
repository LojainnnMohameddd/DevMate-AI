import json
import os
from collections import defaultdict

from prompts.planner_prompt import planner_prompt, planner_completion_prompt
from utils.llm import generate

PLANNER_MODEL = "qwen/qwen3.6-27b"


def _strip_json_fences(text: str):
    text = text.strip()

    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()

    return text


def _get_plan_file_paths(plan):
    return [
        step["args"]["file_path"]
        for step in plan
        if step["tool"] == "create_file"
    ]


def validate_plan_completeness(plan, min_nontrivial_files: int = 1):
    """
    Programmatic (non-LLM) check: for every folder that will contain an
    __init__.py, does the plan also include at least one other
    (non-__init__) file in that same folder?
    """

    file_paths = _get_plan_file_paths(plan)

    files_by_folder = defaultdict(list)

    for path in file_paths:
        folder = os.path.dirname(path).replace("\\", "/")
        files_by_folder[folder].append(path)

    incomplete_folders = []

    for folder, files in files_by_folder.items():

        has_init = any(
            os.path.basename(f) == "__init__.py"
            for f in files
        )

        if not has_init:
            continue

        non_init_files = [
            f for f in files
            if os.path.basename(f) != "__init__.py"
        ]

        if len(non_init_files) < min_nontrivial_files:
            incomplete_folders.append(folder)

    return incomplete_folders


def create_plan(
    user_request: str,
    max_retries: int = 2,
    max_completion_retries: int = 2,
):

    tokens = 3000

    text = ""
    finish_reason = None

    for attempt in range(max_retries + 1):

        prompt = planner_prompt(user_request)

        result = generate(
            prompt,
            model=PLANNER_MODEL,
            max_tokens=tokens,
            reasoning_effort="low",
            return_meta=True,
        )

        text = _strip_json_fences(result["content"])
        finish_reason = result["finish_reason"]

        print("\n===== RAW RESPONSE =====")
        print(repr(text))
        print(
            f"finish_reason={finish_reason}, "
            f"tokens_budget={tokens}"
        )
        print("========================")

        if finish_reason == "length":

            print(
                f"[planner] Response truncated, retrying "
                f"({attempt + 1}/{max_retries})..."
            )

            tokens = int(tokens * 1.75)

            continue

        break

    else:

        raise RuntimeError(
            f"Planner failed after "
            f"{max_retries + 1} attempts."
        )

    if finish_reason == "length":

        raise RuntimeError(
            "Planner response still truncated."
        )

    try:

        plan = json.loads(text)

    except json.JSONDecodeError:

        plan = [
            json.loads(line)
            for line in text.splitlines()
            if line.strip()
        ]

    # ---------------------------------------------------------
    # Validate root project folder
    # ---------------------------------------------------------

    from pathlib import Path

    create_folder_steps = [
        step for step in plan
        if step["tool"] == "create_folder"
    ]

    if len(create_folder_steps) != 1:
        raise RuntimeError(
            "Planner must generate exactly one root project folder."
        )

    root = create_folder_steps[0]["args"]["folder_name"]
    for step in plan:

        if step["tool"] != "create_file":
            continue

        file_path = Path(step["args"]["file_path"]).as_posix()

        if not file_path.startswith(root + "/"):
            raise RuntimeError(
                f"File '{file_path}' is outside the root folder '{root}'.")

    print("\n===== PLAN =====")
    print(type(plan))
    print(plan)

    # ---------------------------------------------------------
    # Programmatic completeness validation
    # ---------------------------------------------------------

    for completion_attempt in range(max_completion_retries):

        incomplete_folders = validate_plan_completeness(plan)

        if not incomplete_folders:
            break

        print(
            "[planner] Missing implementation files in:\n"
            f"{incomplete_folders}"
        )

        completion_prompt = planner_completion_prompt(
            user_request,
            plan,
            incomplete_folders,
        )

        result = generate(
            completion_prompt,
            model=PLANNER_MODEL,
            max_tokens=1500,
            reasoning_effort="low",
            return_meta=True,
        )

        addition_text = _strip_json_fences(
            result["content"]
        )

        completion_finish_reason = result["finish_reason"]

        print("\n===== PLAN COMPLETION =====")
        print(repr(addition_text))
        print(
            f"finish_reason={completion_finish_reason}"
        )
        print("===========================")

        if (
            completion_finish_reason == "length"
            or not addition_text
        ):

            print(
                "[planner] Completion truncated."
            )

            break

        try:

            additional_steps = json.loads(addition_text)

        except json.JSONDecodeError:

            print(
                "[planner] Invalid JSON returned."
            )

            break

        existing_paths = set(
            _get_plan_file_paths(plan)
        )

        new_steps = [

            step

            for step in additional_steps

            if (
                step.get("tool") == "create_file"
                and step.get("args", {}).get("file_path")
                not in existing_paths
            )

        ]

        if not new_steps:

            print(
                "[planner] No additional files generated."
            )

            break

        plan.extend(new_steps)

        print("\n===== UPDATED PLAN =====")
        print(plan)

    remaining = validate_plan_completeness(plan)

    if remaining:

        print(
            "[planner] Warning: Some packages are "
            f"still incomplete: {remaining}"
        )

    return plan