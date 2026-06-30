import asyncio
import sys
from app.database import engine, Base
from app.models import *

async def reset():
    print("Dropping existing tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    print("Creating new tables with updated schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("Database reset complete!")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset())
