"""
Complete database reset - drops and recreates ALL tables.
"""
import asyncio
from database.connection import async_engine
from database.connection import Base

# Import all models so SQLAlchemy knows about them
import database.models  # noqa: F401

async def reset_database():
    """Drop all tables and recreate from models."""
    print("=" * 60)
    print("DATABASE RESET - This will DELETE ALL DATA")
    print("=" * 60)
    
    # Drop all tables
    print("\n[1/2] Dropping all tables...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("✓ All tables dropped")
    
    # Recreate all tables
    print("\n[2/2] Creating all tables from models...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ All tables created")
    
    print("\n" + "=" * 60)
    print("DATABASE RESET COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. python seed_users.py")
    print("  2. python main.py")

if __name__ == "__main__":
    asyncio.run(reset_database())
