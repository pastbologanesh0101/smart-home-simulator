"""Actions that a fired rule performs on the simulated house.

Every action mutates devices exclusively through ``House`` setter methods so
that the change is logged the same way whether it came from a rule firing or
from a demo/test script poking the house directly.
"""

from __future__ import annotations

from typing import Callable, Optional


class Action:
    def apply(self, house) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def describe(self) -> str:
        return self.__class__.__name__

    def __repr__(self) -> str:
        return self.describe()


class SetLight(Action):
    def __init__(self, name: str, on: Optional[bool] = None, brightness: Optional[int] = None):
        self.name = name
        self.on = on
        self.brightness = brightness

    def apply(self, house) -> None:
        house.set_light(self.name, on=self.on, brightness=self.brightness)

    def describe(self) -> str:
        parts = []
        if self.on is not None:
            parts.append(f"on={self.on}")
        if self.brightness is not None:
            parts.append(f"brightness={self.brightness}")
        return f"SetLight({self.name}, {', '.join(parts)})"


class SetThermostatMode(Action):
    def __init__(self, name: str, mode: str):
        self.name = name
        self.mode = mode

    def apply(self, house) -> None:
        house.set_thermostat(self.name, mode=self.mode)

    def describe(self) -> str:
        return f"SetThermostatMode({self.name} -> {self.mode})"


class SetLock(Action):
    def __init__(self, name: str, locked: bool):
        self.name = name
        self.locked = locked

    def apply(self, house) -> None:
        house.set_lock(self.name, self.locked)

    def describe(self) -> str:
        state = "locked" if self.locked else "unlocked"
        return f"SetLock({self.name} -> {state})"


class AllLightsOff(Action):
    """Away-mode helper: turns off every light registered in the house."""

    def apply(self, house) -> None:
        for light in house.lights():
            house.set_light(light.name, on=False)

    def describe(self) -> str:
        return "AllLightsOff (away mode)"


class FunctionAction(Action):
    """Wraps an arbitrary callable as an action, for one-off/demo rules."""

    def __init__(self, fn: Callable[[object], None], description: str = "custom action"):
        self.fn = fn
        self._description = description

    def apply(self, house) -> None:
        self.fn(house)

    def describe(self) -> str:
        return self._description
