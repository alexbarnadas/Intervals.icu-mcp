"""Render a list of typed steps (and optional repeat blocks) into intervals.icu's workout text.

The server has no canned workout shapes: Claude expands pyramids, progressions etc.
into explicit steps itself, so this only needs to render and validate.
"""
import re

from pydantic import BaseModel, Field, field_validator

# 30s, 10m (minutes), 1h30m, 800mtr, 2km, 1.5mi
_DURATION = re.compile(r"^(?:(?:\d+h)?(?:\d+m)?(?:\d+s)?|\d+(?:\.\d+)?(?:mtr|km|mi))$")
_TIME = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
_MAX_STEP_SECS = 5 * 3600  # catches '800m' typed for 800 metres


class Step(BaseModel):
    duration: str  # "10m" (minutes), "90s", "800mtr", "2km"
    target: str    # "Z2 HR", "75%", "200w", "85% Pace", "ramp 50%-75%"
    kind: str | None = None  # section label, e.g. "Warmup", "Main Set", "Recovery", "Cooldown"
    cue: str | None = None   # text shown on the watch for this step

    @field_validator("duration")
    @classmethod
    def _check_duration(cls, v: str) -> str:
        v = v.strip()
        if v and (m := _TIME.fullmatch(v)):
            h, mi, sec = (int(g) if g else 0 for g in m.groups())
            if h * 3600 + mi * 60 + sec > _MAX_STEP_SECS:
                raise ValueError(
                    f"{v!r} is over {_MAX_STEP_SECS // 3600}h for one step. Did you mean "
                    "metres? Use 'mtr' for distance ('800mtr'); 'm' means minutes."
                )
        if not v or not _DURATION.match(v):
            raise ValueError(
                f"Bad duration {v!r}. Use 30s, 10m (minutes!), 1h30m, or 800mtr/2km/1mi "
                "for distance — 'm' alone always means minutes."
            )
        return v

    def line(self) -> str:
        return " ".join(p for p in ("-", self.cue, self.duration, self.target) if p)


class Repeat(BaseModel):
    """A block of steps done `repeat` times; shown on the watch as e.g. 'Main Set 2/5'."""

    repeat: int = Field(ge=2)
    steps: list[Step] = Field(min_length=1)
    kind: str | None = None  # label for the block, e.g. "Main Set"


def render_steps(steps: list[Step | Repeat]) -> str:
    """Consecutive steps sharing a `kind` go under one header; sections are blank-line
    separated. A Repeat is always its own section (the parser needs blank lines around it)."""
    if not steps:
        raise ValueError("a workout needs at least one step")
    sections: list[tuple[str | None, list[str]]] = []
    prev_repeat = False
    for s in steps:
        if isinstance(s, Repeat):
            head = f"{s.kind} {s.repeat}x" if s.kind else f"{s.repeat}x"
            sections.append((head, [st.line() for st in s.steps]))
            prev_repeat = True
            continue
        if not sections or prev_repeat or (s.kind is not None and s.kind != sections[-1][0]):
            sections.append((s.kind, []))
        sections[-1][1].append(s.line())
        prev_repeat = False
    return "\n\n".join(
        (f"{head}\n" if head else "") + "\n".join(lines) for head, lines in sections
    )
