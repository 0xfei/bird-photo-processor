"""Bird species recognition - supports local Birder and iNaturalist API."""

from pathlib import Path
from typing import Optional

from loguru import logger

from src.api.inaturalist import INaturalistClient
from src.utils.models import ImageInfo

# 中文鸟名映射
BIRD_NAME_CN = {
    "passer domesticus": "麻雀",
    "pica pica": "喜鹊",
    "columba livia": "岩鸽",
    "streptopelia chinensis": "珠颈斑鸠",
    "anas platyrhynchos": "绿头鸭",
    "ardea cinerea": "苍鹭",
    "egretta garzetta": "白鹭",
    "corvus corone": "小嘴乌鸦",
    "turdus merula": "乌鸫",
    "parus major": "大山雀",
}


class BirdRecognizer:
    """Bird species recognizer - local Birder with API fallback."""

    def __init__(
        self, model_name: str = "mvit_v2_t", recognizer_type: str = "birder", inat_api_key: str = ""
    ):
        self.model_name = model_name
        self.recognizer_type = recognizer_type
        self.inat_api_key = inat_api_key

        self._model = None
        self._inat_client = None

        self._load_local_model()
        self._load_api_client()

    def _load_local_model(self):
        """Load local Birder model."""
        if self.recognizer_type not in ("birder", "both"):
            return

        try:
            from birder import BirdCommand
            from birder.configuration import load_configuration

            config = load_configuration()
            self._model = config.get_model(self.model_name)
            logger.info(f"Birder model '{self.model_name}' loaded")
        except ImportError:
            logger.warning("Birder not available")
            self._model = None
        except Exception as e:
            logger.warning(f"Failed to load Birder model: {e}")
            self._model = None

    def _load_api_client(self):
        """Load iNaturalist API client."""
        if self.recognizer_type not in ("api", "both"):
            return

        if not self.inat_api_key:
            logger.warning("iNaturalist API key not configured")
            return

        try:
            self._inat_client = INaturalistClient(self.inat_api_key)
            logger.info("iNaturalist API client loaded")
        except Exception as e:
            logger.warning(f"Failed to load iNaturalist client: {e}")

    def recognize(self, image_info: ImageInfo) -> ImageInfo:
        """Recognize bird species in an image."""
        # Try local model first
        if self._model:
            try:
                result = self._recognize_local(image_info)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"Local recognition failed: {e}")

        # Fallback to API
        if self._inat_client:
            try:
                return self._recognize_api(image_info)
            except Exception as e:
                logger.debug(f"API recognition failed: {e}")

        return image_info

    def _recognize_local(self, image_info: ImageInfo) -> Optional[ImageInfo]:
        """Recognize using local Birder model."""
        import torch
        from PIL import Image
        from birder.preprocessing import get_preprocessing_transform

        img = Image.open(image_info.path)
        transform = get_preprocessing_transform(self._model.signature)
        img_tensor = transform(img).unsqueeze(0)

        with torch.no_grad():
            result = self._model(img_tensor)

        class_idx = result.argmax(dim=1).item()
        confidence = result[0, class_idx].item()

        class_name = self._model.get_class_name(class_idx)

        image_info.bird_species = class_name
        image_info.bird_confidence = float(confidence * 100)
        image_info.bird_species_cn = self._get_chinese_name(class_name)

        return image_info

    def _recognize_api(self, image_info: ImageInfo) -> ImageInfo:
        """Recognize using iNaturalist API."""
        result = self._inat_client.identify_species(str(image_info.path))

        if result:
            image_info.bird_species = result.get("scientific_name")
            image_info.bird_species_cn = result.get("common_name")
            image_info.bird_confidence = float(result.get("confidence", 0) * 100)

        return image_info

    def _get_chinese_name(self, scientific_name: str) -> Optional[str]:
        """Get Chinese name from scientific name."""
        name_lower = scientific_name.lower().strip()
        return BIRD_NAME_CN.get(name_lower)

    def recognize_batch(self, images: list[ImageInfo]) -> list[ImageInfo]:
        """Recognize bird species for multiple images."""
        for img in images:
            self.recognize(img)
        return images

    def get_recognized(self, images: list[ImageInfo]) -> list[ImageInfo]:
        """Get images with recognized species."""
        return [img for img in images if img.bird_species]

    def get_species_list(self, images: list[ImageInfo]) -> list[str]:
        """Get unique species list."""
        species = set()
        for img in images:
            if img.bird_species:
                species.add(img.bird_species)
        return sorted(species)

    def get_species_images(self, images: list[ImageInfo], species: str) -> list[ImageInfo]:
        """Get all images of a specific species."""
        return [img for img in images if img.bird_species == species]

    def get_species_stats(self, images: list[ImageInfo]) -> dict[str, int]:
        """Get species statistics."""
        stats: dict[str, int] = {}
        for img in images:
            if img.bird_species:
                name = img.bird_species_cn or img.bird_species
                stats[name] = stats.get(name, 0) + 1
        return dict(sorted(stats.items(), key=lambda x: -x[1]))
