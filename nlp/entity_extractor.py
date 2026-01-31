"""
NLP Layer - Entity Extraction Only.

This module handles ONLY entity extraction using spaCy.
NO intent logic belongs here - that is handled by the intent layer.

STRICT CONSTRAINTS:
- spaCy only
- Entity extraction only
- Returns structured entities
- No intent classification
- No tool selection logic
"""

import spacy
from spacy.tokens import Doc
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
import re
import logging

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """Represents a single extracted entity."""
    text: str
    label: str
    start: int
    end: int
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EntityExtractionResult:
    """Result of entity extraction process."""
    original_text: str
    normalized_text: str
    entities: List[ExtractedEntity]
    tokens: List[str]
    noun_chunks: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "normalized_text": self.normalized_text,
            "entities": [e.to_dict() for e in self.entities],
            "tokens": self.tokens,
            "noun_chunks": self.noun_chunks,
            "metadata": self.metadata,
        }
    
    def get_entities_by_label(self, label: str) -> List[ExtractedEntity]:
        """Get all entities with a specific label."""
        return [e for e in self.entities if e.label == label]
    
    def get_entity_texts_by_label(self, label: str) -> List[str]:
        """Get text values of entities with a specific label."""
        return [e.text for e in self.entities if e.label == label]
    
    def has_entity(self, label: str) -> bool:
        """Check if an entity with the given label exists."""
        return any(e.label == label for e in self.entities)


class EntityExtractor:
    """
    Entity extraction using spaCy.
    
    Extracts:
    - Named entities (PERSON, ORG, GPE, DATE, TIME, MONEY, etc.)
    - Custom patterns (file paths, URLs, emails, etc.)
    - Noun chunks for context
    """
    
    # Custom patterns for common entity types not covered by spaCy NER
    CUSTOM_PATTERNS = {
        "FILE_PATH": [
            r'[/\\]?(?:[a-zA-Z]:)?(?:[/\\][^\s/\\:*?"<>|]+)+',  # Unix/Windows paths
            r'\./[^\s]+',  # Relative paths
            r'~[/\\][^\s]+',  # Home directory paths
        ],
        "URL": [
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            r'www\.[^\s<>"{}|\\^`\[\]]+',
        ],
        "EMAIL": [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        ],
        "IP_ADDRESS": [
            r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',  # IPv6
        ],
        "PORT": [
            r':\d{1,5}\b',
        ],
        "VERSION": [
            r'\bv?\d+\.\d+(?:\.\d+)*(?:-[a-zA-Z0-9]+)?\b',
        ],
        "JSON_PATH": [
            r'\$\.[a-zA-Z0-9_.\[\]]+',
        ],
        "COMMAND": [
            r'`[^`]+`',
        ],
    }
    
    def __init__(self, model_name: Optional[str] = None):
        """Initialize entity extractor with spaCy model."""
        self.model_name = model_name or settings.nlp.SPACY_MODEL
        self._nlp = None
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()
        
    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficiency."""
        for label, patterns in self.CUSTOM_PATTERNS.items():
            self._compiled_patterns[label] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
    
    @property
    def nlp(self) -> spacy.Language:
        """Lazy-load spaCy model."""
        if self._nlp is None:
            try:
                self._nlp = spacy.load(self.model_name)
                logger.info(f"Loaded spaCy model: {self.model_name}")
            except OSError:
                logger.warning(f"Model {self.model_name} not found, downloading...")
                spacy.cli.download(self.model_name)
                self._nlp = spacy.load(self.model_name)
        return self._nlp
    
    def _normalize_text(self, text: str) -> str:
        """Normalize input text for processing."""
        # Remove excessive whitespace
        normalized = re.sub(r'\s+', ' ', text.strip())
        return normalized
    
    def _extract_spacy_entities(self, doc: Doc) -> List[ExtractedEntity]:
        """Extract named entities using spaCy NER."""
        entities = []
        for ent in doc.ents:
            entities.append(ExtractedEntity(
                text=ent.text,
                label=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
                confidence=1.0,  # spaCy doesn't provide confidence scores by default
                metadata={"source": "spacy_ner"}
            ))
        return entities
    
    def _extract_custom_entities(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using custom regex patterns."""
        entities = []
        for label, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    # Avoid overlapping entities
                    matched_text = match.group()
                    entities.append(ExtractedEntity(
                        text=matched_text.strip('`'),  # Clean command backticks
                        label=label,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.9,
                        metadata={"source": "regex_pattern"}
                    ))
        return entities
    
    def _deduplicate_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Remove overlapping entities, preferring spaCy entities."""
        if not entities:
            return entities
        
        # Sort by start position, then by source preference
        sorted_entities = sorted(
            entities,
            key=lambda e: (e.start, 0 if e.metadata.get("source") == "spacy_ner" else 1)
        )
        
        deduplicated = []
        last_end = -1
        
        for entity in sorted_entities:
            # Skip if this entity overlaps with the previous one
            if entity.start >= last_end:
                deduplicated.append(entity)
                last_end = entity.end
        
        return deduplicated
    
    def _extract_noun_chunks(self, doc: Doc) -> List[str]:
        """Extract noun chunks for context understanding."""
        return [chunk.text for chunk in doc.noun_chunks]
    
    def _extract_tokens(self, doc: Doc) -> List[str]:
        """Extract meaningful tokens (excluding stopwords and punctuation)."""
        return [
            token.text for token in doc 
            if not token.is_stop and not token.is_punct and token.text.strip()
        ]
    
    def extract(self, text: str) -> EntityExtractionResult:
        """
        Main extraction method.
        
        Extracts all entities from the input text using both
        spaCy NER and custom regex patterns.
        
        Args:
            text: Input text to extract entities from
            
        Returns:
            EntityExtractionResult containing all extracted entities
        """
        if not text or not text.strip():
            return EntityExtractionResult(
                original_text=text,
                normalized_text="",
                entities=[],
                tokens=[],
                noun_chunks=[],
                metadata={"empty_input": True}
            )
        
        normalized_text = self._normalize_text(text)
        doc = self.nlp(normalized_text)
        
        # Extract from both sources
        spacy_entities = self._extract_spacy_entities(doc)
        custom_entities = self._extract_custom_entities(normalized_text)
        
        # Combine and deduplicate
        all_entities = spacy_entities + custom_entities
        deduplicated_entities = self._deduplicate_entities(all_entities)
        
        # Extract additional context
        tokens = self._extract_tokens(doc)
        noun_chunks = self._extract_noun_chunks(doc)
        
        result = EntityExtractionResult(
            original_text=text,
            normalized_text=normalized_text,
            entities=deduplicated_entities,
            tokens=tokens,
            noun_chunks=noun_chunks,
            metadata={
                "spacy_entities_count": len(spacy_entities),
                "custom_entities_count": len(custom_entities),
                "model": self.model_name,
            }
        )
        
        logger.debug(f"Extracted {len(deduplicated_entities)} entities from text")
        return result


# Singleton instance for reuse
_extractor_instance: Optional[EntityExtractor] = None


def get_entity_extractor() -> EntityExtractor:
    """Get or create the entity extractor singleton."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = EntityExtractor()
    return _extractor_instance


def extract_entities(text: str) -> EntityExtractionResult:
    """Convenience function for entity extraction."""
    return get_entity_extractor().extract(text)
