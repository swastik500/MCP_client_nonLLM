"""
Tests for NLP Entity Extraction.

Verifies that entity extraction works correctly
without any tool-specific logic.
"""

import pytest
from nlp.entity_extractor import (
    EntityExtractor,
    EntityExtractionResult,
    ExtractedEntity,
    extract_entities,
)


class TestEntityExtractor:
    """Tests for EntityExtractor class."""
    
    def test_extract_empty_text(self):
        """Empty text returns empty result."""
        extractor = EntityExtractor()
        result = extractor.extract("")
        
        assert result.original_text == ""
        assert result.normalized_text == ""
        assert len(result.entities) == 0
        assert result.metadata.get("empty_input") == True
    
    def test_extract_file_path_unix(self):
        """Unix file paths are extracted."""
        extractor = EntityExtractor()
        result = extractor.extract("Please read /home/user/documents/file.txt")
        
        file_paths = result.get_entities_by_label("FILE_PATH")
        assert len(file_paths) >= 1
        assert any("/home/user/documents/file.txt" in e.text for e in file_paths)
    
    def test_extract_file_path_windows(self):
        """Windows file paths are extracted."""
        extractor = EntityExtractor()
        result = extractor.extract(r"Open C:\Users\test\file.txt")
        
        file_paths = result.get_entities_by_label("FILE_PATH")
        assert len(file_paths) >= 1
    
    def test_extract_url(self):
        """URLs are extracted."""
        extractor = EntityExtractor()
        result = extractor.extract("Fetch https://example.com/api/data")
        
        urls = result.get_entities_by_label("URL")
        assert len(urls) == 1
        assert "https://example.com/api/data" in urls[0].text
    
    def test_extract_email(self):
        """Email addresses are extracted."""
        extractor = EntityExtractor()
        result = extractor.extract("Send to user@example.com please")
        
        emails = result.get_entities_by_label("EMAIL")
        assert len(emails) == 1
        assert emails[0].text == "user@example.com"
    
    def test_extract_multiple_entities(self):
        """Multiple entity types are extracted."""
        extractor = EntityExtractor()
        result = extractor.extract(
            "Read /tmp/file.txt and fetch https://api.example.com"
        )
        
        assert result.has_entity("FILE_PATH")
        assert result.has_entity("URL")
        assert len(result.entities) >= 2
    
    def test_extract_preserves_original_text(self):
        """Original text is preserved."""
        extractor = EntityExtractor()
        original = "  Multiple   spaces   here  "
        result = extractor.extract(original)
        
        assert result.original_text == original
        assert result.normalized_text == "Multiple spaces here"
    
    def test_extract_tokens(self):
        """Tokens are extracted without stopwords."""
        extractor = EntityExtractor()
        result = extractor.extract("Read the important file now")
        
        # Should have meaningful tokens, excluding stopwords
        assert "Read" in result.tokens or "read" in result.tokens
        assert "file" in result.tokens
    
    def test_convenience_function(self):
        """Convenience function works correctly."""
        result = extract_entities("Test /path/to/file")
        
        assert isinstance(result, EntityExtractionResult)
        assert result.has_entity("FILE_PATH")


class TestEntityExtractionResult:
    """Tests for EntityExtractionResult class."""
    
    def test_to_dict(self):
        """Result can be converted to dictionary."""
        result = EntityExtractionResult(
            original_text="test",
            normalized_text="test",
            entities=[
                ExtractedEntity(
                    text="test",
                    label="TEST",
                    start=0,
                    end=4,
                )
            ],
            tokens=["test"],
            noun_chunks=[],
        )
        
        d = result.to_dict()
        
        assert d["original_text"] == "test"
        assert len(d["entities"]) == 1
        assert d["entities"][0]["label"] == "TEST"
    
    def test_get_entity_texts_by_label(self):
        """Entity texts can be retrieved by label."""
        result = EntityExtractionResult(
            original_text="test",
            normalized_text="test",
            entities=[
                ExtractedEntity(text="path1", label="FILE_PATH", start=0, end=5),
                ExtractedEntity(text="path2", label="FILE_PATH", start=6, end=11),
                ExtractedEntity(text="url", label="URL", start=12, end=15),
            ],
            tokens=[],
            noun_chunks=[],
        )
        
        paths = result.get_entity_texts_by_label("FILE_PATH")
        
        assert len(paths) == 2
        assert "path1" in paths
        assert "path2" in paths
