from datetime import date, timedelta
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .auth import load_auth
from .client import IntervalsClient
from .dsl import Repeat, Step, render_steps
from .units import mps_to_pace, pace_to_mps, pace_unit_for

mcp = FastMCP("intervals-icu")
_client: IntervalsClient | None = None


def client() -> IntervalsClient:
    global _client
    if _client is None:
        _client = IntervalsClient(load_auth())
    return _client


def _pick(d: dict, fields: tuple[str, ...]) -> dict:
    return {k: d[k] for k in fields if k in d}


_ACTIVITY_FIELDS = (
    "id", "start_date_local", "type", "name", "distance", "moving_time",
    "icu_training_load", "icu_average_watts", "average_heartrate",
    "paired_event_id",
)
_EVENT_FIELDS = (
    "id", "start_date_local", "end_date_local", "category", "type", "name", "description",
    "moving_time", "distance_target", "icu_training_load", "indoor", "target", "tags",
    "push_errors",
)
_WELLNESS_FIELDS = (
    "id", "ctl", "atl", "rampRate", "restingHR", "hrv", "sleepSecs", "sleepScore",
    "sleepQuality", "weight", "soreness", "fatigue", "stress", "mood", "motivation",
    "injury", "readiness", "comments",
)
_SPORT_FIELDS = (
    "types", "ftp", "indoor_ftp", "lthr", "max_hr", "threshold_pace", "pace_units",
    "hr_zones", "hr_zone_names", "power_zones", "power_zone_names", "pace_zones",
    "pace_zone_names",
)

# ---------------------------------------------------------------- read ---


@mcp.tool()
async def get_athlete_profile() -> dict:
    """Athlete name and per-sport thresholds and zones (FTP, threshold pace, LTHR, max HR).

    Call this before planning so targets like '% FTP' or '% Pace' make sense. A null
    threshold means that kind of target is meaningless for the sport; use another one.
    HR and power zone arrays are the upper bound of each zone (power as % of FTP).
    threshold_pace is shown as mm:ss per km / 100m / 500m.
    """
    profile = await client().get("/athlete/0")
    sports = []
    for s in await client().get("/athlete/0/sport-settings"):
        row = _pick(s, _SPORT_FIELDS)
        row.pop("pace_units", None)
        unit = pace_unit_for(s["types"][0] if s.get("types") else None) or "km"
        row["threshold_pace"] = mps_to_pace(s.get("threshold_pace"), unit)
        sports.append(row)
    return {"name": profile.get("name"), "sports": sports}


@mcp.tool()
async def get_fitness(oldest: str, newest: str) -> list[dict]:
    """Daily fitness (ctl), fatigue (atl), plus HRV/sleep/RHR for a date range (YYYY-MM-DD).

    TSB (form) = ctl - atl. Use to judge how hard the next block can be. Subjective
    fields (soreness, fatigue, stress, mood, motivation, injury, sleepQuality) are 1-4,
    where 1 is the good end. Null fields were simply not recorded.
    """
    data = await client().get("/athlete/0/wellness", oldest=oldest, newest=newest)
    return [_pick(w, _WELLNESS_FIELDS) for w in data]


@mcp.tool()
async def list_activities(oldest: str, newest: str | None = None, limit: int = 50) -> list[dict]:
    """Completed activities between two dates (YYYY-MM-DD). Distance in metres, time in seconds.

    Some activities (typically ones imported from Strava) come back as bare stubs with only
    an id and date, because intervals.icu withholds their data. Don't treat those as rest days.
    """
    data = await client().get("/athlete/0/activities", oldest=oldest, newest=newest, limit=limit)
    return [_pick(a, _ACTIVITY_FIELDS) for a in data]


_DETAIL_FIELDS = (
    "id", "start_date_local", "type", "name", "description", "distance", "moving_time",
    "elapsed_time", "total_elevation_gain", "icu_training_load", "trimp",
    "average_heartrate", "max_heartrate", "average_cadence", "icu_average_watts",
    "icu_weighted_avg_watts", "icu_intensity", "decoupling", "icu_efficiency_factor",
    "icu_rpe", "feel", "paired_event_id",
    "average_weather_temp", "min_weather_temp", "max_weather_temp", "average_feels_like",
    "max_feels_like", "average_temp",
)
_INTERVAL_FIELDS = (
    "type", "label", "start_time", "moving_time", "distance", "average_heartrate",
    "max_heartrate", "average_watts", "intensity", "zone", "average_cadence", "decoupling",
)


def _zone_minutes(secs: list | None) -> list[float] | None:
    return [round(s / 60, 1) for s in secs] if secs else None


@mcp.tool()
async def get_activity_detail(activity_id: str) -> dict:
    """How a completed activity actually went: summary, detected intervals, time in zones,
    RPE/feel and the weather during it. Use to judge execution vs the plan, e.g. whether
    the athlete hit the targets, faded, or suffered in heat.

    Paces are mm:ss per km (per 100m for swims, 500m for rows). Zone time is minutes per
    zone (Z1 first). average_weather_temp/feels_like are °C from the weather service;
    average_temp is the device sensor (often skewed by body heat). icu_rpe is 1-10;
    decoupling (%) is HR drift vs pace/power (>5% suggests fatigue, heat or low aerobic base).
    """
    a = await client().get(f"/activity/{activity_id}", intervals="true")
    if not a.get("type"):
        return {"id": activity_id, "note": "No data: activities imported from Strava are "
                "withheld by intervals.icu's API. Only the date is available."}
    out = _pick(a, _DETAIL_FIELDS)
    unit = pace_unit_for(a.get("type"))
    if unit:
        out["pace"] = mps_to_pace(a.get("pace") or a.get("average_speed"), unit)
        out["gap"] = mps_to_pace(a.get("gap"), unit)  # gradient-adjusted pace
    out["minutes_in_hr_zones"] = _zone_minutes(a.get("icu_hr_zone_times"))
    if a.get("icu_zone_times"):
        out["minutes_in_power_zones"] = _zone_minutes(
            [z.get("secs", 0) if isinstance(z, dict) else z for z in a["icu_zone_times"]]
        )
    if a.get("pace_zone_times"):
        out["minutes_in_pace_zones"] = _zone_minutes(a["pace_zone_times"])
    intervals = []
    for iv in a.get("icu_intervals") or []:
        if (iv.get("moving_time") or 0) < 5:  # end-of-file fragments, meaningless pace
            continue
        row = _pick(iv, _INTERVAL_FIELDS)
        if unit:
            row["pace"] = mps_to_pace(iv.get("average_speed"), unit)
        intervals.append({k: v for k, v in row.items() if v is not None})
    out["intervals"] = intervals
    return {k: v for k, v in out.items() if v is not None}


@mcp.tool()
async def list_planned_workouts(oldest: str, newest: str) -> list[dict]:
    """Calendar events (planned workouts, races, notes) between two dates (YYYY-MM-DD).

    Other tools may also write plans into this calendar, so check it before adding workouts.
    A non-empty `push_errors` means the workout failed to sync to a device service
    (e.g. Garmin); tell the athlete and show the message.
    """
    data = await client().get("/athlete/0/events", oldest=oldest, newest=newest)
    return [_pick(e, _EVENT_FIELDS) for e in data]


def _wx(p: dict) -> dict:
    out = _pick(p, ("id", "temp", "feels_like", "humidity", "dew_point", "wind_speed",
                    "wind_gust", "rain", "snow", "clouds", "sunrise", "sunset"))
    if p.get("weather"):
        out["summary"] = p["weather"][0].get("description")
    return out


@mcp.tool()
async def get_weather_forecast(date: str | None = None) -> list[dict]:
    """Weather forecast at the athlete's configured location(s): ~14 days daily, ~5 days 3-hourly.

    Temperatures in °C; wind as reported by the provider (OpenWeather). Heat, humidity
    (dew point above ~18°C is oppressive) and wind change how hard a session feels and
    what targets are realistic: when planning, consider moving key sessions to cooler
    hours/days, going indoor, lowering pace targets or using HR targets in heat.
    Pass `date` (YYYY-MM-DD) to also get that day's 3-hourly forecast.
    """
    data = await client().get("/athlete/0/weather-forecast")
    out = []
    for f in data.get("forecasts", []):
        loc = {"location": f.get("label") or f.get("location"), "error": f.get("error")}
        loc["daily"] = [_wx(d) for d in f.get("daily") or []]
        if date:
            loc["hourly"] = [_wx(h) for h in f.get("hourly") or [] if h.get("id", "").startswith(date)]
        out.append(loc)
    if not out:
        return [{"error": "No forecast location set; the athlete can add one in intervals.icu settings."}]
    return out


# --------------------------------------------------------------- write ---

# Activity types intervals.icu accepts (from its OpenAPI spec).
Sport = Literal[
    "Ride", "Run", "Swim", "WeightTraining", "Hike", "Walk", "AlpineSki", "BackcountrySki",
    "Badminton", "Canoeing", "Crossfit", "EBikeRide", "EMountainBikeRide", "Elliptical", "Golf",
    "GravelRide", "TrackRide", "Handcycle", "HighIntensityIntervalTraining", "Hockey",
    "IceSkate", "InlineSkate", "Kayaking", "Kitesurf", "MountainBikeRide", "Cyclocross",
    "NordicSki", "OpenWaterSwim", "Padel", "Pilates", "Pickleball", "Racquetball", "Rugby",
    "RockClimbing", "RollerSki", "Rowing", "Sail", "Skateboard", "Snowboard", "Snowshoe",
    "Soccer", "Squash", "StairStepper", "StandUpPaddling", "Surfing", "TableTennis", "Tennis",
    "TrailRun", "Transition", "Velomobile", "VirtualRide", "VirtualRow", "VirtualRun",
    "VirtualSki", "WaterSport", "Wheelchair", "Windsurf", "Workout", "Yoga", "Other",
]


def _start(d: str) -> str:
    return d if "T" in d else f"{d}T07:00:00"


class Workout(BaseModel):
    start: str  # 'YYYY-MM-DD' (07:00 default) or 'YYYY-MM-DDTHH:MM:SS'
    sport: Sport
    name: str
    steps: list[Step | Repeat] = []
    notes: str | None = None
    indoor: bool | None = None
    target: Literal["AUTO", "POWER", "HR", "PACE"] | None = None
    carbs_per_hour: int | None = None
    tags: list[str] | None = None
    commute: bool = False
    duration_secs: int | None = None  # only for sessions without steps
    distance_m: float | None = None   # only for sessions without steps


def _event(w: Workout) -> dict:
    parts = [render_steps(w.steps)] if w.steps else []
    if w.notes:
        parts.append(w.notes)  # after the steps so it isn't parsed as a section header
    body = {
        "start_date_local": _start(w.start),
        "category": "WORKOUT",
        "type": w.sport,
        "name": w.name,
        "description": "\n\n".join(parts),
    }
    optional = {
        "indoor": w.indoor, "target": w.target, "carbs_per_hour": w.carbs_per_hour,
        "tags": w.tags, "sub_type": "COMMUTE" if w.commute else None,
        "moving_time": None if w.steps else w.duration_secs,
        "distance_target": None if w.steps else w.distance_m,
    }
    body.update({k: v for k, v in optional.items() if v is not None})
    return body


@mcp.tool()
async def create_workouts(workouts: list[Workout], dry_run: bool = False) -> list[dict]:
    """Plan one or many workouts on the calendar (write). Pass several for a week or block.

    A workout is {start, sport, name, steps, notes?, indoor?, target?, carbs_per_hour?,
    tags?, commute?, duration_secs?, distance_m?}. There are no canned shapes: build any
    session (pyramid, progression, over-unders...) from steps.
    Each step is {duration, target, kind?, cue?}:
      duration: '30s', '10m' (m = MINUTES), '1h30m', or distance '800mtr' / '2km' / '1mi'.
      target:   '75%' (of FTP, cycling), '200w' / '200-240w', 'Z2', '70% HR', 'Z2 HR',
                '95% LTHR', '80% Pace', '5:00/km Pace', 'ramp 50%-75%'. Cadence can be
                appended: '90rpm'. For running, prefer HR zones unless a threshold pace is set.
      kind:     section label. 'Warmup' and 'Cooldown' are recognised by intervals.icu and
                flagged as such on the device; other labels ('Main Set', 'Recovery'...) are
                display text. Consecutive steps with the same kind share one header; a step
                with no kind joins the previous section.
      cue:      optional text shown on the watch for that step.
    A step can also be a repeat block {repeat: N, steps: [...], kind?} for identical
    repetitions (e.g. 5x [3m Z4 HR, 2m Z1 HR]). Prefer it over writing the same steps out
    N times: it is compact on the watch and devices limit total steps (~50).
    target: which metric the device should follow when steps mix power/HR/pace.
    Sessions without structure (e.g. 'easy hike', strength class) may omit steps and give
    duration_secs/distance_m instead. notes is free text shown with the workout.
    dry_run=true returns the generated text without touching the calendar.
    """
    events = [_event(w) for w in workouts]
    if dry_run:
        return [
            {"name": e["name"], "start_date_local": e["start_date_local"],
             "description": e["description"]}
            for e in events
        ]
    if len(events) == 1:
        return [_pick(await client().post("/athlete/0/events", json=events[0]), _EVENT_FIELDS)]
    data = await client().post("/athlete/0/events/bulk", json=events)
    return [_pick(e, _EVENT_FIELDS) for e in data]


@mcp.tool()
async def create_calendar_entry(
    category: Literal["RACE_A", "RACE_B", "RACE_C", "NOTE", "HOLIDAY", "SICK", "INJURED"],
    start: str,
    name: str,
    end: str | None = None,
    sport: Sport | None = None,
    description: str | None = None,
    distance_m: float | None = None,
) -> dict:
    """Add a non-workout entry to the calendar (write).

    RACE_A/B/C: a race by priority (A = season goal, taper for it; C = training race).
      Give sport and, if known, distance_m.
    NOTE: free-text note on a day. HOLIDAY / SICK / INJURED: days the athlete can't train
      normally; pass `end` (YYYY-MM-DD, last day) for multi-day periods.
    start: 'YYYY-MM-DD' or full ISO datetime.
    """
    body = {"category": category, "start_date_local": _start(start), "name": name}
    if end:
        # intervals.icu's end is exclusive: a period ending on day X ends at X+1 00:00.
        last = date.fromisoformat(end[:10])
        body["end_date_local"] = f"{last + timedelta(days=1)}T00:00:00"
    optional = {"type": sport, "description": description, "distance_target": distance_m}
    body.update({k: v for k, v in optional.items() if v is not None})
    return _pick(await client().post("/athlete/0/events", json=body), _EVENT_FIELDS)


@mcp.tool()
async def update_planned_workout(
    event_id: int, changes: dict | None = None, steps: list[Step | Repeat] | None = None
) -> dict:
    """Change an existing planned workout (write). `changes` sets raw event fields, e.g.
    reschedule with {"start_date_local": "2026-10-09T07:00:00"} or {"name": "..."}.
    `steps` replaces the workout content (same step format as create_workouts)."""
    body = dict(changes or {})
    if steps is not None:
        body["description"] = render_steps(steps)
    return _pick(await client().put(f"/athlete/0/events/{event_id}", json=body), _EVENT_FIELDS)


@mcp.tool()
async def delete_planned_workout(event_id: int) -> str:
    """Delete a planned workout from the calendar (write, irreversible)."""
    await client().delete(f"/athlete/0/events/{event_id}")
    return f"Deleted event {event_id}"


@mcp.tool()
async def update_sport_settings(
    sport: str,
    ftp: int | None = None,
    indoor_ftp: int | None = None,
    lthr: int | None = None,
    max_hr: int | None = None,
    threshold_pace: str | None = None,
    recalc_hr_zones: bool = False,
) -> dict:
    """Change an athlete's thresholds for one sport (write; affects all future targets).

    sport: an activity type the settings cover, e.g. 'Run', 'Ride', 'Swim'.
    threshold_pace: 'mm:ss/km', 'mm:ss/mi', 'mm:ss/100m' (swim) or 'mm:ss/500m' (row).
    recalc_hr_zones=true rebuilds the HR zones from the new lthr/max_hr.
    Only pass fields the athlete explicitly gave or agreed to; confirm before changing.
    Past activities keep their old zones.
    """
    body: dict = {}
    for k, v in {"ftp": ftp, "indoor_ftp": indoor_ftp, "lthr": lthr, "max_hr": max_hr}.items():
        if v is not None:
            body[k] = v
    if threshold_pace:
        body["threshold_pace"] = pace_to_mps(threshold_pace)
    if not body:
        raise ValueError("Nothing to change: pass at least one setting.")
    s = await client().put(
        f"/athlete/0/sport-settings/{sport}", json=body,
        params={"recalcHrZones": "true"} if recalc_hr_zones else None,
    )
    row = _pick(s, _SPORT_FIELDS)
    row.pop("pace_units", None)
    row["threshold_pace"] = mps_to_pace(s.get("threshold_pace"),
                                        pace_unit_for(sport) or "km")
    return row


Scale = Literal[1, 2, 3, 4]


@mcp.tool()
async def log_wellness(
    day: str,
    soreness: Scale | None = None,
    fatigue: Scale | None = None,
    stress: Scale | None = None,
    mood: Scale | None = None,
    motivation: Scale | None = None,
    injury: Scale | None = None,
    sleep_quality: Scale | None = None,
    sleep_hours: float | None = None,
    resting_hr: int | None = None,
    hrv: float | None = None,
    weight_kg: float | None = None,
    comments: str | None = None,
) -> dict:
    """Record how the athlete feels on a day (write), e.g. a morning check-in.

    day: YYYY-MM-DD. Subjective scales are 1-4 with 1 the good end:
      soreness/fatigue/stress: 1 low .. 4 extreme; mood: 1 great .. 4 grumpy;
      motivation: 1 extreme .. 4 low; injury: 1 none .. 4 injured;
      sleep_quality: 1 great .. 4 poor.
    Only the fields passed are changed. Use it to adapt the day's plan.
    If the athlete locked the day in intervals.icu, nothing can be written; they must
    unlock it on the website first (this tool reports when that happens).
    """
    fields = {
        "soreness": soreness, "fatigue": fatigue, "stress": stress, "mood": mood,
        "motivation": motivation, "injury": injury, "sleepQuality": sleep_quality,
        "sleepSecs": round(sleep_hours * 3600) if sleep_hours is not None else None,
        "restingHR": resting_hr, "hrv": hrv, "weight": weight_kg, "comments": comments,
    }
    body = {k: v for k, v in fields.items() if v is not None}
    if not body:
        raise ValueError("Nothing to record: pass at least one field.")
    # Never set `locked`: a locked day silently rejects all later API writes, even unlocking.
    saved = await client().put(f"/athlete/0/wellness/{day}", json=body)
    ignored = [k for k, v in body.items() if saved.get(k) != v]
    if ignored:
        raise RuntimeError(
            f"intervals.icu accepted the request but did not save {ignored}. The day is "
            "probably locked: the athlete must unlock it in the intervals.icu website first."
        )
    return _pick(saved, _WELLNESS_FIELDS)


def main() -> None:
    mcp.run()  # stdio


if __name__ == "__main__":
    main()
