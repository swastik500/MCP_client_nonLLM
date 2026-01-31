"""
Test configuration and fixtures.
"""

import pytest
import asyncio
from typing import Generator, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client."""
    client = MagicMock()
    client.connect_server = AsyncMock(return_value=True)
    client.disconnect_server = AsyncMock()
    client.disconnect_all = AsyncMock()
    client.call_tool = AsyncMock()
    client.list_connections = MagicMock(return_value=[])
    client.get_server_tools = MagicMock(return_value=[])
    return client


@pytest.fixture
def sample_tool_schema():
    """Sample tool schema for testing."""
    return {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path to read",
            },
            "encoding": {
                "type": "string",
                "default": "utf-8",
                "description": "File encoding",
            },
        },
        "required": ["path"],
    }


@pytest.fixture
def sample_entities():
    """Sample extracted entities for testing."""
    from nlp.entity_extractor import EntityExtractionResult, ExtractedEntity
    
    return EntityExtractionResult(
        original_text="Read the file /tmp/test.txt",
        normalized_text="Read the file /tmp/test.txt",
        entities=[
            ExtractedEntity(
                text="/tmp/test.txt",
                label="FILE_PATH",
                start=14,
                end=27,
                confidence=0.9,
                metadata={"source": "regex_pattern"},
            ),
        ],
        tokens=["Read", "file", "/tmp/test.txt"],
        noun_chunks=["the file"],
    )
