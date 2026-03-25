"""Data models for GUI."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class PhotoItem:
    """Photo item for GUI display."""

    path: Path
    filename: str
    size: int = 0
    created_time: float = 0.0

    # Quality scores
    quality_score: Optional[float] = None
    clarity_score: Optional[float] = None
    focus_score: Optional[float] = None
    sharpness_score: Optional[float] = None

    # Recognition
    bird_species: Optional[str] = None
    bird_species_cn: Optional[str] = None
    bird_confidence: Optional[float] = None

    # Status
    is_duplicate: bool = False
    duplicate_group: Optional[str] = None
    quality_level: str = "unknown"

    # GUI state
    selected: bool = False
    locked: bool = False
    manual_score: Optional[int] = None

    # For Qt model
    index: int = 0

    def __post_init__(self):
        if isinstance(self.path, str):
            self.path = Path(self.path)

    @property
    def effective_score(self) -> Optional[float]:
        """Get effective quality score (manual if set, otherwise automatic)."""
        if self.manual_score is not None:
            return float(self.manual_score)
        return self.quality_score

    @property
    def status_text(self) -> str:
        """Get status text."""
        if self.locked:
            return "🔒 锁定"
        if self.quality_level == "low":
            return "⚠️ 低质量"
        if self.is_duplicate:
            return f"🔄 重复({self.duplicate_group})"
        if self.bird_species:
            return f"🐦 {self.bird_species_cn or self.bird_species}"
        return "✓"

    @property
    def is_auto_selected(self) -> bool:
        """Check if this photo should be auto-selected for deletion."""
        if self.locked:
            return False
        return self.is_duplicate or self.quality_level == "low"

    def get_info_dict(self) -> dict:
        """Get info dictionary for display."""
        return {
            "filename": self.filename,
            "quality": f"{self.effective_score:.1f}" if self.effective_score else "N/A",
            "clarity": f"{self.clarity_score:.1f}" if self.clarity_score else "N/A",
            "focus": f"{self.focus_score:.1f}" if self.focus_score else "N/A",
            "sharpness": f"{self.sharpness_score:.1f}" if self.sharpness_score else "N/A",
            "species": self.bird_species_cn or self.bird_species or "-",
            "confidence": f"{self.bird_confidence:.0%}" if self.bird_confidence else "-",
            "status": self.status_text,
        }


class PhotoModel(QObject):
    """Photo list model for Qt."""

    photos_changed = pyqtSignal()
    selection_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._photos: list[PhotoItem] = []
        self._current_index: int = -1

    @property
    def photos(self) -> list[PhotoItem]:
        return self._photos

    def set_photos(self, photos: list[PhotoItem]):
        """Set photos list."""
        self._photos = photos
        for i, photo in enumerate(self._photos):
            photo.index = i
            # Auto-select duplicates and low quality for deletion
            photo.selected = photo.is_auto_selected
        self.photos_changed.emit()

    def add_photo(self, photo: PhotoItem):
        """Add a photo."""
        photo.index = len(self._photos)
        photo.selected = photo.is_auto_selected
        self._photos.append(photo)
        self.photos_changed.emit()

    def remove_photo(self, index: int):
        """Remove a photo by index."""
        if 0 <= index < len(self._photos):
            self._photos.pop(index)
            # Reindex
            for i, photo in enumerate(self._photos):
                photo.index = i
            self.photos_changed.emit()

    def get_photo(self, index: int) -> Optional[PhotoItem]:
        """Get photo by index."""
        if 0 <= index < len(self._photos):
            return self._photos[index]
        return None

    def set_current_index(self, index: int):
        """Set current selected index."""
        self._current_index = index
        self.selection_changed.emit()

    def get_current_photo(self) -> Optional[PhotoItem]:
        """Get currently selected photo."""
        return self.get_photo(self._current_index)

    def get_selected_photos(self) -> list[PhotoItem]:
        """Get all selected photos."""
        return [p for p in self._photos if p.selected]

    def get_selected_count(self) -> int:
        """Get count of selected photos."""
        return sum(1 for p in self._photos if p.selected)

    def get_locked_count(self) -> int:
        """Get count of locked photos."""
        return sum(1 for p in self._photos if p.locked)

    def select_all(self):
        """Select all photos."""
        for photo in self._photos:
            if not photo.locked:
                photo.selected = True
        self.selection_changed.emit()

    def deselect_all(self):
        """Deselect all photos."""
        for photo in self._photos:
            photo.selected = False
        self.selection_changed.emit()

    def select_duplicates(self):
        """Select all duplicate photos."""
        for photo in self._photos:
            if photo.is_duplicate and not photo.locked:
                photo.selected = True
        self.selection_changed.emit()

    def select_low_quality(self):
        """Select all low quality photos."""
        for photo in self._photos:
            if photo.quality_level == "low" and not photo.locked:
                photo.selected = True
        self.selection_changed.emit()

    def filter_by_quality(self, threshold: float) -> list[PhotoItem]:
        """Filter photos by quality threshold."""
        return [p for p in self._photos if (p.effective_score or 100) <= threshold]

    def filter_by_species(self, species: str) -> list[PhotoItem]:
        """Filter photos by species."""
        if not species:
            return self._photos
        return [
            p
            for p in self._photos
            if species.lower() in (p.bird_species or "").lower()
            or species.lower() in (p.bird_species_cn or "").lower()
        ]
