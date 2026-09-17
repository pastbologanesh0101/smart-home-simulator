"""Virtual (simulated) smart-home devices.

None of these classes talk to any real hardware or network protocol -- they
are plain in-memory data holders. All mutation happens through the
``House`` class so that every change can be logged and can trigger the rule
engine consistently.
"""

from dataclasses import dataclass


@dataclass
class Light:
    name: str
    room: str
    on: bool = False
    brightness: int = 100  # 0-100

    def __post_init__(self):
        if not 0 <= self.brightness <= 100:
            raise ValueError("brightness must be between 0 and 100")


@dataclass
class Thermostat:
    name: str
    room: str
    current_temp: float = 70.0
    target_temp: float = 70.0
    mode: str = "off"  # "heat" | "cool" | "off"

    VALID_MODES = ("heat", "cool", "off")

    def __post_init__(self):
        if self.mode not in self.VALID_MODES:
            raise ValueError(f"invalid thermostat mode: {self.mode!r}")


@dataclass
class DoorLock:
    name: str
    room: str
    locked: bool = True


@dataclass
class MotionSensor:
    name: str
    room: str
    triggered: bool = False
