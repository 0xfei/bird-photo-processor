"""Data models for bird-photo-processor."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ImageInfo:
    """Image information and processing results."""

    path: Path
    filename: str
    size: int = 0
    created_time: float = 0.0
    modified_time: float = 0.0
    width: int = 0
    height: int = 0
    format: str = ""

    # Processing results
    hash: Optional[str] = None
    quality_score: Optional[float] = None
    bird_species: Optional[str] = None
    bird_species_cn: Optional[str] = None
    bird_confidence: Optional[float] = None

    # Metadata
    is_duplicate: bool = False
    duplicate_group: Optional[str] = None
    quality_level: Optional[str] = None  # high/medium/low

    # Classification
    family: Optional[str] = None  # 科
    genus: Optional[str] = None  # 属

    # Filter status
    filtered_out: bool = False

    def __post_init__(self):
        if isinstance(self.path, str):
            self.path = Path(self.path)

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass
class DuplicateGroup:
    """A group of duplicate images."""

    group_id: str
    images: list[ImageInfo] = field(default_factory=list)

    @property
    def best_image(self) -> Optional[ImageInfo]:
        """Get the best quality image from the group."""
        valid = [img for img in self.images if img.quality_score is not None]
        if not valid:
            return self.images[0] if self.images else None
        return min(valid, key=lambda x: x.quality_score or float("inf"))

    @property
    def backup_image(self) -> Optional[ImageInfo]:
        """Get the backup image (second best)."""
        valid = [img for img in self.images if img.quality_score is not None]
        if len(valid) >= 2:
            sorted_valid = sorted(valid, key=lambda x: x.quality_score or float("inf"))
            return sorted_valid[1]
        return None


@dataclass
class ProcessingResult:
    """Result of processing operation."""

    total_images: int = 0
    duplicate_groups: list[DuplicateGroup] = field(default_factory=list)
    low_quality_images: list[ImageInfo] = field(default_factory=list)
    recognized_images: list[ImageInfo] = field(default_factory=list)
    unprocessed_images: list[ImageInfo] = field(default_factory=list)
    deleted_images: list[str] = field(default_factory=list)
    moved_images: list[tuple[str, str]] = field(default_factory=list)
    duration: float = 0.0

    @property
    def total_duplicates(self) -> int:
        return sum(len(g.images) - 1 for g in self.duplicate_groups)

    @property
    def species_count(self) -> int:
        species = set()
        for img in self.recognized_images:
            if img.bird_species:
                species.add(img.bird_species)
        return len(species)

    def get_species_stats(self) -> dict[str, int]:
        """Get species statistics."""
        stats: dict[str, int] = {}
        for img in self.recognized_images:
            if img.bird_species:
                name = img.bird_species_cn or img.bird_species
                stats[name] = stats.get(name, 0) + 1
        return dict(sorted(stats.items(), key=lambda x: -x[1]))
