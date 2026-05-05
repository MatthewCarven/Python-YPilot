# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project shape

Single-file pygame-ce game. Everything lives in [ypilot.py](ypilot.py) (~1780 lines). No build system, no test suite, no linter — read the file and run it.

```
pip install pygame-ce
python ypilot.py
```

There is no separate `ypilot v0.1.py` file in the working tree despite what [README.md](README.md) "File layout" claims — don't go looking for it.

## Where the real docs live

[README.md](README.md) is the authoritative design doc. It already covers:

- Full controls reference (also duplicated in the docstring at the top of [ypilot.py](ypilot.py))
- High-level architecture (Body/Camera/Ship/predictor/combat)
- "Notable design choices" — Hill-sphere precession, relative landing speed, brake-assist semantics
- "Implementation notes" — load-bearing frame-loop ordering, `Ship.update` step list, state machine, coords, brake-assist autopilot, predictor adaptive dt, tunable constants table, **bug-fix history (don't reintroduce)**, visual conventions
- "Working with the project author" — tone, UX expectations, how feedback gets delivered

Read the "Implementation notes" section before touching physics, takeoff/landing, or the predictor. The bug-fix history exists specifically to stop regressions from being reintroduced; the load-bearing ordering rules in `Ship.update` and the body/ship update sequence in the main loop are not safe to rearrange casually.

## Code map (top-level structures in [ypilot.py](ypilot.py))

- `Camera`, `Body`, `Deposit`, `BuildPad`, `Bullet`, `Enemy`, `Turret`, `Ship`, `Starfield` classes
- `make_solar_system`, `update_bodies`, `gravity_at`, `gravity_at_t` — physics setup + per-frame body update + Newtonian gravity sums (live and at-time variants — the predictor uses the at-time form via closed-form Keplerian `body.position_at(t)`)
- `build_world`, `main` — world reset and the event/update/render loop
- `draw_*` — render helpers; HUD draws in screen pixels, world objects scale via the camera

## Physics timestep

Live sim and short/medium-horizon predictor both run on a fixed `PHYSICS_DT = 1/60`. The main loop accumulates wall time and drains it in fixed chunks (capped by `MAX_FRAME_DT = 0.25` so a stall doesn't spiral). The planned (orange) ghost trajectory is intentionally bit-equivalent to what the live integrator will fly — keep that invariant if you change the predictor.

## Workflow notes

- Recent commit messages are descriptive on purpose. When figuring out *why* something is the way it is, check `git log` before assuming.
- The repo root accumulates `YYYY-MM-DD - HH-MM-SS.png` files. Those are F12 screenshots the player saved next to the game; leave them alone.
- The author tunes constants by feel via playtesting and is comfortable editing them between sessions. Diagnosis-then-patch is preferred over blind fixes; a one- or two-sentence "here's why this needs to change" before the change is welcome. If a fix doesn't actually solve the reported problem, expect honest pushback ("it still does X") — treat it as a real signal, not noise.
