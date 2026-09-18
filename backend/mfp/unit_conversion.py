"""Unit conversion service for food measurements.

Converts various food measurement units (cups, tbsp, fl oz, etc.) to grams
for standardized storage and comparison. Grams is the base unit.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Unit conversion factors to grams
# Based on common food measurement conversions
UNIT_TO_GRAMS = {
    # Volume measurements (approximate for water/generic foods)
    "cup": 240.0,
    "tbsp": 15.0,
    "tsp": 5.0,
    "fl oz": 29.5735,
    "ml": 1.0,  # 1 ml water = ~1 gram

    # Fractional cups
    "1/4 cup": 60.0,
    "1/3 cup": 80.0,
    "1/2 cup": 120.0,
    "3/4 cup": 180.0,

    # Fractional tbsp
    "1/4 tbsp": 3.75,
    "1/2 tbsp": 7.5,
    "quarter": 60.0,  # quarter cup

    # Standard weight units
    "g": 1.0,
    "gram": 1.0,
    "oz": 28.3495,  # ounce
    "lb": 453.592,  # pound
    "kg": 1000.0,

    # Alternative spellings and abbreviations
    "tablespoon": 15.0,
    "teaspoon": 5.0,
    "ounce": 28.3495,
    "pound": 453.592,
}

# Aliases for common variations
UNIT_ALIASES = {
    "tablespoons": "tbsp",
    "tbsps": "tbsp",
    "teaspoons": "tsp",
    "tsps": "tsp",
    "cups": "cup",
    "ounces": "oz",
    "pounds": "lb",
    "grams": "g",
    "milliliters": "ml",
    "ml.": "ml",
    "fl oz": "fl oz",
    "fl. oz": "fl oz",
    "fluid ounces": "fl oz",
}


def normalize_unit(unit: str) -> str:
    """Normalize unit string to standard form.

    Args:
        unit: Raw unit string from MFP (e.g., "tbsp", "Tbsp", "TBSP")

    Returns:
        Normalized unit string
    """
    if not unit:
        return "g"

    normalized = unit.strip().lower()

    # Check aliases first
    if normalized in UNIT_ALIASES:
        normalized = UNIT_ALIASES[normalized]

    return normalized


def convert_to_grams(quantity: float, unit: str) -> float:
    """Convert a quantity in given unit to grams.

    Args:
        quantity: Numeric amount
        unit: Unit of measurement

    Returns:
        Equivalent amount in grams

    Raises:
        ValueError: If unit is not recognized
    """
    if quantity <= 0:
        return 0.0

    normalized = normalize_unit(unit)

    if normalized not in UNIT_TO_GRAMS:
        logger.warning(f"Unknown unit '{unit}', treating as grams")
        return float(quantity)

    grams_per_unit = UNIT_TO_GRAMS[normalized]
    return float(quantity) * grams_per_unit


def parse_measurement(measurement_str: str) -> tuple[float, str]:
    """Parse a measurement string like '2 cups' into quantity and unit.

    Args:
        measurement_str: String like "2 cups", "1/2 tbsp", "100 g"

    Returns:
        Tuple of (quantity, unit)
    """
    if not measurement_str:
        return 1.0, "g"

    measurement_str = measurement_str.strip()
    parts = measurement_str.split(None, 1)

    if len(parts) == 1:
        # Only quantity, assume grams
        try:
            quantity = float(parts[0])
            return quantity, "g"
        except ValueError:
            # Just a unit, assume 1
            return 1.0, parts[0]

    # Has both quantity and unit
    try:
        quantity = float(parts[0])
    except ValueError:
        # Quantity is not a simple float (might be "1/2")
        try:
            quantity = eval(parts[0])  # Handle fractions like "1/2"
        except:
            logger.warning(f"Could not parse quantity from '{parts[0]}'")
            quantity = 1.0

    unit = parts[1] if len(parts) > 1 else "g"
    return quantity, unit


def standardize_measurement(quantity: float, unit: str) -> dict:
    """Convert any measurement to standard grams format.

    Args:
        quantity: Amount of food
        unit: Unit of measurement

    Returns:
        Dict with 'unit': 'g' and 'value': grams
    """
    try:
        grams = convert_to_grams(quantity, unit)
        return {
            "unit": "g",
            "value": round(grams, 2)
        }
    except Exception as e:
        logger.warning(f"Failed to convert {quantity} {unit} to grams: {e}")
        return {
            "unit": "g",
            "value": 1.0
        }
