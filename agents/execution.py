import subprocess
import sys
from pathlib import Path


def execute_project(project_path: str) -> dict:
    """
    Executes a generated Python project and returns the execution result.

    Returns:
    {
        "passed": bool,
        "return_code": int,
        "stdout": str,
        "stderr": str,
        "errors": list[str]
    }
    """

    project_path = Path(project_path)

    requirements = project_path / "requirements.txt"

    if requirements.exists():
        print("\nInstalling dependencies...")

        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                "requirements.txt",
            ],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        print("\n===== PIP STDOUT =====")
        print(install.stdout)

        print("\n===== PIP STDERR =====")
        print(install.stderr)

    if not project_path.exists():
        return {
            "passed": False,
            "return_code": -1,
            "stdout": "",
            "stderr": "",
            "errors": [f"Project path '{project_path}' does not exist."]
        }

    # Find entry point
    entry_candidates = [
        "main.py",
        "app.py",
        "run.py",
        "app/main.py",
        "src/main.py",
        "src/app.py",
    ]

    entry_file = None

    for file in entry_candidates:
        candidate = project_path / file
        if candidate.exists():
            entry_file = candidate
            break

    if entry_file is None:
        return {
            "passed": False,
            "return_code": -1,
            "stdout": "",
            "stderr": "",
            "errors": [
                "No entry point found (main.py, app.py, run.py)."
            ]
        }

    try:
        module = (
            entry_file.relative_to(project_path)
            .with_suffix("")
            .as_posix()
            .replace("/", ".")
        )

        result = subprocess.run(
            [sys.executable, "-m", module],
            cwd=project_path,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
        )
        errors = []

        if result.returncode != 0:
            errors.append(result.stderr.strip())

        return {
            "passed": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "errors": errors
        }

    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "return_code": -1,
            "stdout": "",
            "stderr": "",
            "errors": [
                "Execution timed out after 30 seconds."
            ]
        }

    except Exception as e:
        return {
            "passed": False,
            "return_code": -1,
            "stdout": "",
            "stderr": "",
            "errors": [str(e)]
        }