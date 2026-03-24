"""iNaturalist API client for bird species recognition."""

import os
from typing import Optional

import httpx
from loguru import logger


class INaturalistClient:
    """iNaturalist API client for species identification."""

    BASE_URL = "https://api.inaturalist.org/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("INATURALIST_API_KEY", "")
        self.client = httpx.Client(timeout=30.0)

    def identify_species(self, image_path: str) -> Optional[dict]:
        """Identify species from an image using iNaturalist API.

        Returns:
            Dict with species name, confidence, and other info, or None if failed.
        """
        if not self.api_key:
            logger.warning("iNaturalist API key not configured")
            return None

        try:
            # Upload image for identification
            with open(image_path, "rb") as f:
                files = {"photo": (image_path, f, "image/jpeg")}
                data = {"observation[species_guess]": "bird"}
                headers = {"Authorization": self.api_key}

                response = self.client.post(
                    f"{self.BASE_URL}/observations", files=files, data=data, headers=headers
                )

            if response.status_code != 200:
                logger.warning(f"iNaturalist API error: {response.status_code}")
                return None

            result = response.json()

            # Extract best identification
            if result.get("results"):
                observation = result["results"][0]
                taxon = observation.get("taxon", {})

                return {
                    "scientific_name": taxon.get("name"),
                    "common_name": taxon.get("preferred_common_name"),
                    "taxon_id": taxon.get("id"),
                    "confidence": observation.get("confidence", 0),
                }

        except Exception as e:
            logger.warning(f"iNaturalist identification failed: {e}")

        return None

    def search_species(self, query: str, limit: int = 10) -> list[dict]:
        """Search for species by name."""
        if not self.api_key:
            return []

        try:
            response = self.client.get(
                f"{self.BASE_URL}/taxa",
                params={"q": query, "limit": limit, "taxon_type": "Species"},
                headers={"Authorization": self.api_key},
            )

            if response.status_code == 200:
                results = response.json()
                return [
                    {
                        "id": t["id"],
                        "name": t["name"],
                        "common_name": t.get("preferred_common_name"),
                        "iconic_taxon": t.get("iconic_taxon_name"),
                    }
                    for t in results.get("results", [])
                ]
        except Exception as e:
            logger.warning(f"iNaturalist search failed: {e}")

        return []

    def get_species_info(self, taxon_id: int) -> Optional[dict]:
        """Get detailed info for a species."""
        if not self.api_key:
            return None

        try:
            response = self.client.get(
                f"{self.BASE_URL}/taxa/{taxon_id}", headers={"Authorization": self.api_key}
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("results"):
                    return result["results"][0]
        except Exception as e:
            logger.warning(f"iNaturalist species info failed: {e}")

        return None

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
