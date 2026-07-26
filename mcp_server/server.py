from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("DevMate")


@mcp.tool()
def create_folder(folder_name: str) -> str:
    project_path = Path("generated_projects") / folder_name
    project_path.mkdir(parents=True, exist_ok=True)

    return f"Folder '{folder_name}' created successfully!"


@mcp.tool()
def create_file(file_path: str) -> str:
    path = Path("generated_projects") / file_path

    path.parent.mkdir(parents=True, exist_ok=True)

    path.touch(exist_ok=True)

    return f"File '{file_path}' created successfully!"


@mcp.tool()
def write_file(file_path: str, content: str) -> str:
    path = Path("generated_projects") / file_path

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(content, encoding="utf-8")

    return f"Content written to '{file_path}' successfully!"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")