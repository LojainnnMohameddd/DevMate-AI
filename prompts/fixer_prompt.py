import json


def fixer_prompt(
    user_request,
    plan,
    project,
    review,
    execution,
):
    # Kept for reference/fallback.
    # The current fixer.py uses the two-phase diagnosis + file-fix flow.
    return fixer_diagnosis_prompt(
        user_request=user_request,
        plan=plan,
        project=project,
        review=review,
        execution=execution,
    )


def fixer_diagnosis_prompt(
    user_request,
    plan,
    project,
    review,
    execution,
) -> str:
    """
    Phase 1: whole-project analysis.

    Output is small: root cause + affected file paths.
    The project input contains only file paths, not full file contents.
    """

    project_paths = [
        path
        for path in project.get("files", [])
        if isinstance(path, str)
    ]

    return f"""
You are a Senior Python Software Engineer specializing in debugging.

=====================
USER REQUEST
=====================

{user_request}

=====================
PLAN
=====================

{json.dumps(plan, indent=2)}

=====================
CURRENT PROJECT FILE PATHS
=====================

{json.dumps({"files": project_paths}, indent=2)}

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

1. Read the execution error carefully.

2. Identify the REAL root cause, not just the immediate symptom.

3. Determine which existing project files actually need to change.

4. If the same mistake appears in multiple files, list EVERY affected file.

5. Do not include files that do not need changes.

6. Do not invent files that do not exist unless strictly required to fix
   the root cause.

7. The execution command specified by the USER REQUEST is an explicit
   contract for the generated project.

8. The fix MUST make the project work with the exact execution command
   requested by the user.

9. If the user explicitly requires a command such as:
       python app.py
   then do NOT assume that command-line arguments will be supplied.

10. If the requested execution command contains no input arguments, do NOT
    introduce interactive input() calls as a workaround.

11. Do NOT make the application depend on stdin, terminal interaction,
    prompts, or manual user input merely to pass automated execution.

12. If the requested command runs without arguments, determine the smallest
    behavior that allows that exact command to execute successfully while
    still satisfying the user's requested functionality.

13. Do not replace a requested application with a meaningless placeholder,
    empty success, or arbitrary behavior just to obtain return code 0.

14. Distinguish between:
    - a genuine runtime bug,
    - a mismatch between the generated code and the user's execution
      command,
    - an invalid dependency/import,
    - and an application that incorrectly requires interactive input.

15. Do not blame the Executor for an application-level contract mismatch
    when the generated project itself violates the user's requested
    execution command.

16. Do not invent external dependencies.

17. Do not change architecture unless it is strictly necessary.

18. Do not write fixed code yet. Only diagnose the problem.

=====================
OUTPUT
=====================

Return ONLY valid JSON, no markdown, no explanation.

Schema:

{{
    "root_cause": "concise explanation of the real root cause",
    "affected_files": [
        "path/to/file1.py",
        "path/to/file2.py"
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
) -> str:
    """
    Phase 2: fix ONE file.

    The fixer receives the current file content plus relevant related files
    so it can make a context-aware fix without rewriting unrelated code.

    Output is raw corrected file content.
    """

    return f"""
You are a Senior Python Software Engineer specializing in debugging.

=====================
USER REQUEST
=====================

{user_request}

=====================
DIAGNOSED ROOT CAUSE
=====================

{root_cause}

=====================
EXECUTION ERROR
=====================

{json.dumps(execution, indent=2)}

=====================
FILE TO FIX
=====================

Path:

{file_path}

Current content:

-----
{current_content}
-----

=====================
RELATED PROJECT FILES
=====================

The following files are provided only as context.

Do not modify them. You are fixing ONLY the file specified above.

{json.dumps(related_files, indent=2)}

=====================
INSTRUCTIONS
=====================

1. Apply the fix needed for the diagnosed root cause to THIS FILE ONLY.

2. Preserve all working code. Do not rewrite unrelated parts.

3. Use the related files only to understand imports, function names,
   interfaces, data structures, and dependencies.

4. Make sure the corrected file remains compatible with the related files.

5. The execution command specified in the USER REQUEST is an explicit
   contract and MUST remain supported after the fix.

6. If the user requested a command with no arguments, such as:
       python app.py
   the corrected project MUST be able to execute that exact command
   successfully.

7. If the requested command has no arguments:
   - Do NOT add input().
   - Do NOT require stdin.
   - Do NOT wait for terminal interaction.
   - Do NOT assume hidden command-line arguments.
   - Do NOT solve the problem by simply printing usage and exiting
     with a failure code.

8. If the application needs a default non-interactive execution path
   because the user explicitly requested a no-argument command, implement
   the SMALLEST reasonable behavior that is consistent with the user's
   requested functionality.

9. The no-argument execution path must still perform meaningful application
   behavior. Do not make the program merely print a success message or
   exit successfully without exercising the requested functionality.

10. Do not introduce arbitrary features, demo screens, unrelated output,
    or behavior that was not requested.

11. Respect the user's requested functionality and project structure.

12. Do NOT add sys.path hacks.

13. Do NOT suppress exceptions.

14. Do NOT comment out broken code.

15. Do NOT remove required functionality.

16. Do NOT create new files.

17. Do NOT change the project's architecture unless it is strictly
    necessary to fix the diagnosed root cause.

18. Do NOT leave placeholders.

19. Prefer the smallest targeted change that fixes the actual problem.

20. If the failure is caused by a mismatch between the generated code and
    the user's execution command, fix the generated code rather than
    changing or ignoring the user's command.

21. If the failure is caused by interactive input being unavailable,
    replace the dependency on interactive input with a non-interactive
    execution path that still satisfies the user request.

22. Do not blindly follow an earlier Fixer attempt if that attempt caused
    the current failure. Re-evaluate the current file and execution report.

23. Output ONLY the complete corrected raw content of THIS file.

24. Do NOT output JSON.

25. Do NOT use markdown code fences.

26. Do NOT explain anything before or after the code.

=====================
FINAL OUTPUT
=====================

Return only the complete corrected content of:

{file_path}
"""