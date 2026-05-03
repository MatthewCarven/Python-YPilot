# YPilot

A 2D space-flight game in Python + pygame-ce. Orbit a planet under Newtonian
gravity, mine ore from surface deposits, construct auto-aim turrets at build
pads, and defend against UFOs that drift in from off-screen.

## Run

```
pip install pygame-ce
python ypilot.py
```

Tested on Python 3.14 / pygame-ce 2.5+. Window auto-sizes to your desktop
resolution.

## Controls

See the docstring at the top of `ypilot.py` for the full list. Briefly:

- **Mouse** aims the ship's nose
- **W / Shift+W / Ctrl+W** thrust forward (nominal / 5x boost / 10% precision)
- **S** retro-thrust at 10% of forward
- **H** toggles brake-assist autopilot. By default it matches the velocity of the nearest landable body, so a "stop" really means "match the planet" — landings on a moving body just work. **Shift** while H is on = hover-hold (zero only radial velocity, drift tangentially — useful for lining up over a build pad). **Ctrl** while H is on = damp to 0.25x strength (fine soft landings; stacks with Shift).
- **B (hold)** opens the build menu when landed near an unoccupied build pad
- **+ / -** zoom in/out; **0** resets zoom
- **/ *** shorten/lengthen the trajectory prediction window
- **F11** toggle fullscreen
- **R** reset world; **Esc** quit

Soft landing requires low relative speed (≤35 px/s vs. the body) and nose
pointed away from the planet.

## Architecture

Single-file Python, ~1290 lines. Key design choices:

- **Solar system**: a `Body` class represents the sun and planet. The planet
  orbits the sun on closed-form Keplerian rails. Ship feels gravity from
  all bodies (Newtonian summation).
- **Integrator**: leapfrog (kick-drift-kick), symplectic — closed orbits stay
  closed.
- **Trajectory predictor**: calls `body.position_at(t)` per prediction step
  so it accounts for body motion during prediction. Variable dt scales with
  window length so cost stays bounded.
- **Camera**: a `Camera` class with `pos` and `zoom` plus `world_to_screen`.
  HUD renders at native screen pixels; world objects scale.
- **Combat**: enemies and bullets travel in straight lines (no gravity, kept
  predictable). Turrets lead targets with single-pass intercept solution,
  add random ±5% aim noise per frame for the "dumb turret" feel.

## Notable design choices

- The Hill sphere of the planet is ~441 px. The default orbit at 370 px is
  just inside it — so "circular" orbits visibly precess due to solar tide.
  Intentional. It's the multi-body experience.
- Soft-landing speed is *relative* to the body, not absolute world-frame
  speed. The trajectory predictor's impact-color marker also uses relative
  speed.
- Fuel consumption scales with thrust magnitude. 5x boost burns 5x as fast.
- Brake-assist matches the velocity of the nearest landable body rather
  than zeroing absolute world velocity. This is the difference between
  "stop" (which means "drift away from a moving planet") and "match"
  (which means "settle onto it"). Two modifiers while H is on:
  **Shift** = hover-hold, kills only the radial component of relative
  velocity so altitude locks while tangential drift continues — useful
  for setting up an approach over a build pad. **Ctrl** = 0.25x scale,
  fine soft landings; stacks cleanly with hover-hold.

## Educational forks (planned)

This game's simulation is designed to be forkable into educational variants
because the physics it does is genuinely teachable.

### Elementary edition
Resource transactions become arithmetic problems ("you have 47 ore, the
turret costs 50 — how much more?"). Aimed at grade-school. UX-heavy:
encouraging tone, clear feedback, big text. The math is the bookkeeping
the game already does.

### Physics / orbital mechanics edition
Hide some HUD readouts and ask the player to derive them. "Predict before
you act" mode: enter the speed needed to circularize at radius R; if your
answer is within 5%, the engine fires automatically. Curriculum could
ladder: KE/PE → conservation → Kepler's third law → escape velocity →
Hohmann transfer.

Both forks share the engine (this repo) and add their own quiz overlay
without touching the simulation.

## Deferred TODO (applies to any fork)

- **Composable multi-part turrets** — a better tier with base + barrel +
  ammo crate, faster aim, longer range. Reuses the eventual ship-builder
  grid code.
- **Save/load to disk** — persist world state across sessions.
- **Passive harvest structures** — long-term miners and fuel synthesis
  (H₂O + ore + sunlight). Adds water as a second resource.
- **Build-while-hovering** — "unreliable catch arm" with rubber-seal
  failure flavor. Adds engineering grit.
- **Recursive build pads** — let the player construct their own pads.
- **Multiplayer sync** — v2.0, big project.
- **Player / planet HP and combat consequences** — currently enemy contact
  is instant death. Add hit points and repair-with-ore.
- **Polish pass** — engine trails, particles, sounds, screen shake.
- **Landing pads with compression absorption** — buildable that softens
  hard landings.
- **Tier 3: a moon** — proper 3-body chaos for the trajectory predictor.

## File layout

```
ypilot.py       # the entire game
README.md       # this file
.gitignore      # standard Python ignores
```
