"""OpenGround adapter SDK — public surface for third-party adapter authors."""

from openground.sdk.adapter import TelemetryAdapter
from openground.sdk.channel import ChannelSpec
from openground.sdk.enrichment import EnrichmentContext, EnrichmentStep
from openground.sdk.frame import EnrichedFrame, TelemetryFrame
from openground.sdk.store import TelemetryStore

__all__ = [
    "TelemetryAdapter",
    "ChannelSpec",
    "TelemetryFrame",
    "EnrichedFrame",
    "EnrichmentStep",
    "EnrichmentContext",
    "TelemetryStore",
]
