"""iNaturalist API client for bird species recognition."""

import base64
import time
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger


class INaturalistClient:
    """iNaturalist API client for species identification.

    API Key 申请: https://www.inaturalist.org/users/api_token
    文档: https://www.inaturalist.org/pages/api+reference
    """

    BASE_URL = "https://api.inaturalist.org/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ""
        self.client = httpx.Client(timeout=60.0)

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    def identify_species(self, image_path: str) -> Optional[dict]:
        """Identify species from an image.

        This method uploads the image to iNaturalist and creates an observation.
        Note: This is async - results may take time to process.

        Args:
            image_path: Path to the image file

        Returns:
            Dict with species info or None if failed
        """
        if not self.is_configured():
            logger.warning("iNaturalist API key not configured")
            return None

        try:
            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Create observation with image
            # Using the simplified endpoint
            data = {
                "observation[species_guess]": "bird",
                "observation[observation_field_values_attributes][0][observation_field_id]": "",
                "observation[photos_attributes][0][base64_uri]": f"data:image/jpeg;base64,{image_data}",
            }

            headers = {"Authorization": self.api_key}

            response = self.client.post(f"{self.BASE_URL}/observations", data=data, headers=headers)

            if response.status_code == 200:
                result = response.json()
                if result.get("results"):
                    observation = result["results"][0]
                    taxon = observation.get("taxon", {})

                    return {
                        "source": "iNaturalist",
                        "scientific_name": taxon.get("name"),
                        "common_name": taxon.get("preferred_common_name"),
                        "taxon_id": taxon.get("id"),
                        "confidence": observation.get("confidence", 0),
                        "image_url": observation.get("photos", [{}])[0].get("url")
                        if observation.get("photos")
                        else None,
                    }
            else:
                logger.warning(
                    f"iNaturalist API error: {response.status_code} - {response.text[:200]}"
                )

        except Exception as e:
            logger.warning(f"iNaturalist identification failed: {e}")

        return None

    def identify_by_url(self, image_url: str) -> Optional[dict]:
        """Identify species from an image URL."""
        if not self.is_configured():
            return None

        try:
            data = {
                "observation[species_guess]": "bird",
                "observation[photos_attributes][0][url]": image_url,
            }

            headers = {"Authorization": self.api_key}

            response = self.client.post(f"{self.BASE_URL}/observations", data=data, headers=headers)

            if response.status_code == 200:
                result = response.json()
                if result.get("results"):
                    observation = result["results"][0]
                    taxon = observation.get("taxon", {})

                    return {
                        "source": "iNaturalist",
                        "scientific_name": taxon.get("name"),
                        "common_name": taxon.get("preferred_common_name"),
                        "taxon_id": taxon.get("id"),
                        "confidence": observation.get("confidence", 0),
                    }

        except Exception as e:
            logger.warning(f"iNaturalist identification failed: {e}")

        return None

    def search_species(self, query: str, limit: int = 10) -> list[dict]:
        """Search for species by name.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of species matching the query
        """
        if not self.is_configured():
            return []

        try:
            response = self.client.get(
                f"{self.BASE_URL}/taxa",
                params={
                    "q": query,
                    "limit": limit,
                    "taxon_type": "Species",
                    "rank": "species",
                },
                headers={"Authorization": self.api_key} if self.api_key else {},
            )

            if response.status_code == 200:
                results = response.json()
                return [
                    {
                        "id": t["id"],
                        "name": t["name"],
                        "common_name": t.get("preferred_common_name"),
                        "iconic_taxon": t.get("iconic_taxon_name"),
                        "image_url": t.get("default_photo", {}).get("url")
                        if t.get("default_photo")
                        else None,
                    }
                    for t in results.get("results", [])
                ]
        except Exception as e:
            logger.warning(f"iNaturalist search failed: {e}")

        return []

    def get_species_info(self, taxon_id: int) -> Optional[dict]:
        """Get detailed info for a species."""
        if not self.is_configured():
            return None

        try:
            response = self.client.get(
                f"{self.BASE_URL}/taxa/{taxon_id}",
                headers={"Authorization": self.api_key} if self.api_key else {},
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("results"):
                    return result["results"][0]
        except Exception as e:
            logger.warning(f"iNaturalist species info failed: {e}")

        return None

    def get_observations_nearby(self, lat: float, lng: float, radius: int = 10) -> list[dict]:
        """Get recent observations nearby.

        Args:
            lat: Latitude
            lng: Longitude
            radius: Radius in km
        """
        if not self.is_configured():
            return []

        try:
            response = self.client.get(
                f"{self.BASE_URL}/observations",
                params={
                    "lat": lat,
                    "lng": lng,
                    "radius": radius,
                    "per_page": 20,
                },
            )

            if response.status_code == 200:
                result = response.json()
                return [
                    {
                        "id": obs["id"],
                        "species": obs.get("species_guess"),
                        "taxon": obs.get("taxon", {}).get("name"),
                        "common_name": obs.get("taxon", {}).get("preferred_common_name"),
                        "observed_on": obs.get("observed_on"),
                    }
                    for obs in result.get("results", [])
                ]
        except Exception as e:
            logger.warning(f"iNaturalist nearby observations failed: {e}")

        return []

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
