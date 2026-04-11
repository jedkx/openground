"""Milestone timeline loader and interpolation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from openground.services.milestone_timeline import MilestoneTimeline, load_milestone_document


def test_interpolation_midpoint(tmp_path: Path) -> None:
    p = tmp_path / "milestones.json"
    p.write_text(
        json.dumps(
            {
                "milestones": [
                    {
                        "t_met_s": 0,
                        "label": "A",
                        "alt_km_approx": 0,
                        "v_kms_approx": 0,
                        "temperature_c_approx": 0,
                        "refs": ["README.md"],
                    },
                    {
                        "t_met_s": 100,
                        "label": "B",
                        "alt_km_approx": 10,
                        "v_kms_approx": 1,
                        "temperature_c_approx": 100,
                        "refs": ["README.md"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    tl = MilestoneTimeline.from_path(p)
    s = tl.sample(50.0)
    assert s["altitude_m"] == pytest.approx(5000.0)
    assert s["velocity_mps"] == pytest.approx(500.0)
    assert s["temperature_c"] == pytest.approx(50.0)
    assert s["mission_event"] == "A"


def test_sample_wraps_by_cycle_duration(tmp_path: Path) -> None:
    p = tmp_path / "milestones.json"
    p.write_text(
        json.dumps(
            {
                "milestones": [
                    {
                        "t_met_s": 0,
                        "label": "A",
                        "alt_km_approx": 0,
                        "v_kms_approx": 0,
                        "refs": ["README.md"],
                    },
                    {
                        "t_met_s": 10,
                        "label": "B",
                        "alt_km_approx": 0,
                        "v_kms_approx": 0,
                        "refs": ["README.md"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    tl = MilestoneTimeline.from_path(p)
    assert tl.sample(25.0)["altitude_m"] == pytest.approx(tl.sample(5.0)["altitude_m"])


def test_bundled_milestone_file_loads() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "data" / "demo_documented_milestones.json"
    disclaimer, milestones = load_milestone_document(path)
    assert len(milestones) >= 2
    assert disclaimer
    tl = MilestoneTimeline(milestones, disclaimer)
    assert tl.cycle_duration_s > 0
    sample = tl.sample(0.0)
    assert sample["altitude_m"] == pytest.approx(0.0)
    assert "mission_event" in sample
    assert sample.get("phase_code") == "LAUNCH"
