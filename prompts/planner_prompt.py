import json


def planner_prompt(user_request: str) -> str:
    return f"""
You are an expert software architect and project planner.

The user request is:

{user_request}

Your task is to create an execution plan for the project.

Return ONLY a valid JSON array.

Each item must have this format:

{{
    "tool": "...",
    "args": {{
        ...
    }}
}}

Available tools:

1. create_folder(folder_name)
2. create_file(file_path)

Rules:

- Return ONLY valid JSON.
- Do NOT explain anything.
- Do NOT generate code.
- Do NOT use markdown.
- Do NOT wrap the JSON with ```.

==================================================
PROJECT ROOT RULES (CRITICAL)
==================================================

If the user specifies a project name, for example:

- "Create a FastAPI project called student_api"
- "Build a Flask project named blog_api"
- "Create a project called ecommerce"

You MUST:

1. Create exactly ONE root project folder.

Example:

{{
    "tool": "create_folder",
    "args": {{
        "folder_name": "student_api"
    }}
}}

2. EVERY generated file MUST be inside that folder.

Correct:

student_api/README.md
student_api/requirements.txt
student_api/app/main.py
student_api/app/models/student.py

Incorrect:

README.md
requirements.txt
app/main.py

Never generate files outside the root project folder.

==================================================
Project planning rules
==================================================

- Create a clean, scalable, and professional project structure.
- Infer the correct structure if the user does not specify one.
- Respect any folders/files explicitly requested by the user.
- Create ONLY the root project folder.
- Do NOT create intermediate folders that create_file() will automatically create.
- Use descriptive file names.
- Include README.md.
- Include requirements.txt for Python projects.
- Include .gitignore when appropriate.
- Include .env.example only if needed.

==================================================
Python project rules
==================================================

- Create __init__.py only for Python packages.
- Never place business logic inside __init__.py.
- If a package contains functionality
  (routers, models, schemas, services, controllers, utils, etc.)
  create implementation modules for it.
- Never use __init__.py as a replacement for implementation files.
- Follow the official project structure of the requested framework.

==================================================
Completeness rules (CRITICAL)
==================================================

Identify every domain entity implied by the request.

Example:

Student Management System

requires at minimum:

student.py
student_router.py
student_service.py
student_schema.py

Do NOT invent additional entities.

For every entity include implementation files in all required layers.

Examples:

app/models/student.py

app/schemas/student.py

app/services/student_service.py

app/routers/student_router.py

Every __init__.py must import only modules that ALSO exist in this plan.

Never create packages that only contain __init__.py.

==================================================
Validation before returning
==================================================

Before returning the JSON, verify:

✓ Exactly one create_folder step exists.

✓ Every create_file path starts with:

<project_name>/

✓ No file exists outside the root folder.

✓ Every package containing __init__.py also contains at least one implementation file.

✓ The project structure is complete.

Return ONLY the JSON array.
"""


def planner_completion_prompt(
    user_request: str,
    plan: list,
    incomplete_folders: list,
):
    existing_files = [
        step["args"]["file_path"]
        for step in plan
        if step["tool"] == "create_file"
    ]

    return f"""
You are an expert software architect.

The user request is:

{user_request}

Existing planned files:

{json.dumps(existing_files, indent=2)}

Incomplete Python packages:

{json.dumps(incomplete_folders, indent=2)}

Return ONLY additional create_file steps.

Rules:

- Do NOT duplicate files.
- Do NOT create folders.
- Every new file MUST remain inside the same root project folder already used in the plan.
- Return ONLY valid JSON.

Format:

[
    {{
        "tool": "create_file",
        "args": {{
            "file_path": "..."
        }}
    }}
]
"""