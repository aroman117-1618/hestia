"""
Daily Briefing Generator for Hestia.

Generates personalized daily briefings by aggregating data from:
- Calendar (today's events)
- Reminders (overdue and due today)
- Background tasks (pending)
- Weather (via OpenWeatherMap API)
- Behavioral patterns (suggestions)

Implements ADR-017: Proactive Intelligence Framework.

Security:
- Weather location input validation (regex pattern)
- API key retrieved from Keychain when available
- Input sanitization for external API calls
"""

import asyncio
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4

import httpx

from hestia.logging import get_logger, LogComponent
from hestia.proactive.models import (
    Briefing,
    BriefingSection,
    BehaviorPattern,
    ProactiveConfig,
)


# Security: Pattern for valid weather locations
# Allows letters, spaces, hyphens, commas, and periods (for abbreviations)
# Examples: "San Francisco, US", "New York", "London, UK", "St. Louis, MO"
LOCATION_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9\s\-,\.]{1,99}$')


class BriefingGenerator:
    """
    Generates daily briefings for the user.

    Aggregates information from multiple sources into a cohesive
    natural language briefing with structured data for UI rendering.
    """

    def __init__(self, config: Optional[ProactiveConfig] = None):
        """
        Initialize the briefing generator.

        Args:
            config: Proactive configuration. If None, uses defaults.
        """
        self.config = config or ProactiveConfig()
        self.logger = get_logger()

        # Weather API configuration
        self._weather_api_key = self._get_weather_api_key()
        self._weather_base_url = "https://api.openweathermap.org/data/2.5"

    def _get_weather_api_key(self) -> Optional[str]:
        """
        Get weather API key from secure storage.

        Security: Prefers Keychain storage over environment variables.
        Falls back to environment variable if Keychain not available.

        Returns:
            API key string or None if not configured.
        """
        # Try Keychain first (most secure)
        try:
            from hestia.security import get_api_key
            key = get_api_key("openweathermap_api_key")
            if key:
                return key
        except Exception as e:
            self.logger.debug(
                f"Keychain lookup failed: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
            )

        # Fall back to environment variable
        env_key = os.environ.get("OPENWEATHERMAP_API_KEY")
        if env_key:
            self.logger.warning(
                "Using weather API key from environment (store in Keychain for better security)",
                component=LogComponent.ORCHESTRATION,
            )
        return env_key

    async def generate(
        self,
        patterns: Optional[List[BehaviorPattern]] = None,
    ) -> Briefing:
        """
        Generate today's briefing.

        Args:
            patterns: Optional list of detected behavior patterns for suggestions.

        Returns:
            Complete Briefing object.
        """
        now = datetime.now(timezone.utc)

        self.logger.info(
            "Generating daily briefing",
            component=LogComponent.ORCHESTRATION,
            data={"timestamp": now.isoformat()},
        )

        # Generate greeting based on time of day
        greeting = self._generate_greeting(now)

        # Gather data from all sources in parallel
        calendar_task = self._get_calendar_data()
        reminders_task = self._get_reminders_data()
        tasks_task = self._get_tasks_data()
        weather_task = self._get_weather_data() if self.config.weather_enabled else asyncio.sleep(0)
        health_task = self._get_health_data()

        results = await asyncio.gather(
            calendar_task,
            reminders_task,
            tasks_task,
            weather_task,
            health_task,
            return_exceptions=True,
        )

        # Process results
        calendar_data = results[0] if not isinstance(results[0], Exception) else None
        reminders_data = results[1] if not isinstance(results[1], Exception) else None
        tasks_data = results[2] if not isinstance(results[2], Exception) else None
        weather_data = results[3] if not isinstance(results[3], Exception) else None
        health_data = results[4] if not isinstance(results[4], Exception) else None

        # Build briefing
        briefing = Briefing(
            greeting=greeting,
            timestamp=now,
        )

        # Add calendar section
        if calendar_data:
            self._add_calendar_section(briefing, calendar_data)

        # Add reminders section
        if reminders_data:
            self._add_reminders_section(briefing, reminders_data)

        # Add tasks section
        if tasks_data:
            self._add_tasks_section(briefing, tasks_data)

        # Add weather section
        if weather_data:
            self._add_weather_section(briefing, weather_data)

        # Add health section
        if health_data:
            self._add_health_section(briefing, health_data)

        # Add pattern-based suggestions
        if patterns:
            self._add_suggestions(briefing, patterns, now)

        self.logger.info(
            "Briefing generated",
            component=LogComponent.ORCHESTRATION,
            data={
                "sections": len(briefing.sections),
                "suggestions": len(briefing.suggestions),
            },
        )

        return briefing

    def _generate_greeting(self, now: datetime) -> str:
        """Generate time-appropriate greeting."""
        local_hour = now.hour

        if 5 <= local_hour < 12:
            return "Good morning."
        elif 12 <= local_hour < 17:
            return "Good afternoon."
        elif 17 <= local_hour < 21:
            return "Good evening."
        else:
            return "Hello."

    def _parse_datetime(self, dt_string: str) -> datetime:
        """Parse datetime string, handling Z suffix for UTC."""
        if dt_string.endswith("Z"):
            dt_string = dt_string[:-1] + "+00:00"
        return datetime.fromisoformat(dt_string)

    async def _get_calendar_data(self) -> Optional[Dict[str, Any]]:
        """Get today's calendar events."""
        try:
            from hestia.apple.calendar import CalendarClient

            client = CalendarClient()
            events = client.get_today_events()

            return {
                "events": [
                    {
                        "title": e.title,
                        "start": e.start_date.isoformat() if e.start_date else None,
                        "end": e.end_date.isoformat() if e.end_date else None,
                        "location": e.location,
                        "is_all_day": e.is_all_day,
                    }
                    for e in events
                ],
                "count": len(events),
            }
        except Exception as e:
            self.logger.warning(
                f"Failed to get calendar data: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
            )
            return None

    async def _get_reminders_data(self) -> Optional[Dict[str, Any]]:
        """Get overdue and due-today reminders."""
        try:
            from hestia.apple.reminders import RemindersClient

            client = RemindersClient()
            overdue = client.get_overdue()
            due_today = client.get_due_today()

            return {
                "overdue": [
                    {"title": r.title, "due": r.due_date.isoformat() if r.due_date else None}
                    for r in overdue
                ],
                "due_today": [
                    {"title": r.title, "due": r.due_date.isoformat() if r.due_date else None}
                    for r in due_today
                ],
                "overdue_count": len(overdue),
                "due_today_count": len(due_today),
            }
        except Exception as e:
            self.logger.warning(
                f"Failed to get reminders data: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
            )
            return None

    async def _get_tasks_data(self) -> Optional[Dict[str, Any]]:
        """Get pending background tasks."""
        try:
            from hestia.tasks import get_task_manager

            manager = await get_task_manager()
            pending = await manager.list_tasks(status="pending")
            awaiting = await manager.list_tasks(status="awaiting_approval")

            return {
                "pending_count": len(pending),
                "awaiting_approval_count": len(awaiting),
                "total": len(pending) + len(awaiting),
            }
        except Exception as e:
            self.logger.warning(
                f"Failed to get tasks data: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
            )
            return None

    def _validate_location(self, location: str) -> Optional[str]:
        """
        Validate and sanitize weather location string.

        Security: Prevents injection attacks via location parameter.

        Args:
            location: Raw location string from config.

        Returns:
            Sanitized location string, or None if invalid.
        """
        if not location:
            return None

        # Strip and limit length
        location = location.strip()[:100]

        # Validate against pattern
        if not LOCATION_PATTERN.match(location):
            self.logger.warning(
                f"Invalid weather location rejected",
                component=LogComponent.ORCHESTRATION,
                data={"location_length": len(location)},
            )
            return None

        return location

    async def _get_weather_data(self) -> Optional[Dict[str, Any]]:
        """Get weather forecast from OpenWeatherMap."""
        if not self._weather_api_key:
            return None

        raw_location = self.config.weather_location or "San Francisco,US"
        location = self._validate_location(raw_location)

        if not location:
            self.logger.warning(
                "Weather location validation failed, using default",
                component=LogComponent.ORCHESTRATION,
            )
            location = "San Francisco,US"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._weather_base_url}/weather",
                    params={
                        "q": location,
                        "appid": self._weather_api_key,
                        "units": "imperial",
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                current = response.json()

                # Also get forecast
                forecast_response = await client.get(
                    f"{self._weather_base_url}/forecast",
                    params={
                        "q": location,
                        "appid": self._weather_api_key,
                        "units": "imperial",
                        "cnt": 8,  # Next 24 hours
                    },
                    timeout=10.0,
                )
                forecast_response.raise_for_status()
                forecast = forecast_response.json()

                # Check for rain in forecast
                rain_times = []
                for item in forecast.get("list", []):
                    weather = item.get("weather", [{}])[0]
                    if weather.get("main", "").lower() in ["rain", "drizzle", "thunderstorm"]:
                        dt = datetime.fromtimestamp(item["dt"])
                        rain_times.append(dt.strftime("%-I%p").lower())

                return {
                    "current": {
                        "temp": round(current["main"]["temp"]),
                        "feels_like": round(current["main"]["feels_like"]),
                        "description": current["weather"][0]["description"],
                        "icon": current["weather"][0]["icon"],
                    },
                    "high": round(current["main"]["temp_max"]),
                    "low": round(current["main"]["temp_min"]),
                    "rain_times": rain_times[:3] if rain_times else None,
                    "location": location,
                }
        except Exception as e:
            self.logger.warning(
                f"Failed to get weather data: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
            )
            return None

    def _add_calendar_section(self, briefing: Briefing, data: Dict[str, Any]) -> None:
        """Add calendar information to briefing."""
        events = data.get("events", [])
        briefing.calendar_events = events

        if not events:
            briefing.calendar_summary = "No meetings scheduled today."
            return

        # Build natural language summary
        count = len(events)
        if count == 1:
            e = events[0]
            if e.get("start"):
                start = self._parse_datetime(e["start"])
                time_str = start.strftime("%-I:%M%p").lower()
                briefing.calendar_summary = f"You have 1 meeting today: {e['title']} at {time_str}."
            else:
                briefing.calendar_summary = f"You have 1 event today: {e['title']}."
        else:
            # List first few events
            event_strs = []
            for e in events[:3]:
                if e.get("start") and not e.get("is_all_day"):
                    start = self._parse_datetime(e["start"])
                    time_str = start.strftime("%-I%p").lower()
                    event_strs.append(f"{time_str} {e['title']}")
                else:
                    event_strs.append(e["title"])

            if count > 3:
                briefing.calendar_summary = f"You have {count} meetings today ({', '.join(event_strs)}, and {count - 3} more)."
            else:
                briefing.calendar_summary = f"You have {count} meetings today ({', '.join(event_strs)})."

        briefing.sections.append(BriefingSection(
            title="Calendar",
            content=briefing.calendar_summary,
            priority=90,
            icon="calendar",
        ))

    def _add_reminders_section(self, briefing: Briefing, data: Dict[str, Any]) -> None:
        """Add reminders information to briefing."""
        overdue = data.get("overdue", [])
        due_today = data.get("due_today", [])

        briefing.overdue_count = len(overdue)
        briefing.due_today_count = len(due_today)

        if not overdue and not due_today:
            return

        parts = []

        if overdue:
            titles = [r["title"] for r in overdue[:3]]
            if len(overdue) == 1:
                parts.append(f"1 overdue reminder: {titles[0]}")
            elif len(overdue) <= 3:
                parts.append(f"{len(overdue)} overdue reminders: {', '.join(titles)}")
            else:
                parts.append(f"{len(overdue)} overdue reminders: {', '.join(titles)}, and {len(overdue) - 3} more")

        if due_today:
            titles = [r["title"] for r in due_today[:3]]
            if len(due_today) == 1:
                parts.append(f"1 reminder due today: {titles[0]}")
            else:
                parts.append(f"{len(due_today)} reminders due today")

        briefing.reminders_summary = ". ".join(parts) + "."

        briefing.sections.append(BriefingSection(
            title="Reminders",
            content=briefing.reminders_summary,
            priority=80 if overdue else 70,
            icon="checklist",
        ))

    def _add_tasks_section(self, briefing: Briefing, data: Dict[str, Any]) -> None:
        """Add background tasks information to briefing."""
        pending = data.get("pending_count", 0)
        awaiting = data.get("awaiting_approval_count", 0)

        briefing.pending_task_count = pending + awaiting

        if pending == 0 and awaiting == 0:
            return

        parts = []
        if pending > 0:
            parts.append(f"{pending} pending background task{'s' if pending != 1 else ''}")
        if awaiting > 0:
            parts.append(f"{awaiting} task{'s' if awaiting != 1 else ''} awaiting approval")

        briefing.tasks_summary = " and ".join(parts) + "."

        briefing.sections.append(BriefingSection(
            title="Tasks",
            content=briefing.tasks_summary,
            priority=60,
            icon="gearshape.2",
        ))

    def _add_weather_section(self, briefing: Briefing, data: Dict[str, Any]) -> None:
        """Add weather information to briefing."""
        briefing.weather_data = data

        current = data.get("current", {})
        rain_times = data.get("rain_times")

        parts = []
        if current:
            temp = current.get("temp")
            desc = current.get("description", "").capitalize()
            if temp:
                parts.append(f"{desc}, {temp}°F")

        if rain_times:
            if len(rain_times) == 1:
                parts.append(f"Rain expected around {rain_times[0]}—might want an umbrella")
            else:
                parts.append(f"Rain forecast {'-'.join([rain_times[0], rain_times[-1]])}—might want an umbrella")

        if parts:
            briefing.weather_summary = ". ".join(parts) + "."
            briefing.sections.append(BriefingSection(
                title="Weather",
                content=briefing.weather_summary,
                priority=50,
                icon="cloud.sun",
            ))

    async def _get_health_data(self) -> Optional[Dict[str, Any]]:
        """Get today's health summary from synced HealthKit data."""
        try:
            from hestia.health import get_health_manager

            manager = await get_health_manager()
            summary = await manager.get_daily_summary()

            if not summary or not summary.get("categories"):
                return None

            return summary
        except Exception as e:
            self.logger.warning(
                f"Failed to get health data: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
            )
            return None

    def _add_health_section(self, briefing: Briefing, data: Dict[str, Any]) -> None:
        """Add health information to briefing."""
        briefing.health_data = data

        parts = []
        categories = data.get("categories", {})

        # Activity highlights
        activity = categories.get("activity", {})
        if activity:
            steps = activity.get("stepCount")
            if steps:
                parts.append(f"You walked {int(steps.get('total', 0)):,} steps")

            calories = activity.get("activeEnergyBurned")
            if calories:
                parts.append(f"burned {int(calories.get('total', 0))} active calories")

            exercise = activity.get("appleExerciseTime")
            if exercise:
                mins = int(exercise.get("total", 0))
                if mins > 0:
                    parts.append(f"{mins} minutes of exercise")

        # Sleep
        sleep = categories.get("sleep", {})
        if sleep:
            sleep_data = sleep.get("sleepAnalysis")
            if sleep_data:
                total_mins = sleep_data.get("total", 0)
                if total_mins > 0:
                    hours = total_mins / 60
                    parts.append(f"slept {hours:.1f} hours")

        # Heart rate
        heart = categories.get("heart", {})
        if heart:
            rhr = heart.get("restingHeartRate")
            if rhr:
                parts.append(f"resting HR {int(rhr.get('avg', 0))} bpm")

        if not parts:
            return

        briefing.health_summary = ", ".join(parts) + "."

        # Capitalize first letter
        briefing.health_summary = briefing.health_summary[0].upper() + briefing.health_summary[1:]

        briefing.sections.append(BriefingSection(
            title="Health",
            content=briefing.health_summary,
            priority=65,  # Between tasks (60) and reminders (70)
            icon="heart.fill",
        ))

    def _add_suggestions(
        self,
        briefing: Briefing,
        patterns: List[BehaviorPattern],
        now: datetime,
    ) -> None:
        """Add pattern-based suggestions to briefing."""
        # Filter to valid patterns that apply to current context
        current_day = now.weekday()
        current_hour = now.hour

        for pattern in patterns:
            if not pattern.is_valid(
                min_confidence=self.config.pattern_min_confidence,
                min_occurrences=self.config.pattern_min_occurrences,
            ):
                continue

            # Check if pattern applies to current context
            applies = False

            if pattern.pattern_type.value == "day_of_week":
                # Check if context matches current day
                day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                if any(day_names[current_day] in pattern.context.lower() for day_names in [day_names]):
                    applies = True

            elif pattern.pattern_type.value == "time_of_day":
                # Check if context matches current time period
                if current_hour < 12 and "morning" in pattern.context.lower():
                    applies = True
                elif 12 <= current_hour < 17 and "afternoon" in pattern.context.lower():
                    applies = True
                elif current_hour >= 17 and "evening" in pattern.context.lower():
                    applies = True

            if applies:
                briefing.suggestions.append(pattern.generate_suggestion())

        # Limit suggestions
        briefing.suggestions = briefing.suggestions[:3]


# Module-level singleton
_generator: Optional[BriefingGenerator] = None


def get_briefing_generator(config: Optional[ProactiveConfig] = None) -> BriefingGenerator:
    """Get or create the singleton briefing generator."""
    global _generator
    if _generator is None or config is not None:
        _generator = BriefingGenerator(config)
    return _generator
