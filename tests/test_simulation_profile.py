"""Named simulation profiles."""

from __future__ import annotations

from openground.simulation_profile import PRESETS, get_profile


def test_get_profile_nominal() -> None:
    p = get_profile("nominal")
    assert p.name == "nominal"
    assert p.thrust_n == 1500.0


def test_get_profile_unknown_falls_back() -> None:
    p = get_profile("nope")
    assert p.name == "nominal"


def test_presets_cover_scenarios() -> None:
    assert {"nominal", "sport", "gentle", "stress"} <= PRESETS.keys()
