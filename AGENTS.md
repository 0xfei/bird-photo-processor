# Agent Coding Guidelines

This document provides guidelines for AI agents working on the bird-photo-processor project.

## Project Overview

bird-photo-processor is a CLI tool for bird photographers to deduplicate, assess quality, and recognize bird species in their photo collections.

- **Language**: Python 3.11+
- **Framework**: Click for CLI
- **Testing**: pytest

## Build/Test Commands

### Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[all]"

# Optional: download Birder model
python -m birder.tools download-model mvit_v2_t
```

### Running Tests

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_scanner.py

# Run tests matching a pattern
pytest -k "dedup"

# Run with coverage
pytest --cov=src --cov-report=html
```

### Linting & Formatting

```bash
# Check code style
ruff check src/

# Format code
ruff format src/

# Type checking
mypy src/
```

### Development

```bash
# Run CLI
python -m src.cli scan /path/to/photos

# Run with debug output
python -m src.cli scan /path/to/photos -v
```

## Code Style Guidelines

### General Conventions

- **File names**: snake_case (`image_scanner.py`, `dedup_engine.py`)
- **Class names**: PascalCase (`ImageScanner`, `Deduplicator`)
- **Function names**: snake_case (`find_duplicates`, `assess_quality`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_SIMILARITY_THRESHOLD`)

### Python Specific

- Use Python 3.11+ features (dataclasses, pattern matching)
- Use `dataclasses` for data structures
- Use `typing` for type hints
- Use `pathlib.Path` for file paths
- Use `loguru` for logging

Example:
```python
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class ImageInfo:
    path: Path
    filename: str
    size: int
    quality_score: Optional[float] = None
```

### CLI Design

- Use Click for CLI framework
- Use subcommands for different operations
- Support `--dry-run` flag for all file-modifying operations
- Use `--verbose` flag for detailed output

### Error Handling

- Use custom exceptions for domain-specific errors
- Log warnings for non-critical issues
- Provide helpful error messages in Chinese

### Imports

Order imports in this sequence:
1. Standard library
2. Third-party libraries
3. Local application imports

```python
# Good
from src.scanner import ImageScanner
from src.processor.dedup import Deduplicator

# Avoid
from ..scanner import ImageScanner
```

### Testing

- Use pytest as test framework
- Place tests in `tests/` directory
- Use descriptive test names
- Use fixtures for common setup

Example:
```python
import pytest
from pathlib import Path
from src.scanner import ImageScanner

@pytest.fixture
def sample_images(tmp_path):
    # Create sample images for testing
    ...

def test_scan_directory(sample_images):
    scanner = ImageScanner()
    results = scanner.scan(sample_images)
    assert len(results) > 0
```

## Project Structure

```
bird-photo-processor/
├── src/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── inaturalist.py # iNaturalist API client
│   ├── scanner/
│   │   ├── __init__.py
│   │   └── directory.py   # Directory scanning
│   ├── processor/
│   │   ├── __init__.py
│   │   ├── dedup.py       # Deduplication engine
│   │   ├── quality.py     # Quality assessment
│   │   ├── recognizer.py  # Bird recognition
│   │   ├── organizer.py   # File organization
│   │   └── engine.py      # Processing engine
│   └── utils/
│       ├── __init__.py
│       ├── config.py      # Configuration management
│       └── models.py      # Data models
├── tests/
│   ├── __init__.py
│   ├── test_scanner.py
│   └── test_dedup.py
├── pyproject.toml
├── build.sh
├── run.sh
└── README.md
```

## Dependencies

### Core Dependencies

- `click` - CLI framework
- `Pillow` - Image processing
- `imagehash` - Perceptual hashing
- `loguru` - Logging
- `tomli-w` - TOML config writing

### Optional Dependencies

- `birder` - Local bird recognition
- `brisque` - Quality assessment
- `httpx` - HTTP client for API calls

### Development Dependencies

- `pytest` - Testing
- `ruff` - Linting
- `mypy` - Type checking

## Key Files

- `src/cli.py` - Main CLI entry point
- `src/scanner/directory.py` - Directory scanning logic
- `src/processor/dedup.py` - Deduplication engine
- `src/processor/quality.py` - Quality assessment
- `src/processor/recognizer.py` - Bird recognition
- `src/processor/organizer.py` - File organization
- `src/utils/config.py` - Configuration management
- `pyproject.toml` - Project configuration
