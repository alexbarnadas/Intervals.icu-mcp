"""Pace conversions. intervals.icu stores pace/speed as metres per second."""
import re

_UNIT_METRES = {"km": 1000.0, "mi": 1609.344, "100m": 100.0, "100y": 91.44, "500m": 500.0}
_PACE = re.compile(r"^(\d+):([0-5]\d)\s*/\s*(km|mi|100m|100y|500m)$")


def pace_to_mps(pace: str) -> float:
    """'4:30/km' -> 3.7037 m/s. Also /mi, /100m, /100y, /500m."""
    m = _PACE.match(pace.strip().lower())
    if not m:
        raise ValueError(
            f"Bad pace {pace!r}. Use mm:ss/unit, e.g. '4:30/km', '7:15/mi', '1:50/100m'."
        )
    secs = int(m[1]) * 60 + int(m[2])
    if secs == 0:
        raise ValueError("pace must be greater than 0:00")
    return _UNIT_METRES[m[3]] / secs


def mps_to_pace(mps: float | None, unit: str = "km") -> str | None:
    """3.7037 m/s -> '4:30/km'. None/0 -> None."""
    if not mps:
        return None
    secs = round(_UNIT_METRES[unit] / mps)
    return f"{secs // 60}:{secs % 60:02d}/{unit}"


def pace_unit_for(sport: str | None) -> str | None:
    """Which pace unit reads naturally for a sport, or None if pace isn't meaningful."""
    s = (sport or "").lower()
    if "swim" in s:
        return "100m"
    if "row" in s:
        return "500m"
    if any(k in s for k in ("run", "walk", "hike", "ski", "snowshoe")):
        return "km"
    return None
