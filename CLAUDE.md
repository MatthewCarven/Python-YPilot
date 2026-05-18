# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Run / test

```
pip install pygame-ce
python ypilot.py
```

Optional: `winget install ffmpeg` (Windows) or `brew install ffmpeg` to enable F9 video recording. The game silently no-ops F9 if ffmpeg isn't on PATH.

There is **no test suite, no linter config, and no build step**. The project is validated by playtesting — launch the game and exercise the change in-flight. The author tunes constants by feel; "near enough is good enough" applies.

## Repository shape

The entire game lives in a single file: `ypilot.py` (~5200 lines). There is no module split, no asset pipeline, no ECS. Every game object is a small class with `update()` / `draw()` methods, and `main()` drives the loop. The codebase deliberately trades modular fanciness for diff-readability.

The repo root is **not a git repository**.

## Existing documentation — read these before non-trivial work

The author has split design docs by topic. Always consult the relevant doc(s) before changes that touch their domain — they encode load-bearing invariants and bug-fix history:

- **[DESIGN.md](DESIGN.md)** — architecture, physics model (leapfrog, hierarchical Keplerian system), autopilots, tunable constants, planned forks. Read this first for any feature work.
- **[PROGRAM_FLOW.md](PROGRAM_FLOW.md)** — per-frame sequencing, ship-state machine, recorder threading, and a **"don't reintroduce" bug-fix history**. Read this before reordering anything in `Ship.update` or the main loop.
- **[CONTROLS.md](CONTROLS.md)** — full keyboard/mouse reference, including modifier ladders (Shift/Ctrl/Alt scale steps for thrust, plan-mode duration, plan-mode fire-time).
- **[TRAJECTORY.md](TRAJECTORY.md)** — what each marker on the predicted trajectory means (apsis dots, closest-approach diamond, SOI rings, chaos cone).

## Architecture invariants (don't break these)

These are the load-bearing rules that surface bugs if violated. They are documented at length in PROGRAM_FLOW.md "Bug-fix history" — summarised here as a reminder of *what* to be careful about:

1. **Body update order matters.** `update_bodies(t)` walks parents before children — for the default world that's Sun → Planet → Moon → Ember → Frostbite, but in random universes (`Shift+R`) the order is whatever `make_random_solar_system` returns: Sun first, then heliocentric planets, then moons after their parent planet. Each child reads its parent's freshly-updated `pos`/`vel`, so the dependency-order invariant is fixed regardless of layout.
2. **`update_bodies(sim_time)` runs before `ship.update(dt, ...)` each physics tick.** Body state is frozen during ship update; multiple subsystems (launch-pad bump, brake-assist target velocity, trajectory predictor sampling) depend on this freeze. Don't interleave body and ship updates within a frame.
3. **Predictor and live integrator share the same `PHYSICS_DT` leapfrog step** for short horizons. This bit-equivalence is why path-hold can track an orange line as if it were the live trajectory. The predictor uses `body.position_at(t)` (closed-form, stateless) while the live sim uses `body.pos` (live state) — keep these two paths in sync if you change body motion.
4. **Path-hold corrective accel is computed ONCE per `Ship.update()`** (against start-of-step state) and cached on `self._path_hold_cached_accel`. Both leapfrog half-kicks read the cached value via `_compute_accel`. Computing fresh per half-kick reintroduces a one-step phase offset the controller would burn fuel fighting forever.
5. **On plan-mode commit, snapshot the predictor BEFORE applying live burns.** If landed, mirror the launch-pad bump in the snapshot's `pos0`. Otherwise the snapshot's first sample is bump-height above where the live ship actually starts and path-hold will fight that offset.
6. **`gravity_at` (live) vs `gravity_at_t` (predictor)** — the predictor uses the time-parameterised version so it accounts for body motion during prediction rather than freezing the system at `t_now`. Don't accidentally swap them.
7. **`brake_assist` target body is latched at H-press time** (sticky-on-engage), not recomputed per frame. A Moon flyby would otherwise yank the autopilot off Planet mid-hover.
8. **Strafe (Q/E) deliberately does NOT cancel autopilot** — only forward (W) and retro (S) do. The hover-hold + strafe combo is the build-pad alignment workflow; preserve this asymmetry.

## Tunable constants

Most numbers in the game are named constants at the top of `ypilot.py`. The author tweaks them between sessions by hand. DESIGN.md "Tunable constants" lists the ones most likely to be tuned by feel and the rules of thumb behind them. Prefer adjusting an existing constant over introducing a new one.

## Working with the author

From README "Working with the project author":

- Casual tone; uses `:-{D`-style smileys; expects the same in return.
- Strong UX instinct — will sharply call out usability problems.
- Prefers **diagnosis-then-patch over blind fixes**. Briefly explain *why* a change is needed before making it.
- "It still does X" is honest, useful feedback worth digging into — not a vague complaint. Don't claim a bug is fixed without evidence; if you can't run the game (no display, no input), say so explicitly rather than asserting success.
- Comfortable enough with code to tweak constants directly between sessions, so don't hide tuning knobs behind unnecessary abstraction.
- Recent git history (when present) is the most reliable source of truth for what changed and why; commit messages have been kept descriptive on purpose.
