"""Trigger metrics monitor — configurable threshold checking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from hestia.logging import get_logger, LogComponent
from hestia.learning.models import TriggerAlert


logger = get_logger()


class TriggerMonitor:
    """Checks system metrics against configurable thresholds.

    Reads threshold definitions from config/triggers.yaml.
    Respects cooldown periods to prevent alert fatigue.
    """

    def __init__(self, learning_db: Any, config: Dict[str, Any]) -> None:
        self._learning_db = learning_db
        self._config = config

    async def check_thresholds(
        self, user_id: str, metrics: Dict[str, float]
    ) -> List[TriggerAlert]:
        """Check all configured thresholds against current metrics.

        Returns list of newly fired alerts (respects cooldown).
        """
        triggers_cfg = self._config.get("triggers", {})
        if not triggers_cfg.get("enabled", False):
            return []

        thresholds = triggers_cfg.get("thresholds", {})
        fired: List[TriggerAlert] = []

        for name, threshold_cfg in thresholds.items():
            current = metrics.get(name)
            if current is None:
                continue

            threshold_value = threshold_cfg["value"]
            direction = threshold_cfg["direction"]
            cooldown_days = threshold_cfg.get("cooldown_days", 30)

            # Check direction
            exceeded = False
            if direction == "above" and current > threshold_value:
                exceeded = True
            elif direction == "below" and current < threshold_value:
                exceeded = True

            if not exceeded:
                continue

            # Check cooldown
            last_fire = await self._learning_db.get_last_trigger_fire(user_id, name)
            if last_fire:
                cooldown_until = last_fire.timestamp + timedelta(days=cooldown_days)
                if datetime.now(timezone.utc) < cooldown_until:
                    continue

            # Fire alert
            message = threshold_cfg["message"].replace("{value}", str(current))
            alert = TriggerAlert(
                id=str(uuid.uuid4()),
                user_id=user_id,
                trigger_name=name,
                current_value=current,
                threshold_value=threshold_value,
                direction=direction,
                message=message,
                timestamp=datetime.now(timezone.utc),
            )
            await self._learning_db.store_trigger_alert(alert)
            fired.append(alert)

            logger.info(
                f"Trigger fired: {name}",
                component=LogComponent.LEARNING,
                data={
                    "trigger": name,
                    "current": current,
                    "threshold": threshold_value,
                    "direction": direction,
                },
            )

        return fired
