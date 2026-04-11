"""Mission-style flight rules: declarative redlines evaluated on each telemetry frame.

These are *ground-side advisory* checks (like ops flight rules), not flight software
redundancy or vehicle-side FDIR. Extend the table as the mission model grows.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

RuleWhen = Callable[[dict[str, Any]], bool]


def _rule(
    rule_id: str,
    severity: str,
    message: str,
    when: RuleWhen,
) -> tuple[str, str, str, RuleWhen]:
    return (rule_id, severity, message, when)


# Severity: CRITICAL / WARNING / ADVISORY (ops-style; not tied to Open MCT alarms yet)
_FLIGHT_RULES: list[tuple[str, str, str, RuleWhen]] = [
    _rule(
        "FR-BATT-CRIT",
        "CRITICAL",
        "Battery below mission redline (15%).",
        lambda p: float(p.get("battery", 100.0)) < 15.0,
    ),
    _rule(
        "FR-BATT-WARN",
        "WARNING",
        "Battery below advisory threshold (25%) but above redline.",
        lambda p: 15.0 <= float(p.get("battery", 100.0)) < 25.0,
    ),
    _rule(
        "FR-THERM-WARN",
        "WARNING",
        "Thermal margin: temperature above 70 °C (at or below redline).",
        lambda p: 70.0 < float(p.get("temperature", 0.0)) <= 85.0,
    ),
    _rule(
        "FR-THERM-CRIT",
        "CRITICAL",
        "Thermal redline: temperature above 85 °C.",
        lambda p: float(p.get("temperature", 0.0)) > 85.0,
    ),
    _rule(
        "FR-LINK-WARN",
        "WARNING",
        "Telemetry loss rate elevated (>3%).",
        lambda p: float(p.get("ccsds", {}).get("loss_rate", 0.0)) > 3.0,
    ),
    _rule(
        "FR-GROUND-LOST",
        "CRITICAL",
        "Ground state machine reports LOST.",
        lambda p: str(p.get("system_state", "")).upper() == "LOST",
    ),
]


def evaluate_flight_rules(packet: dict[str, Any]) -> list[dict[str, str]]:
    """Return all violated rules for this frame (empty list = no violations)."""
    violations: list[dict[str, str]] = []
    for rule_id, severity, message, when in _FLIGHT_RULES:
        try:
            if when(packet):
                violations.append(
                    {
                        "id": rule_id,
                        "severity": severity,
                        "message": message,
                    }
                )
        except (TypeError, ValueError, KeyError) as e:
            log.debug("Flight rule %s skipped due to eval error: %s", rule_id, e)
    return violations
