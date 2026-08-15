import json


def fixer_prompt(user_request, plan, project, review, execution):
    # Legacy / fallback
    return ""


def summarize_project(project):
    return {
        "files": [f["path"] for f in project["files"]]
    }


def fixer_diagnosis_prompt(
    user_request,
    plan,
    project,
    review,
    execution,
) -> str:

    return f"""
You are a Principal Python Software Engineer specializing in debugging.

Your task is to determine ALL files that should be fixed.

=====================
USER REQUEST
=====================

{user_request}

=====================
PLAN
=====================

{json.dumps(plan, indent=2)}

=====================
PROJECT FILES
=====================

{json.dumps(summarize_project(project), indent=2)}

=====================
REVIEW REPORT
=====================

{json.dumps(review, indent=2)}

=====================
EXECUTION REPORT
=====================

{json.dumps(execution, indent=2)}

=====================
INSTRUCTIONS
=====================

Read BOTH the review report and execution report.

Identify ALL root causes.

Do NOT stop at the first exception.

Think ahead.

If fixing one file will expose another obvious error,
include that file now.

Examples:

- Missing dependency in requirements.txt
- Wrong import pattern
- Missing config fields
- Deprecated Pydantic API
- SQLAlchemy incompatibility
- Async/sync mismatch
- Missing response models
- Broken package exports
- Missing __init__ exports

Return ONLY files that actually require modification.

=====================
OUTPUT
=====================

Return ONLY valid JSON.

Schema:

{{
    "root_cause": "short explanation",
    "affected_files": [
        "path/file1.py",
        "path/file2.py"
    ]
}}
"""


def fixer_file_prompt(
    user_request,
    root_cause,
    file_path,
    current_content,
    related_files,
    execution,
):

    related = json.dumps(
        related_files,
        indent=2,
        ensure_ascii=False,
    )

    return f"""
You are a Principal Python Software Engineer.

Your goal is NOT simply fixing today's exception.

Your goal is to make this file production-ready and
prevent future execution failures.

=====================
USER REQUEST
=====================

{user_request}

=====================
ROOT CAUSE
=====================

{root_cause}

=====================
EXECUTION REPORT
=====================

{json.dumps(execution, indent=2)}

=====================
TARGET FILE
=====================

{file_path}

=====================
CURRENT FILE
=====================

{current_content}

=====================
RELATED FILES
=====================

{related}

=====================
INSTRUCTIONS
=====================

Fix this file completely.

Do NOT make the minimum possible edit.

Instead:

- Fix the reported bug.
- Fix any related bug you discover.
- Fix broken imports.
- Fix inconsistent names.
- Fix invalid references.
- Fix missing configuration.
- Fix dependency usage.
- Fix SQLAlchemy compatibility.
- Fix FastAPI compatibility.
- Fix Pydantic v2 compatibility.
- Fix async/sync inconsistencies.
- Fix response models.
- Fix type hints.
- Fix package exports.
- Preserve working logic.

Assume this is your ONLY chance to edit this file.

Do NOT introduce placeholders.

Do NOT remove functionality.

Do NOT leave TODO comments.

Output ONLY the COMPLETE corrected file.

No markdown.

No explanations.

No JSON.
"""