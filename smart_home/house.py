"""The simulated house: owns all virtual devices, the simulated clock, the
automation log, and the rule engine. This is the only place that mutates
device state, which keeps logging and rule evaluation consistent no matter
whether a change came from a demo script, a test, or a rule's own action.
"""

from __future__ import annotations

from typing import Optional

from .clock import Clock
from .devices import Light, Thermostat, DoorLock, MotionSensor
from .rules import RuleEngine, Rule


class House:
    def __init__(self, start_minutes: int = 0):
        self.clock = Clock(start_minutes)
        self.devices: dict[str, object] = {}
        self.rule_engine = RuleEngine()
        self.log_entries: list[str] = []
        # last simulated total_minutes each motion sensor was triggered
        self.last_motion_time: dict[str, int] = {}

    # -- device registration -------------------------------------------------
    def add_light(self, name: str, room: str, on: bool = False, brightness: int = 100) -> Light:
        device = Light(name=name, room=room, on=on, brightness=brightness)
        self.devices[name] = device
        return device

    def add_thermostat(
        self,
        name: str,
        room: str,
        current_temp: float = 70.0,
        target_temp: float = 70.0,
        mode: str = "off",
    ) -> Thermostat:
        device = Thermostat(
            name=name, room=room, current_temp=current_temp, target_temp=target_temp, mode=mode
        )
        self.devices[name] = device
        return device

    def add_door_lock(self, name: str, room: str, locked: bool = True) -> DoorLock:
        device = DoorLock(name=name, room=room, locked=locked)
        self.devices[name] = device
        return device

    def add_motion_sensor(self, name: str, room: str, triggered: bool = False) -> MotionSensor:
        device = MotionSensor(name=name, room=room, triggered=triggered)
        self.devices[name] = device
        if triggered:
            self.last_motion_time[name] = self.clock.total_minutes
        return device

    # -- lookups --------------------------------------------------------------
    def get_device(self, name: str):
        try:
            return self.devices[name]
        except KeyError:
            raise KeyError(f"no such device: {name!r}") from None

    def lights(self) -> list[Light]:
        return [d for d in self.devices.values() if isinstance(d, Light)]

    def door_locks(self) -> list[DoorLock]:
        return [d for d in self.devices.values() if isinstance(d, DoorLock)]

    def motion_sensors(self) -> list[MotionSensor]:
        return [d for d in self.devices.values() if isinstance(d, MotionSensor)]

    def thermostats(self) -> list[Thermostat]:
        return [d for d in self.devices.values() if isinstance(d, Thermostat)]

    # -- rules ------------------------------------------------------------
    def add_rule(self, rule: Rule) -> Rule:
        return self.rule_engine.add_rule(rule)

    # -- logging ----------------------------------------------------------
    def log(self, message: str) -> str:
        entry = f"[{self.clock.time_str()} t={self.clock.total_minutes}] {message}"
        self.log_entries.append(entry)
        return entry

    # -- device mutation (always goes through these) -----------------------
    def set_light(self, name: str, on: Optional[bool] = None, brightness: Optional[int] = None):
        device: Light = self.get_device(name)
        changed = False
        if on is not None and device.on != on:
            device.on = on
            changed = True
            self.log(f"{name}: light turned {'ON' if on else 'OFF'}")
        if brightness is not None and device.brightness != brightness:
            device.brightness = brightness
            changed = True
            self.log(f"{name}: brightness set to {brightness}")
        if changed:
            self.rule_engine.handle_event(self, changed_device=name)
        return device

    def set_thermostat(
        self,
        name: str,
        current_temp: Optional[float] = None,
        target_temp: Optional[float] = None,
        mode: Optional[str] = None,
    ):
        device: Thermostat = self.get_device(name)
        changed = False
        if current_temp is not None and device.current_temp != current_temp:
            device.current_temp = current_temp
            changed = True
            self.log(f"{name}: current_temp -> {current_temp}")
        if target_temp is not None and device.target_temp != target_temp:
            device.target_temp = target_temp
            changed = True
            self.log(f"{name}: target_temp -> {target_temp}")
        if mode is not None and device.mode != mode:
            if mode not in Thermostat.VALID_MODES:
                raise ValueError(f"invalid thermostat mode: {mode!r}")
            device.mode = mode
            changed = True
            self.log(f"{name}: mode -> {mode}")
        if changed:
            self.rule_engine.handle_event(self, changed_device=name)
        return device

    def set_lock(self, name: str, locked: bool):
        device: DoorLock = self.get_device(name)
        if device.locked != locked:
            device.locked = locked
            self.log(f"{name}: {'LOCKED' if locked else 'UNLOCKED'}")
            self.rule_engine.handle_event(self, changed_device=name)
        return device

    def trigger_motion(self, name: str, triggered: bool = True):
        """Inject a synthetic motion sensor event."""
        device: MotionSensor = self.get_device(name)
        state_changed = device.triggered != triggered
        if triggered:
            self.last_motion_time[name] = self.clock.total_minutes
        if state_changed:
            device.triggered = triggered
            self.log(f"{name}: motion {'DETECTED' if triggered else 'CLEARED'}")
            self.rule_engine.handle_event(self, changed_device=name)
        return device

    # -- simulation clock ---------------------------------------------------
    def advance_clock(self, minutes: int, tick: int = 1) -> None:
        """Step the simulated world forward by ``minutes``, evaluating
        time-based rules at each ``tick``-minute boundary in between."""
        if minutes < 0:
            raise ValueError("minutes must be non-negative")
        remaining = minutes
        while remaining > 0:
            step = min(tick, remaining)
            self.clock.advance(step)
            remaining -= step
            self.rule_engine.handle_tick(self)
