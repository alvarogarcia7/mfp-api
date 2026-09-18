"""Tests for food measurement unit conversion."""

import pytest
from backend.mfp.unit_conversion import (
    convert_to_grams,
    normalize_unit,
    parse_measurement,
    standardize_measurement,
)


class TestNormalizeUnit:
    """Test unit normalization."""

    def test_lowercase_unit(self):
        assert normalize_unit("tbsp") == "tbsp"

    def test_uppercase_unit(self):
        assert normalize_unit("TBSP") == "tbsp"

    def test_mixed_case_unit(self):
        assert normalize_unit("Tbsp") == "tbsp"

    def test_whitespace(self):
        assert normalize_unit("  cup  ") == "cup"

    def test_unit_alias_tablespoons(self):
        assert normalize_unit("tablespoons") == "tbsp"

    def test_unit_alias_teaspoons(self):
        assert normalize_unit("teaspoons") == "tsp"

    def test_empty_unit_defaults_to_grams(self):
        assert normalize_unit("") == "g"

    def test_none_defaults_to_grams(self):
        assert normalize_unit("g") == "g"


class TestConvertToGrams:
    """Test unit to grams conversion."""

    # Cup conversions
    def test_convert_cup_to_grams(self):
        assert convert_to_grams(1, "cup") == 240.0

    def test_convert_half_cup_to_grams(self):
        assert convert_to_grams(0.5, "cup") == 120.0

    def test_convert_quarter_cup_to_grams(self):
        assert convert_to_grams(0.25, "cup") == 60.0

    def test_convert_fractional_cup_notation(self):
        assert convert_to_grams(1, "1/2 cup") == 120.0

    # Tablespoon conversions
    def test_convert_tbsp_to_grams(self):
        assert convert_to_grams(1, "tbsp") == 15.0

    def test_convert_half_tbsp_to_grams(self):
        assert convert_to_grams(0.5, "tbsp") == 7.5

    def test_convert_quarter_tbsp_to_grams(self):
        assert convert_to_grams(0.25, "tbsp") == 3.75

    # Teaspoon conversions
    def test_convert_tsp_to_grams(self):
        assert convert_to_grams(1, "tsp") == 5.0

    def test_convert_multiple_tsp_to_grams(self):
        assert convert_to_grams(3, "tsp") == 15.0

    # Fluid ounce conversions
    def test_convert_fl_oz_to_grams(self):
        assert abs(convert_to_grams(1, "fl oz") - 29.5735) < 0.01

    def test_convert_fl_oz_uppercase(self):
        assert abs(convert_to_grams(1, "FL OZ") - 29.5735) < 0.01

    # Weight conversions
    def test_convert_gram_to_grams(self):
        assert convert_to_grams(100, "g") == 100.0

    def test_convert_ounce_to_grams(self):
        assert abs(convert_to_grams(1, "oz") - 28.3495) < 0.01

    def test_convert_pound_to_grams(self):
        assert abs(convert_to_grams(1, "lb") - 453.592) < 0.01

    def test_convert_kilogram_to_grams(self):
        assert convert_to_grams(1, "kg") == 1000.0

    # ML conversions
    def test_convert_ml_to_grams(self):
        assert convert_to_grams(100, "ml") == 100.0

    # Edge cases
    def test_zero_quantity(self):
        assert convert_to_grams(0, "cup") == 0.0

    def test_negative_quantity(self):
        assert convert_to_grams(-1, "cup") == 0.0

    def test_unknown_unit_default(self):
        # Unknown units should return quantity as-is (treating as grams)
        assert convert_to_grams(100, "unknown") == 100.0

    def test_case_insensitive_conversion(self):
        assert convert_to_grams(1, "CUP") == 240.0
        assert convert_to_grams(1, "Cup") == 240.0


class TestParseMeasurement:
    """Test parsing measurement strings."""

    def test_parse_simple_quantity_and_unit(self):
        quantity, unit = parse_measurement("2 cups")
        assert quantity == 2
        assert unit == "cups"

    def test_parse_fractional_quantity(self):
        quantity, unit = parse_measurement("1/2 cup")
        assert quantity == 0.5
        assert unit == "cup"

    def test_parse_decimal_quantity(self):
        quantity, unit = parse_measurement("2.5 tbsp")
        assert quantity == 2.5
        assert unit == "tbsp"

    def test_parse_quantity_only(self):
        quantity, unit = parse_measurement("100")
        assert quantity == 100
        assert unit == "g"

    def test_parse_unit_only(self):
        quantity, unit = parse_measurement("cup")
        assert quantity == 1.0
        assert unit == "cup"

    def test_parse_with_extra_whitespace(self):
        quantity, unit = parse_measurement("  2   cups  ")
        assert quantity == 2
        assert unit == "cups"

    def test_parse_empty_string(self):
        quantity, unit = parse_measurement("")
        assert quantity == 1.0
        assert unit == "g"


class TestStandardizeMeasurement:
    """Test standardizing measurements to grams."""

    def test_standardize_cup_to_grams(self):
        result = standardize_measurement(1, "cup")
        assert result["unit"] == "g"
        assert result["value"] == 240.0

    def test_standardize_tbsp_to_grams(self):
        result = standardize_measurement(2, "tbsp")
        assert result["unit"] == "g"
        assert result["value"] == 30.0

    def test_standardize_already_grams(self):
        result = standardize_measurement(100, "g")
        assert result["unit"] == "g"
        assert result["value"] == 100.0

    def test_standardize_fl_oz_to_grams(self):
        result = standardize_measurement(1, "fl oz")
        assert result["unit"] == "g"
        assert abs(result["value"] - 29.57) < 0.1

    def test_standardize_oz_to_grams(self):
        result = standardize_measurement(1, "oz")
        assert result["unit"] == "g"
        assert abs(result["value"] - 28.35) < 0.1

    def test_standardize_fractional_cup(self):
        result = standardize_measurement(0.5, "cup")
        assert result["unit"] == "g"
        assert result["value"] == 120.0

    def test_standardize_invalid_unit_default(self):
        result = standardize_measurement(100, "unknown")
        assert result["unit"] == "g"
        # Unknown units treated as grams
        assert result["value"] == 100.0


class TestRealWorldExamples:
    """Test real-world food measurement conversions."""

    def test_recipe_conversion(self):
        """Test converting a recipe that uses multiple units."""
        # 1 cup flour
        flour = standardize_measurement(1, "cup")
        assert flour["value"] == 240.0

        # 2 tbsp butter
        butter = standardize_measurement(2, "tbsp")
        assert butter["value"] == 30.0

        # 1/4 tsp salt
        salt = standardize_measurement(0.25, "tsp")
        assert salt["value"] == 1.25

    def test_liquid_conversions(self):
        """Test converting liquid measurements."""
        # 8 fl oz water
        water = standardize_measurement(8, "fl oz")
        assert abs(water["value"] - 236.59) < 0.1

        # 200 ml equivalent
        ml = standardize_measurement(200, "ml")
        assert ml["value"] == 200.0

    def test_weight_conversions(self):
        """Test converting weight measurements."""
        # 1 lb chicken breast
        chicken = standardize_measurement(1, "lb")
        assert abs(chicken["value"] - 453.59) < 0.1

        # 200 grams equivalent
        grams = standardize_measurement(200, "g")
        assert grams["value"] == 200.0
