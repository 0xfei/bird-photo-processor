"""Quality assessment using BRISQUE algorithm."""

from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger
from PIL import Image

from src.utils.models import ImageInfo


class QualityAssessor:
    """Image quality assessor using BRISQUE algorithm."""

    def __init__(self, threshold: float = 40.0):
        self.threshold = threshold
        self._brisque = None
        self._load_brisque()

    def _load_brisque(self):
        """Load BRISQUE library."""
        try:
            from brisque import BRISQUE

            self._brisque = BRISQUE(url=False)
            logger.info("BRISQUE loaded successfully")
        except ImportError:
            logger.warning("BRISQUE not available, using fallback quality assessment")
            self._brisque = None

    def assess(self, image_info: ImageInfo) -> ImageInfo:
        """Assess quality of a single image."""
        try:
            if self._brisque:
                score = self._brisque.score(str(image_info.path))
                image_info.quality_score = float(score)
            else:
                # Fallback: use basic metrics
                score = self._fallback_assess(image_info.path)
                image_info.quality_score = score

            # Determine quality level
            image_info.quality_level = self._get_quality_level(image_info.quality_score)

        except Exception as e:
            logger.warning(f"Failed to assess quality for {image_info.path}: {e}")
            image_info.quality_score = None
            image_info.quality_level = "unknown"

        return image_info

    def _fallback_assess(self, path: Path) -> float:
        """Fallback quality assessment using Laplacian variance."""
        try:
            img = Image.open(path).convert("L")
            img_array = np.array(img)

            # Calculate Laplacian variance (sharpness)
            laplacian = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]])
            result = np.convolve(img_array.flatten(), laplacian.flatten(), mode="same")
            variance = np.var(result)

            # Convert to BRISQUE-like score (0-100, lower is better)
            # High sharpness = low BRISQUE score
            score = 100 - min(variance / 10, 100)
            return score

        except Exception:
            return 50.0  # Default middle score

    def _get_quality_level(self, score: Optional[float]) -> str:
        """Determine quality level from score."""
        if score is None:
            return "unknown"

        if score < self.threshold:
            return "low"
        elif score < 60:
            return "medium"
        else:
            return "high"

    def assess_batch(self, images: list[ImageInfo]) -> list[ImageInfo]:
        """Assess quality for multiple images."""
        for img in images:
            self.assess(img)
        return images

    def get_low_quality(self, images: list[ImageInfo]) -> list[ImageInfo]:
        """Get all low quality images."""
        return [img for img in images if img.quality_level == "low"]

    def get_acceptable_quality(self, images: list[ImageInfo]) -> list[ImageInfo]:
        """Get images with acceptable quality (not low)."""
        return [img for img in images if img.quality_level in ("medium", "high", None)]
