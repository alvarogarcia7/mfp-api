"""Shared utilities for MyFitnessPal data fetching and processing.

Common functions reused across multiple fetch/parse operations.
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)


def parse_date_range(args) -> tuple[date, date]:
    """Parse date range from CLI arguments.

    Supports: --today, --last-two-weeks, --last-month, --range-start/--range-end
    """
    today = date.today()

    if args.today:
        return today, today
    elif args.last_two_weeks:
        start = today - timedelta(days=14)
        return start, today
    elif args.last_month:
        start = today - timedelta(days=30)
        return start, today
    elif args.range_start and args.range_end:
        try:
            start = date.fromisoformat(args.range_start)
            end = date.fromisoformat(args.range_end)
            if start > end:
                raise ValueError("range-start must be before range-end")
            return start, end
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}. Use YYYY-MM-DD")
    else:
        raise ValueError("Must specify one of: --today, --last-two-weeks, --last-month, or --range-start/--range-end")


def load_schema(schema_file: Path) -> dict:
    """Load JSON schema from file.

    Args:
        schema_file: Path to JSON schema file

    Returns:
        Parsed schema dict, or minimal schema if file not found
    """
    try:
        with open(schema_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load schema from {schema_file}: {e}")
        return {"type": "object"}


def validate_data(data_list: list, schema: dict, data_type_name: str = "data") -> tuple[int, int]:
    """Validate a list of data items against a JSON schema.

    Marks each item with 'valid' bool and adds 'validation_error' if invalid.

    Args:
        data_list: List of items to validate
        schema: JSON schema to validate against
        data_type_name: Name of data type for logging (e.g., "food", "diary entry")

    Returns:
        Tuple of (valid_count, invalid_count)
    """
    valid_count = 0
    invalid_count = 0

    for item in data_list:
        try:
            validate(instance=item, schema=schema)
            item["valid"] = True
            valid_count += 1
        except ValidationError as e:
            name = item.get('name', item.get('date', 'unknown'))
            logger.warning(f"{data_type_name} '{name}' failed schema validation: {e.message}")
            item["valid"] = False
            item["validation_error"] = e.message
            invalid_count += 1

    if invalid_count > 0:
        logger.warning(f"Marked {invalid_count} invalid {data_type_name}s")

    return valid_count, invalid_count


def save_raw_data(data: dict, filename: str, raw_data_dir: Path) -> str:
    """Save raw API response to disk with metadata.

    Args:
        data: Dict containing metadata and raw_response
        filename: Filename pattern (without path/extension)
        raw_data_dir: Directory to save to

    Returns:
        Path to saved file as string
    """
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = raw_data_dir / f"{filename}_{timestamp}.json"

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved raw data to {filepath}")
    return str(filepath)


def safe_float(value) -> float:
    """Convert value to float, return 0.0 if None/invalid."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value) -> int:
    """Convert value to int, return 0 if None/invalid."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
