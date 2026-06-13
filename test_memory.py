import asyncio
from agents.logistics import run_logistics

async def main():
    result = await run_logistics(
        task="I'm flying into Dallas for the Morocco vs Brazil match on June 13. What should I expect and where should I stay?",
        session_id="test-logistics-1",
        user_id="test-user-1",
    )
    print("RESULT:", result["result"])
    print("ERROR:", result["error"])

if __name__ == "__main__":
    asyncio.run(main())