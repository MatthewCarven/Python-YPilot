# YPilot

A 2D space-flight game in Python + pygame-ce. Orbit a planet under Newtonian
gravity, mine ore from surface deposits, construct auto-aim turrets at build
pads, and defend against UFOs that drift in from off-screen. There's also
a second planet — **Ember**, a rust-coloured wilderness world at orbit
radius 1800 — for when home gets boring; a Hohmann transfer takes about
52 seconds.

## Run

```
pip install pygame-ce
python ypilot.py
```
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/b26fe13c-2f4b-4020-ae4b-a164926014ae" />
<img width="1920" height="1080" alt="2026-05-04 - 21-14-45" src="https://github.com/user-attachments/assets/a024ba52-82ad-4d8f-a4f5-ec9c5a78a706" />
<img width="1920" height="1080" alt="2026-05-06 - 01-09-40" src="https://github.com/user-attachments/assets/bdd0c7c8-d181-405a-a30e-e3ed909cafd1" />

Tested on Python 3.14 / pygame-ce 2.5+. Window auto-sizes to your desktop
resolution.

## Controls

See the docstring at the top of `ypilot.py` for the full list. Briefly:

- **Mouse** aims the ship's nose
- **W / Shift+W / Ctrl+W / Ctrl+Shift+W** thrust forward (nominal / 5x boost / 1% precision / 0.1% extra-fine trim). On takeoff from the surface, the ship auto-commits to full vertical boost for ~0.3s regardless of input — gives a clean launch
- **S / Ctrl+S / Ctrl+Shift+S** retro-thrust (10% / 1% precision / 0.1% extra-fine trim)
- **Q / E** strafe left / right at 10% of forward (perpendicular to nose; does NOT cancel autopilot, so you can hover-hold + Q/E to align over a build pad)
- **H** toggles brake-assist autopilot. By default it matches the velocity of the nearest landable body, so a "stop" really means "match the planet" — landings on a moving body just work. **Shift** while H is on = hover-hold (zero only radial velocity, drift tangentially — useful for lining up over a build pad). **Ctrl** while H is on = damp to 0.25x strength (fine soft landings; stacks with Shift).
- **B (hold)** opens the build menu when landed near an unoccupied build pad
- **+ / -** zoom in/out; **0** resets zoom
- **/ *** shorten/lengthen the trajectory prediction window
- **Space** pause + plan-mode "what-if" overlay: mouse aims a burn direction, an orange ghost trajectory shows where the ship would end up if it received an instantaneous delta-v in that direction. Bodies, ship, enemies, fuel all freeze. Use it to plan Hohmann transfers or surface-skim approaches before committing. Press Space again to resume without burning.
- **[ / ]** (paused only) shorten / lengthen the planned burn duration in 0.1s steps. **Ctrl + [ / ]** = 0.01s precision step, **Ctrl+Shift + [ / ]** = 0.001s extra-fine step (mirrors the thrust trim ladder — for trimming Hohmann burns to milliseconds)
- **Enter** (paused only) commit the planned burn: apply the impulse the orange trajectory shows and unpause. Lifts off automatically if landed.
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
ypilot.py            # the entire game (~1300 lines)
ypilot v0.1.py       # pre-refactor reference; not used at runtime, kept for diff
README.md            # this file
LICENSE.md           # public domain
.gitignore           # standard Python ignores
```

## Implementation notes

These are notes for future maintainers — human or AI — picking up the
project mid-stream. They capture the load-bearing structural decisions and
the bug-fix history so old mistakes don't get reintroduced.

### Frame loop order (load-bearing)

The main loop advances `sim_time` and calls `update_bodies(sim_time)`
**before** `ship.update(dt, ...)`. During `ship.update`, every `body.pos`
and `body.vel` is frozen at the new sim_time. Several pieces of code depend
on this freeze (notably the launch-pad bump and the trajectory predictor).
Don't be tempted to interleave body and ship updates within a single frame.

### Order of operations in `Ship.update`

1. Decrement `takeoff_lock_timer`; compute `steering_active = (timer ≤ 0)`
2. Mouse aim — gated by `steering_active and mouse_aim_active`
3. Turn keys A/D, Left/Right — gated by `steering_active`
4. `_read_thrust_input` — reads W/S/Q/E + Shift/Ctrl, sets thrust flags
5. **Takeoff-lock override** — if `timer > 0`, force `thrusting=True`,
   retro/strafe `False`, `thrust_scale=BOOST`, `brake_assist=False`
6. **Landed clamp** — if landed: glue pos to surface, set vel=body.vel,
   lock angle to `landed_radial`. If thrusting/retro: bump pos to launch-pad
   height, unlatch, arm `takeoff_lock_timer = TAKEOFF_LOCK_SECONDS`.
   Else: refuel + mine + return.
7. Zero thrust if `fuel == 0`
8. Burn calculation (sums forward, retro, strafe, brake-assist contributions)
9. Leapfrog integration (kick-drift-kick, symplectic)
10. `_check_body_contact` — re-land or crash on impact

This order is the result of several debug iterations. Small reorderings can
break subtle behavior. If you change it, retest takeoff (especially trailing-
side launches relative to orbital direction) and landing carefully.

### State machine

- `alive`: True until crashed (hard impact, or contact with a non-landable
  body like the sun)
- `landed` ↔ airborne: toggled in `_resolve_surface_contact` (landing) and
  in landed-clamp's unlatch (takeoff)
- `landed_body`, `landed_radial`: stored at touchdown, persist through the
  parked period and the takeoff frame
- `takeoff_lock_timer`: when `> 0`, suppresses player input and forces full
  boost. Decremented per frame.
- `brake_assist`: H toggles. **Cancelled by W or S, NOT by Q/E.** That
  asymmetry is deliberate — strafe + autopilot together is the
  build-pad-alignment workflow.
- `hover_hold`, `brake_assist_scale`: derived per-frame from Shift/Ctrl, but
  only when forward thrust isn't pressed (Shift/Ctrl conflict with thrust
  scale modifiers otherwise).

### Coordinates and direction math

pygame screen: +x right, +y **down**. World coords match this convention.
Camera transform is `screen = (world - camera.pos) * zoom + screen_center`.

```
forward     = ( cos(angle),  sin(angle))
pilot_left  = ( sin(angle), -cos(angle))   # math -90° rotation, but
pilot_right = (-sin(angle),  cos(angle))   # pygame y-flip makes it "left"
```

### Brake-assist autopilot (`_brake_assist_accel`)

Returns `Vector2(0,0)` when off. When on:

- Picks `target = nearest_landable(pos, bodies)`
- Default mode: drives `vel - target.vel` toward zero — "match the planet"
  rather than "stop in space"
- Hover-hold (Shift): drives only the radial component of `vel - target.vel`
  to zero — altitude locks, tangential drift continues
- Damp (Ctrl): scales the desired thrust to 0.25× — gentle approach control
- Falls back to zeroing absolute `vel` when no landable body exists
- Clamps output to `BRAKE_MAX_ACCEL = 3 * SHIP_THRUST = 660 px/s²`

### Trajectory predictor

Adaptive dt: `dt = max(PREDICT_DT_MIN, seconds / PREDICT_TARGET_STEPS)`. With
current settings (`MAX=1000s`, `TARGET=6400`), full native fidelity
(`dt=1/60`) up to ~107s of look-ahead, then coarsens linearly. Bodies queried
via `body.position_at(t)` (closed-form Keplerian; doesn't share state with
the live sim, so prediction can run safely without disturbing simulation
state). Predictions are mathematically real but informationally fictional
past 2-3 planetary periods (~150s) due to chaos in the reduced 3-body
problem.

### Tunable constants (current values)

| Constant | Value | Purpose / rule of thumb |
|---|---|---|
| `TAKEOFF_LOCK_SECONDS` | 0.30 | Lock window after liftoff (user-tuned by feel) |
| `LAUNCH_PAD_HEIGHT` | 5.0 | Pre-takeoff radial bump; must exceed `body.vel * dt + safety` |
| `LATERAL_THRUST_SCALE` | 0.1 | Q/E strafe magnitude |
| `RETRO_THRUST_SCALE` | 0.1 | S retro magnitude (default, 10%) |
| `RETRO_PRECISION_SCALE` | 0.01 | Ctrl+S retro (1% precision) |
| `RETRO_FINE_SCALE` | 0.001 | Ctrl+Shift+S retro (0.1% extra-fine) |
| `THRUST_BOOST_SCALE` | 5.0 | Shift+W boost |
| `THRUST_PRECISION_SCALE` | 0.01 | Ctrl+W precision (1%) |
| `THRUST_FINE_SCALE` | 0.001 | Ctrl+Shift+W extra-fine (0.1%) |
| `BRAKE_KP` | 2.0 | Autopilot PD gain |
| `BRAKE_MAX_ACCEL` | 660 | Autopilot output cap (= 3 × `SHIP_THRUST`) |
| `LAND_SPEED_MAX` | 35 | Landing rel-speed limit |
| `LAND_ANGLE_TOLERANCE` | 30° | Landing nose-alignment limit |
| `PLANET_MU` | 4e6 | Planet's gravitational parameter |
| `SUN_MU` | 8e6 | Sun's gravitational parameter |
| `PLANET_ORBIT_RADIUS` | 800 | Planet-sun distance |
| `PREDICT_MAX_SECONDS` | 1000 | Predictor look-ahead ceiling (~16.7 min) |
| `PREDICT_TARGET_STEPS` | 6400 | Predictor step-cap (worst-case per-frame work) |

Derived: planet orbital speed ≈ 100 px/s; orbital period ≈ 50 s; Hill sphere
radius ≈ 441 px.

### Bug-fix history (don't reintroduce)

**Re-grounding loop on trailing-side launches.** Ship inherits `body.vel` at
takeoff. body.pos is frozen during `ship.update`. If `landed_radial` is
anti-parallel to `body.vel` (ship landed on the trailing side of the
planet's orbit), the ship's tangential motion *within the frame* carries it
into body's static position before the leapfrog has a chance to lift it
clear. Each frame the ship re-lands, the lock timer keeps refreshing, and
the loop only breaks when orbital geometry shifts enough. Fix: at unlatch,
bump `self.pos` to `body.pos + radial * (body.radius + LAUNCH_PAD_HEIGHT)`.
Pad height must exceed `body.vel.length() * dt`; for planet at 100 px/s and
`dt=1/60`, minimum is ~3.5, so 5.0 leaves comfortable margin.

**Mouse aim drifted nose off-vertical while parked.** Cursor anywhere off
screen-center would slowly rotate `self.angle` away from radial during the
parked phase, making takeoff thrust direction wrong. Fix: set
`self.angle = self.landed_radial` inside the landed clamp every frame, so
any aim drift is overwritten while the ship is parked.

**Takeoff sliding tangentially.** With nose off-vertical at the moment of
liftoff, boost vector wasn't radial and the ship would skitter along the
surface for a second before centrifugal effect spun it free. Fix:
`takeoff_lock_timer` suppresses mouse-aim, turn keys, and strafe for ~0.3s
post-liftoff, and the lock-override forces full boost regardless of input —
"press W, ship handles the launch."

**Strafe used to cancel autopilot.** This made hover-over-build-pad-with-
alignment-strafing impossible. Fix: removed `brake_assist = False` for Q/E.
Only forward (W) and retro (S) cancel the autopilot — those are "I'm taking
control" gestures, while strafe is a "nudge while autopilot holds position"
gesture.

**Trim modifiers blocked when any thrust pressed.** Hover-hold (Shift) and
damp (Ctrl) would deactivate even on Q/E. Fix: gate the trim modifier
reads on forward AND retro only — both use Shift/Ctrl as scale modifiers
(forward: Shift=boost, Ctrl=precision, Ctrl+Shift=extra-fine; retro:
Ctrl=precision, Ctrl+Shift=extra-fine). Strafe doesn't use modifiers, so
Q/E never suppresses the trim. Note: pressing forward or retro already
cancels brake-assist, so this gate is technically defensive — but explicit
is better than relying on the cancel ordering.

### Visual conventions

- Forward thrust: orange flame, length scales with `sqrt(thrust_scale)` (so
  5× boost has a flame about 2.2× normal size, not 5×)
- Retro thrust: small blue-white flame in front of nose
- Strafe Q/E: small orange puff on the *opposite* side of the ship from the
  motion direction (Newton's 3rd law — exhaust shoots one way, ship goes the
  other)
- Landed: green ring around ship
- Brake-assist on: cyan ring around ship
- Trajectory line: blue → fading-to-background gradient with stride 6
- Trajectory impact marker: green dot if soft (within `LAND_SPEED_MAX`),
  red dot if hard

### Working with the project author

- Casual conversational tone; uses `:-{D`-style smileys
- Strong UX instinct, will sharply call out usability problems
- Tunes constants by feel via playtesting; subscribes to "near enough is
  good enough" — bespoke craftwork is appreciated but not required
- Prefers diagnosis-then-patch over blind fixes; appreciates a brief
  explanation of *why* a change is needed before the change is made
- Will push back if a fix doesn't actually solve the problem; "it still
  does X" is honest feedback worth digging into, not vague complaint
- Comfortable enough with code to tweak constants directly between sessions
- Recent git history is the most reliable source of truth for what changed
  and why; commit messages have been kept descriptive on purpose
