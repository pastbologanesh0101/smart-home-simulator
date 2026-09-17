#!/usr/bin/env python3
"""Demo CLI for the Smart Home Automation simulator.

*** THIS IS A SOFTWARE SIMULATION. There is no real hardware anywhere in
this script. *** It builds a small virtual house, wires up a handful of
automation rules, then runs a simulated day: advancing a simulated clock and
injecting synthetic motion / temperature events, and finally prints the
resulting automation log.

Run it with:

    python demo.py

See README.md for a full walkthrough and sample output.
"""

from smart_home import (
    House,
    Rule,
    DeviceState,
    ThermostatExceedsTarget,
    TimeWindow,
    NoMotionSince,
    And,
    Or,
    SetLight,
    SetThermostatMode,
    AllLightsOff,
)


def build_house() -> House:
    """Set up a small house: a few rooms, each with lights and/or sensors."""
    # Start the simulated clock at 06:00 on "day one".
    house = House(start_minutes=6 * 60)

    # Rooms & devices.
    house.add_light("hallway_light", room="hallway")
    house.add_light("bedroom_light", room="bedroom")
    house.add_light("living_room_light", room="living_room")
    house.add_light("porch_light", room="entrance")

    house.add_thermostat("living_thermostat", room="living_room", current_temp=70.0, target_temp=70.0)

    house.add_door_lock("front_door", room="entrance", locked=False)
    house.add_door_lock("back_door", room="kitchen", locked=False)

    house.add_motion_sensor("hallway_motion", room="hallway")
    house.add_motion_sensor("bedroom_motion", room="bedroom")
    house.add_motion_sensor("front_motion", room="entrance")
    house.add_motion_sensor("back_motion", room="kitchen")

    return house


def add_rules(house: House) -> None:
    """Define a handful of automation rules covering event-triggered,
    time-based, AND-composed, and OR-composed conditions."""

    # 1. Event-triggered + AND-composed: motion in the hallway at night
    #    turns the hallway light on.
    house.add_rule(
        Rule(
            name="hallway_night_light",
            trigger="event",
            condition=And(
                DeviceState("hallway_motion", "triggered", "==", True),
                TimeWindow("18:00", "06:00"),
            ),
            action=SetLight("hallway_light", on=True, brightness=60),
        )
    )

    # 2. Event-triggered + AND-composed: motion in the bedroom late at
    #    night turns the bedroom light on, dim.
    house.add_rule(
        Rule(
            name="bedroom_night_light",
            trigger="event",
            condition=And(
                DeviceState("bedroom_motion", "triggered", "==", True),
                TimeWindow("22:00", "06:00"),
            ),
            action=SetLight("bedroom_light", on=True, brightness=25),
        )
    )

    # 3. Event-triggered + OR-composed: motion at either entrance at night
    #    turns the porch light on.
    house.add_rule(
        Rule(
            name="porch_light_on_entry_motion",
            trigger="event",
            condition=And(
                Or(
                    DeviceState("front_motion", "triggered", "==", True),
                    DeviceState("back_motion", "triggered", "==", True),
                ),
                TimeWindow("18:00", "06:00"),
            ),
            action=SetLight("porch_light", on=True, brightness=100),
        )
    )

    # 4. Event-triggered: thermostat runs too hot relative to its own
    #    target -> switch it to cooling mode.
    house.add_rule(
        Rule(
            name="auto_cool_when_hot",
            trigger="event",
            condition=ThermostatExceedsTarget("living_thermostat", delta=2),
            action=SetThermostatMode("living_thermostat", mode="cool"),
        )
    )

    # 5. Time-based + AND-composed: both doors locked AND no motion
    #    anywhere for 30 minutes -> away mode (all lights off).
    house.add_rule(
        Rule(
            name="away_mode",
            trigger="time",
            condition=And(
                DeviceState("front_door", "locked", "==", True),
                DeviceState("back_door", "locked", "==", True),
                NoMotionSince(
                    ["hallway_motion", "bedroom_motion", "front_motion", "back_motion"],
                    minutes=30,
                ),
            ),
            action=AllLightsOff(),
        )
    )


def run_simulated_day(house: House) -> None:
    """Advance the clock and inject a plausible sequence of synthetic
    sensor events across one simulated day."""

    house.log("--- simulated day begins ---")

    # 06:00 -> someone leaves through the front door in the morning.
    house.trigger_motion("front_motion", True)
    house.set_lock("front_door", True)
    house.trigger_motion("front_motion", False)

    # Jump to midday, temperature climbs above comfortable range.
    house.advance_clock(6 * 60)  # now 12:00
    house.set_thermostat("living_thermostat", current_temp=75.0)  # triggers auto_cool_when_hot

    # Someone is home working in the living room during the afternoon.
    house.advance_clock(4 * 60)  # now 16:00
    house.set_thermostat("living_thermostat", current_temp=71.0)

    # Evening arrives: motion in the hallway and at both entrances.
    house.advance_clock(3 * 60)  # now 19:00
    house.trigger_motion("hallway_motion", True)
    house.trigger_motion("front_motion", True)
    house.trigger_motion("front_motion", False)
    house.trigger_motion("hallway_motion", False)

    # Late night: motion in the bedroom (someone heading to bed).
    house.advance_clock(3 * 60)  # now 22:00
    house.trigger_motion("bedroom_motion", True)
    house.trigger_motion("bedroom_motion", False)

    # Everyone is settled in for the night: lock up and go quiet.
    house.set_lock("back_door", True)

    # 35 quiet minutes with both doors locked -> away_mode should fire.
    house.advance_clock(35)

    house.log("--- simulated day ends ---")


def main() -> None:
    print("Smart Home Automation -- SOFTWARE SIMULATION (no real hardware).\n")

    house = build_house()
    add_rules(house)
    run_simulated_day(house)

    print("Automation log:")
    print("=" * 70)
    for entry in house.log_entries:
        print(entry)
    print("=" * 70)

    fired = [r for r in house.rule_engine.rules if r.fire_count > 0]
    print(f"\n{len(fired)} of {len(house.rule_engine.rules)} rules fired at least once:")
    for rule in house.rule_engine.rules:
        print(f"  - {rule.name}: fired {rule.fire_count} time(s)")


if __name__ == "__main__":
    main()
