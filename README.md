# Smart Home Automation (Simulator)

[![Tests](https://github.com/pastbologanesh0101/smart-home-simulator/actions/workflows/tests.yml/badge.svg)](https://github.com/pastbologanesh0101/smart-home-simulator/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**This is a software simulation. There is no real IoT hardware anywhere in
this repository.** There are no smart bulbs, no thermostats, no lock
controllers, and no motion sensors being talked to over Wi-Fi, Zigbee,
Z-Wave, or anything else. Every "device" here is a small in-memory Python
object, and the "clock" is a plain integer counter that test code and the
demo script advance by hand.

What **is** real and genuinely functional: the automation **rule engine**
itself. Conditions, AND/OR/NOT composition, event-triggered rules,
time-based rules, and the simulation loop that ticks a virtual clock forward
and evaluates rules against virtual device state -- all of that is real
logic, fully testable, and exercised by the unit test suite in this repo.
Think of this project as a rule-engine kata that happens to use "smart
home" as its domain, with a set of virtual stand-ins for devices instead of
real hardware drivers.

## Why simulate?

This environment has no physical devices, no hub, and no network of real
sensors to talk to. Rather than pretend to control hardware that doesn't
exist, this project is explicit about being a simulator: it models device
*state* (a light is either on or off; a door is either locked or unlocked)
and lets you inject synthetic sensor events (`house.trigger_motion(...)`,
`house.set_thermostat(...)`) to drive the same rule-firing logic a real
smart-home hub would run. Swapping in real hardware later would mean
writing a thin adapter layer that calls the same `House` setter methods
this simulator already uses -- the rule engine wouldn't need to change.

## Design

```
smart_home/
  clock.py       Clock: a monotonically increasing simulated-minutes counter
  devices.py     Light, Thermostat, DoorLock, MotionSensor (plain dataclasses)
  conditions.py  Condition classes: DeviceState, ThermostatExceedsTarget,
                 TimeWindow, NoMotionSince, And, Or, Not
  actions.py     Action classes: SetLight, SetThermostatMode, SetLock,
                 AllLightsOff, FunctionAction
  rules.py       Rule (condition -> action pair) and RuleEngine
  house.py       House: owns all devices + the clock + the rule engine +
                 the automation log; the only place device state is mutated
```

### Devices

* **Light** -- `on` (bool), `brightness` (0-100)
* **Thermostat** -- `current_temp`, `target_temp`, `mode` (`heat`/`cool`/`off`)
* **DoorLock** -- `locked` (bool)
* **MotionSensor** -- `triggered` (bool)
* **Clock** -- `total_minutes` (never wraps -- used for "no motion for N
  minutes" style conditions) and `time_of_day` (`total_minutes % 1440` --
  used for time-of-day windows)

All device state changes go through `House` (`set_light`, `set_thermostat`,
`set_lock`, `trigger_motion`), which is what lets every change be logged
consistently and lets the rule engine react immediately.

### Rules: (condition -> action) pairs

```python
Rule(
    name="hallway_night_light",
    trigger="event",  # or "time"
    condition=And(
        DeviceState("hallway_motion", "triggered", "==", True),
        TimeWindow("18:00", "06:00"),
    ),
    action=SetLight("hallway_light", on=True, brightness=60),
)
```

* **Event-triggered rules** (`trigger="event"`) are re-evaluated the
  instant a device they reference changes state, and fire immediately if
  the condition holds. An unrelated device changing elsewhere in the house
  does not cause the rule to spuriously re-fire -- each condition tracks
  which device(s) it inspects (`Condition.referenced_devices()`), including
  through `And`/`Or`/`Not` composition, and the engine only re-checks rules
  that actually care about the device that just changed.
* **Time-based rules** (`trigger="time"`) are re-evaluated once per
  simulated clock tick (see `House.advance_clock`). They are
  edge-triggered: a rule fires the tick its condition transitions from
  false to true, not on every subsequent tick where the condition happens
  to still hold -- so a standing "away mode" condition fires once, not once
  per minute for as long as the house stays empty.
* **Conditions compose** with `And(...)`, `Or(...)`, and `Not(...)`, which
  can nest arbitrarily.
* Conditions available out of the box: `DeviceState(device, attr, op,
  value)` (generic attribute comparison), `ThermostatExceedsTarget(name,
  delta)`, `TimeWindow(start, end)` (supports windows that cross midnight),
  and `NoMotionSince(sensor_names, minutes)`.

### Simulation loop

`House.advance_clock(minutes, tick=1)` steps the simulated world forward
minute by minute (or in whatever `tick` size you choose), evaluating all
time-based rules at every tick boundary. `House.trigger_motion(...)`,
`House.set_light(...)`, `House.set_thermostat(...)`, and
`House.set_lock(...)` let you inject synthetic sensor/device events at any
point, each of which immediately evaluates the relevant event-triggered
rules. Every state change and every rule firing is appended to
`House.log_entries`.

## Running the demo

```bash
python demo.py
```

The demo builds a small house (hallway, bedroom, living room, and an
entrance/porch), wires up five rules -- two AND-composed motion+time-window
rules, one OR-composed dual-entrance rule, a thermostat auto-cool rule, and
a time-based away-mode rule requiring both doors locked *and* 30 minutes of
no motion -- then runs one simulated day, advancing the clock and injecting
motion/temperature events along the way.

### Example log output

```
[06:00 t=360] --- simulated day begins ---
[06:00 t=360] front_motion: motion DETECTED
[06:00 t=360] front_door: LOCKED
[06:00 t=360] front_motion: motion CLEARED
[12:00 t=720] living_thermostat: current_temp -> 75.0
[12:00 t=720] living_thermostat: mode -> cool
[12:00 t=720] RULE FIRED: auto_cool_when_hot [living_thermostat.current_temp > target_temp + 2] -> SetThermostatMode(living_thermostat -> cool)
[16:00 t=960] living_thermostat: current_temp -> 71.0
[19:00 t=1140] hallway_motion: motion DETECTED
[19:00 t=1140] hallway_light: light turned ON
[19:00 t=1140] hallway_light: brightness set to 60
[19:00 t=1140] RULE FIRED: hallway_night_light [(hallway_motion.triggered == True) AND (time in [18:00-06:00))] -> SetLight(hallway_light, on=True, brightness=60)
[19:00 t=1140] front_motion: motion DETECTED
[19:00 t=1140] porch_light: light turned ON
[19:00 t=1140] RULE FIRED: porch_light_on_entry_motion [((front_motion.triggered == True) OR (back_motion.triggered == True)) AND (time in [18:00-06:00))] -> SetLight(porch_light, on=True, brightness=100)
[19:00 t=1140] front_motion: motion CLEARED
[19:00 t=1140] hallway_motion: motion CLEARED
[22:00 t=1320] bedroom_motion: motion DETECTED
[22:00 t=1320] bedroom_light: light turned ON
[22:00 t=1320] bedroom_light: brightness set to 25
[22:00 t=1320] RULE FIRED: bedroom_night_light [(bedroom_motion.triggered == True) AND (time in [22:00-06:00))] -> SetLight(bedroom_light, on=True, brightness=25)
[22:00 t=1320] bedroom_motion: motion CLEARED
[22:00 t=1320] back_door: LOCKED
[22:30 t=1350] hallway_light: light turned OFF
[22:30 t=1350] bedroom_light: light turned OFF
[22:30 t=1350] porch_light: light turned OFF
[22:30 t=1350] RULE FIRED: away_mode [(front_door.locked == True) AND (back_door.locked == True) AND (no motion on ['hallway_motion', 'bedroom_motion', 'front_motion', 'back_motion'] for >= 30min)] -> AllLightsOff (away mode)
[22:35 t=1355] --- simulated day ends ---
```

## Running the tests

```bash
python -m unittest discover -s tests -v
```

or, if you have pytest installed:

```bash
python -m pytest tests/
```

The suite (12 tests, pure standard library, no external dependencies) covers:

* a simple trigger -> action rule firing correctly on the matching event
* an AND-composed condition firing only once every sub-condition is true
* an OR-composed condition firing when any sub-condition is true
* a `ThermostatExceedsTarget` condition
* a time-based rule only firing inside its configured time window
* clock-advance re-evaluating time-based rules across tick boundaries,
  without refiring an edge-triggered rule on every subsequent tick
* the away-mode rule requiring *both* "doors locked" and "no motion for 30
  minutes", and not firing when only one holds
* multiple independent rules firing correctly off a single event, without
  interfering with each other's fire counts
* device state changes and rule firings being recorded in the automation log
* a rule whose condition can never match never firing (no false positives)
* setting a device to its current value being a no-op (no duplicate log
  entries, no re-firing)

A GitHub Actions workflow (`.github/workflows/tests.yml`) runs this same
suite on Python 3.11 and 3.12 on every push and pull request.

## What this project is (and isn't)

* **Is:** a real, working, tested rule-engine implementation over a small
  set of simulated device models and a simulated clock.
* **Isn't:** a controller for any real smart-home hardware, a home
  automation hub you can install, or anything that talks to a real
  network, a real sensor, or the real time of day.

## License

MIT -- see [LICENSE](LICENSE).
