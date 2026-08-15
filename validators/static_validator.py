import ast
from pathlib import Path
import sys

STANDARD_LIBS = {
    "os",
    "sys",
    "json",
    "typing",
    "pathlib",
    "collections",
    "datetime",
    "math",
    "re",
    "asyncio",
    "logging",
    "functools",
    "itertools",
    "enum",
    "dataclasses",
    "abc",
    "uuid",
    "time",
    "copy",
}

STANDARD_LIBS |= sys.stdlib_module_names

def validate_project(plan, project):

    report = {
        "missing_files": [],
        "empty_files": [],
        "missing_requirements": [],
        "broken_imports": [],
    }

    # ----------------------------------
    # Planned vs Generated files
    # ----------------------------------

    planned_files = {
        step["args"]["file_path"]
        for step in plan
        if step["tool"] == "create_file"
    }

    generated_files = {
        file["path"]
        for file in project["files"]
    }

    report["missing_files"] = sorted(
        planned_files - generated_files
    )

    # ----------------------------------
    # requirements.txt
    # ----------------------------------

    requirements = set()

    for file in project["files"]:

        if file["path"].endswith("requirements.txt"):

            requirements = {
                line.strip().split("==")[0].lower()
                for line in file["content"].splitlines()
                if line.strip()
            }

    # ----------------------------------
    # Validate every python file
    # ----------------------------------

    imported_packages = set()

    for file in project["files"]:

        path = file["path"]

        if not path.endswith(".py"):
            continue

        content = file["content"]

        # ----------------------------
        # Empty file
        # ----------------------------

        if (
            Path(path).name != "__init__.py"
            and content.strip() == ""
        ):
            report["empty_files"].append(path)

        try:

            tree = ast.parse(content)

        except SyntaxError:

            report["broken_imports"].append({
                "file": path,
                "error": "Syntax error"
            })

            continue

        # ----------------------------
        # Parse imports
        # ----------------------------

        for node in ast.walk(tree):

            # import xxx

            if isinstance(node, ast.Import):

                for alias in node.names:

                    module = alias.name.split(".")[0]

                    imported_packages.add(module)

            # from xxx import yyy

            elif isinstance(node, ast.ImportFrom):

                if node.module is None:
                    continue

                module = node.module

                root = module.split(".")[0]

                imported_packages.add(root)

                # local import check

                if root in {
                    "app",
                    "student_api",
                }:

                    expected = module.replace(".", "/") + ".py"

                    if expected not in generated_files:

                        report["broken_imports"].append({
                            "file": path,
                            "import": module
                        })

    # ----------------------------------
    # Missing requirements
    # ----------------------------------

    ignore = {
        *STANDARD_LIBS,
        "app",
        "student_api",

        # Local project modules
        "config",
        "database",
        "models",
        "routers",
        "schemas",
        "services",
        "__future__",
        "main",
        "student",
        "student_router",
        "student_service",
    }

    for package in sorted(imported_packages):

        if package in ignore:
            continue

        # Handle common package aliases
        mapped = {
            "fastapi": "fastapi",
            "uvicorn": "uvicorn",
            "dotenv": "python-dotenv",
            "pydantic": "pydantic",
            "sqlalchemy": "sqlalchemy",
            "tortoise": "tortoise-orm",
            "pydantic_settings": "pydantic-settings",
        }.get(package, package)

        if mapped.lower() not in requirements:

            report["missing_requirements"].append(mapped)

    # ----------------------------------
    # Remove duplicates
    # ----------------------------------

    report["missing_requirements"] = sorted(
        set(report["missing_requirements"])
    )

    seen = set()
    unique_imports = []

    for item in report["broken_imports"]:

        key = tuple(sorted(item.items()))

        if key not in seen:
            seen.add(key)
            unique_imports.append(item)

    report["broken_imports"] = unique_imports

    report["empty_files"] = sorted(
        set(report["empty_files"])
    )

    return report