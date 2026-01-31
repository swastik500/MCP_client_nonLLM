"""
Intent Classification Layer.

This module handles intent classification using:
1. Forced overrides (deterministic patterns)
2. scikit-learn ML classifier (when no override matches)

STRICT CONSTRAINTS:
- scikit-learn only for ML
- Returns (intent, confidence) tuple
- Forced overrides take priority
- No tool selection logic
- No execution logic
"""

import re
import logging
import pickle
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass, field
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: str
    confidence: float
    is_forced: bool = False
    matched_pattern: Optional[str] = None
    alternative_intents: List[Tuple[str, float]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "is_forced": self.is_forced,
            "matched_pattern": self.matched_pattern,
            "alternative_intents": self.alternative_intents,
            "metadata": self.metadata,
        }
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if confidence meets threshold."""
        return self.confidence >= settings.nlp.INTENT_CONFIDENCE_THRESHOLD


@dataclass
class ForcedOverride:
    """Represents a forced intent override pattern."""
    pattern: str
    pattern_type: str  # "regex", "exact", "prefix", "contains"
    target_intent: str
    priority: int = 0
    enabled: bool = True
    
    def matches(self, text: str) -> bool:
        """Check if the pattern matches the input text."""
        if not self.enabled:
            return False
            
        normalized_text = text.lower().strip()
        
        if self.pattern_type == "exact":
            return normalized_text == self.pattern.lower()
        elif self.pattern_type == "prefix":
            return normalized_text.startswith(self.pattern.lower())
        elif self.pattern_type == "contains":
            return self.pattern.lower() in normalized_text
        elif self.pattern_type == "regex":
            try:
                return bool(re.search(self.pattern, text, re.IGNORECASE))
            except re.error:
                logger.error(f"Invalid regex pattern: {self.pattern}")
                return False
        return False


class ForcedOverrideRegistry:
    """
    Registry for forced intent overrides.
    These patterns bypass ML classification entirely.
    """
    
    # Default forced overrides for deterministic commands
    DEFAULT_OVERRIDES = [
        # File operations
        ForcedOverride(
            pattern=r"^(list|show|get)\s+(files?|directory|dir|folder)",
            pattern_type="regex",
            target_intent="list_files",
            priority=100
        ),
        ForcedOverride(
            pattern=r"^read\s+(file|content)",
            pattern_type="regex",
            target_intent="read_file",
            priority=100
        ),
        ForcedOverride(
            pattern=r"^(create|write|save)\s+file",
            pattern_type="regex",
            target_intent="write_file",
            priority=100
        ),
        ForcedOverride(
            pattern=r"^(delete|remove)\s+file",
            pattern_type="regex",
            target_intent="delete_file",
            priority=100
        ),
        
        # Fetch operations
        ForcedOverride(
            pattern=r"^fetch\s+(url|http|https|webpage|page)",
            pattern_type="regex",
            target_intent="fetch_url",
            priority=100
        ),
        ForcedOverride(
            pattern=r"^(get|download)\s+(from\s+)?(url|http|https)",
            pattern_type="regex",
            target_intent="fetch_url",
            priority=100
        ),
        
        # Memory operations
        ForcedOverride(
            pattern=r"^(store|save|put)\s+(in|to)?\s*memory",
            pattern_type="regex",
            target_intent="store_memory",
            priority=100
        ),
        ForcedOverride(
            pattern=r"^(get|retrieve|fetch)\s+(from\s+)?memory",
            pattern_type="regex",
            target_intent="retrieve_memory",
            priority=100
        ),
        
        # System commands
        ForcedOverride(
            pattern="help",
            pattern_type="exact",
            target_intent="show_help",
            priority=200
        ),
        ForcedOverride(
            pattern=r"(list|show|get)\s+(all\s+)?tools?",
            pattern_type="regex",
            target_intent="list_tools",
            priority=200
        ),
        ForcedOverride(
            pattern=r"(list|show|get)\s+(all\s+)?servers?",
            pattern_type="regex",
            target_intent="list_servers",
            priority=200
        ),
        ForcedOverride(
            pattern=r"(show|get|check)\s+(server\s+)?status",
            pattern_type="regex",
            target_intent="list_servers",
            priority=200
        ),
        
        # Browser automation (Playwright)
        ForcedOverride(
            pattern=r"(navigate|go)\s+(to\s+)?(\w+|https?://)",
            pattern_type="regex",
            target_intent="browser_navigate",
            priority=150
        ),
        ForcedOverride(
            pattern=r"(click|press|tap)\s+(on\s+)?",
            pattern_type="regex",
            target_intent="browser_click",
            priority=150
        ),
        ForcedOverride(
            pattern=r"(screenshot|capture|snap)",
            pattern_type="regex",
            target_intent="browser_screenshot",
            priority=150
        ),
    ]
    
    def __init__(self):
        """Initialize with default overrides."""
        self._overrides: List[ForcedOverride] = self.DEFAULT_OVERRIDES.copy()
        
    def add_override(self, override: ForcedOverride) -> None:
        """Add a new override."""
        self._overrides.append(override)
        # Re-sort by priority (higher first)
        self._overrides.sort(key=lambda x: x.priority, reverse=True)
        
    def remove_override(self, pattern: str) -> bool:
        """Remove an override by pattern."""
        original_len = len(self._overrides)
        self._overrides = [o for o in self._overrides if o.pattern != pattern]
        return len(self._overrides) < original_len
    
    def load_from_database(self, overrides: List[Dict[str, Any]]) -> None:
        """Load overrides from database records."""
        for override_data in overrides:
            self._overrides.append(ForcedOverride(
                pattern=override_data["pattern"],
                pattern_type=override_data["pattern_type"],
                target_intent=override_data["target_intent"],
                priority=override_data.get("priority", 0),
                enabled=override_data.get("enabled", True),
            ))
        self._overrides.sort(key=lambda x: x.priority, reverse=True)
    
    def find_match(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Find matching override for input text.
        
        Returns:
            Tuple of (intent, matched_pattern) or None if no match
        """
        for override in self._overrides:
            if override.matches(text):
                return (override.target_intent, override.pattern)
        return None


class IntentClassifier:
    """
    scikit-learn based intent classifier.
    Uses TF-IDF + Logistic Regression pipeline.
    """
    
    MODEL_PATH = Path("models/intent_classifier.pkl")
    
    def __init__(self):
        """Initialize the classifier."""
        self._pipeline: Optional[Pipeline] = None
        self._classes: List[str] = []
        self._is_trained = False
        
    @property
    def is_trained(self) -> bool:
        return self._is_trained
    
    def _create_pipeline(self) -> Pipeline:
        """Create the ML pipeline."""
        return Pipeline([
            ('tfidf', TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2),
                max_features=5000,
                stop_words='english'
            )),
            ('classifier', LogisticRegression(
                max_iter=1000,
                multi_class='multinomial',
                solver='lbfgs',
                class_weight='balanced'
            ))
        ])
    
    def train(self, texts: List[str], labels: List[str], test_size: float = 0.2) -> Dict[str, Any]:
        """
        Train the classifier on the provided data.
        
        Args:
            texts: List of training texts
            labels: List of corresponding intent labels
            test_size: Proportion of data to use for testing
            
        Returns:
            Training metrics dictionary
        """
        if len(texts) != len(labels):
            raise ValueError("texts and labels must have the same length")
        
        if len(texts) < 10:
            raise ValueError("Need at least 10 training samples")
        
        self._pipeline = self._create_pipeline()
        self._classes = list(set(labels))
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=test_size, stratify=labels, random_state=42
        )
        
        # Train
        self._pipeline.fit(X_train, y_train)
        self._is_trained = True
        
        # Evaluate
        y_pred = self._pipeline.predict(X_test)
        report = classification_report(y_test, y_pred, output_dict=True)
        
        logger.info(f"Trained intent classifier with {len(self._classes)} classes")
        
        return {
            "num_classes": len(self._classes),
            "classes": self._classes,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "metrics": report
        }
    
    def predict(self, text: str) -> Tuple[str, float, List[Tuple[str, float]]]:
        """
        Predict intent for input text.
        
        Args:
            text: Input text to classify
            
        Returns:
            Tuple of (predicted_intent, confidence, alternative_intents)
        """
        if not self._is_trained or self._pipeline is None:
            raise RuntimeError("Classifier has not been trained")
        
        # Get probabilities for all classes
        probas = self._pipeline.predict_proba([text])[0]
        
        # Get top prediction
        predicted_idx = np.argmax(probas)
        predicted_intent = self._pipeline.classes_[predicted_idx]
        confidence = float(probas[predicted_idx])
        
        # Get alternatives sorted by probability
        alternatives = [
            (self._pipeline.classes_[i], float(probas[i]))
            for i in np.argsort(probas)[::-1][1:4]  # Top 3 alternatives
        ]
        
        return predicted_intent, confidence, alternatives
    
    def save(self, path: Optional[Path] = None) -> None:
        """Save the trained model to disk."""
        path = path or self.MODEL_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        
        joblib.dump({
            'pipeline': self._pipeline,
            'classes': self._classes,
            'is_trained': self._is_trained
        }, path)
        
        logger.info(f"Saved intent classifier to {path}")
    
    def load(self, path: Optional[Path] = None) -> bool:
        """Load a trained model from disk."""
        path = path or self.MODEL_PATH
        
        if not path.exists():
            logger.warning(f"No saved model found at {path}")
            return False
        
        try:
            data = joblib.load(path)
            self._pipeline = data['pipeline']
            self._classes = data['classes']
            self._is_trained = data['is_trained']
            logger.info(f"Loaded intent classifier from {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False


class IntentEngine:
    """
    Main intent classification engine.
    
    Combines forced overrides (deterministic) with ML classification.
    Forced overrides are checked first for deterministic commands.
    """
    
    def __init__(self):
        """Initialize the intent engine."""
        self.override_registry = ForcedOverrideRegistry()
        self.classifier = IntentClassifier()
        
        # Try to load existing model
        self.classifier.load()
    
    def classify(self, text: str) -> IntentResult:
        """
        Classify intent for input text.
        
        Process:
        1. Check forced overrides (deterministic)
        2. If no override, use ML classifier
        3. Return intent with confidence
        
        Args:
            text: Input text to classify
            
        Returns:
            IntentResult with intent and metadata
        """
        if not text or not text.strip():
            return IntentResult(
                intent="unknown",
                confidence=0.0,
                metadata={"error": "empty_input"}
            )
        
        # Step 1: Check forced overrides
        override_match = self.override_registry.find_match(text)
        if override_match:
            intent, pattern = override_match
            logger.debug(f"Forced override matched: {pattern} -> {intent}")
            return IntentResult(
                intent=intent,
                confidence=1.0,  # Forced overrides have 100% confidence
                is_forced=True,
                matched_pattern=pattern,
                metadata={"source": "forced_override"}
            )
        
        # Step 2: Use ML classifier
        if not self.classifier.is_trained:
            logger.warning("ML classifier not trained, returning unknown intent")
            return IntentResult(
                intent="unknown",
                confidence=0.0,
                metadata={"error": "classifier_not_trained"}
            )
        
        try:
            intent, confidence, alternatives = self.classifier.predict(text)
            return IntentResult(
                intent=intent,
                confidence=confidence,
                is_forced=False,
                alternative_intents=alternatives,
                metadata={"source": "ml_classifier"}
            )
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return IntentResult(
                intent="unknown",
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    def train_classifier(self, texts: List[str], labels: List[str]) -> Dict[str, Any]:
        """Train the ML classifier with provided data."""
        return self.classifier.train(texts, labels)
    
    def save_classifier(self) -> None:
        """Save the trained classifier."""
        self.classifier.save()
    
    def load_overrides_from_db(self, overrides: List[Dict[str, Any]]) -> None:
        """Load forced overrides from database."""
        self.override_registry.load_from_database(overrides)


# Singleton instance
_intent_engine: Optional[IntentEngine] = None


def get_intent_engine() -> IntentEngine:
    """Get or create the intent engine singleton."""
    global _intent_engine
    if _intent_engine is None:
        _intent_engine = IntentEngine()
    return _intent_engine


def classify_intent(text: str) -> IntentResult:
    """Convenience function for intent classification."""
    return get_intent_engine().classify(text)
