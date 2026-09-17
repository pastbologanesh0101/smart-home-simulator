"""Smart Home Automation -- a software simulator.

This package is a pure-Python, fully in-memory simulation of a smart-home
automation rule engine and a handful of virtual devices (lights,
thermostats, door locks, motion sensors, and a simulated clock). Nothing in
this package talks to real hardware, a real network, or real time -- see
the top-level README for the full "software simulation" framing.
"""

from .clock import Clock
from .devices import Light, Thermostat, DoorLock, MotionSensor
from .conditions import (
    Condition,
    DeviceState,
    ThermostatExceedsTarget,
    TimeWindow,
    NoMotionSince,
    And,
    Or,
    Not,
)
from .actions import Action, SetLight, SetThermostatMode, SetLock, AllLightsOff, FunctionAction
from .rules import Rule, RuleEngine
from .house import House

__all__ = [
    "Clock",
    "Light",
    "Thermostat",
    "DoorLock",
    "MotionSensor",
    "Condition",
    "DeviceState",
    "ThermostatExceedsTarget",
    "TimeWindow",
    "NoMotionSince",
    "And",
    "Or",
    "Not",
    "Action",
    "SetLight",
    "SetThermostatMode",
    "SetLock",
    "AllLightsOff",
    "FunctionAction",
    "Rule",
    "RuleEngine",
    "House",
]

__version__ = "1.0.0"
