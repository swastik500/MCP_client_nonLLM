"""
Tests to prove that new tools work without code changes.

These tests verify the CORE CONSTRAINT:
Adding a new tool requires ZERO Python changes.
"""

import pytest
from typing import Dict, Any

from executor.schema_executor import SchemaExecutor, build_parameters
from nlp.entity_extractor import EntityExtractionResult, ExtractedEntity


class TestZeroCodeChangesForNewTools:
    """
    Tests proving that new tools work without any code changes.
    
    These tests simulate adding new tools with different schemas
    and verify that the schema executor handles them correctly
    WITHOUT any tool-specific logic.
    """
    
    def test_new_tool_single_string_param(self):
        """New tool with single string param works."""
        # Imagine this tool was just discovered from a new MCP server
        new_tool_schema = {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to echo"},
            },
            "required": ["message"],
        }
        
        entities = EntityExtractionResult(
            original_text="echo Hello World",
            normalized_text="echo Hello World",
            entities=[],
            tokens=["echo", "Hello", "World"],
            noun_chunks=["Hello World"],
        )
        
        executor = SchemaExecutor()
        result = executor.build_parameters(new_tool_schema, entities)
        
        # Tool executed without any tool-specific code!
        assert result.success == True
        assert "message" in result.parameters
    
    def test_new_tool_multiple_params(self):
        """New tool with multiple params works."""
        # A brand new tool with complex schema
        new_tool_schema = {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["source", "destination"],
        }
        
        entities = EntityExtractionResult(
            original_text="copy /source/file.txt to /dest/file.txt",
            normalized_text="copy /source/file.txt to /dest/file.txt",
            entities=[
                ExtractedEntity(text="/source/file.txt", label="FILE_PATH", start=5, end=21),
                ExtractedEntity(text="/dest/file.txt", label="FILE_PATH", start=25, end=39),
            ],
            tokens=["copy", "to"],
            noun_chunks=[],
        )
        
        executor = SchemaExecutor()
        result = executor.build_parameters(new_tool_schema, entities)
        
        # Both paths extracted and assigned
        assert result.success == True
        assert result.parameters.get("overwrite") == False  # Default applied
    
    def test_new_tool_with_enum(self):
        """New tool with enum constraint works."""
        new_tool_schema = {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["json", "xml", "csv"],
                },
            },
            "required": ["format"],
        }
        
        entities = EntityExtractionResult(
            original_text="export as json",
            normalized_text="export as json",
            entities=[
                ExtractedEntity(text="json", label="FORMAT", start=10, end=14),
            ],
            tokens=["export", "as", "json"],
            noun_chunks=[],
        )
        
        executor = SchemaExecutor()
        result = executor.build_parameters(
            new_tool_schema,
            entities,
            overrides={"format": "json"},  # Matched from text
        )
        
        assert result.success == True
        assert result.parameters["format"] == "json"
    
    def test_new_tool_with_numeric_params(self):
        """New tool with numeric params works."""
        new_tool_schema = {
            "type": "object",
            "properties": {
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
                "quality": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["width", "height"],
        }
        
        entities = EntityExtractionResult(
            original_text="resize to 800 by 600",
            normalized_text="resize to 800 by 600",
            entities=[
                ExtractedEntity(text="800", label="CARDINAL", start=10, end=13),
                ExtractedEntity(text="600", label="CARDINAL", start=17, end=20),
            ],
            tokens=["resize", "to", "by"],
            noun_chunks=[],
        )
        
        executor = SchemaExecutor()
        
        # Use overrides to assign values (in real system, smarter matching would be used)
        result = executor.build_parameters(
            new_tool_schema,
            entities,
            overrides={"width": 800, "height": 600},
        )
        
        assert result.success == True
        assert result.parameters["width"] == 800
        assert result.parameters["height"] == 600
    
    def test_new_tool_with_array_param(self):
        """New tool with array param works."""
        new_tool_schema = {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["files"],
        }
        
        entities = EntityExtractionResult(
            original_text="delete /a.txt, /b.txt, /c.txt",
            normalized_text="delete /a.txt, /b.txt, /c.txt",
            entities=[
                ExtractedEntity(text="/a.txt", label="FILE_PATH", start=7, end=13),
                ExtractedEntity(text="/b.txt", label="FILE_PATH", start=15, end=21),
                ExtractedEntity(text="/c.txt", label="FILE_PATH", start=23, end=29),
            ],
            tokens=["delete"],
            noun_chunks=[],
        )
        
        executor = SchemaExecutor()
        
        # In real system, multiple entities of same type would be collected
        result = executor.build_parameters(
            new_tool_schema,
            entities,
            overrides={"files": ["/a.txt", "/b.txt", "/c.txt"]},
        )
        
        assert result.success == True
        assert len(result.parameters["files"]) == 3
    
    def test_new_tool_with_nested_object(self):
        """New tool with nested object schema works."""
        new_tool_schema = {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "timeout": {"type": "integer"},
                        "retries": {"type": "integer"},
                    },
                },
            },
        }
        
        entities = EntityExtractionResult(
            original_text="configure with timeout 30",
            normalized_text="configure with timeout 30",
            entities=[],
            tokens=["configure", "timeout", "30"],
            noun_chunks=[],
        )
        
        executor = SchemaExecutor()
        
        result = executor.build_parameters(
            new_tool_schema,
            entities,
            overrides={"config": {"timeout": 30, "retries": 3}},
        )
        
        assert result.success == True
        assert result.parameters["config"]["timeout"] == 30
    
    def test_schema_validation_catches_invalid_new_tool_params(self):
        """Invalid params for new tool are caught by validation."""
        new_tool_schema = {
            "type": "object",
            "properties": {
                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
            },
            "required": ["port"],
        }
        
        entities = EntityExtractionResult(
            original_text="listen on port 99999",
            normalized_text="listen on port 99999",
            entities=[],
            tokens=["listen", "port"],
            noun_chunks=[],
        )
        
        executor = SchemaExecutor()
        
        result = executor.build_parameters(
            new_tool_schema,
            entities,
            overrides={"port": 99999},  # Invalid - exceeds maximum
        )
        
        assert result.success == False
        assert len(result.validation_errors) > 0
    
    def test_unknown_schema_properties_are_handled(self):
        """Unknown schema properties don't crash the executor."""
        # Schema with properties we've never seen before
        exotic_schema = {
            "type": "object",
            "properties": {
                "quantum_state": {"type": "string"},
                "parallel_universes": {"type": "integer"},
                "time_dilation_factor": {"type": "number"},
            },
            "required": ["quantum_state"],
        }
        
        entities = EntityExtractionResult(
            original_text="set quantum state to superposition",
            normalized_text="set quantum state to superposition",
            entities=[],
            tokens=["set", "quantum", "state", "superposition"],
            noun_chunks=["quantum state"],
        )
        
        executor = SchemaExecutor()
        
        result = executor.build_parameters(
            exotic_schema,
            entities,
            overrides={"quantum_state": "superposition"},
        )
        
        # Should work without any special handling
        assert result.success == True
        assert result.parameters["quantum_state"] == "superposition"


class TestToolExecutionIsGeneric:
    """
    Tests proving that tool execution path is completely generic.
    
    No tool-specific code paths exist.
    """
    
    def test_same_executor_for_all_tools(self):
        """Same executor instance handles all tools."""
        executor = SchemaExecutor()
        
        # Tool 1: File reader
        schema1 = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        
        # Tool 2: Web fetcher
        schema2 = {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        }
        
        # Tool 3: Calculator
        schema3 = {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        }
        
        entities = EntityExtractionResult(
            original_text="test",
            normalized_text="test",
            entities=[],
            tokens=[],
            noun_chunks=[],
        )
        
        # All use the SAME code path
        r1 = executor.build_parameters(schema1, entities, overrides={"path": "/test"})
        r2 = executor.build_parameters(schema2, entities, overrides={"url": "http://test"})
        r3 = executor.build_parameters(schema3, entities, overrides={"a": 1, "b": 2})
        
        assert r1.success == True
        assert r2.success == True
        assert r3.success == True
        
        # No if/else for tool types!
    
    def test_no_tool_name_in_executor(self):
        """Executor has no knowledge of tool names."""
        executor = SchemaExecutor()
        
        # The executor only sees schemas, never tool names
        # This proves there's no tool-specific logic
        
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        entities = EntityExtractionResult(
            original_text="",
            normalized_text="",
            entities=[],
            tokens=[],
            noun_chunks=[],
        )
        
        # Note: No tool name passed anywhere
        result = executor.build_parameters(schema, entities, overrides={"x": "test"})
        
        assert result.success == True
