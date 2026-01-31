"""
Application settings - centralized configuration management.
All settings are loaded from environment variables with sensible defaults.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    
    # Allow direct DATABASE_URL override
    DATABASE_URL: Optional[str] = None
    
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "post2004"
    POSTGRES_DB: str = "mcp_client"
    
    @property
    def database_url(self) -> str:
        # Use DATABASE_URL if provided, otherwise construct from parts
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    @property
    def sync_database_url(self) -> str:
        # Convert async URL to sync URL
        if self.DATABASE_URL:
            return self.DATABASE_URL.replace('+asyncpg', '')
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    class Config:
        env_prefix = ""


class JWTSettings(BaseSettings):
    """JWT authentication settings."""
    
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    class Config:
        env_prefix = ""


class NLPSettings(BaseSettings):
    """NLP processing settings."""
    
    SPACY_MODEL: str = "en_core_web_sm"
    INTENT_CONFIDENCE_THRESHOLD: float = 0.7
    ENTITY_EXTRACTION_ENABLED: bool = True
    
    class Config:
        env_prefix = ""


class MCPSettings(BaseSettings):
    """MCP client settings."""
    
    MCP_SERVERS_CONFIG_PATH: str = "config/mcp_servers.json"
    MCP_DISCOVERY_TIMEOUT: int = 30
    MCP_EXECUTION_TIMEOUT: int = 60
    MCP_RETRY_ATTEMPTS: int = 3
    MCP_RETRY_DELAY: float = 1.0
    
    class Config:
        env_prefix = ""


class LoggingSettings(BaseSettings):
    """Logging settings."""
    
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = "logs/mcp_client.log"
    
    class Config:
        env_prefix = ""


class AppSettings(BaseSettings):
    """Main application settings."""
    
    APP_NAME: str = "MCP Client"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    
    # Nested settings
    database: DatabaseSettings = DatabaseSettings()
    jwt: JWTSettings = JWTSettings()
    nlp: NLPSettings = NLPSettings()
    mcp: MCPSettings = MCPSettings()
    logging: LoggingSettings = LoggingSettings()
    
    class Config:
        env_prefix = ""


@lru_cache()
def get_settings() -> AppSettings:
    """Get cached application settings."""
    return AppSettings()


settings = get_settings()
