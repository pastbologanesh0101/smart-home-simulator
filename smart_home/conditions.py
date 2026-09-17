"""Trigger conditions for automation rules.

Conditions are small composable objects with an ``evaluate(house) -> bool``
method. They can be combined with ``And`` / ``Or`` / ``Not`` to build
arbitrarily nested boolean expressions, e.g.::

    And(
        DeviceState("hallway_motion", "triggered", "==", True),
        TimeWindow("18:00", "06:00"),
    )
"""

from __future__ import annotations

import operator
from typing import Any, Iterable, Set

from .clock import parse_hm, format_minutes

_OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}


class Condition:
    """Base class for all trigger conditions."""

    def evaluate(self, house) -> bool:  # pragma: no cover - abstract
        raise NotImplementedError

    def referenced_devices(self) -> Set[str]:
        """Names of devices this condition inspects. Used by the rule
        engine to decide which event-triggered rules are worth
        re-evaluating when a specific device changes. Conditions with no
        device of their own (e.g. a bare ``TimeWindow``) return an empty
        set."""
        return set()

    def describe(self) -> str:
        return self.__class__.__name__

    def __repr__(self) -> str:
        return self.describe()


class DeviceState(Condition):
    """Compares one attribute of one device against a fixed value."""

    def __init__(self, device_name: str, attr: str, op: str, value: Any):
        if op not in _OPS:
            raise ValueError(f"unsupported operator: {op!r}")
        self.device_name = device_name
        self.attr = attr
        self.op = op
        self.value = value

    def evaluate(self, house) -> bool:
        device = house.get_device(self.device_name)
        actual = getattr(device, self.attr)
        return _OPS[self.op](actual, self.value)

    def referenced_devices(self) -> Set[str]:
        return {self.device_name}

    def describe(self) -> str:
        return f"{self.device_name}.{self.attr} {self.op} {self.value!r}"


class ThermostatExceedsTarget(Condition):
    """True when a thermostat's current temperature is ``delta`` degrees
    (or more) above its own target temperature."""

    def __init__(self, thermostat_name: str, delta: float):
        self.thermostat_name = thermostat_name
        self.delta = delta

    def evaluate(self, house) -> bool:
        device = house.get_device(self.thermostat_name)
        return device.current_temp > device.target_temp + self.delta

    def referenced_devices(self) -> Set[str]:
        return {self.thermostat_name}

    def describe(self) -> str:
        return f"{self.thermostat_name}.current_temp > target_temp + {self.delta}"


class TimeWindow(Condition):
    """True while the simulated time-of-day falls within [start, end).

    Supports windows that cross midnight, e.g. ``TimeWindow("18:00", "06:00")``.
    """

    def __init__(self, start: str, end: str):
        self.start = parse_hm(start)
        self.end = parse_hm(end)

    def evaluate(self, house) -> bool:
        t = house.clock.time_of_day
        if self.start <= self.end:
            return self.start <= t < self.end
        # window wraps across midnight
        return t >= self.start or t < self.end

    def describe(self) -> str:
        return f"time in [{format_minutes(self.start)}-{format_minutes(self.end)})"


class NoMotionSince(Condition):
    """True when none of ``sensor_names`` have registered motion in the
    last ``minutes`` simulated minutes (and none is currently triggered)."""

    def __init__(self, sensor_names: Iterable[str] | str, minutes: int):
        if isinstance(sensor_names, str):
            sensor_names = [sensor_names]
        self.sensor_names = list(sensor_names)
        self.minutes = minutes

    def evaluate(self, house) -> bool:
        for name in self.sensor_names:
            sensor = house.get_device(name)
            if sensor.triggered:
                return False
            last_seen = house.last_motion_time.get(name, 0)
            if house.clock.total_minutes - last_seen < self.minutes:
                return False
        return True

    def referenced_devices(self) -> Set[str]:
        return set(self.sensor_names)

    def describe(self) -> str:
        return f"no motion on {self.sensor_names} for >= {self.minutes}min"


class And(Condition):
    def __init__(self, *conditions: Condition):
        self.conditions = conditions

    def evaluate(self, house) -> bool:
        return all(c.evaluate(house) for c in self.conditions)

    def referenced_devices(self) -> Set[str]:
        devices: Set[str] = set()
        for c in self.conditions:
            devices |= c.referenced_devices()
        return devices

    def describe(self) -> str:
        return " AND ".join(f"({c.describe()})" for c in self.conditions)


class Or(Condition):
    def __init__(self, *conditions: Condition):
        self.conditions = conditions

    def evaluate(self, house) -> bool:
        return any(c.evaluate(house) for c in self.conditions)

    def referenced_devices(self) -> Set[str]:
        devices: Set[str] = set()
        for c in self.conditions:
            devices |= c.referenced_devices()
        return devices

    def describe(self) -> str:
        return " OR ".join(f"({c.describe()})" for c in self.conditions)


class Not(Condition):
    def __init__(self, condition: Condition):
        self.condition = condition

    def evaluate(self, house) -> bool:
        return not self.condition.evaluate(house)

    def referenced_devices(self) -> Set[str]:
        return self.condition.referenced_devices()

    def describe(self) -> str:
        return f"NOT ({self.condition.describe()})"
