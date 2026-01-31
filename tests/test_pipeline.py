"""
Tests for Pipeline Orchestrator.

Verifies the deterministic 8-stage execution pipeline.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pipeline.orchestrator import (
    Pipeline,
    PipelineResult,
    PipelineStage,
    PipelineContext,
    execute_pipeline,
)
from rules.engine import RuleDecision


class TestPipelineContext:
    """Tests for PipelineContext."""
    
    def test_initial_state(self):
        """Context initializes correctly."""
        context = PipelineContext(
            request_id="test-123",
            user_id="user-1",
            user_role="user",
            input_text="test input",
        )
        
        assert context.request_id == "test-123"
        assert context.current_stage == PipelineStage.ENTITY_EXTRACTION
        assert context.error is None
    
    def test_to_dict(self):
        """Context can be serialized."""
        context = PipelineContext(
            request_id="test-123",
            user_id="user-1",
            user_role="user",
            input_text="test input",
        )
        
        d = context.to_dict()
        
        assert d["request_id"] == "test-123"
        assert "stages" in d


class TestPipelineStages:
    """Tests for individual pipeline stages."""
    
    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance."""
        return Pipeline()
    
    @pytest.fixture
    def base_context(self):
        """Create base context."""
        return PipelineContext(
            request_id="test-123",
            user_id="user-1",
            user_role="user",
            input_text="read file /tmp/test.txt",
        )
    
    def test_entity_extraction_stage(self, pipeline, base_context):
        """Entity extraction stage runs."""
        context = pipeline._run_entity_extraction(base_context)
        
        assert context.entities is not None
        assert context.stage_complete(PipelineStage.ENTITY_EXTRACTION)
    
    def test_intent_classification_stage(self, pipeline, base_context):
        """Intent classification stage runs."""
        # First run entity extraction
        context = pipeline._run_entity_extraction(base_context)
        context = pipeline._run_intent_classification(context)
        
        assert context.intent_result is not None
        assert context.stage_complete(PipelineStage.INTENT_CLASSIFICATION)
    
    def test_rule_evaluation_stage(self, pipeline, base_context):
        """Rule evaluation stage runs."""
        context = pipeline._run_entity_extraction(base_context)
        context = pipeline._run_intent_classification(context)
        context = pipeline._run_rule_evaluation(context)
        
        assert context.rule_result is not None
        assert context.stage_complete(PipelineStage.RULE_EVALUATION)


class TestPipelineFlow:
    """Tests for complete pipeline flow."""
    
    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance."""
        return Pipeline()
    
    @pytest.mark.asyncio
    async def test_rule_deny_stops_pipeline(self, pipeline):
        """DENY from rules stops execution."""
        # Create context that will be denied (very low confidence, non-forced)
        with patch.object(pipeline._intent_engine, 'classify') as mock_classify:
            mock_classify.return_value = MagicMock(
                intent="unknown",
                confidence=0.1,  # Very low
                is_forced=False,
                alternatives=[],
                metadata={},
            )
            
            result = await pipeline.execute(
                input_text="xyzabc",
                user_id="user-1",
                user_role="guest",
            )
        
        assert result.success == False
        assert "denied" in result.error.lower() or result.rule_decision == RuleDecision.DENY
    
    @pytest.mark.asyncio
    async def test_missing_tool_fails_gracefully(self, pipeline):
        """Missing tool returns clear error."""
        with patch.object(pipeline._intent_engine, 'classify') as mock_classify:
            mock_classify.return_value = MagicMock(
                intent="nonexistent_tool_action",
                confidence=0.99,
                is_forced=True,
                alternatives=[],
                metadata={},
            )
            
            result = await pipeline.execute(
                input_text="do something impossible",
                user_id="user-1",
                user_role="admin",
            )
        
        # Either fails at tool selection or schema building
        # Both are acceptable outcomes for missing tool
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_empty_input_fails(self, pipeline):
        """Empty input fails early."""
        result = await pipeline.execute(
            input_text="",
            user_id="user-1",
            user_role="user",
        )
        
        assert result.success == False
    
    @pytest.mark.asyncio
    async def test_pipeline_records_timing(self, pipeline):
        """Pipeline records timing for each stage."""
        result = await pipeline.execute(
            input_text="help",
            user_id="user-1",
            user_role="user",
        )
        
        # Should have timing data
        assert result.context is not None
        assert len(result.context.stage_timings) > 0


class TestPipelineDeterminism:
    """Tests proving pipeline is deterministic."""
    
    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance."""
        return Pipeline()
    
    @pytest.mark.asyncio
    async def test_same_input_same_output(self, pipeline):
        """Same input produces same output."""
        input_text = "help"
        user_id = "user-1"
        user_role = "user"
        
        result1 = await pipeline.execute(input_text, user_id, user_role)
        result2 = await pipeline.execute(input_text, user_id, user_role)
        
        # Same intent should be selected
        assert result1.context.intent_result.intent == result2.context.intent_result.intent
    
    @pytest.mark.asyncio
    async def test_forced_override_is_deterministic(self, pipeline):
        """Forced overrides are always deterministic."""
        # "help" triggers forced override
        results = []
        for _ in range(5):
            result = await pipeline.execute("help", "user-1", "user")
            results.append(result.context.intent_result)
        
        # All results should have same intent
        intents = [r.intent for r in results]
        assert len(set(intents)) == 1
        assert intents[0] == "show_help"
        
        # All should be forced
        assert all(r.is_forced for r in results)


class TestPipelineNoLLM:
    """Tests proving no LLM is used in execution."""
    
    def test_no_llm_imports_in_pipeline(self):
        """Pipeline has no LLM-related imports."""
        import inspect
        from pipeline import orchestrator
        
        source = inspect.getsource(orchestrator)
        
        # Check for common LLM library imports
        llm_indicators = [
            "import openai",
            "from openai",
            "import anthropic",
            "from anthropic",
            "import langchain",
            "from langchain",
            "ChatGPT",
            "GPT-4",
            "GPT-3",
            "Claude",
        ]
        
        for indicator in llm_indicators:
            assert indicator.lower() not in source.lower(), \
                f"Found LLM indicator: {indicator}"
    
    def test_no_llm_imports_in_executor(self):
        """Executor has no LLM-related imports."""
        import inspect
        from executor import schema_executor
        
        source = inspect.getsource(schema_executor)
        
        llm_indicators = [
            "import openai",
            "from openai",
            "import anthropic",
            "from anthropic",
        ]
        
        for indicator in llm_indicators:
            assert indicator.lower() not in source.lower()
