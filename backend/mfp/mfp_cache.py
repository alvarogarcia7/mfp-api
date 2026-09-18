"""Caching proxy for MyFitnessPal API responses.

Records raw API responses to disk for processing without repeated API calls.
Implements request/response caching with filesystem persistence.
"""

import json
import logging
from datetime import date, datetime
from hashlib import md5, sha1, sha256
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Cache directory for MFP API responses
CACHE_DIR = Path(__file__).parent.parent / "data" / "mfp_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class MFPResponseCache:
    """Caches MFP API responses to disk for later processing."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cached responses
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, endpoint: str, params: dict) -> dict[str, str]:
        """Generate cache keys from endpoint and parameters.

        Args:
            endpoint: API endpoint (e.g., "/diary")
            params: Query parameters

        Returns:
            Dict with SHA-1, SHA-256, and MD5 hashes
        """
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return {
            "sha256": sha256(key_data.encode()).hexdigest(),
            "sha1": sha1(key_data.encode()).hexdigest(),
            "md5": md5(key_data.encode()).hexdigest(),
        }

    def _get_cache_file(self, cache_key: dict[str, str]) -> Path:
        """Get the cache file path for a given key.

        Args:
            cache_key: Cache key dict with SHA-256, SHA-1, MD5 hashes

        Returns:
            Path to cache file (named with SHA-256 hash)
        """
        return self.cache_dir / f"{cache_key['sha256']}.json"

    def _verify_cache_integrity(self, cache_entry: dict, expected_key: dict[str, str]) -> bool:
        """Verify cache entry integrity by checking stored hashes.

        Args:
            cache_entry: Cache entry from disk
            expected_key: Expected hash values

        Returns:
            True if hashes match
        """
        stored_hashes = cache_entry.get("hashes", {})
        return (
            stored_hashes.get("sha256") == expected_key["sha256"]
            and stored_hashes.get("sha1") == expected_key["sha1"]
            and stored_hashes.get("md5") == expected_key["md5"]
        )

    def save_response(
        self,
        endpoint: str,
        params: dict,
        response_data: Any,
        date_str: str | None = None,
    ) -> Path:
        """Save an API response to cache.

        Args:
            endpoint: API endpoint
            params: Query parameters
            response_data: Response data to cache
            date_str: Date for the response (YYYY-MM-DD)

        Returns:
            Path to saved cache file
        """
        if date_str is None:
            date_str = date.today().isoformat()

        cache_key = self._get_cache_key(endpoint, params)
        cache_file = self._get_cache_file(cache_key)

        cache_entry = {
            "endpoint": endpoint,
            "params": params,
            "date": date_str,
            "cached_at": datetime.now().isoformat(),
            "hashes": cache_key,
            "data": response_data,
        }

        try:
            with open(cache_file, "w") as f:
                json.dump(cache_entry, f, indent=2)
            logger.debug(f"Cached response to {cache_file}")
            return cache_file
        except Exception as e:
            logger.error(f"Failed to cache response: {e}")
            raise

    def load_response(
        self,
        endpoint: str,
        params: dict,
    ) -> Optional[Any]:
        """Load a cached API response.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            Cached response data, or None if not found
        """
        cache_key = self._get_cache_key(endpoint, params)
        cache_file = self._get_cache_file(cache_key)

        if not cache_file.exists():
            logger.debug(f"Cache miss for {endpoint}")
            return None

        try:
            with open(cache_file, "r") as f:
                cache_entry = json.load(f)
            logger.debug(f"Cache hit for {endpoint}")
            return cache_entry.get("data")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    def cache_exists(self, endpoint: str, params: dict) -> bool:
        """Check if a response is cached.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            True if response is in cache
        """
        cache_key = self._get_cache_key(endpoint, params)
        cache_file = self._get_cache_file(cache_key)
        if not cache_file.exists():
            return False
        try:
            with open(cache_file, "r") as f:
                cache_entry = json.load(f)
            return self._verify_cache_integrity(cache_entry, cache_key)
        except Exception:
            return False

    def list_cached_dates(self, endpoint: str) -> list[str]:
        """List all cached dates for an endpoint.

        Args:
            endpoint: API endpoint

        Returns:
            List of dates in YYYY-MM-DD format
        """
        dates = set()
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r") as f:
                    cache_entry = json.load(f)
                if cache_entry.get("endpoint") == endpoint:
                    dates.add(cache_entry.get("date"))
            except:
                pass
        return sorted(list(dates))

    def clear_cache(self) -> int:
        """Clear all cached responses.

        Returns:
            Number of files deleted
        """
        deleted = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete {cache_file}: {e}")
        logger.info(f"Cleared {deleted} cache files")
        return deleted


class CachedMFPClient:
    """Wrapper around MFP client that caches responses."""

    def __init__(self, mfp_client, use_cache: bool = True):
        """Initialize cached client.

        Args:
            mfp_client: MyFitnessPal Client instance
            use_cache: Whether to use caching
        """
        self.client = mfp_client
        self.cache = MFPResponseCache() if use_cache else None
        self.use_cache = use_cache

    def get_date(self, target_date: date):
        """Get diary for a date, using cache if available.

        Args:
            target_date: Date to fetch

        Returns:
            Day object from MFP
        """
        if self.use_cache and self.cache:
            # Try to load from cache
            cached = self.cache.load_response(
                "/diary",
                {"date": target_date.isoformat()},
            )
            if cached:
                logger.debug(f"Using cached data for {target_date}")
                return cached

        # Fetch from API
        logger.debug(f"Fetching data from API for {target_date}")
        day = self.client.get_date(target_date)

        # Cache the response
        if self.use_cache and self.cache and day:
            try:
                day_data = {
                    "date": target_date.isoformat(),
                    "meals": [
                        {
                            "name": meal.name,
                            "entries": [
                                {
                                    "name": entry.name,
                                    "quantity": getattr(entry, "quantity", 1.0),
                                    "unit": getattr(entry, "unit", "g"),
                                    "totals": dict(entry.totals),
                                }
                                for entry in meal.entries
                            ],
                        }
                        for meal in day.meals
                    ],
                }
                self.cache.save_response(
                    "/diary",
                    {"date": target_date.isoformat()},
                    day_data,
                    target_date.isoformat(),
                )
            except Exception as e:
                logger.warning(f"Failed to cache response: {e}")

        return day
