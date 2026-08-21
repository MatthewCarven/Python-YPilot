# Tasks

Near-term in-progress design decisions and todos. Longer-term direction
lives in [DESIGN.md § Educational forks (planned)](DESIGN.md#educational-forks-planned);
the retired-feature graveyard is in [DESIGN.md § Deferred TODO](DESIGN.md#deferred-todo).

In flight: the **gameplay-elements arc** (planned with Matthew
2026-06-07).

**Session state as of 2026-06-10** (for whoever picks this up next):

- Local main = `2c19ad1` (raids plan) -- **needs `git push`** (Matthew
  runs pushes natively).
- Playtest queue, in one field run: (a) scrap economy feel questions
  below; (b) ore sprinkle (commit `70a382f`) -- default world should
  show exactly 1 new deposit on Ember, Moon stays bare; roll some
  Shift+R universes and judge whether middle-planet strikes feel like
  finds or freebies.
- Step 2 (raids) is fully planned in RAIDS_PLAN.md but **blocked on
  Matthew's answers to its 5 open questions** + the playtest verdicts.
  Next coding session starts at Phase A (structure HP) once unblocked.

- **Step 1 -- scrap economy + missile rebalance: SHIPPED 2026-06-08.**
  Kills drop salvageable wreckage instead of instant ore; missiles
  150/30 -> 100/10. Headless-tested only -- **needs playtest**. Feel
  questions: does salvage collection feel rewarding or like a chore?
  do piles cluster sensibly around the fortress? is 10/shot vs 12
  salvage the right missile margin? Knobs: `SCRAP_VALUE`,
  `SCRAP_VALUE_BATTERY`, `SCRAP_MERGE_DIST`, `SCRAP_SCATTER_SPEED`.
- **Step 2 (planned 2026-06-10, not started): escalating raids** that
  target structures, not just the ship. Full design in
  [RAIDS_PLAN.md](RAIDS_PLAN.md): structure HP + beam repair, kamikaze
  raider intent, threat-driven wave director with a 10 s telegraph,
  three one-session phases. **Blocked on Matthew answering the open
  questions at the bottom of that doc** (threat driver, repair model,
  raider-vs-ship lethality, wave targeting, hostile cap), and on the
  step-1 playtest verdict.
- **Side idea (raised 2026-08-21, not started): live thrust-preview
  ghosts.** Matthew's pitch: draw the path you *would* fly if you held
  W or S for 0.1 s. Verdict -- worth having, but note plan mode already
  is this feature (`PLAN_BURN_DURATION_DEFAULT` is literally `0.1`);
  what's actually being asked for is plan mode *live and unpaused*,
  locked to prograde/retro. Numbers check out: 0.1 s x `SHIP_THRUST`
  220 = 22 u/s of dv, which fans the ghost ~660 units off the cyan line
  over the default 30 s horizon (~110 units at the 5 s floor) -- clearly
  legible, not a hairline. Proposed shape:
  - **Held peek, not always-on.** Three lines fanning from one point is
    permanent clutter, and the ghost only matters in the moment *before*
    you commit -- once W is down you're already flying it. Bind to a held
    modifier so it costs literally nothing when not asked for.
  - **Bare lines only, no markers.** The SOI / apsis / closest-approach
    walks are where the per-frame cost actually lives, and three sets of
    dots would be unreadable. Dim green prograde, dim magenta retro,
    thinner than the cyan.
  - **Reuse the predictor verbatim**: two `predict_trajectory` calls with
    `vel0 = ship.vel +/- heading * (SHIP_THRUST * 0.1)`, at a *reduced*
    step budget (~400 steps is plenty for a visual delta -- it does not
    need the full 6400), hung off the existing `predict_cache`
    dirty-check so it rides the same 3-frame cadence.
  - **Alternative worth deciding first**: a *single* ghost on the
    existing modifier ladder (`[` / `]` with Shift/Ctrl/Alt scaling)
    instead of two fixed-0.1 s ghosts -- same code, peek at 1 s or
    0.01 s too, and consistent with how every other duration in the
    game is tuned. **Needs Matthew's call on one-vs-two before coding.**
- **Step 3 (undecided): harvester structure vs asteroid mining.**
  Harvester wants a renewable ore source to exist first (scrap from
  raids may be enough); asteroids are the skill-expression option.

Previous item (takeoff steering lock rethink) shipped 2026-05-17 as a
full retirement of the time-based lock, replaced with state-based
steering gating (`steering_active = not self.landed`) plus a red HUD
prompt while landed. See PROGRAM_FLOW.md "Bug-fix history" for the
"don't reintroduce a time-based lock" warning.
