# Tasks

Near-term in-progress design decisions and todos. Longer-term direction
lives in [DESIGN.md § Educational forks (planned)](DESIGN.md#educational-forks-planned);
the retired-feature graveyard is in [DESIGN.md § Deferred TODO](DESIGN.md#deferred-todo).

In flight: the **gameplay-elements arc** (planned with Matthew
2026-06-07).

- **Step 1 -- scrap economy + missile rebalance: SHIPPED 2026-06-08.**
  Kills drop salvageable wreckage instead of instant ore; missiles
  150/30 -> 100/10. Headless-tested only -- **needs playtest**. Feel
  questions: does salvage collection feel rewarding or like a chore?
  do piles cluster sensibly around the fortress? is 10/shot vs 12
  salvage the right missile margin? Knobs: `SCRAP_VALUE`,
  `SCRAP_VALUE_BATTERY`, `SCRAP_MERGE_DIST`, `SCRAP_SCATTER_SPEED`.
- **Step 2 (decided, not started): escalating raids** that target
  structures, not just the ship. Needs structure HP + a wave director.
  Pairs with scrap: bigger waves -> more salvage -> bigger defenses.
  Should respect the F10 spawn toggle so pressure stays opt-in.
- **Step 3 (undecided): harvester structure vs asteroid mining.**
  Harvester wants a renewable ore source to exist first (scrap from
  raids may be enough); asteroids are the skill-expression option.

Previous item (takeoff steering lock rethink) shipped 2026-05-17 as a
full retirement of the time-based lock, replaced with state-based
steering gating (`steering_active = not self.landed`) plus a red HUD
prompt while landed. See PROGRAM_FLOW.md "Bug-fix history" for the
"don't reintroduce a time-based lock" warning.
