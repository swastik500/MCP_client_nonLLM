"""
Schema Executor - Generic parameter building and validation.

This module:
- Accepts tool schema + extracted entities
- Builds parameters generically
- Validates with JSON Schema
- Has NO tool awareness

STRICT CONSTRAINTS:
- No tool-specific logic
- No hardcoded parameters
- Schema is the only source of truth
- Always validates before returning
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
import re

from jsonschema import validate, ValidationError, Draft7Validator
from jsonschema.exceptions import SchemaError

from nlp.entity_extractor import EntityExtractionResult, ExtractedEntity

logger = logging.getLogger(__name__)


@dataclass
class ParameterBuildResult:
    """Result of parameter building."""
    success: bool
    parameters: Dict[str, Any]
    missing_required: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    mapping_log: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "parameters": self.parameters,
            "missing_required": self.missing_required,
            "validation_errors": self.validation_errors,
            "mapping_log": self.mapping_log,
            "metadata": self.metadata,
        }


class SchemaAnalyzer:
    """
    Analyzes JSON Schema to understand parameter requirements.
    """
    
    # Mapping from schema types to entity labels
    TYPE_TO_ENTITY_MAP = {
        "string": ["FILE_PATH", "URL", "EMAIL", "PERSON", "ORG", "GPE", "COMMAND"],
        "integer": ["CARDINAL", "QUANTITY"],
        "number": ["CARDINAL", "MONEY", "PERCENT", "QUANTITY"],
        "boolean": [],  # Usually from keywords
        "array": [],  # Handled specially
        "object": [],  # Handled specially
    }
    
    # Common parameter name patterns
    PARAM_PATTERNS = {
        "path": ["FILE_PATH"],
        "file": ["FILE_PATH"],
        "directory": ["FILE_PATH"],
        "url": ["URL"],
        "uri": ["URL"],
        "email": ["EMAIL"],
        "name": ["PERSON", "ORG"],
        "location": ["GPE", "LOC"],
        "date": ["DATE"],
        "time": ["TIME"],
        "amount": ["MONEY", "CARDINAL"],
        "count": ["CARDINAL"],
        "number": ["CARDINAL"],
        "command": ["COMMAND"],
        "query": [],  # Free text
        "content": [],  # Free text
        "text": [],  # Free text
    }
    
    @classmethod
    def get_required_params(cls, schema: Dict[str, Any]) -> List[str]:
        """Extract required parameter names from schema."""
        return schema.get("required", [])
    
    @classmethod
    def get_all_params(cls, schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract all parameters with their definitions."""
        properties = schema.get("properties", {})
        return properties
    
    @classmethod
    def get_param_type(cls, param_def: Dict[str, Any]) -> str:
        """Get the type of a parameter."""
        return param_def.get("type", "string")
    
    @classmethod
    def get_param_constraints(cls, param_def: Dict[str, Any]) -> Dict[str, Any]:
        """Extract constraints from parameter definition."""
        constraints = {}
        
        # String constraints
        if "minLength" in param_def:
            constraints["minLength"] = param_def["minLength"]
        if "maxLength" in param_def:
            constraints["maxLength"] = param_def["maxLength"]
        if "pattern" in param_def:
            constraints["pattern"] = param_def["pattern"]
        if "enum" in param_def:
            constraints["enum"] = param_def["enum"]
        
        # Numeric constraints
        if "minimum" in param_def:
            constraints["minimum"] = param_def["minimum"]
        if "maximum" in param_def:
            constraints["maximum"] = param_def["maximum"]
        
        # Array constraints
        if "items" in param_def:
            constraints["items"] = param_def["items"]
        if "minItems" in param_def:
            constraints["minItems"] = param_def["minItems"]
        if "maxItems" in param_def:
            constraints["maxItems"] = param_def["maxItems"]
        
        return constraints
    
    @classmethod
    def suggest_entity_labels(cls, param_name: str, param_def: Dict[str, Any]) -> List[str]:
        """
        Suggest entity labels that might match a parameter.
        
        Based on parameter name patterns and type.
        """
        suggestions = []
        param_type = cls.get_param_type(param_def)
        
        # Check parameter name patterns
        param_lower = param_name.lower()
        for pattern, labels in cls.PARAM_PATTERNS.items():
            if pattern in param_lower:
                suggestions.extend(labels)
        
        # Add type-based suggestions
        type_labels = cls.TYPE_TO_ENTITY_MAP.get(param_type, [])
        suggestions.extend(type_labels)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for label in suggestions:
            if label not in seen:
                seen.add(label)
                unique_suggestions.append(label)
        
        return unique_suggestions


class EntityMatcher:
    """
    Matches extracted entities to schema parameters.
    """
    
    @classmethod
    def match_entity_to_param(
        cls,
        entity: ExtractedEntity,
        param_name: str,
        param_def: Dict[str, Any]
    ) -> Tuple[bool, float]:
        """
        Check if an entity matches a parameter.
        
        Returns:
            Tuple of (matches, confidence)
        """
        suggested_labels = SchemaAnalyzer.suggest_entity_labels(param_name, param_def)
        
        # Direct label match
        if entity.label in suggested_labels:
            return True, 0.9
        
        # Check if entity text matches enum values
        if "enum" in param_def:
            if entity.text.lower() in [str(v).lower() for v in param_def["enum"]]:
                return True, 1.0
        
        # Type compatibility check
        param_type = param_def.get("type", "string")
        
        if param_type == "string":
            # Most entities can be strings
            return True, 0.5
        
        elif param_type in ("integer", "number"):
            # Check if entity text is numeric
            try:
                float(entity.text.replace(",", ""))
                return True, 0.8
            except ValueError:
                return False, 0.0
        
        elif param_type == "boolean":
            if entity.text.lower() in ("true", "false", "yes", "no", "1", "0"):
                return True, 0.9
            return False, 0.0
        
        return False, 0.0
    
    @classmethod
    def find_best_entity(
        cls,
        entities: List[ExtractedEntity],
        param_name: str,
        param_def: Dict[str, Any],
        used_entities: Set[int]
    ) -> Optional[Tuple[ExtractedEntity, float]]:
        """
        Find the best matching entity for a parameter.
        
        Args:
            entities: List of extracted entities
            param_name: Parameter name
            param_def: Parameter schema definition
            used_entities: Set of already used entity indices
            
        Returns:
            Tuple of (best_entity, confidence) or None
        """
        best_match = None
        best_confidence = 0.0
        best_idx = -1
        
        for idx, entity in enumerate(entities):
            if idx in used_entities:
                continue
            
            matches, confidence = cls.match_entity_to_param(
                entity, param_name, param_def
            )
            
            if matches and confidence > best_confidence:
                best_match = entity
                best_confidence = confidence
                best_idx = idx
        
        if best_match:
            used_entities.add(best_idx)
            return (best_match, best_confidence)
        
        return None


class ValueConverter:
    """
    Converts entity values to the correct type for parameters.
    """
    
    @staticmethod
    def _normalize_url(url: str) -> str:
        """
        Normalize a URL by adding protocol if missing.
        
        Examples:
            google.com -> https://google.com
            google -> https://google.com
            https://google.com -> https://google.com (unchanged)
        """
        url = url.strip()
        
        # Already has protocol
        if url.startswith(('http://', 'https://', 'ftp://', 'file://')):
            return url
        
        # Add .com if it looks like a domain without TLD
        if '.' not in url and not url.startswith('localhost'):
            url = f"{url}.com"
        
        # Add https:// protocol
        return f"https://{url}"
    
    @classmethod
    def convert(cls, value: str, param_def: Dict[str, Any]) -> Any:
        """
        Convert a string value to the appropriate type.
        
        Args:
            value: String value to convert
            param_def: Parameter schema definition
            
        Returns:
            Converted value
        """
        param_type = param_def.get("type", "string")
        
        if param_type == "string":
            # Check if this is a URL parameter and normalize if needed
            param_format = param_def.get("format")
            param_desc = param_def.get("description", "").lower()
            
            # Detect URL parameters
            if param_format == "uri" or "url" in param_desc or "uri" in param_desc:
                value = cls._normalize_url(value)
            
            return str(value)
        
        elif param_type == "integer":
            # Remove commas and convert
            cleaned = value.replace(",", "").strip()
            return int(float(cleaned))
        
        elif param_type == "number":
            cleaned = value.replace(",", "").strip()
            return float(cleaned)
        
        elif param_type == "boolean":
            lower = value.lower()
            if lower in ("true", "yes", "1"):
                return True
            elif lower in ("false", "no", "0"):
                return False
            raise ValueError(f"Cannot convert '{value}' to boolean")
        
        elif param_type == "array":
            # Handle comma-separated values
            items_def = param_def.get("items", {"type": "string"})
            items = [v.strip() for v in value.split(",")]
            return [cls.convert(item, items_def) for item in items]
        
        elif param_type == "null":
            return None
        
        # Default to string
        return str(value)


class SchemaValidator:
    """
    Validates parameters against JSON Schema.
    """
    
    @classmethod
    def validate(
        cls,
        parameters: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate parameters against schema.
        
        Args:
            parameters: Parameters to validate
            schema: JSON Schema
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            # Validate schema itself first
            Draft7Validator.check_schema(schema)
        except SchemaError as e:
            return False, [f"Invalid schema: {e.message}"]
        
        errors = []
        try:
            validate(instance=parameters, schema=schema)
            return True, []
        except ValidationError as e:
            # Collect all validation errors
            validator = Draft7Validator(schema)
            for error in validator.iter_errors(parameters):
                path = ".".join(str(p) for p in error.absolute_path)
                if path:
                    errors.append(f"{path}: {error.message}")
                else:
                    errors.append(error.message)
            return False, errors


class SchemaExecutor:
    """
    Main schema executor.
    
    Builds parameters from entities and schema, then validates.
    Has NO awareness of specific tools - only works with schemas.
    """
    
    def __init__(self):
        """Initialize the executor."""
        self.analyzer = SchemaAnalyzer
        self.matcher = EntityMatcher
        self.converter = ValueConverter
        self.validator = SchemaValidator
    
    def build_parameters(
        self,
        schema: Dict[str, Any],
        entities: EntityExtractionResult,
        defaults: Optional[Dict[str, Any]] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> ParameterBuildResult:
        """
        Build parameters from schema and extracted entities.
        
        Process:
        1. Analyze schema for required/optional params
        2. Match entities to parameters
        3. Convert values to correct types
        4. Apply defaults and overrides
        5. Validate against schema
        
        Args:
            schema: JSON Schema for the tool
            entities: Extracted entities from input
            defaults: Default values for parameters
            overrides: Override values (take precedence)
            
        Returns:
            ParameterBuildResult with built parameters
        """
        defaults = defaults or {}
        overrides = overrides or {}
        
        parameters = {}
        mapping_log = {}
        missing_required = []
        used_entities: Set[int] = set()
        
        # Get schema properties
        all_params = self.analyzer.get_all_params(schema)
        required_params = self.analyzer.get_required_params(schema)
        
        # Process each parameter
        for param_name, param_def in all_params.items():
            # Check overrides first
            if param_name in overrides:
                parameters[param_name] = overrides[param_name]
                mapping_log[param_name] = "override"
                continue
            
            # Try to match an entity
            entity_match = self.matcher.find_best_entity(
                entities.entities,
                param_name,
                param_def,
                used_entities
            )
            
            if entity_match:
                entity, confidence = entity_match
                try:
                    converted_value = self.converter.convert(entity.text, param_def)
                    parameters[param_name] = converted_value
                    mapping_log[param_name] = f"entity:{entity.label}:{confidence:.2f}"
                    continue
                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to convert entity for {param_name}: {e}")
            
            # Special handling for URL parameters - extract from tokens
            param_format = param_def.get("format")
            param_desc = param_def.get("description", "").lower()
            if (param_name == "url" or param_format == "uri" or "url" in param_desc):
                # Skip common action verbs
                skip_verbs = {'navigate', 'go', 'open', 'visit', 'browse', 'to', 'show', 'get', 'fetch'}
                
                # Look for URL-like tokens (domains, etc.)
                for token in entities.tokens:
                    # Skip action verbs and short words
                    if token.lower() in skip_verbs or len(token) < 3:
                        continue
                    # Found a potential URL/domain in tokens
                    url_candidate = self.converter._normalize_url(token)
                    parameters[param_name] = url_candidate
                    mapping_log[param_name] = f"token_url:{token}"
                    break
                if param_name in parameters:
                    continue
            
            # Try noun chunks for free-text parameters
            if param_name in ("query", "content", "text", "message", "description"):
                if entities.noun_chunks:
                    parameters[param_name] = " ".join(entities.noun_chunks)
                    mapping_log[param_name] = "noun_chunks"
                    continue
                elif entities.normalized_text:
                    parameters[param_name] = entities.normalized_text
                    mapping_log[param_name] = "full_text"
                    continue
            
            # Apply default
            if param_name in defaults:
                parameters[param_name] = defaults[param_name]
                mapping_log[param_name] = "default"
                continue
            
            # Check if parameter has a default in schema
            if "default" in param_def:
                parameters[param_name] = param_def["default"]
                mapping_log[param_name] = "schema_default"
                continue
            
            # Track missing required parameters
            if param_name in required_params:
                missing_required.append(param_name)
        
        # Validate
        validation_errors = []
        if not missing_required:
            is_valid, validation_errors = self.validator.validate(parameters, schema)
        else:
            is_valid = False
        
        success = is_valid and not missing_required
        
        return ParameterBuildResult(
            success=success,
            parameters=parameters,
            missing_required=missing_required,
            validation_errors=validation_errors,
            mapping_log=mapping_log,
            metadata={
                "entities_used": len(used_entities),
                "entities_total": len(entities.entities),
                "params_built": len(parameters),
                "params_total": len(all_params),
            }
        )
    
    def validate_parameters(
        self,
        parameters: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate pre-built parameters against schema.
        
        Args:
            parameters: Parameters to validate
            schema: JSON Schema
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        return self.validator.validate(parameters, schema)


# Singleton instance
_executor: Optional[SchemaExecutor] = None


def get_schema_executor() -> SchemaExecutor:
    """Get or create the schema executor singleton."""
    global _executor
    if _executor is None:
        _executor = SchemaExecutor()
    return _executor


def build_parameters(
    schema: Dict[str, Any],
    entities: EntityExtractionResult,
    defaults: Optional[Dict[str, Any]] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> ParameterBuildResult:
    """Convenience function for parameter building."""
    return get_schema_executor().build_parameters(
        schema, entities, defaults, overrides
    )
