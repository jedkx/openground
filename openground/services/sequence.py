from __future__ import annotations

from openground.ccsds import SEQ_MASK

_HALF = SEQ_MASK // 2  # gaps >= half the counter space are treated as wrap-around, not loss


class SequenceMonitor:
    def __init__(self) -> None:
        self.expected_seq: int | None = None
        self.lost_packets = 0
        self.received_packets = 0

    def observe(self, seq: int) -> dict:
        if self.expected_seq is not None:
            gap = (seq - self.expected_seq) & SEQ_MASK
            if 0 < gap < _HALF:
                self.lost_packets += gap

        self.expected_seq = (seq + 1) & SEQ_MASK
        self.received_packets += 1

        total = self.received_packets + self.lost_packets
        loss_rate = 0.0 if total == 0 else (self.lost_packets / total) * 100.0
        return {
            "lost": self.lost_packets,
            "received": self.received_packets,
            "loss_rate": round(loss_rate, 2),
        }
