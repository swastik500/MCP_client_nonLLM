"""
Database migration script to add missing columns.
Run this if you get "column does not exist" errors.
"""
import asyncio
from sqlalchemy import text
from database.connection import get_async_session, init_database

# Import models so SQLAlchemy knows about them
import database.models  # noqa: F401

async def check_and_add_column(session, table_name, column_name, column_type):
    """Check if column exists and add it if missing."""
    try:
        result = await session.execute(
            text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table_name}' AND column_name='{column_name}'")
        )
        if result.fetchone() is None:
            print(f"Adding {column_name} column to {table_name} table...")
            await session.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            )
            print(f"✓ Added {column_name} column")
            return True
        else:
            print(f"✓ {column_name} column already exists")
            return False
    except Exception as e:
        print(f"Error checking/adding {column_name}: {e}")
        raise

async def migrate_database():
    """Add missing columns to existing tables."""
    print("Starting database migration...")
    
    # Initialize database (creates tables if they don't exist)
    await init_database()
    
    async with get_async_session() as session:
        changes_made = False
        
        # Add missing columns to users table
        users_columns = [
            ('full_name', 'VARCHAR(255)'),
            ('permissions', 'JSONB DEFAULT \'[]\'::jsonb'),
            ('is_verified', 'BOOLEAN DEFAULT FALSE'),
            ('last_login_at', 'TIMESTAMP'),
        ]
        
        for column_name, column_type in users_columns:
            try:
                if await check_and_add_column(session, 'users', column_name, column_type):
                    changes_made = True
            except Exception as e:
                print(f"Failed to add {column_name}: {e}")
                await session.rollback()
                continue
        
        if changes_made:
            try:
                await session.commit()
                print("\n✓ All changes committed successfully")
            except Exception as e:
                print(f"Error committing changes: {e}")
                await session.rollback()
                raise
    
    print("\nMigration complete!")

if __name__ == "__main__":
    asyncio.run(migrate_database())
