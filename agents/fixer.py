import json

from prompts.fixer_prompt import (
    fixer_diagnosis_prompt,
    fixer_file_prompt,
)
from utils.llm import generate
from utils.repetition import find_repetition_loop


FIXER_MODEL = "openai/gpt-oss-20b"


def _strip_code_fences(text: str) -> str:
    text = (text or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines)

    return text.strip()


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


def _get_project_paths(project: dict) -> set[str]:
    """
    Return only valid file paths from the project structure.
    """

    paths = set()

    for file in project.get("files", []):
        if isinstance(file, dict):
            path = file.get("path")

            if isinstance(path, str):
                paths.add(path)

    return paths


def _normalize_diagnosis(
    diagnosis: dict,
    project: dict,
) -> dict:
    """
    Keep only valid project files in affected_files.

    The model may return malformed values, so this function
    validates everything before the rest of the pipeline uses it.
    """

    if not isinstance(diagnosis, dict):
        return {
            "root_cause": "",
            "affected_files": [],
        }

    project_paths = _get_project_paths(project)

    affected_files = diagnosis.get(
        "affected_files",
        [],
    )

    if not isinstance(affected_files, list):
        affected_files = []

    valid_files = []

    for path in affected_files:
        if (
            isinstance(path, str)
            and path in project_paths
        ):
            valid_files.append(path)

    return {
        "root_cause": str(
            diagnosis.get("root_cause", "")
        ).strip(),

        "affected_files": valid_files,
    }


def _build_compact_project(project: dict) -> dict:
    """
    Diagnosis only needs project paths, not file contents.
    """

    project_files = []

    for file in project.get("files", []):
        if isinstance(file, dict):
            path = file.get("path")

            if isinstance(path, str):
                project_files.append(path)

    return {
        "files": project_files
    }


def _build_compact_execution(execution: dict) -> dict:
    """
    Keep execution information needed for diagnosis.
    """

    if not isinstance(execution, dict):
        return {
            "passed": False,
            "return_code": -1,
            "stdout": "",
            "stderr": str(execution),
            "errors": [],
        }

    return {
        "passed": execution.get("passed"),
        "return_code": execution.get("return_code"),
        "stdout": execution.get("stdout", ""),
        "stderr": execution.get("stderr", ""),
        "errors": execution.get("errors", []),
    }


def _build_compact_review(review: dict) -> dict:
    """
    Keep only useful reviewer information.
    """

    if not isinstance(review, dict):
        return {}

    return {
        "request_satisfied": review.get(
            "request_satisfied"
        ),

        "score": review.get("score"),

        "issues": review.get(
            "issues",
            review.get("errors", []),
        ),

        "broken_imports": review.get(
            "broken_imports",
            [],
        ),

        "dependency_issues": review.get(
            "dependency_issues",
            [],
        ),

        "summary": review.get(
            "summary",
            "",
        ),
    }


def _build_compact_plan(plan) -> list:
    """
    Keep only the information relevant to the Fixer.
    """

    if not isinstance(plan, list):
        return []

    compact_plan = []

    for step in plan:
        if not isinstance(step, dict):
            continue

        compact_plan.append(
            {
                "tool": step.get("tool"),
                "args": step.get("args", {}),
            }
        )

    return compact_plan


def _is_request_too_large(error_text: str) -> bool:
    return (
        "413" in error_text
        or "Request too large" in error_text
        or "request too large" in error_text
    )


def _diagnose(
    user_request,
    plan,
    project,
    review,
    execution,
    max_retries: int = 2,
) -> dict:

    compact_project = _build_compact_project(
        project
    )

    compact_execution = _build_compact_execution(
        execution
    )

    compact_review = _build_compact_review(
        review
    )

    compact_plan = _build_compact_plan(
        plan
    )

    tokens = 1200
    temperature = 0

    for attempt in range(max_retries + 1):

        prompt = fixer_diagnosis_prompt(
            user_request,
            compact_plan,
            compact_project,
            compact_review,
            compact_execution,
        )

        try:
            result = generate(
                prompt,
                model=FIXER_MODEL,
                max_tokens=tokens,
                reasoning_effort="low",
                temperature=temperature,
                return_meta=True,
            )

        except Exception as e:

            error_text = str(e)

            print(
                "\n[fixer] Diagnosis model call failed: "
                f"{type(e).__name__}: {e}"
            )

            if _is_request_too_large(
                error_text
            ):
                if attempt < max_retries:

                    tokens = max(
                        600,
                        int(tokens * 0.7),
                    )

                    print(
                        "[fixer] Request too large. "
                        "Retrying with smaller token "
                        f"budget: {tokens}"
                    )

                    continue

            if attempt < max_retries:

                temperature = min(
                    temperature + 0.2,
                    0.6,
                )

                print(
                    "[fixer] Retrying diagnosis..."
                )

                continue

            raise

        text = _strip_json_fences(
            result.get("content", "")
        )

        finish_reason = result.get(
            "finish_reason"
        )

        print(
            "\n========== DIAGNOSIS ==========\n"
        )

        print(text)

        print(
            f"finish_reason={finish_reason}, "
            f"tokens_budget={tokens}, "
            f"temperature={temperature}"
        )

        print(
            "================================\n"
        )

        if finish_reason == "length":

            loop_offset = find_repetition_loop(
                text
            )

            if loop_offset is not None:

                print(
                    "[fixer] Diagnosis repetition "
                    "detected. Retrying..."
                )

                temperature = min(
                    temperature + 0.3,
                    0.8,
                )

            else:

                print(
                    "[fixer] Diagnosis truncated. "
                    "Retrying..."
                )

            tokens = min(
                int(tokens * 1.25),
                1600,
            )

            continue

        try:
            diagnosis = json.loads(text)

        except json.JSONDecodeError:

            print(
                "[fixer] Invalid diagnosis JSON. "
                "Retrying..."
            )

            temperature = min(
                temperature + 0.2,
                0.6,
            )

            continue

        return _normalize_diagnosis(
            diagnosis,
            project,
        )

    raise RuntimeError(
        "Fixer diagnosis failed after "
        f"{max_retries + 1} attempts."
    )


def _get_file_contents(
    project: dict,
) -> dict[str, str]:
    """
    Safely build path -> content mapping.
    """

    content_by_path = {}

    for file in project.get("files", []):

        if not isinstance(file, dict):
            continue

        path = file.get("path")
        content = file.get("content")

        if not isinstance(path, str):
            continue

        if not isinstance(content, str):
            content = ""

        content_by_path[path] = content

    return content_by_path


def _get_related_files(
    file_path: str,
    content_by_path: dict[str, str],
) -> list[dict]:
    """
    Give the Fixer relevant neighboring files.

    Prefer files in the same directory.
    Also include root-level files when fixing a nested file,
    because configuration files often live at project root.
    """

    related_files = []

    file_parts = file_path.split("/")

    if len(file_parts) > 1:
        file_dir = "/".join(
            file_parts[:-1]
        )
    else:
        file_dir = ""

    for path, content in content_by_path.items():

        if path == file_path:
            continue

        same_directory = (
            bool(file_dir)
            and path.startswith(
                file_dir + "/"
            )
        )

        root_file = (
            "/" not in path
        )

        if same_directory or root_file:

            related_files.append(
                {
                    "path": path,
                    "content": content,
                }
            )

    return related_files


def _fix_single_file(
    user_request,
    root_cause,
    file_path,
    current_content,
    related_files,
    execution,
    max_retries: int,
) -> str:

    tokens = 1800

    for attempt in range(
        max_retries + 1
    ):

        prompt = fixer_file_prompt(
            user_request=user_request,
            root_cause=root_cause,
            file_path=file_path,
            current_content=current_content,
            related_files=related_files,
            execution=execution,
        )

        try:
            result = generate(
                prompt,
                model=FIXER_MODEL,
                max_tokens=tokens,
                reasoning_effort="low",
                temperature=0,
                return_meta=True,
            )

        except Exception as e:

            error_text = str(e)

            print(
                f"\n[fixer] Failed while fixing "
                f"'{file_path}': "
                f"{type(e).__name__}: {e}"
            )

            if _is_request_too_large(
                error_text
            ):
                if attempt < max_retries:

                    tokens = max(
                        900,
                        int(tokens * 0.7),
                    )

                    print(
                        f"[fixer] Request too large "
                        f"for '{file_path}'. "
                        f"Retrying with "
                        f"{tokens} tokens..."
                    )

                    continue

            if attempt < max_retries:

                tokens = max(
                    900,
                    int(tokens * 0.85),
                )

                continue

            raise

        content = _strip_code_fences(
            result.get("content", "")
        )

        finish_reason = result.get(
            "finish_reason"
        )

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

            loop_offset = find_repetition_loop(
                content
            )

            if loop_offset is not None:

                print(
                    f"[fixer] '{file_path}' "
                    "entered a repetition loop. "
                    "Retrying..."
                )

                tokens = min(
                    int(tokens * 1.25),
                    2500,
                )

                continue

            print(
                f"[fixer] '{file_path}' "
                "was truncated. Retrying..."
            )

            tokens = min(
                int(tokens * 1.25),
                2500,
            )

            continue

        if not content:

            print(
                f"[fixer] '{file_path}' "
                "returned empty content."
            )

            continue

        return content

    raise RuntimeError(
        f"Fixer failed to repair "
        f"'{file_path}' after "
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

    root_cause = diagnosis.get(
        "root_cause",
        "",
    )

    affected_files = diagnosis.get(
        "affected_files",
        [],
    )

    if not isinstance(
        affected_files,
        list,
    ):
        affected_files = []

    content_by_path = _get_file_contents(
        project
    )

    project_paths = set(
        content_by_path.keys()
    )

    # Final safety check before fixing.
    affected_files = [
        path
        for path in affected_files
        if (
            isinstance(path, str)
            and path in project_paths
        )
    ]

    if not affected_files:

        raise RuntimeError(
            "Fixer diagnosis did not identify "
            "any valid project files to fix."
        )

    fixed_files = []

    for file_path in affected_files:

        current_content = content_by_path.get(
            file_path,
            "",
        )

        related_files = _get_related_files(
            file_path,
            content_by_path,
        )

        content = _fix_single_file(
            user_request=user_request,
            root_cause=root_cause,
            file_path=file_path,
            current_content=current_content,
            related_files=related_files,
            execution=execution,
            max_retries=max_retries,
        )

        fixed_files.append(
            {
                "path": file_path,
                "content": content,
            }
        )

    return {
        "files": fixed_files
    }