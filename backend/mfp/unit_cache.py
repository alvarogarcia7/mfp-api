"""Cache for MFP unit measurements metadata.

Stores unit information from MFP API responses including URLs and conversion data.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Unit measurements cache directory
UNITS_CACHE_DIR = Path(__file__).parent.parent / "data" / "units_cache"
UNITS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

UNITS_CACHE_FILE = UNITS_CACHE_DIR / "mfp_units.json"


class UnitMeasurementsCache:
    """Cache for MFP unit measurements and their metadata."""

    def __init__(self, cache_file: Path = UNITS_CACHE_FILE):
        """Initialize unit measurements cache.

        Args:
            cache_file: Path to units cache JSON file
        """
        self.cache_file = Path(cache_file)
        self._load_cache()

    def _load_cache(self) -> None:
        """Load existing cache from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.units = data.get('units', {})
                    self.metadata = data.get('metadata', {})
            else:
                self.units = {}
                self.metadata = {}
        except Exception as e:
            logger.warning(f"Failed to load units cache: {e}")
            self.units = {}
            self.metadata = {}

    def add_unit(self, unit_name: str, unit_data: dict[str, Any]) -> None:
        """Add or update a unit in the cache.

        Args:
            unit_name: Name or key of the unit
            unit_data: Unit metadata (url, conversion factors, etc.)
        """
        if unit_name not in self.units:
            self.units[unit_name] = unit_data
            logger.debug(f"Added new unit to cache: {unit_name}")

    def get_unit(self, unit_name: str) -> Optional[dict[str, Any]]:
        """Get a unit from the cache.

        Args:
            unit_name: Name or key of the unit

        Returns:
            Unit data or None if not found
        """
        return self.units.get(unit_name)

    def save(self) -> None:
        """Save cache to disk."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump({
                    'units': self.units,
                    'metadata': {
                        'last_updated': datetime.now().isoformat(),
                        'unit_count': len(self.units),
                    }
                }, f, indent=2)
            logger.debug(f"Saved units cache with {len(self.units)} units")
        except Exception as e:
            logger.error(f"Failed to save units cache: {e}")

    def clear(self) -> None:
        """Clear the cache."""
        self.units = {}
        self.metadata = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info("Cleared units cache")
