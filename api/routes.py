"""
API Routes - FastAPI endpoints.

All routes delegate to appropriate service layers.
NO business logic in routes.
"""

from typing import Optional, List
from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from api.schemas import (
    TokenResponse, LoginRequest, RegisterRequest, UserResponse,
    ExecuteRequest, ExecuteResponse, ExecuteDetailedResponse,
    ToolSchema, ToolListResponse, ToolExecuteRequest,
    ServerSchema, ServerListResponse, DiscoveryResponse, DiscoveryAllResponse,
    AuditLogSchema, AuditLogListResponse,
    HealthResponse, ErrorResponse,
)
from api.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
)
from api.dependencies import (
    get_current_user, require_authenticated, require_admin,
    get_user_context,
)
from database.connection import get_session
from database.models import User, MCPServer, MCPTool, ExecutionAuditLog
from registry.tool_registry import get_registry
from discovery.service import get_discovery_service
from config.settings import settings


# ==================== Auth Routes ====================

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Register a new user."""
    # Check if username exists
    existing = await session.execute(
        select(User).where(User.username == request.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Check if email exists
    existing = await session.execute(
        select(User).where(User.email == request.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    # Create user
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role="user",
    )
    session.add(user)
    await session.flush()
    
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Login and get tokens."""
    # Find user
    result = await session.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    await session.flush()
    
    # Create tokens
    access_token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role=user.role,
    )
    refresh_token = create_refresh_token(user_id=str(user.id))
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@auth_router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_authenticated)):
    """Get current user info."""
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# ==================== Execution Routes ====================

execute_router = APIRouter(prefix="/execute", tags=["Execution"])


@execute_router.post("", response_model=ExecuteResponse)
async def execute(
    request: ExecuteRequest,
    user_context: dict = Depends(get_user_context),
    session: AsyncSession = Depends(get_session),
):
    """
    Execute a tool based on natural language input.
    
    This is the main endpoint that runs the full pipeline:
    1. Entity extraction
    2. Intent classification
    3. Rule evaluation
    4. Tool selection
    5. Parameter building
    6. Schema validation
    7. Tool execution
    8. Response formatting
    """
    # Import pipeline here to avoid circular imports
    from pipeline.orchestrator import get_pipeline, PipelineInput
    
    pipeline = get_pipeline()
    
    # Create pipeline input
    pipeline_input = PipelineInput(
        text=request.input_text,
        user_id=user_context.get("user_id"),
        user_role=user_context.get("role", "guest"),
        user_permissions=user_context.get("permissions", []),
        session_id=request.session_id or str(uuid.uuid4()),
        context=request.context or {},
        overrides=request.overrides or {},
    )
    
    # Execute pipeline
    result = await pipeline.execute(pipeline_input)
    
    # Create audit log
    audit_log = ExecutionAuditLog(
        user_id=uuid.UUID(user_context["user_id"]) if user_context.get("user_id") else None,
        session_id=pipeline_input.session_id,
        input_text=request.input_text,
        extracted_entities=result.entities.to_dict() if result.entities else None,
        intent=result.intent.intent if result.intent else None,
        intent_confidence=result.intent.confidence if result.intent else None,
        forced_intent=result.intent.is_forced if result.intent else False,
        rule_decision=result.rule_result.decision if result.rule_result and result.rule_result.decision else None,
        rule_context=result.rule_result.to_dict() if result.rule_result else None,
        tool_name=result.tool_name,
        execution_parameters=result.parameters,
        execution_status=result.status,
        execution_started_at=result.started_at,
        execution_completed_at=result.completed_at,
        execution_duration_ms=result.duration_ms,
        result_data=result.result,
        error_message=result.error,
    )
    session.add(audit_log)
    await session.flush()
    
    return ExecuteResponse(
        success=result.success,
        execution_id=str(audit_log.id),
        tool_name=result.tool_name,
        result=result.result,
        error=result.error,
        metadata={
            "intent": result.intent.intent if result.intent else None,
            "confidence": result.intent.confidence if result.intent else None,
            "duration_ms": result.duration_ms,
        }
    )


# ==================== Tool Routes ====================

tools_router = APIRouter(prefix="/tools", tags=["Tools"])


@tools_router.get("", response_model=ToolListResponse)
async def list_tools(
    category: Optional[str] = None,
    server_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """List all available tools."""
    registry = get_registry()
    tools = await registry.list_tools(
        server_id=server_id,
        category=category,
        session=session,
    )
    
    return ToolListResponse(
        tools=[
            ToolSchema(
                tool_id=t.tool_id,
                tool_name=t.tool_name,
                description=t.description,
                input_schema=t.input_schema,
                output_schema=t.output_schema,
                category=t.category,
                tags=t.tags,
                server_id=t.server_id,
            )
            for t in tools
        ],
        total=len(tools),
    )


@tools_router.get("/{tool_name}", response_model=ToolSchema)
async def get_tool(
    tool_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific tool by name."""
    registry = get_registry()
    tool = await registry.get_tool(tool_name, session)
    
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_name}"
        )
    
    return ToolSchema(
        tool_id=tool.tool_id,
        tool_name=tool.tool_name,
        description=tool.description,
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
        category=tool.category,
        tags=tool.tags,
        server_id=tool.server_id,
    )


@tools_router.post("/{tool_name}/execute", response_model=ExecuteResponse)
async def execute_tool_direct(
    tool_name: str,
    request: ToolExecuteRequest,
    user: User = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
):
    """
    Execute a tool directly with parameters.
    
    Bypasses NLP and intent classification.
    Still validates against schema and applies rules.
    """
    # Import pipeline components
    from pipeline.orchestrator import get_pipeline
    from executor.schema_executor import get_schema_executor
    from mcp.client import get_mcp_client
    from rules.engine import get_rule_engine, RuleContext, RuleDecision
    
    registry = get_registry()
    
    # Get tool with server info
    tool_info = await registry.get_tool_with_server(tool_name, session)
    if not tool_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_name}"
        )
    
    tool, server = tool_info
    
    # Validate parameters against schema
    executor = get_schema_executor()
    is_valid, errors = executor.validate_parameters(
        request.parameters,
        tool.input_schema,
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Parameter validation failed", "errors": errors}
        )
    
    # Apply rules
    rule_engine = get_rule_engine()
    rule_context = RuleContext(
        user_id=str(user.id),
        user_role=user.role,
        user_permissions=user.permissions or [],
        intent="direct_execute",
        intent_confidence=1.0,
        is_forced_intent=True,
        tool_name=tool_name,
        tool_category=tool.category,
    )
    
    rule_result = rule_engine.evaluate(rule_context)
    
    if rule_result.decision == RuleDecision.DENY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Execution denied: {rule_result.reason}"
        )
    
    # Execute tool
    mcp_client = get_mcp_client()
    result = await mcp_client.call_tool(
        server_id=server.server_id,
        tool_name=tool_name,
        arguments=request.parameters,
    )
    
    # Create audit log
    audit_log = ExecutionAuditLog(
        user_id=user.id,
        input_text=f"[DIRECT] {tool_name}",
        intent="direct_execute",
        intent_confidence=1.0,
        forced_intent=True,
        tool_name=tool_name,
        execution_parameters=request.parameters,
        execution_status="success" if result.success else "failed",
        result_data=result.content,
        error_message=result.error,
    )
    session.add(audit_log)
    await session.flush()
    
    return ExecuteResponse(
        success=result.success,
        execution_id=str(audit_log.id),
        tool_name=tool_name,
        result=result.content,
        error=result.error,
        metadata=result.metadata,
    )


# ==================== Server Routes ====================

servers_router = APIRouter(prefix="/servers", tags=["Servers"])


@servers_router.get("", response_model=ServerListResponse)
async def list_servers(
    session: AsyncSession = Depends(get_session),
):
    """List all MCP servers."""
    result = await session.execute(
        select(MCPServer, func.count(MCPTool.id).label("tools_count"))
        .outerjoin(MCPTool)
        .group_by(MCPServer.id)
    )
    servers_data = result.all()
    
    servers = []
    for server, tools_count in servers_data:
        servers.append(ServerSchema(
            server_id=server.server_id,
            name=server.name,
            description=server.description,
            transport=server.transport.value,
            status=server.status.value,
            enabled=server.enabled,
            tools_count=tools_count or 0,
        ))
    
    return ServerListResponse(
        servers=servers,
        total=len(servers),
    )


@servers_router.post("/discover", response_model=DiscoveryAllResponse)
async def discover_all(
    user: User = Depends(require_admin),
):
    """
    Trigger discovery for all configured servers.
    
    Requires admin access.
    """
    discovery = get_discovery_service()
    discovery.load_config()
    results = await discovery.discover_all()
    
    return DiscoveryAllResponse(
        results=[
            DiscoveryResponse(
                server_id=r.server_id,
                success=r.success,
                tools_discovered=r.tools_discovered,
                error=r.error,
            )
            for r in results
        ],
        total_servers=len(results),
        successful_servers=sum(1 for r in results if r.success),
        total_tools=sum(r.tools_discovered for r in results),
    )


@servers_router.post("/{server_id}/discover", response_model=DiscoveryResponse)
async def discover_server(
    server_id: str,
    user: User = Depends(require_admin),
):
    """
    Trigger discovery for a specific server.
    
    Requires admin access.
    """
    discovery = get_discovery_service()
    discovery.load_config()
    result = await discovery.refresh_server(server_id)
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server not found: {server_id}"
        )
    
    return DiscoveryResponse(
        server_id=result.server_id,
        success=result.success,
        tools_discovered=result.tools_discovered,
        error=result.error,
    )


# ==================== Audit Routes ====================

audit_router = APIRouter(prefix="/audit", tags=["Audit"])


@audit_router.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    tool_name: Optional[str] = None,
    status: Optional[str] = None,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    List execution audit logs.
    
    Requires admin access.
    """
    query = select(ExecutionAuditLog)
    
    if tool_name:
        query = query.where(ExecutionAuditLog.tool_name == tool_name)
    if status:
        query = query.where(ExecutionAuditLog.execution_status == status)
    
    # Get total count
    count_query = select(func.count(ExecutionAuditLog.id))
    if tool_name:
        count_query = count_query.where(ExecutionAuditLog.tool_name == tool_name)
    if status:
        count_query = count_query.where(ExecutionAuditLog.execution_status == status)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get paginated results
    query = query.order_by(ExecutionAuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await session.execute(query)
    logs = result.scalars().all()
    
    return AuditLogListResponse(
        logs=[
            AuditLogSchema(
                id=str(log.id),
                input_text=log.input_text,
                intent=log.intent,
                intent_confidence=log.intent_confidence,
                tool_name=log.tool_name,
                execution_status=log.execution_status.value if log.execution_status else "unknown",
                execution_duration_ms=log.execution_duration_ms,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ==================== Health Routes ====================

health_router = APIRouter(tags=["Health"])

_start_time = datetime.utcnow()


@health_router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_session),
):
    """Health check endpoint."""
    from mcp.client import get_mcp_client
    
    # Check database
    try:
        await session.execute(select(1))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    # Check MCP servers
    mcp_client = get_mcp_client()
    server_statuses = {}
    for server_id in mcp_client.list_connections():
        connection = mcp_client.get_connection(server_id)
        if connection and connection.is_initialized:
            server_statuses[server_id] = "connected"
        else:
            server_statuses[server_id] = "disconnected"
    
    uptime = (datetime.utcnow() - _start_time).total_seconds()
    
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        version=settings.APP_VERSION,
        database=db_status,
        mcp_servers=server_statuses,
        uptime_seconds=uptime,
    )


@health_router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes."""
    return {"status": "ready"}


@health_router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes."""
    return {"status": "alive"}
