"""
Health analysis tools for registration with execution layer.

Provides Tool definitions for querying health data synced from iOS HealthKit.
These tools let the user ask about their health data in chat.
"""

from typing import Any, Dict, List, Optional

from ..execution.models import Tool, ToolParam, ToolParamType
from ..execution.registry import ToolRegistry


# ============================================================================
# Health Tool Handlers
# ============================================================================

async def get_health_summary(
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Get today's health summary."""
    from .manager import get_health_manager

    manager = await get_health_manager()
    return await manager.get_daily_summary(date)


async def get_health_trend(
    metric: str,
    days: int = 7,
) -> Dict[str, Any]:
    """Get trend data for a health metric."""
    from .manager import get_health_manager

    manager = await get_health_manager()
    return await manager.get_metric_trend(metric, days)


async def get_sleep_analysis(
    days: int = 7,
) -> Dict[str, Any]:
    """Get sleep analysis."""
    from .manager import get_health_manager

    manager = await get_health_manager()
    return await manager.get_sleep_analysis(days)


async def get_activity_report(
    days: int = 7,
) -> Dict[str, Any]:
    """Get activity report."""
    from .manager import get_health_manager

    manager = await get_health_manager()
    return await manager.get_activity_summary(days)


async def get_vitals() -> Dict[str, Any]:
    """Get latest vital signs."""
    from .manager import get_health_manager

    manager = await get_health_manager()
    return await manager.get_latest_vitals()


# ============================================================================
# Tool Definitions
# ============================================================================

def get_health_tools() -> List[Tool]:
    """Get health data analysis tools."""
    return [
        Tool(
            name="get_health_summary",
            description="Get today's health summary including steps, calories, heart rate, sleep, and more",
            parameters={
                "date": ToolParam(
                    type=ToolParamType.STRING,
                    description="Date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            },
            handler=get_health_summary,
            category="health",
        ),
        Tool(
            name="get_health_trend",
            description="Get trend data for a specific health metric over time",
            parameters={
                "metric": ToolParam(
                    type=ToolParamType.STRING,
                    description="Metric type (e.g., stepCount, heartRate, bodyMass, sleepAnalysis)",
                    required=True,
                    enum=[
                        "stepCount", "distanceWalkingRunning", "activeEnergyBurned",
                        "appleExerciseTime", "flightsClimbed", "vo2Max",
                        "heartRate", "restingHeartRate", "heartRateVariabilitySDNN",
                        "bodyMass", "bodyMassIndex", "bodyFatPercentage",
                        "sleepAnalysis", "mindfulSession",
                        "dietaryEnergyConsumed", "dietaryProtein",
                        "dietaryCarbohydrates", "dietaryWater",
                        "oxygenSaturation", "respiratoryRate",
                    ],
                ),
                "days": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Number of days to look back (default: 7)",
                    required=False,
                    default=7,
                ),
            },
            handler=get_health_trend,
            category="health",
        ),
        Tool(
            name="get_sleep_analysis",
            description="Get sleep analysis including duration, stages, and consistency over a period",
            parameters={
                "days": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Number of days to analyze (default: 7)",
                    required=False,
                    default=7,
                ),
            },
            handler=get_sleep_analysis,
            category="health",
        ),
        Tool(
            name="get_activity_report",
            description="Get activity report including steps, distance, calories, and exercise minutes",
            parameters={
                "days": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Number of days to report on (default: 7)",
                    required=False,
                    default=7,
                ),
            },
            handler=get_activity_report,
            category="health",
        ),
        Tool(
            name="get_vitals",
            description="Get latest vital signs including heart rate, blood pressure, SpO2, and respiratory rate",
            parameters={},
            handler=get_vitals,
            category="health",
        ),
    ]


def register_health_tools(registry: ToolRegistry) -> int:
    """
    Register health tools with a tool registry.

    Args:
        registry: ToolRegistry to register tools with.

    Returns:
        Number of tools registered.
    """
    tools = get_health_tools()
    count = 0
    for tool in tools:
        registry.register(tool)
        count += 1
    return count
