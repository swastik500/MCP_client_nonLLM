"""
Tool Registry - PostgreSQL-backed registry for MCP tools.

The registry is the SINGLE SOURCE OF TRUTH for:
- MCP server configurations
- Tool definitions
- Input/output schemas

STRICT CONSTRAINTS:
- PostgreSQL + SQLAlchemy only
- No tool-specific logic
- Registry operations are control-plane
- Execution uses schemas from registry
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    MCPServer, MCPTool, TransportType, ServerStatus,
    IntentTrainingData, ForcedIntentOverride, RuleDefinition
)
from database.connection import get_async_session, AsyncSessionFactory

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """Lightweight tool information for lookups."""
    tool_id: str
    tool_name: str
    server_id: str
    description: Optional[str]
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]]
    category: Optional[str]
    tags: List[str]
    enabled: bool
    timeout_seconds: int
    
    @classmethod
    def from_model(cls, model: MCPTool) -> "ToolInfo":
        """Create from database model."""
        return cls(
            tool_id=str(model.id),
            tool_name=model.tool_name,
            server_id=str(model.server_id),
            description=model.description,
            input_schema=model.input_schema,
            output_schema=model.output_schema,
            category=model.category,
            tags=model.tags or [],
            enabled=model.enabled,
            timeout_seconds=model.timeout_seconds or 60,
        )


@dataclass
class ServerInfo:
    """Lightweight server information for lookups."""
    server_id: str
    name: str
    transport: str
    command: Optional[str]
    args: List[str]
    url: Optional[str]
    status: str
    enabled: bool
    
    @classmethod
    def from_model(cls, model: MCPServer) -> "ServerInfo":
        """Create from database model."""
        return cls(
            server_id=model.server_id,
            name=model.name,
            transport=model.transport.value,
            command=model.command,
            args=model.args or [],
            url=model.url,
            status=model.status.value,
            enabled=model.enabled,
        )


class ToolRegistry:
    """
    PostgreSQL-backed tool registry.
    
    Provides:
    - Server management (CRUD)
    - Tool management (CRUD)
    - Schema lookups
    - Tool discovery by intent
    """
    
    def __init__(self):
        """Initialize the registry."""
        self._cache: Dict[str, ToolInfo] = {}
        self._cache_valid = False
    
    async def invalidate_cache(self) -> None:
        """Invalidate the tool cache."""
        self._cache.clear()
        self._cache_valid = False
        logger.debug("Tool cache invalidated")
    
    # ==================== Server Operations ====================
    
    async def register_server(
        self,
        server_id: str,
        name: str,
        transport: TransportType,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        url: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """
        Register a new MCP server.
        
        Returns:
            Database UUID of the created server
        """
        async def _register(sess: AsyncSession) -> str:
            # Check if server already exists
            existing = await sess.execute(
                select(MCPServer).where(MCPServer.server_id == server_id)
            )
            existing_server = existing.scalar_one_or_none()
            
            if existing_server:
                # Update existing server
                existing_server.name = name
                existing_server.transport = transport.name
                existing_server.command = command
                existing_server.args = args or []
                existing_server.url = url
                existing_server.description = description
                existing_server.config = config or {}
                existing_server.updated_at = datetime.utcnow()
                await sess.flush()
                return str(existing_server.id)
            
            # Create new server
            server = MCPServer(
                server_id=server_id,
                name=name,
                transport=transport.name,
                command=command,
                args=args or [],
                url=url,
                description=description,
                config=config or {},
            )
            sess.add(server)
            await sess.flush()
            logger.info(f"Registered server: {server_id}")
            return str(server.id)
        
        if session:
            return await _register(session)
        else:
            async with get_async_session() as sess:
                result = await _register(sess)
                return result
    
    async def get_server(
        self,
        server_id: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[ServerInfo]:
        """Get server by server_id."""
        async def _get(sess: AsyncSession) -> Optional[ServerInfo]:
            result = await sess.execute(
                select(MCPServer).where(MCPServer.server_id == server_id)
            )
            server = result.scalar_one_or_none()
            return ServerInfo.from_model(server) if server else None
        
        if session:
            return await _get(session)
        else:
            async with get_async_session() as sess:
                return await _get(sess)
    
    async def get_server_by_uuid(
        self,
        server_uuid: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[MCPServer]:
        """Get server model by UUID."""
        async def _get(sess: AsyncSession) -> Optional[MCPServer]:
            result = await sess.execute(
                select(MCPServer).where(MCPServer.id == uuid.UUID(server_uuid))
            )
            return result.scalar_one_or_none()
        
        if session:
            return await _get(session)
        else:
            async with get_async_session() as sess:
                return await _get(sess)
    
    async def list_servers(
        self,
        enabled_only: bool = True,
        session: Optional[AsyncSession] = None,
    ) -> List[ServerInfo]:
        """List all registered servers."""
        async def _list(sess: AsyncSession) -> List[ServerInfo]:
            query = select(MCPServer)
            if enabled_only:
                query = query.where(MCPServer.enabled == True)
            result = await sess.execute(query)
            servers = result.scalars().all()
            return [ServerInfo.from_model(s) for s in servers]
        
        if session:
            return await _list(session)
        else:
            async with get_async_session() as sess:
                return await _list(sess)
    
    async def update_server_status(
        self,
        server_id: str,
        status: ServerStatus,
        error: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> None:
        """Update server status."""
        async def _update(sess: AsyncSession) -> None:
            await sess.execute(
                update(MCPServer)
                .where(MCPServer.server_id == server_id)
                .values(
                    status=status,
                    last_error=error,
                    updated_at=datetime.utcnow()
                )
            )
        
        if session:
            await _update(session)
        else:
            async with get_async_session() as sess:
                await _update(sess)
    
    # ==================== Tool Operations ====================
    
    async def register_tool(
        self,
        server_uuid: str,
        tool_name: str,
        input_schema: Dict[str, Any],
        description: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        intent_patterns: Optional[List[str]] = None,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """
        Register a new tool.
        
        Returns:
            Database UUID of the created tool
        """
        async def _register(sess: AsyncSession) -> str:
            server_id = uuid.UUID(server_uuid)
            
            # Check if tool already exists for this server
            existing = await sess.execute(
                select(MCPTool).where(
                    and_(
                        MCPTool.server_id == server_id,
                        MCPTool.tool_name == tool_name
                    )
                )
            )
            existing_tool = existing.scalar_one_or_none()
            
            if existing_tool:
                # Update existing tool
                existing_tool.input_schema = input_schema
                existing_tool.output_schema = output_schema
                existing_tool.description = description
                existing_tool.category = category
                existing_tool.tags = tags or []
                existing_tool.intent_patterns = intent_patterns or []
                existing_tool.updated_at = datetime.utcnow()
                await sess.flush()
                await self.invalidate_cache()
                return str(existing_tool.id)
            
            # Create new tool
            tool = MCPTool(
                server_id=server_id,
                tool_name=tool_name,
                input_schema=input_schema,
                output_schema=output_schema,
                description=description,
                category=category,
                tags=tags or [],
                intent_patterns=intent_patterns or [],
            )
            sess.add(tool)
            await sess.flush()
            await self.invalidate_cache()
            logger.info(f"Registered tool: {tool_name}")
            return str(tool.id)
        
        if session:
            return await _register(session)
        else:
            async with get_async_session() as sess:
                return await _register(sess)
    
    async def get_tool(
        self,
        tool_name: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[ToolInfo]:
        """Get tool by name."""
        async def _get(sess: AsyncSession) -> Optional[ToolInfo]:
            result = await sess.execute(
                select(MCPTool)
                .where(MCPTool.tool_name == tool_name)
                .where(MCPTool.enabled == True)
            )
            tool = result.scalar_one_or_none()
            return ToolInfo.from_model(tool) if tool else None
        
        if session:
            return await _get(session)
        else:
            async with get_async_session() as sess:
                return await _get(sess)
    
    async def get_tool_with_server(
        self,
        tool_name: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[Tuple[ToolInfo, ServerInfo]]:
        """Get tool with its server info."""
        async def _get(sess: AsyncSession) -> Optional[Tuple[ToolInfo, ServerInfo]]:
            result = await sess.execute(
                select(MCPTool)
                .options(selectinload(MCPTool.server))
                .where(MCPTool.tool_name == tool_name)
                .where(MCPTool.enabled == True)
            )
            tool = result.scalar_one_or_none()
            if not tool or not tool.server:
                return None
            return (ToolInfo.from_model(tool), ServerInfo.from_model(tool.server))
        
        if session:
            return await _get(session)
        else:
            async with get_async_session() as sess:
                return await _get(sess)
    
    async def list_tools(
        self,
        server_id: Optional[str] = None,
        category: Optional[str] = None,
        enabled_only: bool = True,
        session: Optional[AsyncSession] = None,
    ) -> List[ToolInfo]:
        """List all registered tools with optional filters."""
        async def _list(sess: AsyncSession) -> List[ToolInfo]:
            query = select(MCPTool)
            
            conditions = []
            if enabled_only:
                conditions.append(MCPTool.enabled == True)
            if server_id:
                # Need to look up server UUID first
                server_result = await sess.execute(
                    select(MCPServer.id).where(MCPServer.server_id == server_id)
                )
                server_uuid = server_result.scalar_one_or_none()
                if server_uuid:
                    conditions.append(MCPTool.server_id == server_uuid)
            if category:
                conditions.append(MCPTool.category == category)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            result = await sess.execute(query)
            tools = result.scalars().all()
            return [ToolInfo.from_model(t) for t in tools]
        
        if session:
            return await _list(session)
        else:
            async with get_async_session() as sess:
                return await _list(sess)
    
    async def find_tool_by_intent(
        self,
        intent: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[ToolInfo]:
        """
        Find a tool that matches the given intent.
        
        Uses intent_patterns stored in the tool definition.
        """
        async def _find(sess: AsyncSession) -> Optional[ToolInfo]:
            # Get all enabled tools
            result = await sess.execute(
                select(MCPTool)
                .where(MCPTool.enabled == True)
            )
            tools = result.scalars().all()
            
            # Search for matching intent pattern
            for tool in tools:
                patterns = tool.intent_patterns or []
                if intent in patterns or intent == tool.tool_name:
                    return ToolInfo.from_model(tool)
            
            # Fallback: try to match by tool name similarity
            for tool in tools:
                if intent.replace("_", "-") == tool.tool_name.replace("_", "-"):
                    return ToolInfo.from_model(tool)
            
            return None
        
        if session:
            return await _find(session)
        else:
            async with get_async_session() as sess:
                return await _find(sess)
    
    async def delete_tools_for_server(
        self,
        server_uuid: str,
        session: Optional[AsyncSession] = None,
    ) -> int:
        """Delete all tools for a server."""
        async def _delete(sess: AsyncSession) -> int:
            result = await sess.execute(
                delete(MCPTool)
                .where(MCPTool.server_id == uuid.UUID(server_uuid))
            )
            await self.invalidate_cache()
            return result.rowcount
        
        if session:
            return await _delete(session)
        else:
            async with get_async_session() as sess:
                return await _delete(sess)
    
    # ==================== Schema Operations ====================
    
    async def get_input_schema(
        self,
        tool_name: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get input schema for a tool."""
        tool = await self.get_tool(tool_name, session)
        return tool.input_schema if tool else None
    
    async def get_output_schema(
        self,
        tool_name: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get output schema for a tool."""
        tool = await self.get_tool(tool_name, session)
        return tool.output_schema if tool else None
    
    # ==================== Intent Training Data ====================
    
    async def get_intent_training_data(
        self,
        validated_only: bool = True,
        session: Optional[AsyncSession] = None,
    ) -> List[Tuple[str, str]]:
        """Get training data for intent classifier."""
        async def _get(sess: AsyncSession) -> List[Tuple[str, str]]:
            query = select(IntentTrainingData)
            if validated_only:
                query = query.where(IntentTrainingData.is_validated == True)
            result = await sess.execute(query)
            data = result.scalars().all()
            return [(d.text, d.intent) for d in data]
        
        if session:
            return await _get(session)
        else:
            async with get_async_session() as sess:
                return await _get(sess)
    
    # ==================== Forced Overrides ====================
    
    async def get_forced_overrides(
        self,
        enabled_only: bool = True,
        session: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """Get forced intent overrides."""
        async def _get(sess: AsyncSession) -> List[Dict[str, Any]]:
            query = select(ForcedIntentOverride)
            if enabled_only:
                query = query.where(ForcedIntentOverride.enabled == True)
            query = query.order_by(ForcedIntentOverride.priority.desc())
            result = await sess.execute(query)
            overrides = result.scalars().all()
            return [
                {
                    "pattern": o.pattern,
                    "pattern_type": o.pattern_type,
                    "target_intent": o.target_intent,
                    "priority": o.priority,
                    "enabled": o.enabled,
                }
                for o in overrides
            ]
        
        if session:
            return await _get(session)
        else:
            async with get_async_session() as sess:
                return await _get(sess)
    
    # ==================== Rules ====================
    
    async def get_rules(
        self,
        rule_type: Optional[str] = None,
        enabled_only: bool = True,
        session: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """Get rule definitions."""
        async def _get(sess: AsyncSession) -> List[Dict[str, Any]]:
            query = select(RuleDefinition)
            conditions = []
            if enabled_only:
                conditions.append(RuleDefinition.enabled == True)
            if rule_type:
                conditions.append(RuleDefinition.rule_type == rule_type)
            if conditions:
                query = query.where(and_(*conditions))
            query = query.order_by(RuleDefinition.priority.desc())
            result = await sess.execute(query)
            rules = result.scalars().all()
            return [
                {
                    "rule_name": r.rule_name,
                    "description": r.description,
                    "rule_type": r.rule_type,
                    "rule_logic": r.rule_logic,
                    "priority": r.priority,
                    "enabled": r.enabled,
                }
                for r in rules
            ]
        
        if session:
            return await _get(session)
        else:
            async with get_async_session() as sess:
                return await _get(sess)


# Singleton instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get or create the tool registry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
