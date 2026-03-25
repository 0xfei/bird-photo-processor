"""Configuration management for bird-photo-processor."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tomli_w


DEFAULT_CONFIG = """# bird-photo-processor 配置

[dedup]
# 相似度阈值 (0-1)，超过此值视为重复
# 0.90 = 高度相似（几乎相同）
# 0.80 = 中等相似（可能有小幅变化）
# 0.70 = 低相似度（变化较大）
similarity_threshold = 0.90
# 保留最好质量的照片数量
keep_best_count = 1
# 是否保留备份照片
keep_backup = true
# 是否启用去重
enabled = true
# 哈希算法: phash, dhash, ahash, whash
hash_algorithm = "phash"
# 是否启用鸟种辅助判断（同鸟种+相似才判定为重复）
species_aware = true
# 最大时间间隔（秒），超过此时间间隔的照片不会被判定为重复
# 10秒内：必定判定为重复（连拍）
# 10秒-300秒：逐渐降低重复判定概率
# 300秒以上：不会判定为重复（视为不同次拍摄）
min_time_interval = 300
# 去重模式: delete (删除) / group (分组到目录) / none (不处理)
mode = "group"
# 分组输出目录（仅在 mode=group 时有效）
group_output_dir = "duplicates"

[quality]
threshold = 40.0
enabled = true

[recognizer]
type = "birder"
model = "mvit_v2_t"
inat_api_key = ""
enabled = true

[file]
auto_delete = false
auto_move = false
output_dir = ""
use_trash = true

[organize]
enabled = false
by_species = true
by_date = true
keep_original = true
min_quality_for_keep = 40.0
min_species_images = 1

[device]
watch = false
auto_scan = true

[cache]
dir = ".bird-processor-cache"
enabled = true

[performance]
parallel_workers = 4
batch_size = 10
"""


@dataclass
class DedupConfig:
    similarity_threshold: float = 0.90
    keep_best_count: int = 1
    keep_backup: bool = True
    enabled: bool = True
    hash_algorithm: str = "phash"
    species_aware: bool = True
    min_time_interval: int = 300  # 5 minutes
    mode: str = "group"  # delete / group / none
    group_output_dir: str = "duplicates"


@dataclass
class QualityConfig:
    threshold: float = 40.0
    enabled: bool = True


@dataclass
class RecognizerConfig:
    type: str = "birder"
    model: str = "mvit_v2_t"
    inat_api_key: str = ""
    enabled: bool = True


@dataclass
class FileConfig:
    auto_delete: bool = False
    auto_move: bool = False
    output_dir: str = ""
    use_trash: bool = True


@dataclass
class OrganizeConfig:
    enabled: bool = False
    by_species: bool = True
    by_date: bool = True
    keep_original: bool = True
    min_quality_for_keep: float = 40.0
    min_species_images: int = 1


@dataclass
class DeviceConfig:
    watch: bool = False
    auto_scan: bool = True


@dataclass
class CacheConfig:
    dir: str = ".bird-processor-cache"
    enabled: bool = True


@dataclass
class PerformanceConfig:
    parallel_workers: int = 4
    batch_size: int = 10


@dataclass
class Config:
    dedup: DedupConfig = field(default_factory=DedupConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    recognizer: RecognizerConfig = field(default_factory=RecognizerConfig)
    file: FileConfig = field(default_factory=FileConfig)
    organize: OrganizeConfig = field(default_factory=OrganizeConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load configuration from file."""
        if path is None:
            path = cls.get_config_path()

        if not path.exists():
            config = cls()
            config.save(path)
            return config

        with open(path, "rb") as f:
            data = tomllib.load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create config from dictionary."""
        return cls(
            dedup=DedupConfig(**data.get("dedup", {})),
            quality=QualityConfig(**data.get("quality", {})),
            recognizer=RecognizerConfig(**data.get("recognizer", {})),
            file=FileConfig(**data.get("file", {})),
            organize=OrganizeConfig(**data.get("organize", {})),
            device=DeviceConfig(**data.get("device", {})),
            cache=CacheConfig(**data.get("cache", {})),
            performance=PerformanceConfig(**data.get("performance", {})),
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "dedup": self.dedup.__dict__,
            "quality": self.quality.__dict__,
            "recognizer": self.recognizer.__dict__,
            "file": self.file.__dict__,
            "organize": self.organize.__dict__,
            "device": self.device.__dict__,
            "cache": self.cache.__dict__,
            "performance": self.performance.__dict__,
        }

    def save(self, path: Optional[Path] = None):
        """Save configuration to file."""
        if path is None:
            path = self.get_config_path()

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            tomli_w.dump(self.to_dict(), f)

    @staticmethod
    def get_config_path() -> Path:
        """Get config file path based on OS."""
        if os.name == "nt":
            config_dir = Path(os.environ.get("APPDATA", "")) / "bird-photo-processor"
        else:
            config_dir = Path.home() / ".config" / "bird-photo-processor"

        return config_dir / "config.toml"

    @staticmethod
    def get_default_config_path() -> Path:
        """Get default config path."""
        return Config.get_config_path()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config():
    """Reload config from disk."""
    global _config
    _config = Config.load()
