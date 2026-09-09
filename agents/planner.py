import json
import os
from collections import defaultdict
from pathlib import Path

from prompts.planner_prompt import (
    planner_prompt,
    planner_completion_prompt,
)
from utils.llm import generate


PLANNER_MODEL = "qwen/qwen3.6-27b"

# Qwen reasoning models can consume a large part of the completion
# budget before producing the final JSON.
INITIAL_TOKENS = 6000
MAX_TOKENS = 9000

COMPLETION_TOKENS = 2500


def _strip_json_fences(text: str) -> str:
    text = (text or "").strip()

    if text.startswith("```json"):
        text = text[len("```json"):]

        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]

        return text.strip()

    if text.startswith("```"):
        text = text[3:]

        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]

        return text.strip()

    return text


def _get_plan_file_paths(plan):
    return [
        step["args"]["file_path"]
        for step in plan
        if step.get("tool") == "create_file"
        and "args" in step
        and "file_path" in step["args"]
    ]


def validate_plan_completeness(
    plan,
    min_nontrivial_files: int = 1,
):
    """
    Programmatic non-LLM validation.

    For every folder containing __init__.py,
    make sure the same folder contains at least
    one other implementation file.
    """

    file_paths = _get_plan_file_paths(plan)

    files_by_folder = defaultdict(list)

    for path in file_paths:

        folder = os.path.dirname(
            path
        ).replace("\\", "/")

        files_by_folder[folder].append(path)

    incomplete_folders = []

    for folder, files in files_by_folder.items():

        has_init = any(
            os.path.basename(file_path)
            == "__init__.py"
            for file_path in files
        )

        if not has_init:
            continue

        non_init_files = [
            file_path
            for file_path in files
            if os.path.basename(file_path)
            != "__init__.py"
        ]

        if len(non_init_files) < min_nontrivial_files:

            incomplete_folders.append(folder)

    return incomplete_folders


def _parse_plan(text: str):
    """
    Parse the planner response as JSON.

    Supports:
    - normal JSON array
    - JSON wrapped in markdown fences
    - line-separated JSON objects
    """

    text = _strip_json_fences(text)

    if not text:
        raise json.JSONDecodeError(
            "Empty planner response",
            "",
            0,
        )

    try:
        return json.loads(text)

    except json.JSONDecodeError:

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        objects = []

        for line in lines:

            if not (
                line.startswith("{")
                and line.endswith("}")
            ):
                continue

            try:
                objects.append(
                    json.loads(line)
                )
            except json.JSONDecodeError:
                continue

        if objects:
            return objects

        raise


def _validate_plan_structure(plan):
    """
    Programmatic validation of the planner output.
    """

    if not isinstance(plan, list):

        raise RuntimeError(
            "Planner output must be a JSON array."
        )

    if not plan:

        raise RuntimeError(
            "Planner returned an empty plan."
        )

    # ---------------------------------------------------------
    # Validate root project folder
    # ---------------------------------------------------------

    create_folder_steps = [
        step
        for step in plan
        if step.get("tool") == "create_folder"
    ]

    if len(create_folder_steps) != 1:

        raise RuntimeError(
            "Planner must generate exactly one "
            "root project folder."
        )

    root = (
        create_folder_steps[0]
        .get("args", {})
        .get("folder_name")
    )

    if not root:

        raise RuntimeError(
            "Root project folder name is missing."
        )

    root = Path(root).as_posix()

    # ---------------------------------------------------------
    # Validate create_file paths
    # ---------------------------------------------------------

    for step in plan:

        if step.get("tool") != "create_file":
            continue

        file_path = (
            step
            .get("args", {})
            .get("file_path")
        )

        if not file_path:

            raise RuntimeError(
                "create_file step is missing file_path."
            )

        file_path = Path(
            file_path
        ).as_posix()

        if not file_path.startswith(
            root + "/"
        ):

            raise RuntimeError(
                f"File '{file_path}' is outside "
                f"the root folder '{root}'."
            )

    return root


def _request_plan(
    user_request: str,
    tokens: int,
):
    """
    Single planner model request.
    """

    prompt = planner_prompt(
        user_request
    )

    result = generate(
        prompt,
        model=PLANNER_MODEL,
        max_tokens=tokens,
        reasoning_effort="low",
        temperature=0,
        return_meta=True,
    )

    text = _strip_json_fences(
        result.get("content", "")
    )

    finish_reason = result.get(
        "finish_reason"
    )

    print("\n===== RAW RESPONSE =====")
    print(repr(text))

    print(
        f"finish_reason={finish_reason}, "
        f"tokens_budget={tokens}"
    )

    print("========================")

    return text, finish_reason


def create_plan(
    user_request: str,
    max_retries: int = 2,
    max_completion_retries: int = 2,
):

    tokens = INITIAL_TOKENS

    text = ""
    finish_reason = None

    # ---------------------------------------------------------
    # Main Planning Loop
    # ---------------------------------------------------------

    for attempt in range(
        max_retries + 1
    ):

        try:

            text, finish_reason = _request_plan(
                user_request,
                tokens,
            )

        except Exception as e:

            print(
                "\n[planner] Model request failed:"
                f" {type(e).__name__}: {e}"
            )

            if attempt >= max_retries:
                raise

            tokens = min(
                int(tokens * 1.5),
                MAX_TOKENS,
            )

            print(
                f"[planner] Retrying with "
                f"{tokens} tokens..."
            )

            continue

        # -----------------------------------------------------
        # Truncated response
        # -----------------------------------------------------

        if finish_reason == "length":

            print(
                f"[planner] Response truncated "
                f"(attempt {attempt + 1}/"
                f"{max_retries + 1})."
            )

            if attempt < max_retries:

                tokens = min(
                    int(tokens * 1.5),
                    MAX_TOKENS,
                )

                print(
                    f"[planner] Retrying with "
                    f"{tokens} tokens..."
                )

                continue

            raise RuntimeError(
                "Planner response still truncated "
                "after "
                f"{max_retries + 1} attempts."
            )

        # -----------------------------------------------------
        # Successful completion
        # -----------------------------------------------------

        break

    # ---------------------------------------------------------
    # Parse JSON
    # ---------------------------------------------------------

    try:

        plan = _parse_plan(text)

    except json.JSONDecodeError as e:

        print(
            "\n[planner] Invalid JSON response."
        )

        print(
            f"[planner] Response length: "
            f"{len(text)} characters"
        )

        raise RuntimeError(
            "Planner returned invalid JSON."
        ) from e

    # ---------------------------------------------------------
    # Validate plan
    # ---------------------------------------------------------

    root = _validate_plan_structure(
        plan
    )

    print("\n===== PLAN =====")
    print(type(plan))
    print(plan)

    # ---------------------------------------------------------
    # Programmatic completeness validation
    # ---------------------------------------------------------

    for completion_attempt in range(
        max_completion_retries
    ):

        incomplete_folders = (
            validate_plan_completeness(
                plan
            )
        )

        if not incomplete_folders:

            break

        print(
            "\n[planner] Missing implementation "
            "files in:"
        )

        print(
            incomplete_folders
        )

        completion_prompt = (
            planner_completion_prompt(
                user_request,
                plan,
                incomplete_folders,
            )
        )

        result = generate(
            completion_prompt,
            model=PLANNER_MODEL,
            max_tokens=COMPLETION_TOKENS,
            reasoning_effort="low",
            temperature=0,
            return_meta=True,
        )

        addition_text = _strip_json_fences(
            result.get("content", "")
        )

        completion_finish_reason = (
            result.get("finish_reason")
        )

        print(
            "\n===== PLAN COMPLETION ====="
        )

        print(
            repr(addition_text)
        )

        print(
            f"finish_reason="
            f"{completion_finish_reason}"
        )

        print(
            "==========================="
        )

        if (
            completion_finish_reason
            == "length"
            or not addition_text
        ):

            print(
                "[planner] Completion truncated."
            )

            break

        try:

            additional_steps = _parse_plan(
                addition_text
            )

        except json.JSONDecodeError:

            print(
                "[planner] Invalid JSON returned "
                "during plan completion."
            )

            break

        existing_paths = set(
            _get_plan_file_paths(plan)
        )

        new_steps = []

        for step in additional_steps:

            if step.get("tool") != "create_file":
                continue

            file_path = (
                step
                .get("args", {})
                .get("file_path")
            )

            if not file_path:
                continue

            file_path = Path(
                file_path
            ).as_posix()

            if file_path in existing_paths:
                continue

            if not file_path.startswith(
                root + "/"
            ):
                continue

            new_steps.append(
                {
                    "tool": "create_file",
                    "args": {
                        "file_path": file_path
                    },
                }
            )

        if not new_steps:

            print(
                "[planner] No additional files "
                "generated."
            )

            break

        plan.extend(
            new_steps
        )

        print(
            "\n===== UPDATED PLAN ====="
        )

        print(plan)

    # ---------------------------------------------------------
    # Final completeness warning
    # ---------------------------------------------------------

    remaining = validate_plan_completeness(
        plan
    )

    if remaining:

        print(
            "[planner] Warning: Some packages "
            "are still incomplete:"
        )

        print(
            remaining
        )

    return plan