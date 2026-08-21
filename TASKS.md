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
- **Thrust-preview ghosts: SHIPPED 2026-08-21.** Hold Tab for two ghost
  paths -- dim green = 0.1 s W tap, dim magenta = 0.1 s S tap -- plus a
  `THRUST PEEK` HUD line with both dv numbers. Matthew chose two fixed
  ghosts over the single-scalable-ghost alternative. Obeys the trim
  ladder (`Shift+Tab` = boost tap, `Ctrl+Tab` = precision tap) via new
  shared `forward_thrust_scale` / `retro_thrust_scale` helpers. Docs in
  CONTROLS.md + DESIGN.md. **Headless-tested only -- needs playtest.**
  Feel questions for the field run: (a) is Tab the right key, or does it
  want to be something the left hand can hold while WASD-ing? (b) are
  the ghost colours readable against the cyan line and the starfield, or
  do they need to be dimmer/brighter? (c) is the ~9 deg ghost lag while
  sweeping the nose noticeable enough to be annoying -- if so, drop
  `PREDICT_CACHE_INTERVAL` or add `ship.angle` to the preview cache key
  and eat the cost? (d) does the 0.1 s tap length feel like the right
  unit, or would 0.25 s read better? Knobs:
  `THRUST_PREVIEW_BURN_SECONDS`, `THRUST_PREVIEW_TARGET_STEPS`,
  `THRUST_PREVIEW_STRIDE`, the two `THRUST_PREVIEW_*_COLOR`s.
- **Surfaced 2026-08-21, not started: predictor cost.** The cyan predict
  measures ~57 ms/refresh (~19 ms/frame amortized) on the dev box --
  already over the 16.7 ms 60 FPS budget by itself. `predict_trajectory`
  does ~15 `Body.position_at` evaluations per step (2x `gravity_at_t`
  over every body + the collision sweep), each recursive + trig. The fix
  is to sample every body's position *once* per timestep and share it
  across the gravity calls, the collision check, and any other
  trajectory being predicted that frame. Real win (~3x) but it lands on
  PROGRAM_FLOW.md invariants 3 and 6, so it wants a session of its own
  with a bit-equivalence check against the live integrator.
- **Step 3 (undecided): harvester structure vs asteroid mining.**
  Harvester wants a renewable ore source to exist first (scrap from
  raids may be enough); asteroids are the skill-expression option.

Previous item (takeoff steering lock rethink) shipped 2026-05-17 as a
full retirement of the time-based lock, replaced with state-based
steering gating (`steering_active = not self.landed`) plus a red HUD
prompt while landed. See PROGRAM_FLOW.md "Bug-fix history" for the
"don't reintroduce a time-based lock" warning.
