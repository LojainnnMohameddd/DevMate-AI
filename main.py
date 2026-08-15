import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from agents.orchestrator import execute_plan


def main():
    user_request = input("💬 Enter your request: ")

    asyncio.run(
        execute_plan(user_request)
    )


if __name__ == "__main__":
    main()