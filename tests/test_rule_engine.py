"""
Tests for Rule Engine.

Verifies that json-logic rules are evaluated correctly
for permissions, thresholds, and context.
"""

import pytest
from rules.engine import (
    RuleEngine,
    RuleContext,
    RuleResult,
    RuleDecision,
    Rule,
    evaluate_rules,
)


class TestRuleContext:
    """Tests for RuleContext."""
    
    def test_to_dict(self):
        """Context can be converted to dict."""
        context = RuleContext(
            user_id="123",
            user_role="admin",
            intent="read_file",
            intent_confidence=0.9,
        )
        
        d = context.to_dict()
        
        assert d["user"]["id"] == "123"
        assert d["user"]["role"] == "admin"
        assert d["intent"]["name"] == "read_file"
        assert d["intent"]["confidence"] == 0.9
    
    def test_default_values(self):
        """Default values are set correctly."""
        context = RuleContext()
        
        assert context.user_role == "guest"
        assert context.intent_confidence == 0.0
        assert context.is_forced_intent == False


class TestRule:
    """Tests for Rule evaluation."""
    
    def test_simple_equality_rule(self):
        """Simple equality rule evaluates correctly."""
        rule = Rule(
            name="test_rule",
            description="Test rule",
            rule_type="permission",
            logic={"==": [{"var": "user.role"}, "admin"]},
        )
        
        context_admin = {"user": {"role": "admin"}}
        context_user = {"user": {"role": "user"}}
        
        assert rule.evaluate(context_admin) == True
        assert rule.evaluate(context_user) == False
    
    def test_comparison_rule(self):
        """Comparison rule evaluates correctly."""
        rule = Rule(
            name="confidence_check",
            description="Check confidence threshold",
            rule_type="threshold",
            logic={"<": [{"var": "intent.confidence"}, 0.7]},
        )
        
        low_confidence = {"intent": {"confidence": 0.5}}
        high_confidence = {"intent": {"confidence": 0.9}}
        
        assert rule.evaluate(low_confidence) == True
        assert rule.evaluate(high_confidence) == False
    
    def test_and_rule(self):
        """AND rule evaluates correctly."""
        rule = Rule(
            name="compound_rule",
            description="Compound AND rule",
            rule_type="context",
            logic={
                "and": [
                    {"==": [{"var": "user.role"}, "guest"]},
                    {"var": "execution.is_destructive"},
                ]
            },
        )
        
        guest_destructive = {
            "user": {"role": "guest"},
            "execution": {"is_destructive": True},
        }
        guest_safe = {
            "user": {"role": "guest"},
            "execution": {"is_destructive": False},
        }
        admin_destructive = {
            "user": {"role": "admin"},
            "execution": {"is_destructive": True},
        }
        
        assert rule.evaluate(guest_destructive) == True
        assert rule.evaluate(guest_safe) == False
        assert rule.evaluate(admin_destructive) == False


class TestRuleEngine:
    """Tests for RuleEngine."""
    
    def test_default_rules_loaded(self):
        """Default rules are loaded."""
        engine = RuleEngine()
        
        assert len(engine._rules) > 0
    
    def test_allow_by_default(self):
        """No matching rules results in ALLOW."""
        engine = RuleEngine()
        
        # Remove all default rules
        engine._rules = []
        
        context = RuleContext(
            user_role="user",
            intent_confidence=0.9,
        )
        
        result = engine.evaluate(context)
        
        assert result.decision == RuleDecision.ALLOW
    
    def test_deny_rule_is_terminal(self):
        """DENY rules stop evaluation."""
        engine = RuleEngine()
        engine._rules = []
        
        # Add deny rule
        engine.add_rule(Rule(
            name="always_deny",
            description="Always deny",
            rule_type="permission",
            logic={"==": [1, 1]},  # Always true
            decision_on_match=RuleDecision.DENY,
            priority=100,
        ))
        
        # Add allow rule (should never be reached)
        engine.add_rule(Rule(
            name="always_allow",
            description="Always allow",
            rule_type="permission",
            logic={"==": [1, 1]},
            decision_on_match=RuleDecision.ALLOW,
            priority=50,
        ))
        
        context = RuleContext()
        result = engine.evaluate(context)
        
        assert result.decision == RuleDecision.DENY
        assert "always_deny" in result.matched_rules
        assert "always_allow" not in result.matched_rules
    
    def test_confidence_threshold_rule(self):
        """Low confidence is denied."""
        engine = RuleEngine()
        
        low_confidence_context = RuleContext(
            user_role="user",
            intent="read_file",
            intent_confidence=0.3,
            is_forced_intent=False,
        )
        
        result = engine.evaluate(low_confidence_context)
        
        assert result.decision == RuleDecision.DENY
        assert "confidence_threshold" in result.matched_rules
    
    def test_forced_intent_bypasses_confidence(self):
        """Forced intent bypasses confidence threshold."""
        engine = RuleEngine()
        
        forced_context = RuleContext(
            user_role="user",
            intent="read_file",
            intent_confidence=0.3,  # Low confidence
            is_forced_intent=True,  # But forced
        )
        
        result = engine.evaluate(forced_context)
        
        # Should not be denied for low confidence
        # (may still be denied for other reasons)
        if "confidence_threshold" in result.matched_rules:
            assert result.decision != RuleDecision.DENY
    
    def test_modify_rule_accumulates(self):
        """MODIFY rules accumulate modifications."""
        engine = RuleEngine()
        engine._rules = []
        
        engine.add_rule(Rule(
            name="modify_rule",
            description="Add modification",
            rule_type="context",
            logic={"==": [1, 1]},
            decision_on_match=RuleDecision.MODIFY,
            modifications={"key": "value"},
        ))
        
        context = RuleContext()
        result = engine.evaluate(context)
        
        assert result.decision == RuleDecision.MODIFY
        assert result.modifications.get("key") == "value"
    
    def test_rule_priority_ordering(self):
        """Rules are evaluated in priority order."""
        engine = RuleEngine()
        engine._rules = []
        
        engine.add_rule(Rule(
            name="low_priority",
            description="Low priority",
            rule_type="test",
            logic={"==": [1, 1]},
            priority=10,
            decision_on_match=RuleDecision.DENY,
        ))
        engine.add_rule(Rule(
            name="high_priority",
            description="High priority",
            rule_type="test",
            logic={"==": [1, 1]},
            priority=100,
            decision_on_match=RuleDecision.ALLOW,
        ))
        
        # High priority should be first
        assert engine._rules[0].name == "high_priority"
    
    def test_validate_rule(self):
        """Rule validation works."""
        engine = RuleEngine()
        
        valid_rule = {"==": [{"var": "x"}, 1]}
        is_valid, error = engine.validate_rule(valid_rule)
        
        assert is_valid == True
        assert error is None
    
    def test_convenience_function(self):
        """Convenience function works."""
        context = RuleContext(
            user_role="user",
            intent_confidence=0.9,
            is_forced_intent=True,
        )
        
        result = evaluate_rules(context)
        
        assert isinstance(result, RuleResult)
