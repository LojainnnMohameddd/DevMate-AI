import asyncio

from agents.orchestrator import execute_plan


def main():
    user_request = input("💬 Enter your request: ")

    asyncio.run(
        execute_plan(user_request)
    )


if __name__ == "__main__":
    main()