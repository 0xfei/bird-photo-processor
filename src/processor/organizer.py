"""File organization utilities - organize by species/date."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from send2trash import send2trash

from src.utils.models import ImageInfo


class FileOrganizer:
    """Organize images by species and date."""

    def __init__(
        self,
        output_dir: Path,
        by_species: bool = True,
        by_date: bool = True,
        keep_original: bool = True,
        use_trash: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.by_species = by_species
        self.by_date = by_date
        self.keep_original = keep_original
        self.use_trash = use_trash

    def organize(self, images: list[ImageInfo]) -> list[tuple[Path, Path]]:
        """Organize images into directories."""
        moves = []

        for img in images:
            dest = self._get_destination(img)
            if dest:
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    if dest.exists():
                        dest = self._get_unique_path(dest)

                    if self.keep_original:
                        shutil.copy2(img.path, dest)
                    else:
                        shutil.move(str(img.path), dest)

                    moves.append((img.path, dest))
                    logger.debug(f"Moved {img.path} -> {dest}")

                except Exception as e:
                    logger.error(f"Failed to move {img.path}: {e}")

        return moves

    def _get_destination(self, img: ImageInfo) -> Optional[Path]:
        """Get destination path for an image."""
        parts = []

        # Date-based folder
        if self.by_date:
            date_str = datetime.fromtimestamp(img.created_time).strftime("%Y-%m-%d")
            parts.append(date_str)

        # Species-based folder
        if self.by_species and img.bird_species:
            species_name = self._sanitize_filename(img.bird_species_cn or img.bird_species)
            parts.append(species_name)
        elif self.by_species:
            parts.append("未识别")

        if not parts:
            return None

        folder = self.output_dir / Path(*parts)
        filename = self._sanitize_filename(img.filename)

        return folder / filename

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for filesystem."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")

        # Limit filename length
        if len(name) > 200:
            ext = Path(name).suffix
            name = name[: 200 - len(ext)] + ext

        return name

    def _get_unique_path(self, path: Path) -> Path:
        """Get unique path by adding number suffix."""
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1

        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    def delete_files(self, images: list[ImageInfo]) -> list[Path]:
        """Delete image files."""
        deleted = []

        for img in images:
            try:
                if self.use_trash:
                    send2trash(str(img.path))
                else:
                    img.path.unlink()

                deleted.append(img.path)
                logger.info(f"Deleted: {img.path}")

            except Exception as e:
                logger.error(f"Failed to delete {img.path}: {e}")

        return deleted


class FilterEngine:
    """Filter engine for pre-scoring and filtering."""

    def __init__(
        self,
        min_quality: float = 40.0,
        min_species_images: int = 1,
        keep_best_per_species: bool = True,
    ):
        self.min_quality = min_quality
        self.min_species_images = min_species_images
        self.keep_best_per_species = keep_best_per_species

    def filter(self, images: list[ImageInfo]) -> list[ImageInfo]:
        """Filter images based on quality and species rules."""
        result = []

        # Group by species
        species_groups: dict[str, list[ImageInfo]] = {}
        unclassified = []

        for img in images:
            if img.bird_species:
                species = img.bird_species
                if species not in species_groups:
                    species_groups[species] = []
                species_groups[species].append(img)
            else:
                unclassified.append(img)

        # For each species, keep at least min_species_images
        for species, species_imgs in species_groups.items():
            # Sort by quality score (lower is better for BRISQUE)
            sorted_imgs = sorted(species_imgs, key=lambda x: x.quality_score or float("inf"))

            # Always keep at least min_species_images
            keep_count = max(self.min_species_images, len(sorted_imgs))

            # But only keep those meeting quality threshold
            acceptable = [
                img for img in sorted_imgs if (img.quality_score or 100) <= self.min_quality
            ]

            if acceptable:
                # Keep acceptable quality images
                result.extend(acceptable)
            else:
                # No acceptable quality, keep best one anyway
                result.append(sorted_imgs[0])

        # Add unclassified images that meet quality threshold
        for img in unclassified:
            if (img.quality_score or 100) <= self.min_quality:
                result.append(img)

        return result

    def get_to_delete(
        self, all_images: list[ImageInfo], keep_images: list[ImageInfo]
    ) -> list[ImageInfo]:
        """Get images to delete based on filter results."""
        keep_paths = {img.path for img in keep_images}
        return [img for img in all_images if img.path not in keep_paths]

    def mark_filtered(self, images: list[ImageInfo], to_keep: list[ImageInfo]):
        """Mark images with filtered status."""
        keep_paths = {img.path for img in to_keep}
        for img in images:
            if img.path not in keep_paths:
                img.filtered_out = True
