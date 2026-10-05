import pytest

from intervals_mcp.dsl import Step, render_steps


def S(duration, target, kind=None, cue=None):
    return Step(duration=duration, target=target, kind=kind, cue=cue)


def test_groups_consecutive_kinds_and_separates_sections():
    out = render_steps([
        S("10m", "Z2 HR", "Warmup"),
        S("3m", "Z4 HR", "Main Set"),
        S("2m", "Z1 HR", "Recovery"),
        S("3m", "Z4 HR", "Main Set"),
        S("8m", "Z1 HR", "Cooldown"),
    ])
    assert out == (
        "Warmup\n- 10m Z2 HR\n\nMain Set\n- 3m Z4 HR\n\nRecovery\n- 2m Z1 HR\n\n"
        "Main Set\n- 3m Z4 HR\n\nCooldown\n- 8m Z1 HR"
    )


def test_unspecified_kind_continues_previous_section():
    out = render_steps([S("1m", "Z4 HR", "Main Set"), S("30s", "Z1 HR"), S("1m", "Z4 HR")])
    assert out == "Main Set\n- 1m Z4 HR\n- 30s Z1 HR\n- 1m Z4 HR"


def test_cue_goes_before_duration_and_no_header_without_kind():
    assert render_steps([S("20s", "95% HR", cue="Go!")]) == "- Go! 20s 95% HR"


def test_distance_uses_mtr():
    assert Step(duration="800mtr", target="Z4 HR").line() == "- 800mtr Z4 HR"


@pytest.mark.parametrize("bad", ["800m5", "", "fast", "10 min", "800meters", "800m"])
def test_rejects_bad_duration(bad):
    with pytest.raises(ValueError):
        Step(duration=bad, target="Z2 HR")


def test_repeat_block_gets_header_and_blank_lines():
    from intervals_mcp.dsl import Repeat

    out = render_steps([
        S("10m", "Z2 HR", "Warmup"),
        Repeat(repeat=5, kind="Main Set", steps=[S("3m", "Z4 HR"), S("2m", "Z1 HR")]),
        S("8m", "Z1 HR", "Cooldown"),
    ])
    assert out == (
        "Warmup\n- 10m Z2 HR\n\nMain Set 5x\n- 3m Z4 HR\n- 2m Z1 HR\n\nCooldown\n- 8m Z1 HR"
    )


def test_step_after_repeat_never_joins_the_block():
    from intervals_mcp.dsl import Repeat

    out = render_steps([Repeat(repeat=3, steps=[S("30s", "120%")]), S("5m", "50%")])
    assert out == "3x\n- 30s 120%\n\n- 5m 50%"


def test_repeat_needs_at_least_two_reps():
    from intervals_mcp.dsl import Repeat

    with pytest.raises(ValueError):
        Repeat(repeat=1, steps=[S("1m", "Z4 HR")])


def test_empty_workout_rejected():
    with pytest.raises(ValueError):
        render_steps([])
