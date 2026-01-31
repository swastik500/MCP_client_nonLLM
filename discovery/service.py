"""
MCP Server Discovery Service.

Handles:
- Loading server config from mcp_servers.json
- Starting servers and performing discovery
- Persisting tools and schemas to database

STRICT CONSTRAINTS:
- Control-plane only
- No execution logic
- Discovery is NOT tool execution
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from mcp.client import get_mcp_client, MCPClient
from mcp.transport import TransportType
from registry.tool_registry import get_registry, ToolRegistry
from database.models import ServerStatus
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Server configuration from mcp_servers.json."""
    id: str
    name: str
    description: Optional[str]
    transport: str
    command: Optional[str] = None
    args: Optional[List[str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerConfig":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            transport=data["transport"],
            command=data.get("command"),
            args=data.get("args", []),
            url=data.get("url"),
            headers=data.get("headers", {}),
            enabled=data.get("enabled", True),
        )


@dataclass
class DiscoveryResult:
    """Result of discovery for a single server."""
    server_id: str
    success: bool
    tools_discovered: int = 0
    error: Optional[str] = None


class DiscoveryService:
    """
    Discovers MCP servers and their tools.
    
    Process:
    1. Load server configs from JSON
    2. Register servers in database
    3. Connect and initialize each server
    4. Discover tools
    5. Persist tool schemas to database
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        mcp_client: Optional[MCPClient] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        """
        Initialize discovery service.
        
        Args:
            config_path: Path to mcp_servers.json
            mcp_client: MCP client instance (optional)
            registry: Tool registry instance (optional)
        """
        self.config_path = Path(config_path or settings.mcp.MCP_SERVERS_CONFIG_PATH)
        self.mcp_client = mcp_client or get_mcp_client()
        self.registry = registry or get_registry()
        self._server_configs: List[ServerConfig] = []
    
    def load_config(self) -> List[ServerConfig]:
        """
        Load server configurations from JSON file.
        Supports both formats:
        - Claude Desktop style: {"mcpServers": {"id": {...}}}
        - Array style: {"servers": [{"id": "...", ...}]}
        
        Returns:
            List of server configurations
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return []
        
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
            
            # Support Claude Desktop format: {"mcpServers": {"id": {...}}}
            if "mcpServers" in data:
                mcp_servers = data["mcpServers"]
                server_list = []
                for server_id, config in mcp_servers.items():
                    if config.get("enabled", True):
                        server_config = {
                            "id": server_id,
                            "name": config.get("name", server_id.title()),
                            "description": config.get("description"),
                            "transport": config.get("transport", "stdio"),
                            "command": config.get("command"),
                            "args": config.get("args", []),
                            "url": config.get("url"),
                            "headers": config.get("headers", {}),
                            "enabled": config.get("enabled", True),
                        }
                        server_list.append(server_config)
            # Support array format: {"servers": [...]}
            elif "servers" in data:
                server_list = [s for s in data["servers"] if s.get("enabled", True)]
            else:
                logger.warning("No 'mcpServers' or 'servers' key found in config")
                return []
            
            self._server_configs = [
                ServerConfig.from_dict(s)
                for s in server_list
            ]
            
            logger.info(f"Loaded {len(self._server_configs)} server configs")
            return self._server_configs
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return []
    
    async def register_servers(self) -> None:
        """Register all servers in the database."""
        for config in self._server_configs:
            try:
                transport_type = TransportType(config.transport)
                
                await self.registry.register_server(
                    server_id=config.id,
                    name=config.name,
                    transport=transport_type,
                    command=config.command,
                    args=config.args,
                    url=config.url,
                    description=config.description,
                )
                
                logger.info(f"Registered server: {config.id}")
                
            except Exception as e:
                logger.error(f"Failed to register server {config.id}: {e}")
    
    async def discover_server(self, config: ServerConfig) -> DiscoveryResult:
        """
        Discover tools from a single server.
        
        Args:
            config: Server configuration
            
        Returns:
            DiscoveryResult with discovery status
        """
        logger.info(f"Discovering server: {config.id}")
        
        # Update status to discovering
        await self.registry.update_server_status(
            config.id,
            ServerStatus.DISCOVERING
        )
        
        try:
            # Get transport type
            transport_type = TransportType(config.transport)
            
            # Connect to server
            connected = await self.mcp_client.connect_server(
                server_id=config.id,
                transport_type=transport_type,
                command=config.command,
                args=config.args,
                url=config.url,
                headers=config.headers,
            )
            
            if not connected:
                await self.registry.update_server_status(
                    config.id,
                    ServerStatus.ERROR,
                    error="Failed to connect"
                )
                return DiscoveryResult(
                    server_id=config.id,
                    success=False,
                    error="Failed to connect"
                )
            
            # Get discovered tools
            tools = self.mcp_client.get_server_tools(config.id)
            
            # Get server UUID from registry
            server_info = await self.registry.get_server(config.id)
            if not server_info:
                return DiscoveryResult(
                    server_id=config.id,
                    success=False,
                    error="Server not found in registry"
                )
            
            # Get full server record to get UUID
            from sqlalchemy import select
            from database.models import MCPServer
            from database.connection import get_async_session
            
            async with get_async_session() as session:
                result = await session.execute(
                    select(MCPServer).where(MCPServer.server_id == config.id)
                )
                server_model = result.scalar_one_or_none()
                
                if not server_model:
                    return DiscoveryResult(
                        server_id=config.id,
                        success=False,
                        error="Server not found in database"
                    )
                
                server_uuid = str(server_model.id)
                
                # Delete existing tools for this server (fresh discovery)
                await self.registry.delete_tools_for_server(server_uuid, session)
                
                # Register each tool
                for tool in tools:
                    # Generate intent patterns from tool name
                    intent_patterns = self._generate_intent_patterns(tool.name)
                    
                    await self.registry.register_tool(
                        server_uuid=server_uuid,
                        tool_name=tool.name,
                        input_schema=tool.input_schema,
                        description=tool.description,
                        intent_patterns=intent_patterns,
                        session=session,
                    )
                    
                    logger.debug(f"Registered tool: {tool.name}")
            
            # Update status to active
            await self.registry.update_server_status(
                config.id,
                ServerStatus.ACTIVE
            )
            
            logger.info(f"Discovered {len(tools)} tools from {config.id}")
            
            return DiscoveryResult(
                server_id=config.id,
                success=True,
                tools_discovered=len(tools)
            )
            
        except Exception as e:
            logger.error(f"Discovery failed for {config.id}: {e}")
            
            await self.registry.update_server_status(
                config.id,
                ServerStatus.ERROR,
                error=str(e)
            )
            
            return DiscoveryResult(
                server_id=config.id,
                success=False,
                error=str(e)
            )
    
    def _generate_intent_patterns(self, tool_name: str) -> List[str]:
        """
        Generate intent patterns from tool name.
        
        Converts tool names like "read_file" to patterns
        like ["read_file", "read-file", "readfile"].
        """
        patterns = [tool_name]
        
        # Add hyphenated version
        patterns.append(tool_name.replace("_", "-"))
        
        # Add no-separator version
        patterns.append(tool_name.replace("_", "").replace("-", ""))
        
        # Add parts as individual patterns
        parts = tool_name.replace("-", "_").split("_")
        if len(parts) > 1:
            patterns.append("_".join(parts[::-1]))  # Reversed
        
        return list(set(patterns))
    
    async def discover_all(self) -> List[DiscoveryResult]:
        """
        Discover all configured servers.
        
        Returns:
            List of discovery results
        """
        # Load configs if not already loaded
        if not self._server_configs:
            self.load_config()
        
        # Register servers first
        await self.register_servers()
        
        # Discover each server
        results = []
        for config in self._server_configs:
            if config.enabled:
                result = await self.discover_server(config)
                results.append(result)
        
        # Log summary
        successful = sum(1 for r in results if r.success)
        total_tools = sum(r.tools_discovered for r in results)
        
        logger.info(
            f"Discovery complete: {successful}/{len(results)} servers, "
            f"{total_tools} tools discovered"
        )
        
        return results
    
    async def refresh_server(self, server_id: str) -> Optional[DiscoveryResult]:
        """
        Refresh a single server's tools.
        
        Args:
            server_id: ID of the server to refresh
            
        Returns:
            DiscoveryResult or None if server not found
        """
        # Find config
        config = next(
            (c for c in self._server_configs if c.id == server_id),
            None
        )
        
        if not config:
            # Try to load from database
            server_info = await self.registry.get_server(server_id)
            if not server_info:
                return None
            
            config = ServerConfig(
                id=server_info.server_id,
                name=server_info.name,
                transport=server_info.transport,
                command=server_info.command,
                args=server_info.args,
                url=server_info.url,
                description=None,
                enabled=server_info.enabled,
            )
        
        return await self.discover_server(config)


# Singleton instance
_discovery_service: Optional[DiscoveryService] = None


def get_discovery_service() -> DiscoveryService:
    """Get or create the discovery service singleton."""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = DiscoveryService()
    return _discovery_service


async def run_discovery() -> List[DiscoveryResult]:
    """Convenience function to run full discovery."""
    service = get_discovery_service()
    return await service.discover_all()
