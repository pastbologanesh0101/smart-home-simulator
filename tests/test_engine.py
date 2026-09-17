"""Unit tests for the Smart Home Automation simulator.

These exercise the rule engine and simulated devices directly (no real
hardware, no real time -- everything runs through the in-memory House /
Clock objects). Run with:

    python -m unittest discover -s tests -v

or

    python -m pytest tests/
"""

import unittest

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
    SetLock,
    SetThermostatMode,
    AllLightsOff,
)


def make_basic_house():
    """A small house with one of each device type, useful across tests."""
    house = House(start_minutes=0)
    house.add_light("hall_light", room="hallway")
    house.add_light("bed_light", room="bedroom")
    house.add_thermostat("thermo", room="living_room", current_temp=70.0, target_temp=70.0)
    house.add_door_lock("front_door", room="entrance", locked=False)
    house.add_door_lock("back_door", room="kitchen", locked=False)
    house.add_motion_sensor("hall_motion", room="hallway")
    house.add_motion_sensor("bed_motion", room="bedroom")
    return house


class SimpleTriggerActionTests(unittest.TestCase):
    def test_simple_rule_fires_on_matching_event(self):
        house = make_basic_house()
        rule = house.add_rule(
            Rule(
                name="motion_turns_on_light",
                trigger="event",
                condition=DeviceState("hall_motion", "triggered", "==", True),
                action=SetLight("hall_light", on=True),
            )
        )

        self.assertEqual(rule.fire_count, 0)
        house.trigger_motion("hall_motion", True)

        self.assertEqual(rule.fire_count, 1)
        self.assertTrue(house.get_device("hall_light").on)

    def test_rule_with_no_matching_condition_never_fires(self):
        house = make_basic_house()
        # Condition can never be true: a lock can't equal the string "sideways".
        rule = house.add_rule(
            Rule(
                name="impossible_rule",
                trigger="event",
                condition=DeviceState("front_door", "locked", "==", "sideways"),
                action=SetLight("hall_light", on=True),
            )
        )

        house.trigger_motion("hall_motion", True)
        house.set_lock("front_door", True)
        house.set_lock("back_door", True)
        house.advance_clock(120)

        self.assertEqual(rule.fire_count, 0)
        self.assertFalse(house.get_device("hall_light").on)


class ConditionCompositionTests(unittest.TestCase):
    def test_and_condition_only_fires_when_all_subconditions_true(self):
        house = make_basic_house()
        rule = house.add_rule(
            Rule(
                name="and_rule",
                trigger="event",
                condition=And(
                    DeviceState("hall_motion", "triggered", "==", True),
                    DeviceState("front_door", "locked", "==", False),
                ),
                action=SetLight("hall_light", on=True),
            )
        )

        # Only one sub-condition true (door defaults to unlocked already,
        # so lock it first to make that sub-condition false).
        house.set_lock("front_door", True)
        house.trigger_motion("hall_motion", True)
        self.assertEqual(rule.fire_count, 0)

        # Now make both sub-conditions true.
        house.trigger_motion("hall_motion", False)
        house.set_lock("front_door", False)
        house.trigger_motion("hall_motion", True)
        self.assertEqual(rule.fire_count, 1)

    def test_or_condition_fires_when_any_subcondition_true(self):
        house = make_basic_house()
        rule = house.add_rule(
            Rule(
                name="or_rule",
                trigger="event",
                condition=Or(
                    DeviceState("hall_motion", "triggered", "==", True),
                    DeviceState("bed_motion", "triggered", "==", True),
                ),
                action=SetLight("hall_light", on=True),
            )
        )

        house.trigger_motion("bed_motion", True)
        self.assertEqual(rule.fire_count, 1)

        house.trigger_motion("bed_motion", False)
        house.get_device("hall_light").on = False  # reset for clarity
        house.trigger_motion("hall_motion", True)
        self.assertEqual(rule.fire_count, 2)

    def test_thermostat_exceeds_target_condition(self):
        house = make_basic_house()
        rule = house.add_rule(
            Rule(
                name="auto_cool",
                trigger="event",
                condition=ThermostatExceedsTarget("thermo", delta=2),
                action=SetThermostatMode("thermo", mode="cool"),
            )
        )

        house.set_thermostat("thermo", current_temp=71.0)  # only +1, not enough
        self.assertEqual(rule.fire_count, 0)

        house.set_thermostat("thermo", current_temp=73.0)  # +3, exceeds delta of 2
        self.assertEqual(rule.fire_count, 1)
        self.assertEqual(house.get_device("thermo").mode, "cool")


class TimeBasedRuleTests(unittest.TestCase):
    def test_time_based_rule_only_fires_within_configured_window(self):
        house = House(start_minutes=17 * 60)  # 17:00, just before the window
        house.add_light("porch_light", room="entrance")
        rule = house.add_rule(
            Rule(
                name="night_light",
                trigger="time",
                condition=TimeWindow("18:00", "06:00"),
                action=SetLight("porch_light", on=True),
            )
        )

        house.advance_clock(30)  # -> 17:30, still outside window
        self.assertEqual(rule.fire_count, 0)

        house.advance_clock(30)  # -> 18:00, now inside window
        self.assertEqual(rule.fire_count, 1)
        self.assertTrue(house.get_device("porch_light").on)

    def test_clock_advance_reevaluates_time_rules_across_tick_boundaries(self):
        house = House(start_minutes=0)
        house.add_light("porch_light", room="entrance")
        rule = house.add_rule(
            Rule(
                name="window_rule",
                trigger="time",
                condition=TimeWindow("00:10", "00:20"),
                action=SetLight("porch_light", on=True),
            )
        )

        # Advance minute-by-minute; the rule must only fire once the clock
        # ticks past the 00:10 boundary, not before.
        house.advance_clock(9, tick=1)
        self.assertEqual(rule.fire_count, 0)

        house.advance_clock(1, tick=1)  # crosses to minute 10
        self.assertEqual(rule.fire_count, 1)

        # Staying inside the window on further ticks should not refire
        # the edge-triggered rule.
        house.advance_clock(5, tick=1)
        self.assertEqual(rule.fire_count, 1)

    def test_away_mode_requires_both_lock_and_no_motion_conditions(self):
        house = make_basic_house()
        rule = house.add_rule(
            Rule(
                name="away_mode",
                trigger="time",
                condition=And(
                    DeviceState("front_door", "locked", "==", True),
                    DeviceState("back_door", "locked", "==", True),
                    NoMotionSince(["hall_motion", "bed_motion"], minutes=30),
                ),
                action=AllLightsOff(),
            )
        )

        house.set_light("hall_light", on=True)
        house.set_light("bed_light", on=True)

        # Only "no motion" holds; doors are unlocked -> must not fire.
        house.advance_clock(40)
        self.assertEqual(rule.fire_count, 0)
        self.assertTrue(house.get_device("hall_light").on)

        # Lock both doors, but motion happened recently -> still must not fire.
        house.set_lock("front_door", True)
        house.set_lock("back_door", True)
        house.trigger_motion("hall_motion", True)
        house.trigger_motion("hall_motion", False)
        house.advance_clock(10)
        self.assertEqual(rule.fire_count, 0)
        self.assertTrue(house.get_device("hall_light").on)

        # Now both conditions hold (doors locked AND 30+ quiet minutes) -> fires.
        house.advance_clock(30)
        self.assertEqual(rule.fire_count, 1)
        self.assertFalse(house.get_device("hall_light").on)
        self.assertFalse(house.get_device("bed_light").on)


class MultiRuleAndLoggingTests(unittest.TestCase):
    def test_multiple_rules_fire_from_a_single_event_without_interfering(self):
        house = make_basic_house()
        rule_a = house.add_rule(
            Rule(
                name="turn_on_hall_light",
                trigger="event",
                condition=DeviceState("hall_motion", "triggered", "==", True),
                action=SetLight("hall_light", on=True, brightness=80),
            )
        )
        rule_b = house.add_rule(
            Rule(
                name="unlock_never",
                trigger="event",
                condition=DeviceState("hall_motion", "triggered", "==", True),
                action=SetLock("front_door", locked=True),
            )
        )

        house.trigger_motion("hall_motion", True)

        self.assertEqual(rule_a.fire_count, 1)
        self.assertEqual(rule_b.fire_count, 1)
        self.assertTrue(house.get_device("hall_light").on)
        self.assertEqual(house.get_device("hall_light").brightness, 80)
        self.assertTrue(house.get_device("front_door").locked)

    def test_device_state_changes_are_recorded_in_the_log(self):
        house = make_basic_house()
        house.set_light("hall_light", on=True, brightness=50)
        house.set_lock("front_door", True)
        house.trigger_motion("hall_motion", True)

        log_text = "\n".join(house.log_entries)
        self.assertIn("hall_light: light turned ON", log_text)
        self.assertIn("hall_light: brightness set to 50", log_text)
        self.assertIn("front_door: LOCKED", log_text)
        self.assertIn("hall_motion: motion DETECTED", log_text)

    def test_rule_firing_is_recorded_in_the_log(self):
        house = make_basic_house()
        house.add_rule(
            Rule(
                name="logged_rule",
                trigger="event",
                condition=DeviceState("hall_motion", "triggered", "==", True),
                action=SetLight("hall_light", on=True),
            )
        )
        house.trigger_motion("hall_motion", True)

        log_text = "\n".join(house.log_entries)
        self.assertIn("RULE FIRED: logged_rule", log_text)

    def test_setting_state_to_same_value_does_not_reduplicate_log_entries_or_refire(self):
        house = make_basic_house()
        rule = house.add_rule(
            Rule(
                name="on_lock",
                trigger="event",
                condition=DeviceState("front_door", "locked", "==", True),
                action=SetLight("hall_light", on=True),
            )
        )

        house.set_lock("front_door", True)
        self.assertEqual(rule.fire_count, 1)

        # Locking an already-locked door is a no-op: no new log entry, no refire.
        entries_before = len(house.log_entries)
        house.set_lock("front_door", True)
        self.assertEqual(rule.fire_count, 1)
        self.assertEqual(len(house.log_entries), entries_before)


if __name__ == "__main__":
    unittest.main()
