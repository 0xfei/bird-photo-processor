"""Processing engine - integrates all processors."""

import time
from pathlib import Path
from typing import Optional

from loguru import logger

from src.processor.dedup import Deduplicator
from src.processor.organizer import FileOrganizer, FilterEngine
from src.processor.quality import QualityAssessor
from src.processor.quality_advanced import AdvancedQualityAssessor
from src.processor.recognizer import BirdRecognizer
from src.scanner.directory import ImageScanner
from src.utils.config import Config
from src.utils.models import ImageInfo, ProcessingResult


class ProcessingEngine:
    """Main processing engine for bird photos."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

        # Initialize components
        self.scanner = ImageScanner()

        # Initialize quality assessor based on config
        if self.config.quality.mode == "advanced":
            self.quality = AdvancedQualityAssessor(threshold=self.config.quality.threshold)
            logger.info("Using advanced quality assessment (3D)")
        else:
            self.quality = QualityAssessor(threshold=self.config.quality.threshold)
            logger.info("Using basic quality assessment")
        self.dedup = Deduplicator(
            threshold=self.config.dedup.similarity_threshold,
            keep_best=self.config.dedup.keep_best_count,
            keep_backup=self.config.dedup.keep_backup,
            hash_algorithm=self.config.dedup.hash_algorithm,
            species_aware=self.config.dedup.species_aware,
            min_time_interval=self.config.dedup.min_time_interval,
            mode=self.config.dedup.mode,
            group_output_dir=self.config.dedup.group_output_dir,
        )
        self.recognizer = BirdRecognizer(model_name=self.config.recognizer.model)
        self.filter_engine = FilterEngine(
            min_quality=self.config.organize.min_quality_for_keep,
            min_species_images=self.config.organize.min_species_images,
        )

    def process(
        self,
        path: Path,
        skip_dedup: bool = False,
        skip_quality: bool = False,
        skip_recognize: bool = False,
    ) -> ProcessingResult:
        """Process all images in a directory."""
        start_time = time.time()

        logger.info(f"Starting processing: {path}")

        # Scan for images
        logger.info("Scanning for images...")
        images = self.scanner.scan(path)
        logger.info(f"Found {len(images)} images")

        if not images:
            return ProcessingResult(total_images=0, duration=time.time() - start_time)

        # Quality assessment
        if not skip_quality and self.config.quality.enabled:
            logger.info("Assessing image quality...")
            images = self.quality.assess_batch(images)

        # Bird recognition
        if not skip_recognize and self.config.recognizer.enabled:
            logger.info("Recognizing bird species...")
            images = self.recognizer.recognize_batch(images)

        # Deduplication
        if not skip_dedup and self.config.dedup.enabled:
            logger.info("Finding duplicates...")
            duplicate_groups = self.dedup.find_duplicates(images)
        else:
            duplicate_groups = []

        # Prepare result
        result = ProcessingResult(
            total_images=len(images),
            duplicate_groups=duplicate_groups,
            low_quality_images=self.quality.get_low_quality(images),
            recognized_images=self.recognizer.get_recognized(images),
            duration=time.time() - start_time,
        )

        logger.info(f"Processing completed in {result.duration:.2f}s")

        return result

    def process_organized(
        self, path: Path, output_dir: Path, dry_run: bool = True
    ) -> ProcessingResult:
        """Process and organize images into structured directories."""
        # First process all images
        result = self.process(path)

        if result.total_images == 0:
            return result

        # Get all images from scanner again (need full list)
        images = self.scanner.scan(path)

        # Apply quality assessment
        images = self.quality.assess_batch(images)

        # Apply bird recognition
        images = self.recognizer.recognize_batch(images)

        # Apply filter
        to_keep = self.filter_engine.filter(images)
        to_delete = self.filter_engine.get_to_delete(images, to_keep)

        logger.info(f"Filtered: {len(to_keep)} to keep, {len(to_delete)} to delete")

        # Organize
        organizer = FileOrganizer(
            output_dir=output_dir,
            by_species=self.config.organize.by_species,
            by_date=self.config.organize.by_date,
            keep_original=self.config.organize.keep_original,
            use_trash=self.config.file.use_trash,
        )

        if not dry_run:
            # Move files
            moves = organizer.organize(to_keep)
            result.moved_images = [(str(s), str(d)) for s, d in moves]

            # Delete filtered out images
            deleted = organizer.delete_files(to_delete)
            result.deleted_images = [str(d) for d in deleted]

        return result

    def get_summary(self, result: ProcessingResult) -> str:
        """Get formatted summary of processing result."""
        lines = [
            f"处理完成: {result.total_images} 张照片",
            f"耗时: {result.duration:.2f} 秒",
            "",
            "📊 统计:",
            f"  - 总照片数: {result.total_images}",
            f"  - 重复组: {len(result.duplicate_groups)} 组 ({result.total_duplicates} 张)",
            f"  - 低质量照片: {len(result.low_quality_images)} 张",
            f"  - 已识别鸟种: {result.species_count} 种",
        ]

        if result.recognized_images:
            lines.append("")
            lines.append("🐦 识别到的鸟类:")
            species_stats = result.get_species_stats()
            for name, count in list(species_stats.items())[:10]:
                lines.append(f"  - {name}: {count} 张")

        if result.duplicate_groups:
            lines.append("")
            lines.append("⚠️  重复照片组:")
            for group in result.duplicate_groups[:5]:
                names = ", ".join([img.filename for img in group.images[:3]])
                lines.append(f"  组 {group.group_id}: {names}")

        return "\n".join(lines)
