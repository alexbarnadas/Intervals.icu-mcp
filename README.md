# intervals.icu MCP server

An [MCP](https://modelcontextprotocol.io) server that lets Claude plan training in
[intervals.icu](https://intervals.icu): read your fitness, history, calendar and weather,
then create structured workouts that sync to Garmin/Wahoo.

## Tools

| Read | Write |
|---|---|
| `get_athlete_profile` — thresholds and zones per sport | `create_workouts` — one or many structured workouts (steps + repeat blocks) |
| `get_fitness` — CTL/ATL, HRV, sleep, subjective wellness | `create_calendar_entry` — races (A/B/C), notes, holiday, sick, injured |
| `list_activities` / `get_activity_detail` — what was done and how it went | `update_planned_workout` / `delete_planned_workout` |
| `list_planned_workouts` — the calendar, incl. device sync errors | `update_sport_settings` — FTP, LTHR, max HR, threshold pace |
| `get_weather_forecast` — 14-day forecast at your location | `log_wellness` — soreness, fatigue, sleep, weight… |

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run --with pytest pytest
```

Authentication currently uses a personal API key (intervals.icu → Settings → Developer
Settings), for development only. OAuth login is planned so users won't need a key.

```bash
INTERVALS_API_KEY=your_key uv run mcp dev src/intervals_mcp/server.py
```
