from prompts.coder_prompt import coder_file_prompt
from utils.llm import generate
from utils.repetition import find_repetition_loop


CODER_MODEL = "openai/gpt-oss-120b"


def _strip_code_fences(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines)

    return text.strip()


def get_related_files(file_path: str, generated_files: list):
    related = []

    for file in generated_files:
        path = file["path"]

        # database -> config
        if file_path.endswith("database.py"):
            if path.endswith("config.py"):
                related.append(file)

        # models -> database
        elif "/models/" in file_path.replace("\\", "/"):
            if path.endswith("database.py"):
                related.append(file)

        # services -> models + schemas
        elif "/services/" in file_path.replace("\\", "/"):
            if (
                "/models/" in path.replace("\\", "/")
                or "/schemas/" in path.replace("\\", "/")
            ):
                related.append(file)

        # routers -> services + schemas + database
        elif "/routers/" in file_path.replace("\\", "/"):
            if (
                "/services/" in path.replace("\\", "/")
                or "/schemas/" in path.replace("\\", "/")
                or path.endswith("database.py")
            ):
                related.append(file)

        # __init__.py -> same package
        elif file_path.endswith("__init__.py"):
            current_folder = file_path.replace("\\", "/").rsplit("/", 1)[0]
            other_folder = path.replace("\\", "/").rsplit("/", 1)[0]

            if current_folder == other_folder:
                related.append(file)

        # requirements & README see everything
        elif (
            file_path.endswith("requirements.txt")
            or file_path.endswith("README.md")
        ):
            related.append(file)

    return related


def generate_project(
    user_request: str,
    plan: list,
    max_retries: int = 2,
) -> dict:

    all_files = [
        step["args"]["file_path"]
        for step in plan
        if step["tool"] == "create_file"
    ]

    files = []
    generated_files = []

    for file_path in all_files:

        content = ""
        finish_reason = None
        tokens = 1500

        related_files = get_related_files(
            file_path,
            generated_files,
        )

        for attempt in range(max_retries + 1):

            prompt = coder_file_prompt(
                user_request=user_request,
                plan=plan,
                file_path=file_path,
                generated_files=related_files,
            )

            result = generate(
                prompt,
                model=CODER_MODEL,
                max_tokens=tokens,
                reasoning_effort="low",
                temperature=0.2,
                return_meta=True,
            )

            content = _strip_code_fences(result["content"])
            finish_reason = result["finish_reason"]

            print(
                f"\n===== FILE: {file_path} "
                f"(attempt {attempt + 1}) ====="
            )

            print(
                f"finish_reason={finish_reason}, "
                f"tokens_budget={tokens}"
            )

            print("=" * 60)

            # ---------------------------------------------------------
            # Case 1: Model hit token limit
            # ---------------------------------------------------------
            if finish_reason == "length":

                loop_offset = find_repetition_loop(content)

                if loop_offset is not None:
                    content = content[:loop_offset].rstrip()

                    print(
                        f"[coder] '{file_path}' hit a repetition loop. "
                        f"Truncated to {len(content)} valid chars."
                    )

                    finish_reason = "stop"
                    break

                print(
                    f"[coder] '{file_path}' truncated, "
                    f"retrying with more tokens..."
                )

                tokens = int(tokens * 1.75)
                continue

            # ---------------------------------------------------------
            # Case 2: Empty content
            #
            # requirements.txt is allowed to be empty because a project
            # may use only Python standard-library modules.
            # __init__.py is also allowed to be empty.
            # ---------------------------------------------------------
            if (
                not content
                and not file_path.endswith("__init__.py")
                and not file_path.endswith("requirements.txt")
            ):
                print(
                    f"[coder] '{file_path}' came back empty, "
                    f"retrying..."
                )
                continue

            break

        else:
            raise RuntimeError(
                f"Coder failed to generate '{file_path}' "
                f"after {max_retries + 1} attempts "
                f"(last finish_reason={finish_reason})"
            )

        # -------------------------------------------------------------
        # Empty-file validation
        #
        # requirements.txt and __init__.py are intentionally allowed
        # to be empty.
        # -------------------------------------------------------------
        if (
            not content
            and not file_path.endswith("__init__.py")
            and not file_path.endswith("requirements.txt")
        ):
            raise RuntimeError(
                f"Coder produced empty content for "
                f"'{file_path}' after all retries."
            )

        file_data = {
            "path": file_path,
            "content": content,
        }

        files.append(file_data)
        generated_files.append(file_data)

        print(
            f"[coder] Generated {file_path} "
            f"({len(content)} characters)"
        )

    return {
        "files": files
    }