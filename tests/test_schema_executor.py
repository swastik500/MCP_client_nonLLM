"""
Tests for Schema Executor.

Verifies that parameter building and validation
works without any tool-specific logic.
"""

import pytest
from executor.schema_executor import (
    SchemaExecutor,
    SchemaAnalyzer,
    EntityMatcher,
    ValueConverter,
    SchemaValidator,
    ParameterBuildResult,
    build_parameters,
)
from nlp.entity_extractor import EntityExtractionResult, ExtractedEntity


class TestSchemaAnalyzer:
    """Tests for SchemaAnalyzer."""
    
    def test_get_required_params(self):
        """Required params are extracted."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "encoding": {"type": "string"},
            },
            "required": ["path"],
        }
        
        required = SchemaAnalyzer.get_required_params(schema)
        
        assert required == ["path"]
    
    def test_get_all_params(self):
        """All params are extracted."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "encoding": {"type": "string", "default": "utf-8"},
            },
        }
        
        params = SchemaAnalyzer.get_all_params(schema)
        
        assert "path" in params
        assert "encoding" in params
        assert params["encoding"]["default"] == "utf-8"
    
    def test_suggest_entity_labels_for_path(self):
        """Path parameters suggest FILE_PATH label."""
        param_def = {"type": "string"}
        
        suggestions = SchemaAnalyzer.suggest_entity_labels("file_path", param_def)
        
        assert "FILE_PATH" in suggestions
    
    def test_suggest_entity_labels_for_url(self):
        """URL parameters suggest URL label."""
        param_def = {"type": "string"}
        
        suggestions = SchemaAnalyzer.suggest_entity_labels("url", param_def)
        
        assert "URL" in suggestions


class TestValueConverter:
    """Tests for ValueConverter."""
    
    def test_convert_string(self):
        """String conversion works."""
        result = ValueConverter.convert("test", {"type": "string"})
        
        assert result == "test"
        assert isinstance(result, str)
    
    def test_convert_integer(self):
        """Integer conversion works."""
        result = ValueConverter.convert("42", {"type": "integer"})
        
        assert result == 42
        assert isinstance(result, int)
    
    def test_convert_integer_with_comma(self):
        """Integer with comma is converted."""
        result = ValueConverter.convert("1,000", {"type": "integer"})
        
        assert result == 1000
    
    def test_convert_number(self):
        """Float conversion works."""
        result = ValueConverter.convert("3.14", {"type": "number"})
        
        assert result == 3.14
        assert isinstance(result, float)
    
    def test_convert_boolean_true(self):
        """Boolean true conversion works."""
        for value in ["true", "True", "yes", "1"]:
            result = ValueConverter.convert(value, {"type": "boolean"})
            assert result == True
    
    def test_convert_boolean_false(self):
        """Boolean false conversion works."""
        for value in ["false", "False", "no", "0"]:
            result = ValueConverter.convert(value, {"type": "boolean"})
            assert result == False
    
    def test_convert_array(self):
        """Array conversion works."""
        result = ValueConverter.convert(
            "a, b, c",
            {"type": "array", "items": {"type": "string"}}
        )
        
        assert result == ["a", "b", "c"]


class TestSchemaValidator:
    """Tests for SchemaValidator."""
    
    def test_valid_params(self):
        """Valid params pass validation."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        params = {"name": "test"}
        
        is_valid, errors = SchemaValidator.validate(params, schema)
        
        assert is_valid == True
        assert len(errors) == 0
    
    def test_missing_required(self):
        """Missing required param fails validation."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        params = {}
        
        is_valid, errors = SchemaValidator.validate(params, schema)
        
        assert is_valid == False
        assert len(errors) > 0
    
    def test_wrong_type(self):
        """Wrong type fails validation."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
        }
        params = {"count": "not a number"}
        
        is_valid, errors = SchemaValidator.validate(params, schema)
        
        assert is_valid == False


class TestSchemaExecutor:
    """Tests for SchemaExecutor."""
    
    def test_build_with_entity_match(self, sample_tool_schema, sample_entities):
        """Parameters are built from matching entities."""
        executor = SchemaExecutor()
        
        result = executor.build_parameters(
            schema=sample_tool_schema,
            entities=sample_entities,
        )
        
        assert result.success == True
        assert result.parameters.get("path") == "/tmp/test.txt"
    
    def test_build_applies_schema_default(self):
        """Schema defaults are applied."""
        executor = SchemaExecutor()
        
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["path"],
        }
        
        entities = EntityExtractionResult(
            original_text="read /test.txt",
            normalized_text="read /test.txt",
            entities=[
                ExtractedEntity(text="/test.txt", label="FILE_PATH", start=5, end=14),
            ],
            tokens=["read"],
            noun_chunks=[],
        )
        
        result = executor.build_parameters(schema, entities)
        
        assert result.success == True
        assert result.parameters.get("encoding") == "utf-8"
        assert result.mapping_log.get("encoding") == "schema_default"
    
    def test_build_applies_overrides(self, sample_tool_schema):
        """Overrides take precedence."""
        executor = SchemaExecutor()
        
        entities = EntityExtractionResult(
            original_text="test",
            normalized_text="test",
            entities=[],
            tokens=[],
            noun_chunks=[],
        )
        
        result = executor.build_parameters(
            schema=sample_tool_schema,
            entities=entities,
            overrides={"path": "/override/path.txt"},
        )
        
        assert result.success == True
        assert result.parameters["path"] == "/override/path.txt"
        assert result.mapping_log["path"] == "override"
    
    def test_build_reports_missing_required(self, sample_tool_schema):
        """Missing required params are reported."""
        executor = SchemaExecutor()
        
        entities = EntityExtractionResult(
            original_text="no entities here",
            normalized_text="no entities here",
            entities=[],
            tokens=["no", "entities", "here"],
            noun_chunks=[],
        )
        
        result = executor.build_parameters(sample_tool_schema, entities)
        
        assert result.success == False
        assert "path" in result.missing_required
    
    def test_build_validates_output(self):
        """Built parameters are validated."""
        executor = SchemaExecutor()
        
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "minimum": 1},
            },
            "required": ["count"],
        }
        
        # This would create an invalid value
        entities = EntityExtractionResult(
            original_text="count is zero",
            normalized_text="count is zero",
            entities=[],
            tokens=["count", "zero"],
            noun_chunks=[],
        )
        
        result = executor.build_parameters(
            schema,
            entities,
            overrides={"count": 0},  # Invalid - below minimum
        )
        
        assert result.success == False
        assert len(result.validation_errors) > 0


class TestBuildParametersConvenience:
    """Tests for build_parameters convenience function."""
    
    def test_convenience_function(self, sample_tool_schema, sample_entities):
        """Convenience function works."""
        result = build_parameters(sample_tool_schema, sample_entities)
        
        assert isinstance(result, ParameterBuildResult)
