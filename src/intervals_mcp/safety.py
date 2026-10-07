"""Safe mode: keeps write tools away from anything but disposable test events.

On by default. Set INTERVALS_MCP_SAFE=0 to get the unrestricted behaviour.
In safe mode:
  * created workouts always get the "TEST - " name prefix;
  * update/delete only touch events whose name already starts with "TEST - ";
  * tools that change the athlete's real data (thresholds, wellness, calendar
    entries) are refused.
"""
import os

TEST_PREFIX = "TEST - "


def safe_mode() -> bool:
    return os.environ.get("INTERVALS_MCP_SAFE", "1") != "0"


def prefixed(name: str) -> str:
    """Prefix a name with TEST_PREFIX in safe mode (idempotent); untouched otherwise."""
    if safe_mode() and not name.startswith(TEST_PREFIX):
        return TEST_PREFIX + name
    return name


def check_event_name(name: str | None) -> None:
    """Refuse to modify an event that is not a TEST - event while in safe mode."""
    if safe_mode() and not (name or "").startswith(TEST_PREFIX):
        raise PermissionError(
            f"Safe mode: only events named '{TEST_PREFIX}...' can be changed "
            f"(this one is {name!r}). Set INTERVALS_MCP_SAFE=0 to lift the restriction."
        )


def forbid(tool: str) -> None:
    """Refuse a tool outright while in safe mode."""
    if safe_mode():
        raise PermissionError(
            f"Safe mode: {tool} changes the athlete's real data and is disabled. "
            "Set INTERVALS_MCP_SAFE=0 to lift the restriction."
        )
