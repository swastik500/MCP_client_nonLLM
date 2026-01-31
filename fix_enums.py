"""
Fix enum case mismatch between Python and PostgreSQL.
Drops existing enum types and recreates them.
"""
import asyncio
from sqlalchemy import text
from database.connection import get_async_session

async def fix_enums():
    """Fix enum case mismatch."""
    print("Fixing enum case mismatch...")
    
    async with get_async_session() as session:
        try:
            # Drop existing enum types
            print("Dropping existing enum types...")
            await session.execute(text("DROP TYPE IF EXISTS transporttype CASCADE"))
            await session.execute(text("DROP TYPE IF EXISTS serverstatus CASCADE"))
            await session.execute(text("DROP TYPE IF EXISTS executionstatus CASCADE"))
            await session.execute(text("DROP TYPE IF EXISTS ruledecision CASCADE"))
            
            # Create new enum types with lowercase values
            print("Creating enum types with correct values...")
            await session.execute(text("""
                CREATE TYPE transporttype AS ENUM ('stdio', 'http', 'websocket')
            """))
            await session.execute(text("""
                CREATE TYPE serverstatus AS ENUM ('active', 'inactive', 'error', 'discovering')
            """))
            await session.execute(text("""
                CREATE TYPE executionstatus AS ENUM ('pending', 'running', 'success', 'failed', 'denied')
            """))
            await session.execute(text("""
                CREATE TYPE ruledecision AS ENUM ('allow', 'deny', 'modify')
            """))
            
            await session.commit()
            print("✓ Enum types fixed")
            
        except Exception as e:
            print(f"Error: {e}")
            await session.rollback()
            raise
    
    print("\nNow drop all tables and restart the application:")
    print("  python migrate_db.py")
    print("  python seed_users.py")
    print("  python main.py")

if __name__ == "__main__":
    asyncio.run(fix_enums())
