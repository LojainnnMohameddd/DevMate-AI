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

async def execute_plan(user_request: str):

    print("1. Creating plan...")
    plan = create_plan(user_request)
    print("Plan created!")

    print("2. Generating project...")
    project = generate_project(user_request, plan)
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

    if not review["request_satisfied"]:
        print("\nReview failed. Execution skipped.")
        return

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

    project_name = "student_api"
    project_path = Path("generated_projects") / project_name

    MAX_FIX_ATTEMPTS = 3

    for attempt in range(MAX_FIX_ATTEMPTS):

        print(f"\n===== Execution Attempt {attempt + 1} =====")

        execution = execute_project(str(project_path))

        print(execution)

        if execution["passed"]:
            print("\nProject executed successfully!")
            break

        print("\nFixing project...")

        fixed_project = fix_project(
            user_request,
            plan,
            project,
            review,
            execution
        )

        print(fixed_project)

        project["files"] = [
            file for file in project["files"]
            if file["path"] not in {f["path"] for f in fixed_project["files"]}
        ]

        project["files"].extend(fixed_project["files"])

        # -----------------------------
        # Apply Fixes
        # -----------------------------
        async with streamablehttp_client(
            "http://127.0.0.1:8000/mcp"
        ) as (read_stream, write_stream, _):

            async with ClientSession(read_stream, write_stream) as session:

                await session.initialize()

                for file in fixed_project["files"]:

                    print(f"\nUpdating: {file['path']}")

                    result = await session.call_tool(
                        "write_file",
                        {
                            "file_path": file["path"],
                            "content": file["content"]
                        }
                    )

                    print(result.content[0].text)

        

if __name__ == "__main__":

    asyncio.run(
        execute_plan(
            "Create a FastAPI project called student_api"
        )
    )