"""Sequence counter gap detection."""

from __future__ import annotations

from openground.services.sequence import SequenceMonitor


def test_no_gap_first_packet() -> None:
    m = SequenceMonitor()
    stats = m.observe(0)
    assert stats["lost"] == 0
    assert stats["received"] == 1


def test_detects_gap() -> None:
    m = SequenceMonitor()
    m.observe(0)
    stats = m.observe(3)
    assert stats["lost"] == 2
    assert stats["received"] == 2
