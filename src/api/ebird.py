"""eBird API client for bird data queries.

Note: eBird does not provide image recognition API.
This client provides data query functionality for bird observations.
"""

from typing import Optional

import httpx
from loguru import logger


class EbirdClient:
    """eBird API client for bird data queries.

    API Key 申请: https://ebird.org/st/request
    文档: https://documenter.getpostman.com/view/664302/S1EN2Wqx
    """

    BASE_URL = "https://api.ebird.org/v2"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ""
        self.client = httpx.Client(timeout=30.0)

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    def _get_headers(self) -> dict:
        """Get request headers with API key."""
        return {"X-eBirdApiToken": self.api_key} if self.api_key else {}

    def get_observations_nearby(
        self, lat: float, lng: float, radius: int = 25, back: int = 14, max_results: int = 50
    ) -> list[dict]:
        """Get recent observations near a location.

        Args:
            lat: Latitude
            lng: Longitude
            radius: Radius in km (max 50)
            back: Days back to search (max 30)
            max_results: Maximum results to return

        Returns:
            List of observation records
        """
        if not self.is_configured():
            logger.warning("eBird API key not configured")
            return []

        try:
            response = self.client.get(
                f"{self.BASE_URL}/data/obs/geo/recent",
                params={
                    "lat": lat,
                    "lng": lng,
                    "dist": radius,
                    "back": back,
                    "maxResults": max_results,
                },
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"eBird API error: {response.status_code}")

        except Exception as e:
            logger.warning(f"eBird observations query failed: {e}")

        return []

    def get_observations_at_hotspot(
        self, hotspot_id: str, back: int = 14, max_results: int = 50
    ) -> list[dict]:
        """Get observations at a specific hotspot.

        Args:
            hotspot_id: eBird hotspot ID (e.g., "L12345678")
            back: Days back to search
            max_results: Maximum results

        Returns:
            List of observation records
        """
        if not self.is_configured():
            return []

        try:
            response = self.client.get(
                f"{self.BASE_URL}/data/obs/{hotspot_id}/recent",
                params={
                    "back": back,
                    "maxResults": max_results,
                },
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.warning(f"eBird hotspot query failed: {e}")

        return []

    def get_species_info(self, species_code: str) -> Optional[dict]:
        """Get information about a species.

        Args:
            species_code: eBird species code (e.g., "houspa" for House Sparrow)

        Returns:
            Species information dict
        """
        if not self.is_configured():
            return []

        try:
            response = self.client.get(
                f"{self.BASE_URL}/ref/species/{species_code}", headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.warning(f"eBird species info failed: {e}")

        return None

    def search_species(self, query: str, max_results: int = 10) -> list[dict]:
        """Search for species by name.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of matching species
        """
        if not self.is_configured():
            return []

        try:
            response = self.client.get(
                f"{self.BASE_URL}/ref/species/search",
                params={
                    "q": query,
                    "maxResults": max_results,
                },
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.warning(f"eBird species search failed: {e}")

        return []

    def get_nearest_hotspots(self, lat: float, lng: float, radius: int = 25) -> list[dict]:
        """Get nearest birding hotspots.

        Args:
            lat: Latitude
            lng: Longitude
            radius: Radius in km

        Returns:
            List of hotspot locations
        """
        if not self.is_configured():
            return []

        try:
            response = self.client.get(
                f"{self.BASE_URL}/ref/hotspot/nearest",
                params={
                    "lat": lat,
                    "lng": lng,
                    "dist": radius,
                },
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.warning(f"eBird hotspots query failed: {e}")

        return []

    def get_notable_observations(
        self, lat: float, lng: float, radius: int = 25, max_results: int = 50
    ) -> list[dict]:
        """Get notable (rare) observations near a location.

        Args:
            lat: Latitude
            lng: Longitude
            radius: Radius in km
            max_results: Maximum results

        Returns:
            List of notable observation records
        """
        if not self.is_configured():
            return []

        try:
            response = self.client.get(
                f"{self.BASE_URL}/data/obs/geo/notable",
                params={
                    "lat": lat,
                    "lng": lng,
                    "dist": radius,
                    "maxResults": max_results,
                },
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.warning(f"eBird notable query failed: {e}")

        return []

    def get_taxonomy(self, species_code: Optional[str] = None) -> list[dict]:
        """Get eBird taxonomy.

        Args:
            species_code: Optional species code to filter

        Returns:
            List of taxonomy entries
        """
        if not self.is_configured():
            return []

        try:
            params = {}
            if species_code:
                params["species"] = species_code

            response = self.client.get(
                f"{self.BASE_URL}/ref/taxonomy/ebird", params=params, headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.warning(f"eBird taxonomy query failed: {e}")

        return []

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Common eBird species codes for testing
COMMON_SPECIES_CODES = {
    "houspa": "House Sparrow",
    "norcar": "Northern Cardinal",
    "blkbur": "Blackburnian Warbler",
    "rebwoo": "Red-bellied Woodpecker",
    "pigrin": "Pigeon",
    "mallar3": "Mallard",
    "hergul": "Herring Gull",
    "starling": "European Starling",
    "amerob": "American Robin",
    "bluejay": "Blue Jay",
}
