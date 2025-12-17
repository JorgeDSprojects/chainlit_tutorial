"""
Database initialization script.
This script creates all tables and applies any necessary migrations.
"""
import asyncio
from src.db.database import engine, Base
import src.db.models

async def init_db():
    """Initialize the database with all tables."""
    print("Initializing database...")
    
    async with engine.begin() as conn:
        # Drop all tables (only for development - be careful!)
        # await conn.run_sync(Base.metadata.drop_all)
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database initialized successfully!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
