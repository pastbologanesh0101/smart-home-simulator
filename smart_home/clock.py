"""Simulated clock for the smart-home automation engine.

There is no real time involved at all -- the clock is a plain integer
counter of minutes that test code and the demo script advance by hand.
This is what lets the simulation (and the unit tests) run instantly and
deterministically instead of waiting on a real wall clock.
"""

MINUTES_PER_DAY = 24 * 60


def parse_hm(text: str) -> int:
    """Parse an "HH:MM" string into minutes-since-midnight."""
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def format_minutes(total_minutes: int) -> str:
    tod = total_minutes % MINUTES_PER_DAY
    return f"{tod // 60:02d}:{tod % 60:02d}"


class Clock:
    """A monotonically increasing simulated clock.

    ``total_minutes`` never wraps, so "no motion for N minutes" style
    conditions never have to worry about midnight rollover. ``time_of_day``
    is the wrapped value (0-1439) used by time-of-day window conditions.
    """

    def __init__(self, start_minutes: int = 0):
        self.total_minutes = start_minutes

    @property
    def time_of_day(self) -> int:
        return self.total_minutes % MINUTES_PER_DAY

    def advance(self, minutes: int) -> None:
        if minutes < 0:
            raise ValueError("clock cannot move backwards")
        self.total_minutes += minutes

    def time_str(self) -> str:
        return format_minutes(self.total_minutes)

    def __repr__(self) -> str:
        return f"Clock(total_minutes={self.total_minutes}, time_of_day={self.time_str()})"
