"""
Pydantic schemas for API requests/responses.

Defines all DTOs used by the API layer.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


# ==================== Auth Schemas ====================

class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    """Login request."""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    """User info response."""
    id: str
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Execution Schemas ====================

class ExecuteRequest(BaseModel):
    """Tool execution request."""
    input_text: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    overrides: Optional[Dict[str, Any]] = None


class ExecuteResponse(BaseModel):
    """Tool execution response."""
    success: bool
    execution_id: str
    tool_name: Optional[str]
    result: Optional[Any]
    error: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PipelineStage(str, Enum):
    """Pipeline execution stages."""
    ENTITY_EXTRACTION = "entity_extraction"
    INTENT_CLASSIFICATION = "intent_classification"
    RULE_EVALUATION = "rule_evaluation"
    TOOL_SELECTION = "tool_selection"
    PARAMETER_BUILDING = "parameter_building"
    SCHEMA_VALIDATION = "schema_validation"
    TOOL_EXECUTION = "tool_execution"
    RESPONSE_FORMATTING = "response_formatting"


class PipelineStageResult(BaseModel):
    """Result of a single pipeline stage."""
    stage: PipelineStage
    success: bool
    duration_ms: float
    output: Dict[str, Any]
    error: Optional[str] = None


class ExecuteDetailedResponse(BaseModel):
    """Detailed execution response with pipeline info."""
    success: bool
    execution_id: str
    tool_name: Optional[str]
    result: Optional[Any]
    error: Optional[str]
    pipeline_stages: List[PipelineStageResult]
    total_duration_ms: float


# ==================== Tool Schemas ====================

class ToolSchema(BaseModel):
    """Tool definition schema."""
    tool_id: str
    tool_name: str
    description: Optional[str]
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]]
    category: Optional[str]
    tags: List[str] = Field(default_factory=list)
    server_id: str


class ToolListResponse(BaseModel):
    """List of tools response."""
    tools: List[ToolSchema]
    total: int


class ToolExecuteRequest(BaseModel):
    """Direct tool execution request."""
    tool_name: str
    parameters: Dict[str, Any]


# ==================== Server Schemas ====================

class ServerStatus(str, Enum):
    """Server status enum."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISCOVERING = "discovering"


class ServerSchema(BaseModel):
    """Server definition schema."""
    server_id: str
    name: str
    description: Optional[str]
    transport: str
    status: ServerStatus
    enabled: bool
    tools_count: int = 0


class ServerListResponse(BaseModel):
    """List of servers response."""
    servers: List[ServerSchema]
    total: int


class DiscoveryResponse(BaseModel):
    """Discovery result response."""
    server_id: str
    success: bool
    tools_discovered: int
    error: Optional[str]


class DiscoveryAllResponse(BaseModel):
    """Discovery all results response."""
    results: List[DiscoveryResponse]
    total_servers: int
    successful_servers: int
    total_tools: int


# ==================== Audit Schemas ====================

class AuditLogSchema(BaseModel):
    """Audit log entry schema."""
    id: str
    input_text: str
    intent: Optional[str]
    intent_confidence: Optional[float]
    tool_name: Optional[str]
    execution_status: str
    execution_duration_ms: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """List of audit logs response."""
    logs: List[AuditLogSchema]
    total: int
    page: int
    page_size: int


# ==================== Health Schemas ====================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    database: str
    mcp_servers: Dict[str, str]
    uptime_seconds: float


# ==================== Error Schemas ====================

class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
