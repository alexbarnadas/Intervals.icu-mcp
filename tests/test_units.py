import pytest

from intervals_mcp.units import mps_to_pace, pace_to_mps, pace_unit_for


def test_round_trips_run_pace():
    assert mps_to_pace(pace_to_mps("4:30/km")) == "4:30/km"


def test_matches_intervals_swim_threshold():
    # intervals.icu stored 2:00/100m as 0.8333 m/s for this athlete
    assert pace_to_mps("2:00/100m") == pytest.approx(0.8333333)
    assert mps_to_pace(0.8333333, "100m") == "2:00/100m"


def test_activity_speed_to_pace():
    # 8225 m in 3323 s
    assert mps_to_pace(2.4752781) == "6:44/km"


@pytest.mark.parametrize("bad", ["4.30/km", "4:30", "4:75/km", "0:00/km", "fast"])
def test_rejects_bad_pace(bad):
    with pytest.raises(ValueError):
        pace_to_mps(bad)


def test_unit_per_sport():
    assert pace_unit_for("TrailRun") == "km"
    assert pace_unit_for("OpenWaterSwim") == "100m"
    assert pace_unit_for("VirtualRow") == "500m"
    assert pace_unit_for("Ride") is None
