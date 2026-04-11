"""Load and sample a milestone JSON timeline (MET in seconds, linear interpolation).

Milestone rows need ``t_met_s``, ``label``, ``alt_km_approx``, ``v_kms_approx``;
optional fields map to telemetry via ``_OPTIONAL_LERP``. Put citation paths in ``refs``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

# JSON field suffix on knots → scalar output keys on :meth:`MilestoneTimeline.sample`.
_OPTIONAL_LERP: tuple[tuple[str, str], ...] = (
    ("temperature_c_approx", "temperature_c"),
    ("battery_pct_approx", "battery_pct"),
    ("lat_deg_approx", "lat_deg"),
    ("lon_deg_approx", "lon_deg"),
    ("met_phase_index", "met_phase_index"),
    ("earth_range_km_approx", "earth_range_km"),
    ("moon_range_km_approx", "moon_range_km"),
    ("accel_proxy_mps2_approx", "accel_proxy_mps2"),
)


def _as_float(x: Any, field: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError(f"{field} must be a number")
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"{field} must be finite")
    return v


def _as_opt_float(x: Any, field: str) -> float | None:
    if x is None:
        return None
    return _as_float(x, field)


def _as_opt_int(x: Any, field: str) -> int | None:
    if x is None:
        return None
    if isinstance(x, bool):
        raise TypeError(f"{field} must be an int or null")
    if isinstance(x, int):
        return int(x)
    if isinstance(x, float) and x.is_integer():
        return int(x)
    raise TypeError(f"{field} must be an int or null")


def _as_opt_str(x: Any, field: str) -> str | None:
    if x is None:
        return None
    if not isinstance(x, str) or not x.strip():
        raise ValueError(f"{field} must be a non-empty string or null")
    return x.strip()


def _validate_milestone(row: dict[str, Any], index: int) -> dict[str, Any]:
    prefix = f"milestones[{index}]"
    label = row.get("label")
    if not isinstance(label, str) or not label.strip():
        raise ValueError(f"{prefix}.label must be a non-empty string")
    refs = row.get("refs")
    if not isinstance(refs, list) or len(refs) == 0:
        raise ValueError(f"{prefix}.refs must be a non-empty list")
    for j, r in enumerate(refs):
        if not isinstance(r, str) or not r.strip():
            raise ValueError(f"{prefix}.refs[{j}] must be a non-empty string")
    out: dict[str, Any] = {
        "t_met_s": _as_float(row.get("t_met_s"), f"{prefix}.t_met_s"),
        "label": label.strip(),
        "alt_km_approx": _as_float(row.get("alt_km_approx"), f"{prefix}.alt_km_approx"),
        "v_kms_approx": _as_float(row.get("v_kms_approx"), f"{prefix}.v_kms_approx"),
        "refs": [str(r).strip() for r in refs],
    }
    if row.get("phase_code") is not None:
        out["phase_code"] = _as_opt_str(row.get("phase_code"), f"{prefix}.phase_code")
    for jk, _ok in _OPTIONAL_LERP:
        if jk in row and row[jk] is not None:
            out[jk] = _as_opt_float(row.get(jk), f"{prefix}.{jk}")
    return out


def load_milestone_document(path: Path | str) -> tuple[str | None, list[dict[str, Any]]]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("timeline JSON root must be an object")
    disclaimer = raw.get("_disclaimer")
    if disclaimer is not None and not isinstance(disclaimer, str):
        raise ValueError("_disclaimer must be a string or omitted")
    milestones = raw.get("milestones")
    if not isinstance(milestones, list) or len(milestones) < 2:
        raise ValueError("milestones must be an array with at least two entries")
    cleaned: list[dict[str, Any]] = []
    for i, row in enumerate(milestones):
        if not isinstance(row, dict):
            raise ValueError(f"milestones[{i}] must be an object")
        cleaned.append(_validate_milestone(row, i))
    cleaned.sort(key=lambda m: m["t_met_s"])
    t0 = cleaned[0]["t_met_s"]
    if t0 != 0.0:
        raise ValueError("first milestone must have t_met_s == 0")
    for a, b in zip(cleaned, cleaned[1:], strict=False):
        if b["t_met_s"] <= a["t_met_s"]:
            raise ValueError("t_met_s must be strictly increasing after the first knot")
    last_t = cleaned[-1]["t_met_s"]
    if last_t <= 0.0:
        raise ValueError("last milestone t_met_s must be > 0 (cycle duration)")
    return (str(disclaimer).strip() if isinstance(disclaimer, str) else None, cleaned)


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def _lerp_optional(
    a: dict[str, Any],
    b: dict[str, Any],
    key: str,
    u: float,
) -> float | None:
    av = a.get(key)
    bv = b.get(key)
    if av is None and bv is None:
        return None
    if av is None:
        return float(bv)
    if bv is None:
        return float(av)
    return _lerp(float(av), float(bv), u)


def _mission_event_label(milestones: list[dict[str, Any]], t_met_s: float) -> str:
    label = milestones[0]["label"]
    for m in milestones:
        if float(m["t_met_s"]) <= t_met_s:
            label = str(m["label"])
        else:
            break
    return label


def _phase_code(milestones: list[dict[str, Any]], t_met_s: float) -> str | None:
    code: str | None = None
    for m in milestones:
        if float(m["t_met_s"]) <= t_met_s:
            pc = m.get("phase_code")
            if isinstance(pc, str) and pc.strip():
                code = pc.strip()
        else:
            break
    return code


def _merge_optional_lerped(
    out: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
    u: float,
) -> None:
    for json_key, out_key in _OPTIONAL_LERP:
        v = _lerp_optional(left, right, json_key, u)
        if v is not None:
            out[out_key] = float(v)


def _merge_optional_knot(out: dict[str, Any], knot: dict[str, Any]) -> None:
    for json_key, out_key in _OPTIONAL_LERP:
        if knot.get(json_key) is not None:
            out[out_key] = float(knot[json_key])


class MilestoneTimeline:
    """Piecewise-linear timeline in mission elapsed seconds (demo clock)."""

    def __init__(self, milestones: list[dict[str, Any]], disclaimer: str | None = None) -> None:
        self._milestones = milestones
        self.disclaimer = disclaimer

    @classmethod
    def from_path(cls, path: Path | str) -> MilestoneTimeline:
        disclaimer, milestones = load_milestone_document(path)
        return cls(milestones, disclaimer)

    @property
    def cycle_duration_s(self) -> float:
        return float(self._milestones[-1]["t_met_s"])

    def sample(self, t_met_s: float) -> dict[str, Any]:
        if not math.isfinite(t_met_s):
            raise ValueError("t_met_s must be finite")
        duration = self.cycle_duration_s
        t = float(t_met_s) % duration
        if t < 0:
            t += duration
        pts = self._milestones
        if t <= pts[0]["t_met_s"]:
            return self._at_knot(pts[0], position_t=t)

        for left, right in zip(pts, pts[1:], strict=False):
            if t <= right["t_met_s"]:
                span = float(right["t_met_s"]) - float(left["t_met_s"])
                u = 0.0 if span <= 0.0 else (t - float(left["t_met_s"])) / span
                u = min(1.0, max(0.0, u))
                alt_km = _lerp(float(left["alt_km_approx"]), float(right["alt_km_approx"]), u)
                v_kms = _lerp(float(left["v_kms_approx"]), float(right["v_kms_approx"]), u)
                out: dict[str, Any] = {
                    "t_met_s": t,
                    "altitude_m": alt_km * 1000.0,
                    "velocity_mps": v_kms * 1000.0,
                    "mission_event": _mission_event_label(pts, t),
                    "phase_code": _phase_code(pts, t),
                }
                _merge_optional_lerped(out, left, right, u)
                return out

        return self._at_knot(pts[-1], position_t=t)

    def _at_knot(self, knot: dict[str, Any], position_t: float) -> dict[str, Any]:
        out: dict[str, Any] = {
            "t_met_s": position_t,
            "altitude_m": float(knot["alt_km_approx"]) * 1000.0,
            "velocity_mps": float(knot["v_kms_approx"]) * 1000.0,
            "mission_event": _mission_event_label(self._milestones, position_t),
            "phase_code": _phase_code(self._milestones, position_t),
        }
        _merge_optional_knot(out, knot)
        return out
