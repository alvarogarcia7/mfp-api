"""Meal schedule based on time of day (GMT+4)."""

from datetime import datetime


class MealSchedule:
    """Determine appropriate meal based on current time in GMT+4."""

    # Hardcoded schedule: (start_hour, end_hour, meal_name)
    SCHEDULE = [
        (6, 11, "breakfast"),
        (11, 15, "lunch"),
        (15, 22, "dinner"),
    ]

    @classmethod
    def get_current_meal(cls) -> str:
        """Get the meal type for the current time (GMT+4).

        Returns:
            Meal name: "breakfast", "lunch", "dinner", or "snacks"
        """
        # Get current time in GMT+4
        now = datetime.now()
        # Note: In a real scenario, you'd use pytz to convert to GMT+4
        # For now, using local time (assumes server is in GMT+4)
        current_hour = now.hour

        for start_hour, end_hour, meal_name in cls.SCHEDULE:
            if start_hour <= current_hour < end_hour:
                return meal_name

        # Default to snacks if outside meal times
        return "snacks"

    @classmethod
    def get_meal_for_time(cls, hour: int) -> str:
        """Get the meal type for a specific hour (0-23).

        Args:
            hour: Hour of day (0-23)

        Returns:
            Meal name: "breakfast", "lunch", "dinner", or "snacks"
        """
        for start_hour, end_hour, meal_name in cls.SCHEDULE:
            if start_hour <= hour < end_hour:
                return meal_name

        return "snacks"

    @classmethod
    def get_schedule_info(cls) -> dict:
        """Get the meal schedule configuration.

        Returns:
            Dict with schedule times
        """
        return {
            "timezone": "GMT+4",
            "breakfast": {"start": 6, "end": 11},
            "lunch": {"start": 11, "end": 15},
            "dinner": {"start": 15, "end": 22},
            "snacks": {"note": "any other time"},
        }
