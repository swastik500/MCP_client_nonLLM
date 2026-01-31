"""
MCP Transport Layer - Handles communication with MCP servers.

Supports:
- stdio subprocess
- HTTP
- WebSocket

Uses JSON-RPC 2.0 strictly.

STRICT CONSTRAINTS:
- Pure transport, no business logic
- No tool-specific code
- Protocol-compliant only
"""

import asyncio
import json
import logging
import subprocess
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum

import httpx
import websockets
from websockets.client import WebSocketClientProtocol

from config.settings import settings

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """Supported transport types."""
    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


@dataclass
class JsonRpcRequest:
    """JSON-RPC 2.0 request."""
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "method": self.method,
            "id": self.id,
        }
        if self.params is not None:
            request["params"] = self.params
        return request
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class JsonRpcResponse:
    """JSON-RPC 2.0 response."""
    id: Optional[str]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    
    @property
    def is_error(self) -> bool:
        return self.error is not None
    
    @property
    def error_message(self) -> Optional[str]:
        if self.error:
            return self.error.get("message", "Unknown error")
        return None
    
    @property
    def error_code(self) -> Optional[int]:
        if self.error:
            return self.error.get("code")
        return None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JsonRpcResponse":
        return cls(
            id=data.get("id"),
            result=data.get("result"),
            error=data.get("error"),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "JsonRpcResponse":
        return cls.from_dict(json.loads(json_str))


@dataclass
class MCPCapabilities:
    """Server capabilities from initialization."""
    tools: bool = False
    prompts: bool = False
    resources: bool = False
    logging: bool = False
    experimental: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPCapabilities":
        capabilities = data.get("capabilities", {})
        return cls(
            tools="tools" in capabilities,
            prompts="prompts" in capabilities,
            resources="resources" in capabilities,
            logging="logging" in capabilities,
            experimental=capabilities.get("experimental", {}),
        )


@dataclass
class MCPToolDefinition:
    """Tool definition from MCP server."""
    name: str
    description: Optional[str]
    input_schema: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPToolDefinition":
        return cls(
            name=data["name"],
            description=data.get("description"),
            input_schema=data.get("inputSchema", {}),
        )


class MCPTransport(ABC):
    """Abstract base class for MCP transports."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        pass
    
    @abstractmethod
    async def send_request(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Send a request and wait for response."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        pass


class StdioTransport(MCPTransport):
    """
    stdio transport for MCP servers.
    
    Spawns a subprocess and communicates via stdin/stdout.
    """
    
    def __init__(self, command: str, args: List[str]):
        """
        Initialize stdio transport.
        
        Args:
            command: Command to execute
            args: Command arguments
        """
        self.command = command
        self.args = args
        self._process: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> bool:
        """Start the subprocess and connect."""
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Start reader task
            self._reader_task = asyncio.create_task(self._read_responses())
            
            logger.info(f"Started MCP server: {self.command} {' '.join(self.args)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Terminate the subprocess."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None
            
        logger.info("Disconnected from MCP server")
    
    def is_connected(self) -> bool:
        """Check if subprocess is running."""
        return self._process is not None and self._process.returncode is None
    
    async def _read_responses(self) -> None:
        """Background task to read responses from stdout."""
        if not self._process or not self._process.stdout:
            return
        
        while self.is_connected():
            try:
                line = await self._process.stdout.readline()
                if not line:
                    break
                
                try:
                    response_data = json.loads(line.decode().strip())
                    response = JsonRpcResponse.from_dict(response_data)
                    
                    # Match to pending request
                    if response.id and response.id in self._pending_requests:
                        future = self._pending_requests.pop(response.id)
                        if not future.done():
                            future.set_result(response)
                            
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON response: {e}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading response: {e}")
    
    async def send_request(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Send a request and wait for response."""
        if not self.is_connected():
            raise RuntimeError("Transport not connected")
        
        async with self._lock:
            # Create future for response
            future: asyncio.Future = asyncio.Future()
            self._pending_requests[request.id] = future
            
            # Send request
            request_line = request.to_json() + "\n"
            self._process.stdin.write(request_line.encode())
            await self._process.stdin.drain()
            
        # Wait for response
        try:
            response = await asyncio.wait_for(
                future,
                timeout=settings.mcp.MCP_EXECUTION_TIMEOUT
            )
            return response
        except asyncio.TimeoutError:
            self._pending_requests.pop(request.id, None)
            raise TimeoutError(f"Request {request.id} timed out")


class HttpTransport(MCPTransport):
    """
    HTTP transport for MCP servers.
    
    Uses HTTP POST for JSON-RPC requests.
    """
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize HTTP transport.
        
        Args:
            url: Server URL
            headers: Optional HTTP headers
        """
        self.url = url
        self.headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        """Create HTTP client."""
        try:
            self._client = httpx.AsyncClient(
                timeout=settings.mcp.MCP_EXECUTION_TIMEOUT,
                headers=self.headers,
            )
            logger.info(f"Connected to MCP server: {self.url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Disconnected from MCP server")
    
    def is_connected(self) -> bool:
        """Check if client exists."""
        return self._client is not None
    
    async def send_request(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Send HTTP POST request."""
        if not self._client:
            raise RuntimeError("Transport not connected")
        
        try:
            response = await self._client.post(
                self.url,
                json=request.to_dict(),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return JsonRpcResponse.from_dict(response.json())
            
        except httpx.HTTPStatusError as e:
            return JsonRpcResponse(
                id=request.id,
                error={"code": e.response.status_code, "message": str(e)}
            )
        except Exception as e:
            return JsonRpcResponse(
                id=request.id,
                error={"code": -32603, "message": str(e)}
            )


class WebSocketTransport(MCPTransport):
    """
    WebSocket transport for MCP servers.
    
    Maintains persistent WebSocket connection.
    """
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize WebSocket transport.
        
        Args:
            url: WebSocket URL
            headers: Optional headers for connection
        """
        self.url = url
        self.headers = headers or {}
        self._websocket: Optional[WebSocketClientProtocol] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        try:
            self._websocket = await websockets.connect(
                self.url,
                extra_headers=self.headers,
            )
            
            # Start reader task
            self._reader_task = asyncio.create_task(self._read_messages())
            
            logger.info(f"Connected to MCP server: {self.url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        
        if self._websocket:
            await self._websocket.close()
            self._websocket = None
            
        logger.info("Disconnected from MCP server")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is open."""
        return self._websocket is not None and self._websocket.open
    
    async def _read_messages(self) -> None:
        """Background task to read WebSocket messages."""
        if not self._websocket:
            return
        
        try:
            async for message in self._websocket:
                try:
                    response_data = json.loads(message)
                    response = JsonRpcResponse.from_dict(response_data)
                    
                    if response.id and response.id in self._pending_requests:
                        future = self._pending_requests.pop(response.id)
                        if not future.done():
                            future.set_result(response)
                            
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON message: {e}")
                    
        except websockets.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading message: {e}")
    
    async def send_request(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Send WebSocket message."""
        if not self.is_connected():
            raise RuntimeError("Transport not connected")
        
        async with self._lock:
            # Create future for response
            future: asyncio.Future = asyncio.Future()
            self._pending_requests[request.id] = future
            
            # Send request
            await self._websocket.send(request.to_json())
        
        # Wait for response
        try:
            response = await asyncio.wait_for(
                future,
                timeout=settings.mcp.MCP_EXECUTION_TIMEOUT
            )
            return response
        except asyncio.TimeoutError:
            self._pending_requests.pop(request.id, None)
            raise TimeoutError(f"Request {request.id} timed out")


def create_transport(
    transport_type: TransportType,
    command: Optional[str] = None,
    args: Optional[List[str]] = None,
    url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> MCPTransport:
    """
    Factory function to create appropriate transport.
    
    Args:
        transport_type: Type of transport
        command: Command for stdio
        args: Args for stdio
        url: URL for HTTP/WebSocket
        headers: Headers for HTTP/WebSocket
        
    Returns:
        MCPTransport instance
    """
    if transport_type == TransportType.STDIO:
        if not command:
            raise ValueError("Command required for stdio transport")
        return StdioTransport(command, args or [])
    
    elif transport_type == TransportType.HTTP:
        if not url:
            raise ValueError("URL required for HTTP transport")
        return HttpTransport(url, headers)
    
    elif transport_type == TransportType.WEBSOCKET:
        if not url:
            raise ValueError("URL required for WebSocket transport")
        return WebSocketTransport(url, headers)
    
    else:
        raise ValueError(f"Unsupported transport type: {transport_type}")
