"""OpenGround adapter SDK — public surface for third-party adapter authors."""

from openground.sdk.adapter import TelemetryAdapter
from openground.sdk.channel import ChannelSpec
from openground.sdk.frame import EnrichedFrame, TelemetryFrame

__all__ = ["TelemetryAdapter", "ChannelSpec", "TelemetryFrame", "EnrichedFrame"]
