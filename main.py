"""
main.py
-------
Interactive CLI for the Lease Management Agent.
Run:  python main.py

Each input line is a new user message. The thread ID is fixed to "cli-session"
so conversation history is preserved across turns within a single run.
Press Ctrl-C or type 'exit' to quit.
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from agent import close_pool, run_agent


async def main() -> None:
    thread_id = "cli-session"
    print("Lease Management Agent — Dubai Real Estate")
    print("Type your message. Enter 'exit' to quit.\n")

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break

            if not user_input or user_input.lower() == "exit":
                break

            response = await run_agent(user_input, thread_id=thread_id)
            print(f"\nAgent: {response}\n")

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
