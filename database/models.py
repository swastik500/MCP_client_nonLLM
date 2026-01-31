"""
Database models - SQLAlchemy ORM definitions.
All models follow strict schema with audit capabilities.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, Integer, Text, Boolean, DateTime, 
    ForeignKey, JSON, Enum as SQLEnum, Float, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import enum

from database.connection import Base


class TransportType(enum.Enum):
    """Supported MCP transport types."""
    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


class ServerStatus(enum.Enum):
    """MCP server status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISCOVERING = "discovering"


class ExecutionStatus(enum.Enum):
    """Tool execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DENIED = "denied"


class RuleDecision(enum.Enum):
    """Rule engine decisions."""
    ALLOW = "allow"
    DENY = "deny"
    MODIFY = "modify"


class MCPServer(Base):
    """
    MCP Server registration table.
    Stores connection details and metadata for each MCP server.
    """
    __tablename__ = "mcp_servers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Transport configuration
    transport = Column(SQLEnum(TransportType), nullable=False, default=TransportType.STDIO)
    command = Column(String(1024), nullable=True)  # For stdio
    args = Column(JSONB, nullable=True, default=list)  # For stdio
    url = Column(String(1024), nullable=True)  # For HTTP/WebSocket
    headers = Column(JSONB, nullable=True, default=dict)  # For HTTP/WebSocket
    
    # Status tracking
    status = Column(SQLEnum(ServerStatus), nullable=False, default=ServerStatus.INACTIVE)
    last_discovered_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Configuration
    enabled = Column(Boolean, nullable=False, default=True)
    config = Column(JSONB, nullable=True, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tools = relationship("MCPTool", back_populates="server", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_mcp_servers_status_enabled", "status", "enabled"),
    )


class MCPTool(Base):
    """
    MCP Tool registration table.
    Stores tool definitions with full JSON schemas.
    This is the single source of truth for tool execution.
    """
    __tablename__ = "mcp_tools"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id = Column(UUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    
    # Tool identification
    tool_name = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # JSON Schemas - THE source of truth for execution
    input_schema = Column(JSONB, nullable=False)
    output_schema = Column(JSONB, nullable=True)
    
    # Metadata for discovery
    category = Column(String(100), nullable=True)
    tags = Column(JSONB, nullable=True, default=list)
    examples = Column(JSONB, nullable=True, default=list)
    
    # Intent mapping (for ML classifier)
    intent_patterns = Column(JSONB, nullable=True, default=list)
    
    # Execution settings
    enabled = Column(Boolean, nullable=False, default=True)
    requires_confirmation = Column(Boolean, nullable=False, default=False)
    timeout_seconds = Column(Integer, nullable=True, default=60)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    server = relationship("MCPServer", back_populates="tools")
    
    __table_args__ = (
        Index("ix_mcp_tools_server_tool", "server_id", "tool_name", unique=True),
        Index("ix_mcp_tools_category", "category"),
    )


class User(Base):
    """
    User table for authentication and authorization.
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile
    full_name = Column(String(255), nullable=True)
    
    # Authorization
    role = Column(String(50), nullable=False, default="user")
    permissions = Column(JSONB, nullable=True, default=list)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    audit_logs = relationship("ExecutionAuditLog", back_populates="user")
    
    __table_args__ = (
        Index("ix_users_role_active", "role", "is_active"),
    )


class ExecutionAuditLog(Base):
    """
    Audit log for all tool executions.
    Captures complete execution context for debugging and compliance.
    """
    __tablename__ = "execution_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User context
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(255), nullable=True, index=True)
    
    # Input processing
    input_text = Column(Text, nullable=False)
    extracted_entities = Column(JSONB, nullable=True)
    
    # Intent classification
    intent = Column(String(255), nullable=True, index=True)
    intent_confidence = Column(Float, nullable=True)
    forced_intent = Column(Boolean, nullable=False, default=False)
    
    # Rule engine
    rule_decision = Column(SQLEnum(RuleDecision), nullable=True)
    rule_context = Column(JSONB, nullable=True)
    
    # Tool selection
    tool_id = Column(UUID(as_uuid=True), ForeignKey("mcp_tools.id", ondelete="SET NULL"), nullable=True)
    tool_name = Column(String(255), nullable=True, index=True)
    server_id = Column(String(255), nullable=True)
    
    # Execution
    execution_parameters = Column(JSONB, nullable=True)
    execution_status = Column(SQLEnum(ExecutionStatus), nullable=False, default=ExecutionStatus.PENDING)
    execution_started_at = Column(DateTime, nullable=True)
    execution_completed_at = Column(DateTime, nullable=True)
    execution_duration_ms = Column(Integer, nullable=True)
    
    # Result
    result_data = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(100), nullable=True)
    
    # Metadata
    request_metadata = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    tool = relationship("MCPTool")
    
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_status_created", "execution_status", "created_at"),
        Index("ix_audit_logs_tool_created", "tool_name", "created_at"),
    )


class IntentTrainingData(Base):
    """
    Training data for intent classifier.
    Allows dynamic intent model updates without code changes.
    """
    __tablename__ = "intent_training_data"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Training sample
    text = Column(Text, nullable=False)
    intent = Column(String(255), nullable=False, index=True)
    
    # Metadata
    source = Column(String(100), nullable=True)  # manual, auto-generated, feedback
    confidence_weight = Column(Float, nullable=True, default=1.0)
    
    # Validation
    is_validated = Column(Boolean, nullable=False, default=False)
    validated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_intent_data_intent_validated", "intent", "is_validated"),
    )


class ForcedIntentOverride(Base):
    """
    Deterministic intent overrides.
    Pattern-based rules that bypass ML classification.
    """
    __tablename__ = "forced_intent_overrides"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Pattern matching
    pattern = Column(String(500), nullable=False)  # Regex or exact match
    pattern_type = Column(String(50), nullable=False, default="regex")  # regex, exact, prefix
    
    # Target intent
    target_intent = Column(String(255), nullable=False)
    
    # Priority (higher = evaluated first)
    priority = Column(Integer, nullable=False, default=0)
    
    # Status
    enabled = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_forced_overrides_enabled_priority", "enabled", "priority"),
    )


class RuleDefinition(Base):
    """
    JSON-Logic rule definitions for the rule engine.
    """
    __tablename__ = "rule_definitions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Rule identification
    rule_name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # JSON-Logic rule
    rule_logic = Column(JSONB, nullable=False)
    
    # Rule type
    rule_type = Column(String(50), nullable=False)  # permission, threshold, context
    
    # Priority
    priority = Column(Integer, nullable=False, default=0)
    
    # Status
    enabled = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_rules_type_enabled_priority", "rule_type", "enabled", "priority"),
    )
