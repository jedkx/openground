"""LimitViolationStep — checks numeric channels against declared min/max specs."""

from __future__ import annotations


from collections.abc import Mapping, Sequence
from typing import Any

from openground.sdk.channel import ChannelSpec
from openground.sdk.enrichment import EnrichmentContext, EnrichmentStep



# --- LimitRule ABC and implementations ---
from abc import ABC, abstractmethod

class LimitRule(ABC):
    @abstractmethod
    def check(self, name: str, value: Any, spec: ChannelSpec, severity: str = "warning") -> dict[str, Any] | None:
        ...

class MinLimitRule(LimitRule):
    def check(self, name: str, value: Any, spec: ChannelSpec, severity: str = "warning") -> dict[str, Any] | None:
        if spec.min_val is not None and value < spec.min_val:
            return {"channel": name, "value": value, "min": spec.min_val, "severity": severity}
        return None

class MaxLimitRule(LimitRule):
    def check(self, name: str, value: Any, spec: ChannelSpec, severity: str = "warning") -> dict[str, Any] | None:
        if spec.max_val is not None and value > spec.max_val:
            return {"channel": name, "value": value, "max": spec.max_val, "severity": severity}
        return None


# --- LimitViolationStep as a runner ---
class LimitViolationStep(EnrichmentStep):
    """Runs configured limit rules for each channel and collects violations."""

    def __init__(
        self,
        specs: Mapping[str, ChannelSpec] | None = None,
        rules: Sequence[LimitRule] | None = None,
        severities: Mapping[str, str] | None = None,
    ) -> None:
        self._specs: Mapping[str, ChannelSpec] = specs or {}
        self._rules: Sequence[LimitRule] = rules or (MinLimitRule(), MaxLimitRule())
        self._severities: Mapping[str, str] = severities or {}

    async def apply(self, ctx: EnrichmentContext) -> None:
        violations: list[dict[str, Any]] = []
        for name, value in ctx.frame.channels.items():
            spec = self._specs.get(name)
            if spec is None:
                continue
            severity = self._severities.get(name, "warning")
            for rule in self._rules:
                result = rule.check(name, value, spec, severity)
                if result:
                    violations.append(result)
        if violations:
            ctx.envelope["limit_violations"] = violations
