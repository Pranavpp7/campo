import asyncio
from agents.localpulse import run_localpulse

async def main():
    result = await run_localpulse(
        task="I run a bar near AT&T Stadium in Dallas. What should I expect around the Brazil vs Morocco match on June 13?",
        session_id="test-localpulse-1",
        user_id="test-user-1",
    )
    print("RESULT:", result["result"])
    print("ERROR:", result["error"])

if __name__ == "__main__":
    asyncio.run(main())