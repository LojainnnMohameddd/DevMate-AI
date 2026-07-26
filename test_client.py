import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client(
        "http://127.0.0.1:8000/mcp"
    ) as (read_stream, write_stream, _):

        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()

            result = await session.call_tool(
                "write_file",
                {
                    "file_path": "book_api/app/main.py",
                    "content": """from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Hello DevMate!"}
"""
                }
            )

            print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())