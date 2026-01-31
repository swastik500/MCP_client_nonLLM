"""
MCP Client - High-level client for interacting with MCP servers.

Manages:
- Server lifecycle
- Protocol handshake
- Tool discovery
- Tool execution

STRICT CONSTRAINTS:
- JSON-RPC 2.0 only
- No tool-specific logic
- Transport-agnostic
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from mcp.transport import (
    MCPTransport, TransportType, create_transport,
    JsonRpcRequest, JsonRpcResponse, MCPCapabilities, MCPToolDefinition
)
from config.settings import settings

logger = logging.getLogger(__name__)


# MCP Protocol constants
MCP_PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC methods
METHOD_INITIALIZE = "initialize"
METHOD_INITIALIZED = "notifications/initialized"
METHOD_LIST_TOOLS = "tools/list"
METHOD_CALL_TOOL = "tools/call"
METHOD_PING = "ping"


@dataclass
class MCPServerConnection:
    """Represents a connection to an MCP server."""
    server_id: str
    transport: MCPTransport
    capabilities: Optional[MCPCapabilities] = None
    tools: List[MCPToolDefinition] = field(default_factory=list)
    is_initialized: bool = False
    error: Optional[str] = None


@dataclass
class ToolCallResult:
    """Result of a tool call."""
    success: bool
    content: Any = None
    error: Optional[str] = None
    error_code: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "error_code": self.error_code,
            "metadata": self.metadata,
        }


class MCPClient:
    """
    High-level MCP client.
    
    Handles protocol operations and manages server connections.
    """
    
    def __init__(self):
        """Initialize the MCP client."""
        self._connections: Dict[str, MCPServerConnection] = {}
        self._lock = asyncio.Lock()
    
    async def connect_server(
        self,
        server_id: str,
        transport_type: TransportType,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Connect to an MCP server.
        
        Args:
            server_id: Unique identifier for the server
            transport_type: Type of transport to use
            command: Command for stdio transport
            args: Arguments for stdio transport
            url: URL for HTTP/WebSocket transport
            headers: Headers for HTTP/WebSocket transport
            
        Returns:
            True if connection and initialization successful
        """
        async with self._lock:
            # Disconnect if already connected
            if server_id in self._connections:
                await self._disconnect_server_internal(server_id)
            
            try:
                # Create transport
                transport = create_transport(
                    transport_type,
                    command=command,
                    args=args,
                    url=url,
                    headers=headers,
                )
                
                # Connect
                if not await transport.connect():
                    return False
                
                # Create connection object
                connection = MCPServerConnection(
                    server_id=server_id,
                    transport=transport,
                )
                
                # Initialize
                if not await self._initialize_server(connection):
                    await transport.disconnect()
                    return False
                
                # Store connection
                self._connections[server_id] = connection
                
                logger.info(f"Connected to MCP server: {server_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to server {server_id}: {e}")
                return False
    
    async def _initialize_server(self, connection: MCPServerConnection) -> bool:
        """
        Initialize MCP server with protocol handshake.
        
        Sends initialize request and handles capabilities.
        """
        try:
            # Send initialize request
            init_request = JsonRpcRequest(
                method=METHOD_INITIALIZE,
                params={
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "roots": {"listChanged": True},
                        "sampling": {},
                    },
                    "clientInfo": {
                        "name": settings.APP_NAME,
                        "version": settings.APP_VERSION,
                    }
                }
            )
            
            response = await connection.transport.send_request(init_request)
            
            if response.is_error:
                connection.error = response.error_message
                logger.error(f"Initialize failed: {response.error_message}")
                return False
            
            # Parse capabilities
            connection.capabilities = MCPCapabilities.from_dict(response.result or {})
            
            # Send initialized notification
            initialized_request = JsonRpcRequest(
                method=METHOD_INITIALIZED,
                params={}
            )
            await connection.transport.send_request(initialized_request)
            
            connection.is_initialized = True
            logger.info(f"Server initialized with capabilities: {connection.capabilities}")
            
            # Discover tools if server supports them
            if connection.capabilities.tools:
                await self._discover_tools(connection)
            
            return True
            
        except Exception as e:
            connection.error = str(e)
            logger.error(f"Initialization error: {e}")
            return False
    
    async def _discover_tools(self, connection: MCPServerConnection) -> None:
        """Discover available tools from the server."""
        try:
            request = JsonRpcRequest(
                method=METHOD_LIST_TOOLS,
                params={}
            )
            
            response = await connection.transport.send_request(request)
            
            if response.is_error:
                logger.warning(f"Tool discovery failed: {response.error_message}")
                return
            
            tools_data = response.result or {}
            tools_list = tools_data.get("tools", [])
            
            connection.tools = [
                MCPToolDefinition.from_dict(tool)
                for tool in tools_list
            ]
            
            logger.info(f"Discovered {len(connection.tools)} tools")
            
        except Exception as e:
            logger.error(f"Tool discovery error: {e}")
    
    async def disconnect_server(self, server_id: str) -> None:
        """Disconnect from an MCP server."""
        async with self._lock:
            await self._disconnect_server_internal(server_id)
    
    async def _disconnect_server_internal(self, server_id: str) -> None:
        """Internal disconnect without lock."""
        if server_id in self._connections:
            connection = self._connections.pop(server_id)
            await connection.transport.disconnect()
            logger.info(f"Disconnected from server: {server_id}")
    
    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        async with self._lock:
            for server_id in list(self._connections.keys()):
                await self._disconnect_server_internal(server_id)
    
    def get_connection(self, server_id: str) -> Optional[MCPServerConnection]:
        """Get connection by server ID."""
        return self._connections.get(server_id)
    
    def list_connections(self) -> List[str]:
        """List all connected server IDs."""
        return list(self._connections.keys())
    
    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> ToolCallResult:
        """
        Call a tool on an MCP server.
        
        Args:
            server_id: ID of the server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            ToolCallResult with execution result
        """
        connection = self._connections.get(server_id)
        
        if not connection:
            return ToolCallResult(
                success=False,
                error=f"Server not connected: {server_id}",
                error_code=-32000,
            )
        
        if not connection.is_initialized:
            return ToolCallResult(
                success=False,
                error=f"Server not initialized: {server_id}",
                error_code=-32001,
            )
        
        try:
            request = JsonRpcRequest(
                method=METHOD_CALL_TOOL,
                params={
                    "name": tool_name,
                    "arguments": arguments,
                }
            )
            
            response = await connection.transport.send_request(request)
            
            if response.is_error:
                return ToolCallResult(
                    success=False,
                    error=response.error_message,
                    error_code=response.error_code,
                )
            
            # Parse result
            result = response.result or {}
            content = result.get("content", [])
            
            # Extract text content if available
            if isinstance(content, list) and len(content) > 0:
                first_content = content[0]
                if isinstance(first_content, dict) and first_content.get("type") == "text":
                    content = first_content.get("text", content)
            
            return ToolCallResult(
                success=True,
                content=content,
                metadata={
                    "server_id": server_id,
                    "tool_name": tool_name,
                }
            )
            
        except TimeoutError:
            return ToolCallResult(
                success=False,
                error="Request timed out",
                error_code=-32002,
            )
        except Exception as e:
            return ToolCallResult(
                success=False,
                error=str(e),
                error_code=-32603,
            )
    
    async def ping_server(self, server_id: str) -> bool:
        """
        Ping an MCP server to check connectivity.
        
        Args:
            server_id: ID of the server
            
        Returns:
            True if server responds
        """
        connection = self._connections.get(server_id)
        if not connection:
            return False
        
        try:
            request = JsonRpcRequest(method=METHOD_PING, params={})
            response = await connection.transport.send_request(request)
            return not response.is_error
        except Exception:
            return False
    
    def get_server_tools(self, server_id: str) -> List[MCPToolDefinition]:
        """Get tools for a connected server."""
        connection = self._connections.get(server_id)
        if connection:
            return connection.tools
        return []


# Singleton instance
_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get or create the MCP client singleton."""
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
