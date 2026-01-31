"""
Pipeline Orchestrator - Deterministic execution pipeline.

Executes the FIXED pipeline:
1. NLP Entity Extraction
2. Intent Classification
3. Rule Engine
4. Tool Selection
5. Schema-Driven Parameter Builder
6. JSON Schema Validation
7. MCP Transport Layer
8. Response Formatter

STRICT CONSTRAINTS:
- Steps must execute in order
- No step may be skipped
- No step may mutate another step's responsibility
- NO LLMs in execution
- NO tool-specific logic
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from nlp.entity_extractor import EntityExtractionResult, get_entity_extractor
from intent.classifier import IntentResult, get_intent_engine
from rules.engine import RuleResult, RuleContext, RuleDecision, get_rule_engine
from executor.schema_executor import ParameterBuildResult, get_schema_executor
from registry.tool_registry import ToolInfo, get_registry
from mcp.client import ToolCallResult, get_mcp_client
from database.models import ExecutionStatus

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Pipeline execution stages."""
    ENTITY_EXTRACTION = "entity_extraction"
    INTENT_CLASSIFICATION = "intent_classification"
    RULE_EVALUATION = "rule_evaluation"
    TOOL_SELECTION = "tool_selection"
    PARAMETER_BUILDING = "parameter_building"
    SCHEMA_VALIDATION = "schema_validation"
    TOOL_EXECUTION = "tool_execution"
    RESPONSE_FORMATTING = "response_formatting"


@dataclass
class StageResult:
    """Result of a single pipeline stage."""
    stage: PipelineStage
    success: bool
    duration_ms: float
    output: Any = None
    error: Optional[str] = None


@dataclass
class PipelineInput:
    """Input to the pipeline."""
    text: str
    user_id: Optional[str] = None
    user_role: str = "guest"
    user_permissions: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    overrides: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Complete result of pipeline execution."""
    success: bool
    status: ExecutionStatus
    
    # Stage outputs
    entities: Optional[EntityExtractionResult] = None
    intent: Optional[IntentResult] = None
    rule_result: Optional[RuleResult] = None
    tool_info: Optional[ToolInfo] = None
    parameter_result: Optional[ParameterBuildResult] = None
    tool_result: Optional[ToolCallResult] = None
    
    # Execution info
    tool_name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    result: Any = None
    error: Optional[str] = None
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    # Stage results
    stage_results: List[StageResult] = field(default_factory=list)
    failed_stage: Optional[PipelineStage] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status.value if self.status else None,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "failed_stage": self.failed_stage.value if self.failed_stage else None,
            "stage_results": [
                {
                    "stage": sr.stage.value,
                    "success": sr.success,
                    "duration_ms": sr.duration_ms,
                    "error": sr.error,
                }
                for sr in self.stage_results
            ],
        }


class Pipeline:
    """
    Deterministic execution pipeline.
    
    This is the core execution engine that processes user input
    through a fixed sequence of stages without any LLM involvement.
    """
    
    def __init__(self):
        """Initialize pipeline with all required components."""
        self.entity_extractor = get_entity_extractor()
        self.intent_engine = get_intent_engine()
        self.rule_engine = get_rule_engine()
        self.schema_executor = get_schema_executor()
        self.registry = get_registry()
        self.mcp_client = get_mcp_client()
    
    async def execute(self, input: PipelineInput) -> PipelineResult:
        """
        Execute the complete pipeline.
        
        Each stage executes in strict order.
        If a stage fails, subsequent stages do not execute.
        
        Args:
            input: PipelineInput with user request
            
        Returns:
            PipelineResult with complete execution info
        """
        result = PipelineResult(
            success=False,
            status=ExecutionStatus.PENDING,
            started_at=datetime.utcnow(),
            stage_results=[],
        )
        
        try:
            # Stage 1: Entity Extraction
            stage_result = await self._execute_entity_extraction(input)
            result.stage_results.append(stage_result)
            if not stage_result.success:
                return self._finalize_result(result, stage_result)
            result.entities = stage_result.output
            
            # Stage 2: Intent Classification
            stage_result = await self._execute_intent_classification(input, result.entities)
            result.stage_results.append(stage_result)
            if not stage_result.success:
                return self._finalize_result(result, stage_result)
            result.intent = stage_result.output
            
            # Stage 3: Rule Evaluation
            stage_result = await self._execute_rule_evaluation(input, result.intent)
            result.stage_results.append(stage_result)
            if not stage_result.success:
                return self._finalize_result(result, stage_result)
            result.rule_result = stage_result.output
            
            # Check if denied by rules
            if result.rule_result.decision == RuleDecision.DENY:
                result.status = ExecutionStatus.DENIED
                result.error = result.rule_result.reason or "Denied by rule engine"
                return self._finalize_result(result, None)
            
            # Stage 4: Tool Selection
            stage_result = await self._execute_tool_selection(result.intent)
            result.stage_results.append(stage_result)
            if not stage_result.success:
                return self._finalize_result(result, stage_result)
            result.tool_info = stage_result.output
            result.tool_name = result.tool_info.tool_name
            
            # Stage 5: Parameter Building
            stage_result = await self._execute_parameter_building(
                result.tool_info,
                result.entities,
                input.context,
                input.overrides,
            )
            result.stage_results.append(stage_result)
            if not stage_result.success:
                return self._finalize_result(result, stage_result)
            result.parameter_result = stage_result.output
            result.parameters = result.parameter_result.parameters
            
            # Stage 6: Schema Validation
            stage_result = await self._execute_schema_validation(
                result.tool_info,
                result.parameters,
            )
            result.stage_results.append(stage_result)
            if not stage_result.success:
                return self._finalize_result(result, stage_result)
            
            # Stage 7: Tool Execution
            stage_result = await self._execute_tool(result.tool_info, result.parameters)
            result.stage_results.append(stage_result)
            result.status = ExecutionStatus.RUNNING
            if not stage_result.success:
                result.status = ExecutionStatus.FAILED
                return self._finalize_result(result, stage_result)
            result.tool_result = stage_result.output
            
            # Stage 8: Response Formatting
            stage_result = await self._execute_response_formatting(result.tool_result)
            result.stage_results.append(stage_result)
            result.result = stage_result.output
            
            # Success!
            result.success = True
            result.status = ExecutionStatus.SUCCESS
            
        except Exception as e:
            logger.exception("Pipeline execution failed")
            result.error = str(e)
            result.status = ExecutionStatus.FAILED
        
        return self._finalize_result(result, None)
    
    def _finalize_result(
        self,
        result: PipelineResult,
        failed_stage_result: Optional[StageResult]
    ) -> PipelineResult:
        """Finalize the pipeline result."""
        result.completed_at = datetime.utcnow()
        result.duration_ms = int(
            (result.completed_at - result.started_at).total_seconds() * 1000
        )
        
        if failed_stage_result:
            result.failed_stage = failed_stage_result.stage
            result.error = failed_stage_result.error
            if result.status == ExecutionStatus.PENDING:
                result.status = ExecutionStatus.FAILED
        
        return result
    
    async def _execute_entity_extraction(
        self,
        input: PipelineInput
    ) -> StageResult:
        """Stage 1: Extract entities from input text."""
        start_time = time.perf_counter()
        
        try:
            entities = self.entity_extractor.extract(input.text)
            duration = (time.perf_counter() - start_time) * 1000
            
            logger.debug(f"Extracted {len(entities.entities)} entities")
            
            return StageResult(
                stage=PipelineStage.ENTITY_EXTRACTION,
                success=True,
                duration_ms=duration,
                output=entities,
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Entity extraction failed: {e}")
            
            return StageResult(
                stage=PipelineStage.ENTITY_EXTRACTION,
                success=False,
                duration_ms=duration,
                error=str(e),
            )
    
    async def _execute_intent_classification(
        self,
        input: PipelineInput,
        entities: EntityExtractionResult,
    ) -> StageResult:
        """Stage 2: Classify intent from input text."""
        start_time = time.perf_counter()
        
        try:
            intent = self.intent_engine.classify(input.text)
            duration = (time.perf_counter() - start_time) * 1000
            
            logger.debug(
                f"Classified intent: {intent.intent} "
                f"(confidence: {intent.confidence:.2f}, forced: {intent.is_forced})"
            )
            
            return StageResult(
                stage=PipelineStage.INTENT_CLASSIFICATION,
                success=True,
                duration_ms=duration,
                output=intent,
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Intent classification failed: {e}")
            
            return StageResult(
                stage=PipelineStage.INTENT_CLASSIFICATION,
                success=False,
                duration_ms=duration,
                error=str(e),
            )
    
    async def _execute_rule_evaluation(
        self,
        input: PipelineInput,
        intent: IntentResult,
    ) -> StageResult:
        """Stage 3: Evaluate rules for permission and context."""
        start_time = time.perf_counter()
        
        try:
            context = RuleContext(
                user_id=input.user_id,
                user_role=input.user_role,
                user_permissions=input.user_permissions,
                intent=intent.intent,
                intent_confidence=intent.confidence,
                is_forced_intent=intent.is_forced,
                session_id=input.session_id,
                custom=input.context,
            )
            
            rule_result = self.rule_engine.evaluate(context)
            duration = (time.perf_counter() - start_time) * 1000
            
            logger.debug(
                f"Rule evaluation: {rule_result.decision.value} "
                f"(matched: {rule_result.matched_rules})"
            )
            
            return StageResult(
                stage=PipelineStage.RULE_EVALUATION,
                success=True,
                duration_ms=duration,
                output=rule_result,
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Rule evaluation failed: {e}")
            
            return StageResult(
                stage=PipelineStage.RULE_EVALUATION,
                success=False,
                duration_ms=duration,
                error=str(e),
            )
    
    async def _execute_tool_selection(
        self,
        intent: IntentResult,
    ) -> StageResult:
        """Stage 4: Select tool based on intent."""
        start_time = time.perf_counter()
        
        try:
            tool_info = await self.registry.find_tool_by_intent(intent.intent)
            duration = (time.perf_counter() - start_time) * 1000
            
            if tool_info is None:
                return StageResult(
                    stage=PipelineStage.TOOL_SELECTION,
                    success=False,
                    duration_ms=duration,
                    error=f"No tool found for intent: {intent.intent}",
                )
            
            logger.debug(f"Selected tool: {tool_info.tool_name}")
            
            return StageResult(
                stage=PipelineStage.TOOL_SELECTION,
                success=True,
                duration_ms=duration,
                output=tool_info,
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Tool selection failed: {e}")
            
            return StageResult(
                stage=PipelineStage.TOOL_SELECTION,
                success=False,
                duration_ms=duration,
                error=str(e),
            )
    
    async def _execute_parameter_building(
        self,
        tool_info: ToolInfo,
        entities: EntityExtractionResult,
        context: Dict[str, Any],
        overrides: Dict[str, Any],
    ) -> StageResult:
        """Stage 5: Build parameters from entities and schema."""
        start_time = time.perf_counter()
        
        try:
            # Combine context as defaults
            defaults = context.copy()
            
            param_result = self.schema_executor.build_parameters(
                schema=tool_info.input_schema,
                entities=entities,
                defaults=defaults,
                overrides=overrides,
            )
            duration = (time.perf_counter() - start_time) * 1000
            
            if not param_result.success:
                error_msg = "Parameter building failed"
                if param_result.missing_required:
                    error_msg += f": missing required params {param_result.missing_required}"
                if param_result.validation_errors:
                    error_msg += f": {param_result.validation_errors}"
                
                return StageResult(
                    stage=PipelineStage.PARAMETER_BUILDING,
                    success=False,
                    duration_ms=duration,
                    error=error_msg,
                    output=param_result,
                )
            
            logger.debug(f"Built parameters: {param_result.parameters}")
            
            return StageResult(
                stage=PipelineStage.PARAMETER_BUILDING,
                success=True,
                duration_ms=duration,
                output=param_result,
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Parameter building failed: {e}")
            
            return StageResult(
                stage=PipelineStage.PARAMETER_BUILDING,
                success=False,
                duration_ms=duration,
                error=str(e),
            )
    
    async def _execute_schema_validation(
        self,
        tool_info: ToolInfo,
        parameters: Dict[str, Any],
    ) -> StageResult:
        """Stage 6: Validate parameters against JSON Schema."""
        start_time = time.perf_counter()
        
        try:
            is_valid, errors = self.schema_executor.validate_parameters(
                parameters,
                tool_info.input_schema,
            )
            duration = (time.perf_counter() - start_time) * 1000
            
            if not is_valid:
                return StageResult(
                    stage=PipelineStage.SCHEMA_VALIDATION,
                    success=False,
                    duration_ms=duration,
                    error=f"Validation failed: {errors}",
                )
            
            logger.debug("Schema validation passed")
            
            return StageResult(
                stage=PipelineStage.SCHEMA_VALIDATION,
                success=True,
                duration_ms=duration,
                output=True,
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Schema validation failed: {e}")
            
            return StageResult(
                stage=PipelineStage.SCHEMA_VALIDATION,
                success=False,
                duration_ms=duration,
                error=str(e),
            )
    
    async def _execute_tool(
        self,
        tool_info: ToolInfo,
        parameters: Dict[str, Any],
    ) -> StageResult:
        """Stage 7: Execute the tool via MCP transport."""
        start_time = time.perf_counter()
        
        try:
            # Get server ID from tool
            tool_with_server = await self.registry.get_tool_with_server(
                tool_info.tool_name
            )
            
            if not tool_with_server:
                return StageResult(
                    stage=PipelineStage.TOOL_EXECUTION,
                    success=False,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    error="Tool or server not found",
                )
            
            _, server_info = tool_with_server
            
            # Check if server is connected
            if server_info.server_id not in self.mcp_client.list_connections():
                # Try to reconnect
                from mcp.transport import TransportType
                connected = await self.mcp_client.connect_server(
                    server_id=server_info.server_id,
                    transport_type=TransportType(server_info.transport),
                    command=server_info.command,
                    args=server_info.args,
                    url=server_info.url,
                )
                
                if not connected:
                    return StageResult(
                        stage=PipelineStage.TOOL_EXECUTION,
                        success=False,
                        duration_ms=(time.perf_counter() - start_time) * 1000,
                        error=f"Could not connect to server: {server_info.server_id}",
                    )
            
            # Execute tool
            result = await self.mcp_client.call_tool(
                server_id=server_info.server_id,
                tool_name=tool_info.tool_name,
                arguments=parameters,
            )
            duration = (time.perf_counter() - start_time) * 1000
            
            if not result.success:
                return StageResult(
                    stage=PipelineStage.TOOL_EXECUTION,
                    success=False,
                    duration_ms=duration,
                    error=result.error,
                    output=result,
                )
            
            logger.debug(f"Tool executed successfully")
            
            return StageResult(
                stage=PipelineStage.TOOL_EXECUTION,
                success=True,
                duration_ms=duration,
                output=result,
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Tool execution failed: {e}")
            
            return StageResult(
                stage=PipelineStage.TOOL_EXECUTION,
                success=False,
                duration_ms=duration,
                error=str(e),
            )
    
    async def _execute_response_formatting(
        self,
        tool_result: ToolCallResult,
    ) -> StageResult:
        """Stage 8: Format the response for the user."""
        start_time = time.perf_counter()
        
        try:
            # Format content based on type
            content = tool_result.content
            
            # If content is a list of content blocks, extract text
            if isinstance(content, list):
                formatted_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            formatted_parts.append(item.get("text", ""))
                        elif item.get("type") == "image":
                            formatted_parts.append("[Image content]")
                        else:
                            formatted_parts.append(str(item))
                    else:
                        formatted_parts.append(str(item))
                content = "\n".join(formatted_parts)
            
            duration = (time.perf_counter() - start_time) * 1000
            
            return StageResult(
                stage=PipelineStage.RESPONSE_FORMATTING,
                success=True,
                duration_ms=duration,
                output=content,
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Response formatting failed: {e}")
            
            # Still return the raw content on formatting error
            return StageResult(
                stage=PipelineStage.RESPONSE_FORMATTING,
                success=True,  # Don't fail pipeline for formatting issues
                duration_ms=duration,
                output=tool_result.content,
            )


# Singleton instance
_pipeline: Optional[Pipeline] = None


def get_pipeline() -> Pipeline:
    """Get or create the pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline
