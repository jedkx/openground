"""CcsdsStep — parses raw CCSDS bytes and adds apid/size fields to ccsds metadata."""

from __future__ import annotations

import logging

from openground.ccsds import parse_packet
from openground.sdk.enrichment import EnrichmentContext, EnrichmentStep

log = logging.getLogger(__name__)


class CcsdsStep(EnrichmentStep):
    """When the frame carries raw bytes, parses the CCSDS header and enriches ccsds dict."""

    async def apply(self, ctx: EnrichmentContext) -> None:
        if ctx.frame.raw_bytes is None:
            return
        ccsds = ctx.envelope.setdefault("ccsds", {})
        ccsds["size"] = len(ctx.frame.raw_bytes)
        try:
            ccsds["apid"] = parse_packet(ctx.frame.raw_bytes)["header"]["apid"]
        except Exception:
            log.debug("CCSDS parse failed for frame seq=%d", ctx.frame.seq)
