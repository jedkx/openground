"""Sequence count gap detection on the CCSDS primary header (14-bit counter)."""

from __future__ import annotations


class SequenceMonitor:
    def __init__(self) -> None:
        self.expected_seq: int | None = None
        self.lost_packets = 0
        self.received_packets = 0

    def observe(self, seq: int) -> dict:
        if self.expected_seq is not None:
            gap = (seq - self.expected_seq) & 0x3FFF
            if 0 < gap < 8192:
                self.lost_packets += gap

        self.expected_seq = (seq + 1) & 0x3FFF
        self.received_packets += 1

        total = self.received_packets + self.lost_packets
        loss_rate = 0.0 if total == 0 else (self.lost_packets / total) * 100.0
        return {
            "lost": self.lost_packets,
            "received": self.received_packets,
            "loss_rate": round(loss_rate, 2),
        }
