"""Image scanner for bird-photo-processor."""

import os
from pathlib import Path
from typing import Iterator, Optional

from loguru import logger

from src.utils.models import ImageInfo

# Supported image formats
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".heic",
    ".heif",
    ".cr2",
    ".nef",
    ".arw",
    ".orf",
    ".rw2",
    ".dng",
}


class ImageScanner:
    """Scanner for finding images in directories."""

    def __init__(self, recursive: bool = True):
        self.recursive = recursive

    def scan(self, path: Path) -> list[ImageInfo]:
        """Scan directory for images."""
        images = []
        for img in self.iter_images(path):
            images.append(img)
        return images

    def iter_images(self, path: Path) -> Iterator[ImageInfo]:
        """Iterate over images in directory."""
        path = Path(path)

        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            return

        if path.is_file():
            if self._is_image(path):
                yield self._create_image_info(path)
            return

        # Directory scanning
        if self.recursive:
            for root, _, files in os.walk(path):
                for filename in files:
                    filepath = Path(root) / filename
                    if self._is_image(filepath):
                        yield self._create_image_info(filepath)
        else:
            for filepath in path.iterdir():
                if filepath.is_file() and self._is_image(filepath):
                    yield self._create_image_info(filepath)

    def _is_image(self, path: Path) -> bool:
        """Check if file is an image based on extension."""
        return path.suffix.lower() in IMAGE_EXTENSIONS

    def _create_image_info(self, path: Path) -> ImageInfo:
        """Create ImageInfo from file path."""
        stat = path.stat()

        # Determine format from extension
        fmt = path.suffix.lower().lstrip(".")

        return ImageInfo(
            path=path,
            filename=path.name,
            size=stat.st_size,
            created_time=stat.st_ctime,
            modified_time=stat.st_mtime,
            format=fmt,
        )

    def count_images(self, path: Path) -> int:
        """Count images without loading them all into memory."""
        count = 0
        for _ in self.iter_images(path):
            count += 1
        return count


def get_supported_formats() -> set[str]:
    """Get supported image formats."""
    return IMAGE_EXTENSIONS.copy()


def is_supported_format(path: Path) -> bool:
    """Check if file format is supported."""
    return path.suffix.lower() in IMAGE_EXTENSIONS
