"""Tests for dedup module."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.processor.dedup import Deduplicator
from src.utils.models import ImageInfo


@pytest.fixture
def temp_duplicates(tmp_path):
    """Create temporary duplicate images."""
    images = []

    # Create 3 similar images
    for i in range(3):
        img = Image.new("RGB", (100, 100), color=(100, 100, 100))
        path = tmp_path / f"dup_{i}.jpg"
        img.save(path)

        info = ImageInfo(path=path, filename=path.name, size=path.stat().st_size)
        images.append(info)

    # Create a different image
    img = Image.new("RGB", (100, 100), color=(200, 100, 100))
    path = tmp_path / "unique.jpg"
    img.save(path)

    info = ImageInfo(path=path, filename=path.name, size=path.stat().st_size)
    images.append(info)

    return tmp_path, images


def test_compute_hash(temp_duplicates):
    """Test hash computation."""
    _, images = temp_duplicates

    dedup = Deduplicator()
    hash1 = dedup.compute_hash(images[0])

    assert hash1 is not None
    assert len(hash1) > 0


def test_find_duplicates(temp_duplicates):
    """Test finding duplicate images."""
    _, images = temp_duplicates

    dedup = Deduplicator(threshold=0.90)
    groups = dedup.find_duplicates(images)

    # Should find groups (exact same images are duplicates)
    assert len(groups) >= 1


def test_get_images_to_keep(temp_duplicates):
    """Test getting images to keep."""
    _, images = temp_duplicates

    dedup = Deduplicator(threshold=0.90, keep_best=1, keep_backup=True)
    dedup.find_duplicates(images)

    to_keep = dedup.get_images_to_keep(images)

    # Should keep at least 1 (the best one)
    assert len(to_keep) >= 1


def test_get_images_to_delete(temp_duplicates):
    """Test getting images to delete."""
    _, images = temp_duplicates

    dedup = Deduplicator(threshold=0.90)
    dedup.find_duplicates(images)

    to_delete = dedup.get_images_to_delete(images)

    # Should have at least some duplicates to delete
    assert len(to_delete) >= 1


def test_dedup_with_quality(temp_duplicates):
    """Test deduplication with quality scores."""
    _, images = temp_duplicates

    # Set quality scores
    images[0].quality_score = 30.0
    images[1].quality_score = 50.0
    images[2].quality_score = 40.0

    dedup = Deduplicator(threshold=0.90, keep_best=1, keep_backup=True)
    dedup.find_duplicates(images)

    best = dedup.get_images_to_keep(images)[0]

    # Should keep the best quality (lowest BRISQUE score)
    assert best.quality_score == 30.0
