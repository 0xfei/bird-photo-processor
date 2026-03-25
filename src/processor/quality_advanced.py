"""Advanced quality assessment with focus, sharpness, and clarity scoring."""

import math
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from loguru import logger
from PIL import Image

from src.utils.models import ImageInfo


class AdvancedQualityAssessor:
    """Advanced image quality assessor with multiple metrics.

    Scores:
    - Clarity (清晰度): Overall image clarity based on multiple metrics
    - Focus (对焦): How well the image is focused
    - Edge Sharpness (边缘锐利度): Edge sharpness measurement

    Each score is 0-100, higher is better.
    """

    def __init__(self, threshold: float = 40.0):
        self.threshold = threshold
        self._cv2_available = self._check_cv2()

    def _check_cv2(self) -> bool:
        """Check if OpenCV is available."""
        try:
            import cv2

            return True
        except ImportError:
            logger.warning("OpenCV not available, using basic quality assessment")
            return False

    def assess(self, image_info: ImageInfo) -> ImageInfo:
        """Assess quality with three dimensions."""
        if not self._cv2_available:
            return self._basic_assess(image_info)

        try:
            # Read image with OpenCV
            img = cv2.imread(str(image_info.path))
            if img is None:
                raise ValueError(f"Cannot read image: {image_info.path}")

            # Convert to grayscale for analysis
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Calculate three scores
            clarity_score = self._calculate_clarity(gray, img)
            focus_score = self._calculate_focus(gray)
            sharpness_score = self._calculate_edge_sharpness(gray)

            # Overall quality score (weighted average)
            # Clarity 50%, Focus 30%, Sharpness 20%
            overall_score = clarity_score * 0.5 + focus_score * 0.3 + sharpness_score * 0.2

            # Store scores
            image_info.clarity_score = clarity_score
            image_info.focus_score = focus_score
            image_info.sharpness_score = sharpness_score
            image_info.quality_score = overall_score

            # Determine quality level
            image_info.quality_level = self._get_quality_level(overall_score)

        except Exception as e:
            logger.warning(f"Failed to assess quality for {image_info.path}: {e}")
            image_info.quality_score = None
            image_info.quality_level = "unknown"

        return image_info

    def _calculate_clarity(self, gray: np.ndarray, color_img: np.ndarray) -> float:
        """Calculate image clarity (综合清晰度).

        Uses multiple metrics:
        - Laplacian variance (blur detection)
        - Sobel gradient magnitude
        - Contrast (RMS)
        """
        # 1. Laplacian variance (measures overall blur)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = laplacian.var()

        # 2. Sobel gradient (measures edge definition)
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sobel_mag = np.sqrt(sobelx**2 + sobely**2)
        sobel_mean = sobel_mag.mean()

        # 3. Contrast (RMS)
        contrast = gray.std()

        # Normalize and combine
        # Laplacian: higher is sharper (typically 100-2000)
        laplacian_score = min(laplacian_var / 10, 100)

        # Sobel: higher is clearer (typically 20-100)
        sobel_score = min(sobel_mean / 0.5, 100)

        # Contrast: higher is better (typically 10-80)
        contrast_score = min(contrast / 0.5, 100)

        # Weighted combination
        clarity = laplacian_score * 0.5 + sobel_score * 0.3 + contrast_score * 0.2

        return min(clarity, 100)

    def _calculate_focus(self, gray: np.ndarray) -> float:
        """Calculate focus score (对焦准确度).

        Uses Brenner gradient and frequency analysis to detect
        if the image is in focus.
        """
        # Method 1: Brenner gradient
        h, w = gray.shape
        brenner = 0
        for i in range(h):
            for j in range(w - 2):
                diff = int(gray[i, j + 2]) - int(gray[i, j])
                brenner += diff**2
        brenner /= h * (w - 2)

        # Method 2: Variance of Laplacian (MLAP - Modified Laplacian)
        ml = cv2.Laplacian(gray, cv2.CV_64F)
        ml_var = ml.var()

        # Method 3: High frequency content (FFT)
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)

        # High frequency ratio
        h, w = gray.shape
        cy, cx = h // 2, w // 2
        r = min(h, w) // 4

        # High freq region
        mask = np.ones_like(gray, dtype=float)
        cv2.circle(mask, (cx, cy), r, 0, -1)

        high_freq = magnitude[mask == 0].sum()
        total_freq = magnitude.sum()
        hfreq_ratio = high_freq / (total_freq + 1e-10)

        # Normalize scores
        brenner_score = min(brenner / 100, 100)  # typically 0-5000
        ml_score = min(ml_var / 50, 100)  # typically 0-2000
        hfreq_score = min(hfreq_ratio * 500, 100)  # typically 0-0.2

        # Focus is primarily determined by high frequency content
        # A well-focused image has more high frequency detail
        focus = brenner_score * 0.3 + ml_score * 0.4 + hfreq_score * 0.3

        return min(focus, 100)

    def _calculate_edge_sharpness(self, gray: np.ndarray) -> float:
        """Calculate edge sharpness (边缘锐利度).

        Measures how sharp the edges are in the image.
        Uses Canny edge detection and calculates edge strength.
        """
        # Apply Canny edge detection
        edges = cv2.Canny(gray, 50, 150)
        edge_density = edges.sum() / (255 * edges.size)

        # Calculate edge strength using Sobel
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)

        # Edge magnitude
        edge_mag = np.sqrt(sobelx**2 + sobely**2)

        # Edge statistics
        edge_mean = edge_mag.mean()
        edge_std = edge_mag.std()

        # 锐利边缘占比 (edges with strong magnitude)
        strong_edges = (edge_mag > edge_mean).sum() / edge_mag.size

        # Normalize scores
        density_score = min(edge_density * 500, 100)  # typically 0-0.2
        mean_score = min(edge_mean / 2, 100)  # typically 0-50
        strong_score = min(strong_edges * 200, 100)  # typically 0-0.5

        # Edge sharpness is mainly determined by edge strength
        sharpness = density_score * 0.2 + mean_score * 0.4 + strong_score * 0.4

        return min(sharpness, 100)

    def _basic_assess(self, image_info: ImageInfo) -> ImageInfo:
        """Fallback basic assessment without OpenCV."""
        try:
            from PIL import Image
            import numpy as np

            img = Image.open(image_info.path).convert("L")
            arr = np.array(img)

            # Basic Laplacian variance
            laplacian = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]])
            result = np.convolve(arr.flatten(), laplacian.flatten(), mode="same")
            variance = np.var(result)

            score = 100 - min(variance / 10, 100)

            image_info.quality_score = score
            image_info.clarity_score = score
            image_info.focus_score = score
            image_info.sharpness_score = score
            image_info.quality_level = self._get_quality_level(score)

        except Exception:
            image_info.quality_score = 50.0
            image_info.quality_level = "unknown"

        return image_info

    def _get_quality_level(self, score: float) -> str:
        """Determine quality level from overall score."""
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

    def get_detailed_report(self, image_info: ImageInfo) -> str:
        """Get detailed quality report for an image."""
        if image_info.quality_score is None:
            return "无法评估"

        lines = [
            f"综合质量: {image_info.quality_score:.1f}/100 ({image_info.quality_level})",
            f"清晰度: {image_info.clarity_score:.1f}/100",
            f"对焦度: {image_info.focus_score:.1f}/100",
            f"边缘锐利度: {image_info.sharpness_score:.1f}/100",
        ]

        # Add warnings
        if image_info.clarity_score and image_info.clarity_score < 40:
            lines.append("⚠️ 清晰度较低")
        if image_info.focus_score and image_info.focus_score < 40:
            lines.append("⚠️ 对焦可能不准确")
        if image_info.sharpness_score and image_info.sharpness_score < 40:
            lines.append("⚠️ 边缘较模糊")

        return "\n".join(lines)


def calculate_blur_metric(image_path: str) -> Tuple[float, float]:
    """Standalone function to calculate blur metric.

    Returns:
        (laplacian_variance, focus_measure)
    """
    try:
        import cv2

        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = laplacian.var()

        # Modified Laplacian
        ml = cv2.Laplacian(gray, cv2.CV_64F)
        ml_var = ml.var()

        return lap_var, ml_var

    except Exception as e:
        logger.error(f"Failed to calculate blur: {e}")
        return 0.0, 0.0
