import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():

    async with streamablehttp_client(
        "http://mcp:8000/mcp"
    ) as (read_stream, write_stream, _):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            await session.initialize()

            # -----------------------------
            # Check available tools
            # -----------------------------
            result = await session.list_tools()

            print("\n===== MCP TOOLS =====")

            for tool in result.tools:
                print(f"- {tool.name}")

            # -----------------------------
            # Test create_folder
            # -----------------------------
            print("\n===== 1. CREATE FOLDER =====")

            result = await session.call_tool(
                "create_folder",
                {
                    "folder_name": "mcp_test"
                }
            )

            print(result.content[0].text)

            # -----------------------------
            # Test create_file
            # -----------------------------
            print("\n===== 2. CREATE FILE =====")

            result = await session.call_tool(
                "create_file",
                {
                    "file_path": "mcp_test/test.txt"
                }
            )

            print(result.content[0].text)

            # -----------------------------
            # Test write_file
            # -----------------------------
            print("\n===== 3. WRITE FILE =====")

            result = await session.call_tool(
                "write_file",
                {
                    "file_path": "mcp_test/test.txt",
                    "content": "Hello from DevMate MCP!"
                }
            )

            print(result.content[0].text)

            # -----------------------------
            # Test read_file
            # -----------------------------
            print("\n===== 4. READ FILE =====")

            result = await session.call_tool(
                "read_file",
                {
                    "file_path": "mcp_test/test.txt"
                }
            )

            print("File content:")
            print(result.content[0].text)

            # -----------------------------
            # Test list_files
            # -----------------------------
            print("\n===== 5. LIST FILES =====")

            result = await session.call_tool(
                "list_files",
                {
                    "project_name": "mcp_test"
                }
            )

            print("Files:")
            print(result.content[0].text)

            # -----------------------------
            # Test delete_file
            # -----------------------------
            print("\n===== 6. DELETE FILE =====")

            result = await session.call_tool(
                "delete_file",
                {
                    "file_path": "mcp_test/test.txt"
                }
            )

            print(result.content[0].text)

            print("\n===== MCP TEST COMPLETED =====")


if __name__ == "__main__":
    asyncio.run(main())