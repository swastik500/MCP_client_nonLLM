"""
Rule Engine using json-logic-py.

Enforces:
- Role-based permissions
- Confidence thresholds
- Context rules

Output is ALLOW, DENY, or MODIFY.

STRICT CONSTRAINTS:
- json-logic-py only
- No hardcoded logic
- Rules are data (stored in DB)
- Pure evaluation, no side effects
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from json_logic import jsonLogic

from config.settings import settings

logger = logging.getLogger(__name__)


class RuleDecision(Enum):
    """Possible rule engine decisions."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    MODIFY = "MODIFY"


@dataclass
class RuleContext:
    """Context provided to rule evaluation."""
    # User context
    user_id: Optional[str] = None
    user_role: str = "guest"
    user_permissions: List[str] = field(default_factory=list)
    
    # Intent context
    intent: str = ""
    intent_confidence: float = 0.0
    is_forced_intent: bool = False
    
    # Tool context
    tool_name: Optional[str] = None
    tool_category: Optional[str] = None
    tool_requires_confirmation: bool = False
    
    # Execution context
    is_destructive_operation: bool = False
    target_resource: Optional[str] = None
    
    # Session context
    session_id: Optional[str] = None
    request_count: int = 0
    
    # Custom data
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for json-logic evaluation."""
        return {
            "user": {
                "id": self.user_id,
                "role": self.user_role,
                "permissions": self.user_permissions,
            },
            "intent": {
                "name": self.intent,
                "confidence": self.intent_confidence,
                "is_forced": self.is_forced_intent,
            },
            "tool": {
                "name": self.tool_name,
                "category": self.tool_category,
                "requires_confirmation": self.tool_requires_confirmation,
            },
            "execution": {
                "is_destructive": self.is_destructive_operation,
                "target_resource": self.target_resource,
            },
            "session": {
                "id": self.session_id,
                "request_count": self.request_count,
            },
            "custom": self.custom,
        }


@dataclass
class RuleResult:
    """Result of rule evaluation."""
    decision: RuleDecision
    matched_rules: List[str]
    reason: Optional[str] = None
    modifications: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "matched_rules": self.matched_rules,
            "reason": self.reason,
            "modifications": self.modifications,
            "metadata": self.metadata,
        }


@dataclass
class Rule:
    """Represents a single rule definition."""
    name: str
    description: str
    rule_type: str  # permission, threshold, context
    logic: Dict[str, Any]  # JSON-Logic rule
    priority: int = 0
    enabled: bool = True
    decision_on_match: RuleDecision = RuleDecision.ALLOW
    modifications: Dict[str, Any] = field(default_factory=dict)
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the rule against the context."""
        try:
            result = jsonLogic(self.logic, context)
            return bool(result)
        except Exception as e:
            logger.error(f"Rule evaluation error for {self.name}: {e}")
            return False


class RuleEngine:
    """
    JSON-Logic based rule engine.
    
    Evaluates rules in priority order and returns:
    - ALLOW: Proceed with execution
    - DENY: Block execution
    - MODIFY: Proceed with modifications
    """
    
    # Default rules (can be overridden from database)
    DEFAULT_RULES = [
        # Confidence threshold rule
        Rule(
            name="confidence_threshold",
            description="Deny if intent confidence is below threshold",
            rule_type="threshold",
            priority=100,
            logic={
                "and": [
                    {"!": {"var": "intent.is_forced"}},
                    {"<": [{"var": "intent.confidence"}, settings.nlp.INTENT_CONFIDENCE_THRESHOLD]}
                ]
            },
            decision_on_match=RuleDecision.DENY,
        ),
        
        # Guest user restrictions
        Rule(
            name="guest_readonly",
            description="Guest users can only use read operations",
            rule_type="permission",
            priority=90,
            logic={
                "and": [
                    {"==": [{"var": "user.role"}, "guest"]},
                    {"var": "execution.is_destructive"}
                ]
            },
            decision_on_match=RuleDecision.DENY,
        ),
        
        # Require confirmation for destructive operations
        Rule(
            name="destructive_confirmation",
            description="Require confirmation for destructive operations",
            rule_type="context",
            priority=80,
            logic={
                "and": [
                    {"var": "execution.is_destructive"},
                    {"!": {"var": "tool.requires_confirmation"}}
                ]
            },
            decision_on_match=RuleDecision.MODIFY,
            modifications={"requires_confirmation": True},
        ),
        
        # Admin bypass for low confidence
        Rule(
            name="admin_confidence_bypass",
            description="Admin users can bypass low confidence",
            rule_type="permission",
            priority=200,
            logic={
                "and": [
                    {"==": [{"var": "user.role"}, "admin"]},
                    {"<": [{"var": "intent.confidence"}, settings.nlp.INTENT_CONFIDENCE_THRESHOLD]}
                ]
            },
            decision_on_match=RuleDecision.ALLOW,
        ),
        
        # Rate limiting (example)
        Rule(
            name="rate_limit",
            description="Deny if too many requests in session",
            rule_type="context",
            priority=50,
            logic={
                ">": [{"var": "session.request_count"}, 1000]
            },
            decision_on_match=RuleDecision.DENY,
        ),
    ]
    
    def __init__(self):
        """Initialize the rule engine."""
        self._rules: List[Rule] = self.DEFAULT_RULES.copy()
        self._sort_rules()
    
    def _sort_rules(self) -> None:
        """Sort rules by priority (higher first)."""
        self._rules.sort(key=lambda r: r.priority, reverse=True)
    
    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self._rules.append(rule)
        self._sort_rules()
    
    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        original_len = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < original_len
    
    def load_from_database(self, rules_data: List[Dict[str, Any]]) -> None:
        """Load rules from database records."""
        for rule_data in rules_data:
            rule = Rule(
                name=rule_data["rule_name"],
                description=rule_data.get("description", ""),
                rule_type=rule_data["rule_type"],
                logic=rule_data["rule_logic"],
                priority=rule_data.get("priority", 0),
                enabled=rule_data.get("enabled", True),
                decision_on_match=RuleDecision(
                    rule_data.get("decision_on_match", "allow")
                ),
                modifications=rule_data.get("modifications", {}),
            )
            self._rules.append(rule)
        self._sort_rules()
    
    def evaluate(self, context: RuleContext) -> RuleResult:
        """
        Evaluate all rules against the context.
        
        Process:
        1. Convert context to dict for json-logic
        2. Evaluate rules in priority order
        3. Return first matching DENY or final decision
        
        Args:
            context: RuleContext with all evaluation data
            
        Returns:
            RuleResult with decision and metadata
        """
        context_dict = context.to_dict()
        matched_rules = []
        accumulated_modifications = {}
        final_decision = RuleDecision.ALLOW
        deny_reason = None
        
        for rule in self._rules:
            if not rule.enabled:
                continue
            
            try:
                if rule.evaluate(context_dict):
                    matched_rules.append(rule.name)
                    logger.debug(f"Rule matched: {rule.name} -> {rule.decision_on_match.value}")
                    
                    if rule.decision_on_match == RuleDecision.DENY:
                        # DENY rules are terminal
                        return RuleResult(
                            decision=RuleDecision.DENY,
                            matched_rules=matched_rules,
                            reason=rule.description,
                            metadata={"terminal_rule": rule.name}
                        )
                    
                    elif rule.decision_on_match == RuleDecision.MODIFY:
                        final_decision = RuleDecision.MODIFY
                        accumulated_modifications.update(rule.modifications)
                    
                    elif rule.decision_on_match == RuleDecision.ALLOW:
                        # ALLOW rules can override previous decisions
                        if final_decision != RuleDecision.DENY:
                            final_decision = RuleDecision.ALLOW
                            
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {e}")
                continue
        
        return RuleResult(
            decision=final_decision,
            matched_rules=matched_rules,
            reason=deny_reason,
            modifications=accumulated_modifications,
            metadata={"rules_evaluated": len(self._rules)}
        )
    
    def validate_rule(self, logic: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a JSON-Logic rule.
        
        Args:
            logic: JSON-Logic rule definition
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to evaluate with empty context
            jsonLogic(logic, {})
            return True, None
        except Exception as e:
            return False, str(e)


# Singleton instance
_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    """Get or create the rule engine singleton."""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine


def evaluate_rules(context: RuleContext) -> RuleResult:
    """Convenience function for rule evaluation."""
    return get_rule_engine().evaluate(context)
