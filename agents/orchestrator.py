import asyncio
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from agents.planner import create_plan
from agents.coder import generate_project
from agents.reviewer import review_project
from validators.static_validator import validate_project
from agents.execution import execute_project
from agents.fixer import fix_project


MAX_REVIEW_FIX_ATTEMPTS = 2
MAX_FIX_ATTEMPTS = 3


async def _write_files_via_mcp(plan, project):
    async with streamablehttp_client(
        "http://127.0.0.1:8000/mcp"
    ) as (read_stream, write_stream, _):

        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()

            # Execute folder creation
            for step in plan:

                if step["tool"] == "create_folder":

                    print("\nRunning: create_folder")

                    result = await session.call_tool(
                        "create_folder",
                        step["args"]
                    )

                    print(result.content[0].text)

            # Create files and write content
            for file in project["files"]:

                print(f"\nCreating: {file['path']}")

                await session.call_tool(
                    "create_file",
                    {
                        "file_path": file["path"]
                    }
                )

                result = await session.call_tool(
                    "write_file",
                    {
                        "file_path": file["path"],
                        "content": file["content"]
                    }
                )

                print(result.content[0].text)


def _merge_fixed_files(project, fixed_project):
    fixed_paths = {
        file["path"]
        for file in fixed_project["files"]
    }

    project["files"] = [
        file
        for file in project["files"]
        if file["path"] not in fixed_paths
    ]

    project["files"].extend(
        fixed_project["files"]
    )


async def _apply_fixed_files(fixed_project):
    async with streamablehttp_client(
        "http://127.0.0.1:8000/mcp"
    ) as (read_stream, write_stream, _):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            await session.initialize()

            for file in fixed_project["files"]:

                print(
                    f"\nUpdating: {file['path']}"
                )

                result = await session.call_tool(
                    "write_file",
                    {
                        "file_path": file["path"],
                        "content": file["content"]
                    }
                )

                print(result.content[0].text)


def _report_progress(progress_callback, step, state, message=""):
    """Report pipeline progress without affecting execution if the UI is disconnected."""
    if progress_callback is None:
        return

    try:
        progress_callback({
            "step": step,
            "state": state,
            "message": message,
        })
    except Exception as e:
        print(f"[orchestrator] Progress callback failed: {e}")


async def execute_plan(user_request: str, progress_callback=None):

    # -----------------------------
    # Planning
    # -----------------------------

    _report_progress(progress_callback, "planner", "running", "Creating the project plan...")
    print("1. Creating plan...")

    plan = create_plan(
        user_request
    )

    _report_progress(progress_callback, "planner", "completed", "Project plan created.")
    _report_progress(progress_callback, "coder", "running", "Generating the project structure and code...")
    print("Plan created!")

    # -----------------------------
    # Code Generation
    # -----------------------------

    print("2. Generating project...")

    project = generate_project(
        user_request,
        plan
    )

    _report_progress(progress_callback, "coder", "completed", "Project code generated.")
    _report_progress(progress_callback, "validator", "running", "Checking project integrity...")
    print("Project generated!")

    # -----------------------------
    # Static Validation
    # -----------------------------

    print("3. Running static validation...")

    validation = validate_project(
        plan,
        project
    )

    print("Static validation completed!")
    print(validation)
    _report_progress(progress_callback, "validator", "completed", "Static validation completed.")
    _report_progress(progress_callback, "reviewer", "running", "Reviewing the generated project...")

    # -----------------------------
    # Reviewer
    # -----------------------------

    print("4. Reviewing project...")

    review = review_project(
        user_request,
        plan,
        project,
        validation
    )

    print("Review completed!")
    print(review)
    _report_progress(progress_callback, "reviewer", "completed", "Project review completed.")

    # -----------------------------
    # Reviewer Auto-Fix Loop
    # -----------------------------

    review_fix_attempt = 0

    while (
        not review["request_satisfied"]
        and
        review_fix_attempt < MAX_REVIEW_FIX_ATTEMPTS
    ):

        review_fix_attempt += 1

        _report_progress(progress_callback, "fixer", "running", "Fixing issues found during review...")
        print(
            f"\nReview flagged issues "
            f"(attempt {review_fix_attempt}/"
            f"{MAX_REVIEW_FIX_ATTEMPTS}). "
            f"Attempting to fix based on "
            f"review feedback before execution..."
        )

        pre_execution_placeholder = {
            "passed": False,
            "stdout": "",
            "stderr": (
                "N/A - the project was not executed. "
                "The Reviewer flagged issues before "
                "execution; see the review report "
                "for details."
            ),
        }

        try:

            fixed_project = fix_project(
                user_request,
                plan,
                project,
                review,
                pre_execution_placeholder,
            )

        except Exception as e:

            _report_progress(progress_callback, "fixer", "failed", "Fixer could not resolve the review issues.")
            print(
                "\n[orchestrator] Fixer failed during "
                f"review-fix attempt: {e}"
            )

            break

        print("\n===== REVIEW-FIX RESULT =====")
        print(fixed_project)
        print("==============================")

        _merge_fixed_files(
            project,
            fixed_project
        )
        _report_progress(progress_callback, "fixer", "completed", "Review fixes applied.")
        _report_progress(progress_callback, "validator", "running", "Re-validating after fixes...")

        print(
            "\n5. Re-validating project after fix..."
        )

        validation = validate_project(
            plan,
            project
        )

        print(validation)
        _report_progress(progress_callback, "validator", "completed", "Re-validation completed.")
        _report_progress(progress_callback, "reviewer", "running", "Re-reviewing the updated project...")

        print(
            "6. Re-reviewing project..."
        )

        review = review_project(
            user_request,
            plan,
            project,
            validation
        )

        print(review)
        _report_progress(progress_callback, "reviewer", "completed", "Re-review completed.")

    if not review["request_satisfied"]:

        print(
            f"\nReview still failing after "
            f"{MAX_REVIEW_FIX_ATTEMPTS} fix "
            f"attempt(s). Proceeding to write "
            f"and execute anyway -- the "
            f"execution/fix loop below may still "
            f"resolve remaining issues."
        )

    # -----------------------------
    # Write Initial Project via MCP
    # -----------------------------

    _report_progress(progress_callback, "mcp", "running", "Writing project files through MCP...")
    print(
        "\n===== Writing Project via MCP ====="
    )

    await _write_files_via_mcp(
        plan,
        project
    )
    _report_progress(progress_callback, "mcp", "completed", "Project files written successfully.")

    print("\n===== PLAN =====")
    print(plan)

    # -----------------------------
    # Determine Project Root
    # -----------------------------

    project_roots = {
        Path(file["path"]).parts[0]
        for file in project["files"]
        if len(Path(file["path"]).parts) > 1
    }

    if len(project_roots) != 1:

        raise RuntimeError(
            "Expected exactly one project root, "
            f"got: {project_roots}"
        )

    project_name = project_roots.pop()

    project_path = (
        Path("generated_projects")
        / project_name
    )

    print(
        "\n===== PROJECT PATH ====="
    )

    print(project_path)
    print(
        "Exists:",
        project_path.exists()
    )

    if project_path.exists():

        print("\nFiles:")

        for path in project_path.rglob("*"):

            print(
                " -",
                path.relative_to(
                    project_path
                )
            )

    # -----------------------------
    # Execution + Auto-Fix Loop
    # -----------------------------

    execution = None

    for attempt in range(
        MAX_FIX_ATTEMPTS
    ):

        _report_progress(
            progress_callback,
            "executor",
            "running",
            f"Running generated project (attempt {attempt + 1}/{MAX_FIX_ATTEMPTS})..."
        )
        print(
            f"\n===== Execution Attempt "
            f"{attempt + 1}/"
            f"{MAX_FIX_ATTEMPTS} ====="
        )

        execution = execute_project(
            str(project_path)
        )

        print(execution)

        # -------------------------
        # Success
        # -------------------------

        if execution["passed"]:

            _report_progress(progress_callback, "executor", "completed", "Project executed successfully.")
            print(
                "\nProject executed successfully!"
            )

            break

        # -------------------------
        # Execution Failed
        # -------------------------

        _report_progress(progress_callback, "executor", "failed", "Execution failed. Diagnosing the error...")
        print(
            "\nProject execution failed."
        )

        _report_progress(progress_callback, "fixer", "running", "Diagnosing and fixing the execution error...")
        print(
            "\nSending execution error "
            "to Fix Agent..."
        )

        try:

            fixed_project = fix_project(
                user_request,
                plan,
                project,
                review,
                execution
            )

        except Exception as e:

            _report_progress(progress_callback, "fixer", "failed", "Fixer could not apply the required repair.")
            print(
                "\n[orchestrator] Fixer failed "
                f"during execution-fix attempt: {e}"
            )

            break

        print(
            "\n===== EXECUTION-FIX RESULT ====="
        )

        print(
            fixed_project
        )

        print(
            "================================="
        )

        # -------------------------
        # Merge Fixed Files
        # -------------------------

        _merge_fixed_files(
            project,
            fixed_project
        )

        # -------------------------
        # Apply Fixes through MCP
        # -------------------------

        try:

            await _apply_fixed_files(
                fixed_project
            )

        except Exception as e:

            print(
                "\n[orchestrator] Failed to "
                "apply fixes through MCP: "
                f"{e}"
            )

            break

        _report_progress(progress_callback, "fixer", "completed", "Execution fixes applied. Retrying...")
        print(
            "\nFixes applied successfully."
        )

    else:

        print(
            "\nMaximum execution-fix attempts "
            "reached."
        )

    print(
        "\n===== DevMate Finished ====="
    )

    if execution and execution["passed"]:
        _report_progress(progress_callback, "executor", "completed", "Execution completed successfully.")
        _report_progress(progress_callback, "pipeline", "completed", "DevMate pipeline completed successfully.")
    else:
        _report_progress(progress_callback, "pipeline", "failed", "DevMate pipeline finished with an execution failure.")

    return {
        "success": bool(
            execution and execution["passed"]
        ),
        "execution": execution,
        "project_path": str(project_path),
    }


if __name__ == "__main__":

    asyncio.run(
        execute_plan(
            "Create a FastAPI project called student_api"
        )
    )