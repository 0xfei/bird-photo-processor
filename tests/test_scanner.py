"""Tests for scanner module."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.scanner.directory import ImageScanner, get_supported_formats, is_supported_format


@pytest.fixture
def temp_images(tmp_path):
    """Create temporary test images."""
    images = []

    # Create test images
    for i in range(5):
        img = Image.new("RGB", (100, 100), color=(i * 50, 100, 150))
        path = tmp_path / f"test_{i}.jpg"
        img.save(path)
        images.append(path)

    # Create a non-image file
    (tmp_path / "readme.txt").write_text("not an image")

    return tmp_path, images


def test_scan_directory(temp_images):
    """Test scanning a directory."""
    tmp_path, expected_images = temp_images

    scanner = ImageScanner()
    results = scanner.scan(tmp_path)

    assert len(results) == 5
    assert all(r.path.suffix.lower() == ".jpg" for r in results)


def test_iter_images(temp_images):
    """Test iterating over images."""
    tmp_path, expected_images = temp_images

    scanner = ImageScanner()
    count = 0
    for img in scanner.iter_images(tmp_path):
        count += 1
        assert img.filename.startswith("test_")
        assert img.size > 0

    assert count == 5


def test_is_supported_format():
    """Test format detection."""
    assert is_supported_format(Path("image.jpg"))
    assert is_supported_format(Path("image.JPEG"))
    assert is_supported_format(Path("image.png"))
    assert is_supported_format(Path("image.heic"))
    assert not is_supported_format(Path("document.txt"))
    assert not is_supported_format(Path("video.mp4"))


def test_get_supported_formats():
    """Test getting supported formats."""
    formats = get_supported_formats()
    assert ".jpg" in formats
    assert ".jpeg" in formats
    assert ".png" in formats
    assert ".heic" in formats


def test_count_images(temp_images):
    """Test counting images."""
    tmp_path, _ = temp_images

    scanner = ImageScanner()
    count = scanner.count_images(tmp_path)

    assert count == 5
