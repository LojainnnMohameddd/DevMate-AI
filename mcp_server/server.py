from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


PROJECTS_ROOT = Path("generated_projects").resolve()


transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "localhost:*",
        "127.0.0.1:*",
        "mcp:*",
    ],
)


mcp = FastMCP(
    "DevMate",
    transport_security=transport_security,
)


def _safe_path(file_path: str) -> Path:
    path = (PROJECTS_ROOT / file_path).resolve()

    if not path.is_relative_to(PROJECTS_ROOT):
        raise ValueError(
            f"Path '{file_path}' is outside generated_projects."
        )

    return path


@mcp.tool()
def create_folder(folder_name: str) -> str:
    path = _safe_path(folder_name)

    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        f"Folder '{folder_name}' created successfully!"
    )


@mcp.tool()
def create_file(file_path: str) -> str:
    path = _safe_path(file_path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.touch(
        exist_ok=True
    )

    return (
        f"File '{file_path}' created successfully!"
    )


@mcp.tool()
def write_file(
    file_path: str,
    content: str,
) -> str:

    path = _safe_path(file_path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content,
        encoding="utf-8",
    )

    return (
        f"Content written to '{file_path}' successfully!"
    )


@mcp.tool()
def read_file(file_path: str) -> str:
    path = _safe_path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File '{file_path}' does not exist."
        )

    if not path.is_file():
        raise IsADirectoryError(
            f"'{file_path}' is not a file."
        )

    return path.read_text(
        encoding="utf-8"
    )


@mcp.tool()
def list_files(
    project_name: str,
) -> list[str]:

    project_path = _safe_path(
        project_name
    )

    if not project_path.exists():
        raise FileNotFoundError(
            f"Project '{project_name}' does not exist."
        )

    if not project_path.is_dir():
        raise NotADirectoryError(
            f"'{project_name}' is not a directory."
        )

    return sorted(
        str(path.relative_to(project_path))
        for path in project_path.rglob("*")
        if path.is_file()
    )


@mcp.tool()
def delete_file(file_path: str) -> str:
    path = _safe_path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File '{file_path}' does not exist."
        )

    if not path.is_file():
        raise IsADirectoryError(
            f"'{file_path}' is not a file."
        )

    path.unlink()

    return (
        f"File '{file_path}' deleted successfully!"
    )


if __name__ == "__main__":

    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = 8000

    mcp.run(
        transport="streamable-http"
    )