"""Image deduplication using perceptual hashing."""

import hashlib
import json
from pathlib import Path
from typing import Optional

import imagehash
from loguru import logger
from PIL import Image

from src.utils.models import ImageInfo, DuplicateGroup


class Deduplicator:
    """Image deduplicator using perceptual hashing."""

    def __init__(
        self,
        threshold: float = 0.90,
        keep_best: int = 1,
        keep_backup: bool = True,
        hash_algorithm: str = "phash",
        species_aware: bool = True,
        min_time_interval: int = 300,
        mode: str = "group",
        group_output_dir: str = "duplicates",
    ):
        self.threshold = threshold
        self.keep_best = keep_best
        self.keep_backup = keep_backup
        self.hash_algorithm = hash_algorithm.lower()
        self.species_aware = species_aware
        self.min_time_interval = min_time_interval
        self.mode = mode  # delete / group / none
        self.group_output_dir = group_output_dir
        self._hash_cache: dict[str, str] = {}

    def compute_hash(self, image_info: ImageInfo) -> str:
        """Compute perceptual hash for an image."""
        path_key = str(image_info.path)
        if path_key in self._hash_cache:
            return self._hash_cache[path_key]

        try:
            img = Image.open(image_info.path)

            # Use configured hash algorithm
            if self.hash_algorithm == "phash":
                hash_obj = imagehash.phash(img)
            elif self.hash_algorithm == "dhash":
                hash_obj = imagehash.dhash(img)
            elif self.hash_algorithm == "ahash":
                hash_obj = imagehash.average_hash(img)
            elif self.hash_algorithm == "whash":
                hash_obj = imagehash.whash(img)
            else:
                hash_obj = imagehash.phash(img)

            hash_str = str(hash_obj)

            self._hash_cache[path_key] = hash_str
            image_info.hash = hash_str

            return hash_str

        except Exception as e:
            logger.warning(f"Failed to compute hash for {image_info.path}: {e}")
            # Fallback to MD5
            with open(image_info.path, "rb") as f:
                hash_str = hashlib.md5(f.read()).hexdigest()
            image_info.hash = hash_str
            return hash_str

    def compute_hashes(self, images: list[ImageInfo]) -> list[ImageInfo]:
        """Compute hashes for multiple images."""
        for img in images:
            self.compute_hash(img)
        return images

    def _calculate_similarity(self, hash1: str, hash2: str) -> float:
        """Calculate similarity between two hashes (0-1)."""
        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            # Similarity = 1 - (hamming_distance / hash_length)
            return 1 - (h1 - h2) / len(h1)
        except Exception:
            # Fallback to exact match
            return 1.0 if hash1 == hash2 else 0.0

    def _is_same_species(self, img1: ImageInfo, img2: ImageInfo) -> bool:
        """Check if two images have the same bird species."""
        if not self.species_aware:
            return True  # Treat all as same species if disabled

        # If either doesn't have species info, assume same (conservative)
        if not img1.bird_species or not img2.bird_species:
            return True

        return img1.bird_species == img2.bird_species

    def _get_time_penalty(self, img1: ImageInfo, img2: ImageInfo) -> float:
        """Calculate time-based penalty for duplicate detection.

        Short burst photos are more likely to be duplicates (higher penalty).
        Long interval photos might be different sessions (lower penalty).

        Returns:
            Penalty value (0-1): higher = more likely duplicate
        """
        time_diff = abs(img1.created_time - img2.created_time)

        # No penalty for very close photos (likely burst)
        if time_diff <= 10:  # within 10 seconds
            return 1.0

        # Gradual penalty reduction for time intervals
        # After max_time_interval, penalty becomes 0 (different sessions)
        if time_diff >= self.min_time_interval:
            return 0.0

        # Linear interpolation
        normalized = (self.min_time_interval - time_diff) / self.min_time_interval
        return normalized

    def _calculate_effective_similarity(
        self, img1: ImageInfo, img2: ImageInfo, base_similarity: float
    ) -> float:
        """Calculate effective similarity with time weighting.

        Photos taken in quick succession (burst) are more likely to be duplicates.
        Photos taken at different times are less likely to be true duplicates.
        """
        time_penalty = self._get_time_penalty(img1, img2)

        # Effective similarity = base + time bonus
        # Quick burst photos get boosted similarity (more likely duplicates)
        # Long interval photos get reduced similarity
        effective = base_similarity * time_penalty

        # Also apply species check: different species = not duplicate
        if self.species_aware:
            if not self._is_same_species(img1, img2):
                return 0.0  # Different species, not a duplicate

        return effective

    def find_duplicates(self, images: list[ImageInfo]) -> list[DuplicateGroup]:
        """Find duplicate images in the list."""
        # First compute all hashes
        self.compute_hashes(images)

        # Build similarity matrix
        n = len(images)
        similar_pairs = []

        for i in range(n):
            for j in range(i + 1, n):
                img1, img2 = images[i], images[j]

                # Calculate hash similarity
                if not img1.hash or not img2.hash:
                    continue

                base_similarity = self._calculate_similarity(img1.hash, img2.hash)

                # Calculate effective similarity with time weighting
                effective_similarity = self._calculate_effective_similarity(
                    img1, img2, base_similarity
                )

                # Apply threshold
                if effective_similarity >= self.threshold:
                    similar_pairs.append((i, j, effective_similarity))

        # Union-Find to group duplicates
        parent = list(range(n))

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i, j, _ in similar_pairs:
            union(i, j)

        # Group images
        groups_dict: dict[int, list[ImageInfo]] = {}
        for i in range(n):
            root = find(i)
            if root not in groups_dict:
                groups_dict[root] = []
            groups_dict[root].append(images[i])

        # Create DuplicateGroups
        duplicate_groups = []
        for group_images in groups_dict.values():
            if len(group_images) > 1:
                group = DuplicateGroup(
                    group_id=f"group_{len(duplicate_groups) + 1}", images=group_images
                )
                duplicate_groups.append(group)

                # Mark duplicates
                for img in group_images:
                    img.is_duplicate = True
                    img.duplicate_group = group.group_id

        return duplicate_groups

    def get_images_to_keep(self, images: list[ImageInfo]) -> list[ImageInfo]:
        """Get images that should be kept (not deleted)."""
        duplicates = self.find_duplicates(images)

        keep = set()

        for group in duplicates:
            # Always keep best quality
            if group.best_image:
                keep.add(group.best_image.path)

            # Optionally keep backup
            if self.keep_backup and group.backup_image:
                keep.add(group.backup_image.path)

        # Also keep non-duplicates
        for img in images:
            if not img.is_duplicate:
                keep.add(img.path)

        return [img for img in images if img.path in keep]

    def get_images_to_delete(self, images: list[ImageInfo]) -> list[ImageInfo]:
        """Get images that should be deleted."""
        keep_paths = {img.path for img in self.get_images_to_keep(images)}
        return [img for img in images if img.path not in keep_paths]

    def group_duplicates(
        self, images: list[ImageInfo], base_dir: Path, dry_run: bool = True
    ) -> list[tuple[Path, Path]]:
        """Group duplicates into directories instead of deleting.

        Args:
            images: List of images to process
            base_dir: Base directory for output
            dry_run: If True, don't actually move files

        Returns:
            List of (original_path, new_path) tuples
        """
        import shutil

        duplicates = self.find_duplicates(images)

        if self.mode != "group":
            logger.info("Group mode is not enabled, skipping")
            return []

        moves = []
        output_dir = base_dir / self.group_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        for group in duplicates:
            # Create group folder name
            best = group.best_image
            if best:
                # Use best image's species or filename as folder name
                if best.bird_species_cn:
                    folder_name = f"{best.bird_species_cn}_{group.group_id}"
                elif best.bird_species:
                    folder_name = f"{best.bird_species}_{group.group_id}"
                else:
                    folder_name = f"group_{group.group_id}"
            else:
                folder_name = f"group_{group.group_id}"

            # Sanitize folder name
            folder_name = "".join(c for c in folder_name if c.isalnum() or c in "-_")

            group_dir = output_dir / folder_name
            group_dir.mkdir(parents=True, exist_ok=True)

            # Move images to group directory
            for img in group.images:
                dest = group_dir / img.filename

                # Handle filename conflicts
                counter = 1
                while dest.exists():
                    stem = img.path.stem
                    suffix = img.path.suffix
                    dest = group_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                if not dry_run:
                    shutil.copy2(img.path, dest)

                moves.append((img.path, dest))
                logger.info(f"{'Would copy' if dry_run else 'Copied'}: {img.path} -> {dest}")

        return moves

    def save_cache(self, path: Path):
        """Save hash cache to disk."""
        with open(path, "w") as f:
            json.dump(self._hash_cache, f)

    def load_cache(self, path: Path):
        """Load hash cache from disk."""
        if path.exists():
            with open(path, "r") as f:
                self._hash_cache = json.load(f)

    def clear_cache(self):
        """Clear hash cache."""
        self._hash_cache.clear()


def get_hash_algorithms() -> list[str]:
    """Get available hash algorithms."""
    return ["phash", "dhash", "ahash", "whash"]
