"""
Seed the database with demo users.
Creates admin, user, and guest accounts for testing.
"""
import asyncio
from database.connection import get_async_session
from database.models import User
from api.auth import hash_password

async def seed_users():
    """Create demo users in the database."""
    print("Seeding database with demo users...")
    
    demo_users = [
        {
            "username": "admin",
            "password": "admin",
            "email": "admin@example.com",
            "full_name": "Admin User",
            "role": "admin",
            "is_active": True,
            "is_verified": True,
            "permissions": ["read", "write", "execute", "admin"]
        },
        {
            "username": "user",
            "password": "user",
            "email": "user@example.com",
            "full_name": "Regular User",
            "role": "user",
            "is_active": True,
            "is_verified": True,
            "permissions": ["read", "execute"]
        },
        {
            "username": "guest",
            "password": "guest",
            "email": "guest@example.com",
            "full_name": "Guest User",
            "role": "guest",
            "is_active": True,
            "is_verified": False,
            "permissions": ["read"]
        }
    ]
    
    async with get_async_session() as session:
        for user_data in demo_users:
            # Check if user already exists
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.username == user_data["username"])
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"✓ User '{user_data['username']}' already exists")
                continue
            
            # Create new user
            password = user_data.pop("password")
            user = User(
                **user_data,
                hashed_password=hash_password(password)
            )
            session.add(user)
            print(f"✓ Created user '{user_data['username']}'")
        
        await session.commit()
    
    print("\nDemo users created successfully!")
    print("\nLogin credentials:")
    print("  Admin: admin / admin")
    print("  User:  user / user")
    print("  Guest: guest / guest")

if __name__ == "__main__":
    asyncio.run(seed_users())
