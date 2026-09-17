"""The rule engine: (trigger condition -> action) pairs.

Two kinds of rules are supported:

* ``trigger="event"`` -- re-evaluated immediately whenever any device state
  changes, and fires every time its condition is true at that moment (so a
  motion sensor flipping on/off/on can fire the rule twice, correctly).
* ``trigger="time"`` -- re-evaluated once per simulated clock tick. These
  are edge-triggered: the rule fires only on the tick where the condition
  transitions from False to True, so a rule whose condition stays true for
  many ticks in a row (e.g. a standing away-mode condition) fires once, not
  once per tick.
"""

from __future__ import annotations

from .conditions import Condition
from .actions import Action


class Rule:
    def __init__(self, name: str, condition: Condition, action: Action, trigger: str = "event"):
        if trigger not in ("event", "time"):
            raise ValueError("trigger must be 'event' or 'time'")
        self.name = name
        self.condition = condition
        self.action = action
        self.trigger = trigger
        self.fire_count = 0
        self._last_result = False  # used for edge-triggering time-based rules

    def __repr__(self) -> str:
        return f"Rule({self.name!r}, trigger={self.trigger!r})"


class RuleEngine:
    def __init__(self):
        self.rules: list[Rule] = []
        self._handling_event = False

    def add_rule(self, rule: Rule) -> Rule:
        self.rules.append(rule)
        return rule

    def handle_event(self, house, changed_device: str) -> None:
        """Evaluate event-triggered rules after ``changed_device``'s state
        changed. Only rules whose condition actually inspects
        ``changed_device`` (directly, or via And/Or/Not composition) are
        re-evaluated -- an unrelated device changing elsewhere in the house
        must not cause a rule to noisily re-fire.

        Guarded against re-entrancy: an action can itself change device
        state (e.g. a rule that turns on a light), which would otherwise
        recursively re-trigger this same pass and double-fire rules. A
        rule's action running mid-pass is instead simply picked up by any
        later rule in the same, single top-level pass.
        """
        if self._handling_event:
            return
        self._handling_event = True
        try:
            for rule in self.rules:
                if rule.trigger != "event":
                    continue
                if changed_device not in rule.condition.referenced_devices():
                    continue
                if rule.condition.evaluate(house):
                    self._fire(rule, house)
        finally:
            self._handling_event = False

    def handle_tick(self, house) -> None:
        """Evaluate all time-based rules. Called once per clock tick."""
        for rule in self.rules:
            if rule.trigger != "time":
                continue
            result = rule.condition.evaluate(house)
            if result and not rule._last_result:
                self._fire(rule, house)
            rule._last_result = result

    def _fire(self, rule: Rule, house) -> None:
        rule.fire_count += 1
        rule.action.apply(house)
        house.log(
            f"RULE FIRED: {rule.name} "
            f"[{rule.condition.describe()}] -> {rule.action.describe()}"
        )
