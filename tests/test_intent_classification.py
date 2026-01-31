"""
Tests for Intent Classification.

Verifies that intent classification works with
forced overrides and ML classifier.
"""

import pytest
from intent.classifier import (
    IntentEngine,
    IntentResult,
    ForcedOverride,
    ForcedOverrideRegistry,
    IntentClassifier,
    classify_intent,
)


class TestForcedOverride:
    """Tests for ForcedOverride pattern matching."""
    
    def test_exact_match(self):
        """Exact pattern matching works."""
        override = ForcedOverride(
            pattern="help",
            pattern_type="exact",
            target_intent="show_help",
        )
        
        assert override.matches("help") == True
        assert override.matches("HELP") == True  # Case insensitive
        assert override.matches("help me") == False
    
    def test_prefix_match(self):
        """Prefix pattern matching works."""
        override = ForcedOverride(
            pattern="list",
            pattern_type="prefix",
            target_intent="list_items",
        )
        
        assert override.matches("list files") == True
        assert override.matches("list") == True
        assert override.matches("show list") == False
    
    def test_contains_match(self):
        """Contains pattern matching works."""
        override = ForcedOverride(
            pattern="tools",
            pattern_type="contains",
            target_intent="list_tools",
        )
        
        assert override.matches("list tools") == True
        assert override.matches("show me all tools please") == True
        assert override.matches("help") == False
    
    def test_regex_match(self):
        """Regex pattern matching works."""
        override = ForcedOverride(
            pattern=r"^read\s+file",
            pattern_type="regex",
            target_intent="read_file",
        )
        
        assert override.matches("read file /path") == True
        assert override.matches("Read File test.txt") == True
        assert override.matches("please read file") == False
    
    def test_disabled_override(self):
        """Disabled override doesn't match."""
        override = ForcedOverride(
            pattern="help",
            pattern_type="exact",
            target_intent="show_help",
            enabled=False,
        )
        
        assert override.matches("help") == False


class TestForcedOverrideRegistry:
    """Tests for ForcedOverrideRegistry."""
    
    def test_default_overrides_loaded(self):
        """Default overrides are loaded."""
        registry = ForcedOverrideRegistry()
        
        # Should have some default overrides
        assert len(registry._overrides) > 0
    
    def test_find_match_returns_intent(self):
        """Finding a match returns intent and pattern."""
        registry = ForcedOverrideRegistry()
        
        result = registry.find_match("help")
        
        assert result is not None
        intent, pattern = result
        assert intent == "show_help"
    
    def test_find_match_priority(self):
        """Higher priority overrides are checked first."""
        registry = ForcedOverrideRegistry()
        
        # Add two overrides for same input
        registry.add_override(ForcedOverride(
            pattern="test",
            pattern_type="exact",
            target_intent="low_priority",
            priority=10,
        ))
        registry.add_override(ForcedOverride(
            pattern="test",
            pattern_type="exact",
            target_intent="high_priority",
            priority=100,
        ))
        
        result = registry.find_match("test")
        
        assert result is not None
        intent, _ = result
        assert intent == "high_priority"
    
    def test_no_match_returns_none(self):
        """No match returns None."""
        registry = ForcedOverrideRegistry()
        
        result = registry.find_match("xyzabc123notamatch")
        
        assert result is None


class TestIntentEngine:
    """Tests for IntentEngine."""
    
    def test_forced_override_takes_priority(self):
        """Forced overrides bypass ML classifier."""
        engine = IntentEngine()
        
        result = engine.classify("help")
        
        assert result.intent == "show_help"
        assert result.is_forced == True
        assert result.confidence == 1.0
    
    def test_empty_input_returns_unknown(self):
        """Empty input returns unknown intent."""
        engine = IntentEngine()
        
        result = engine.classify("")
        
        assert result.intent == "unknown"
        assert result.confidence == 0.0
    
    def test_result_has_metadata(self):
        """Result includes source metadata."""
        engine = IntentEngine()
        
        result = engine.classify("list files")
        
        assert "source" in result.metadata
    
    def test_classify_intent_convenience(self):
        """Convenience function works."""
        result = classify_intent("help")
        
        assert isinstance(result, IntentResult)
        assert result.intent == "show_help"


class TestIntentClassifier:
    """Tests for ML IntentClassifier."""
    
    def test_untrained_classifier_raises(self):
        """Untrained classifier raises on predict."""
        classifier = IntentClassifier()
        
        with pytest.raises(RuntimeError, match="not been trained"):
            classifier.predict("test input")
    
    def test_train_requires_minimum_samples(self):
        """Training requires minimum samples."""
        classifier = IntentClassifier()
        
        with pytest.raises(ValueError, match="at least 10"):
            classifier.train(
                texts=["a", "b", "c"],
                labels=["x", "y", "z"],
            )
    
    def test_train_and_predict(self):
        """Classifier can be trained and used for prediction."""
        classifier = IntentClassifier()
        
        # Create training data
        texts = [
            "read file", "open file", "get file content",
            "show file", "display file", "cat file",
            "write file", "save file", "create file",
            "store file", "put file", "write to file",
            "delete file", "remove file", "erase file",
            "trash file", "destroy file", "delete content",
        ]
        labels = [
            "read", "read", "read",
            "read", "read", "read",
            "write", "write", "write",
            "write", "write", "write",
            "delete", "delete", "delete",
            "delete", "delete", "delete",
        ]
        
        metrics = classifier.train(texts, labels)
        
        assert classifier.is_trained == True
        assert "num_classes" in metrics
        assert metrics["num_classes"] == 3
        
        # Predict
        intent, confidence, alternatives = classifier.predict("read this file")
        
        assert intent in ["read", "write", "delete"]
        assert 0.0 <= confidence <= 1.0
        assert len(alternatives) <= 3
