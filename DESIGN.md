# Design

The *why* behind YPilot's structure. For *what* the keys do, see
[CONTROLS.md](CONTROLS.md). For *when* things happen during a frame, see
[PROGRAM_FLOW.md](PROGRAM_FLOW.md). For *how to read the trajectory line*,
see [TRAJECTORY.md](TRAJECTORY.md).

## Architecture in one breath

Single-file Python (`ypilot.py`, ~4500 lines) on top of pygame-ce. The
sim is a fixed-timestep leapfrog integrator over a hierarchical Keplerian
solar system; the visible game (mining, building, combat, AA defence,
missile printers, save/load, random universes) hangs off that. There is
no ECS, no scene graph, no asset pipeline — every game object is a
small class with `update()` / `draw()` methods, and `main()` drives the
loop.

The codebase trades modular fanciness for diff-readability: when you
change something, you can usually see all of its dependents on the same
screen.

## Solar system

### Bodies

A `Body` represents any celestial object — Sun, planet, or moon. Bodies
have mass (`mu` — gravitational parameter), an optional parent, an orbit
radius (semi-major axis `a`), an initial phase angle, a `landable` flag,
and optional `eccentricity` (≤ 0.3) + `arg_periapsis` for elliptical
orbits.

The default world is hand-tuned and circular:

```
Sun
└── Planet     (orbit_radius=800,  landable, e=0)
│   └── Moon   (orbit_radius=250 around Planet, landable, e=0)
└── Ember      (orbit_radius=1800, landable, e=0)
└── Frostbite  (orbit_radius=3000, landable, e=0)
```

Each body has two methods:

- `update_at(t)` — sets `pos` and `vel` to the body's state at sim time
  `t`. Reads its parent's *current* `pos` / `vel`, so the order in which
  bodies are updated matters: parent before child.
- `position_at(t)` — closed-form recursive query for the body's
  position at any time, without touching state. Used by the trajectory
  predictor.

For circular orbits both methods take a fast path that's bit-identical
to the pre-eccentric code (so path-hold's predictor↔live agreement
stays exact on the default world). For e > 0, `solve_kepler` runs a
3–4-iteration Newton solve (5-iter cap defensively).

`update_bodies(bodies, t)` walks the list in dependency order
(`Sun → Planet → Moon → Ember → Frostbite`) so the chain stays consistent
within a single physics step. The two outer planets parent directly to
the Sun; the Moon's Planet-parented entry sits before them in the list
so it can read Planet's freshly-updated state. `make_random_solar_system`
returns bodies in the same parent-before-child order — Sun, then planets
sorted by semi-major axis, then moons grouped after their parent.

### Why hierarchical orbits?

Two reasons:

1. **Composition is free.** `Moon.position_at(t)` recurses through its
   parent and analytically composes Sun + Planet + Moon offsets in one
   call. Gravity prediction sees a moving moon at the right place
   without the predictor needing to know anything about the moon's
   parent.
2. **Tunable difficulty.** The Moon's orbit radius (250 px around
   Planet) is well inside Planet's Hill sphere (~441 px), but the
   Moon's *own* Hill sphere is only ~64 px. Above the Moon's surface
   there's only ~39 px before Planet's gravity overpowers Moon's —
   so landings need real precision.

### Why four landable bodies (in the default world)?

With one planet, "navigate" means "fly forward". With two, you get a
Hohmann transfer (Planet ↔ Ember, ~52 s burn). With four — Planet, Moon,
Ember, and Frostbite — the trajectory predictor's closest-approach marker
always has somewhere meaningful to point, and the *resource economy*
gives each body a distinct role:

- **Planet** — main fortress (5 build pads), starter ore (2 deposits).
- **Moon** — moving point-defense platform (2 build pads orbiting Planet
  at ~12 s period). No ore.
- **Ember** — forward base (3 build pads), no ore. You haul ore here.
- **Frostbite** — the ore world (6 deposits), no defenses. A
  ~92 s Hohmann from Planet, ~146 s from Ember. The round trip is the
  whole point: every defensive build commits the player to a real
  expedition.

The asymmetry is what makes the orbital mechanics matter beyond
sightseeing. Mining and defending happen on different worlds; cargo
trips have weight (even before any explicit cargo-capacity system —
just by virtue of travel time and exposure to UFOs en route).

The Moon **laps the player's default 370 px orbit** because shorter
orbits are faster (`v = √(μ/r)`). Intercepts are real puzzles, not just
"point and fly".

## Random universes

`Shift+R` rolls a fresh universe with a random planet count; `Ctrl+Shift+R`
opens a digit-only modal prompt for a specific seed (the latter is how
you re-summon a memorable roll across sessions). `Ctrl+Alt+Shift+1..6`
rolls a fresh universe with a **pinned** planet count — useful for
quickly testing single-planet collapse, two-planet Hohmann setups, etc.
without spam-rolling Shift+R until the right count appears.

`make_random_solar_system(seed, n_planets_override=None)` is
deterministic — same `(seed, n_planets)` pair, same world. The override
short-circuits the natural `rng.randint(1, 6)` planet-count roll *after*
the randint has been called, so rng state stays in lockstep up to that
point; only the count itself diverges.

### Layout

- **1–6 planets** (`RANDOM_PLANETS_MIN/MAX`), shell-packed by geometric
  spacing (`RANDOM_SPACING_RATIO_MIN/MAX = 1.7..2.4`) so adjacent shells
  can't overlap even at max eccentricity. Innermost is at least
  `RANDOM_FIRST_AXIS_MIN..MAX = 600..1200` from the sun.
- **0–2 moons per planet**, capped at **4 total** so the predictor cost
  stays bounded (each body adds Kepler-solve work to every predictor
  step). Moons live within `RANDOM_MOON_ZONE_FRAC = 0.4 × SOI` of their
  parent — Hill/2.5-ish — so they don't get yanked off at periapsis of
  an elliptical planet orbit.
- **Eccentricity ≤ 0.3** (`RANDOM_MAX_E`). A two-pass roll uses
  provisional `e_next = 0` first, then refines knowing the actual
  neighbours. For e ≤ 0.3 it converges after one pass; the second is
  belt-and-braces.
- **Color palette** indexed by orbit position (hot red innermost →
  icy white-blue outermost). Names are `P1..P6` / `P{i}M{j}` so
  save-file `body_ref` lookups stay stable per seed.

### Allocation policy

`build_world_for(spec)` picks the **innermost landable** planet as the
"starter" (where the ship spawns and gets its bootstrap deposits + most
of the pads) and the **outermost landable** as the "destination" (the
ore world, no pads). Middle bodies pick up forward-base pads. This
preserves the "mine here, defend there, travel matters" gameplay arc
regardless of how many planets rolled.

In a single-planet system, the lone planet collapses both roles —
6 deposits + 5 pads. Defensive builds compete with mining for the
same surface real estate, which is its own kind of puzzle.

AA batteries are rolled per-world with a seed offset
(`seed ^ 0xBA77E1F`) so the same world seed always produces the same
battery layout — including for the default world (`seed=0`).

## Physics

### Integrator

**Leapfrog (kick-drift-kick), symplectic.** Closed orbits stay closed.
Energy oscillates around the true value rather than drifting, which
matters because the player will sit in a single orbit for tens of
seconds at a time.

```
v_half = v + a(pos) * dt/2     # kick
pos    = pos + v_half * dt      # drift
v      = v_half + a(pos) * dt/2 # kick
```

The same step is used live (`Ship.update`) and in the predictor
(`Ship.predict_trajectory`), so over short/medium horizons the predicted
ghost line is **bit-equivalent** to what the live integrator will fly —
ignoring chaos amplification of any residual diff. That's why the
trajectory predictor is trustworthy enough to plan Hohmann transfers
against.

### Gravity

Newtonian summation over all bodies:

```
F = Σ_i  μ_i / r_i² · (body_i - pos)/r_i
```

Two helper functions:

- `gravity_at(pos, bodies)` — uses each body's current `pos`. Used by
  the live `Ship._compute_accel`.
- `gravity_at_t(pos, t, bodies)` — uses `body.position_at(t)`. Used by
  the predictor so it accounts for body motion during prediction
  rather than freezing the system at `t_now`.

### Fixed timestep

Live physics runs in fixed `PHYSICS_DT = 1/60 s` chunks via a wall-time
accumulator. Each frame, measured wall time is fed in (scaled by
`time_scale` from F7/F8, capped at `MAX_FRAME_DT = 0.25 s`) and the loop
runs as many `PHYSICS_DT` ticks as fit, draining the accumulator.

The cap prevents a stall from causing a burst of catch-up steps. The
fixed step keeps the predictor and the live integrator producing
matching trajectories regardless of frame rate or time scale.

## Trajectory predictor

`Ship.predict_trajectory(bodies, t_start, seconds, ...)` walks a leapfrog
forward from the ship's current state and returns `(points,
impact_speed, dt)`.

### Adaptive step

```
dt = max(PHYSICS_DT, seconds / target_steps)
```

Where `target_steps` is the runtime budget (default 6400, halved/doubled
by F5/F6, clamped to [100, 102400]). With the defaults, you get full
native fidelity (`dt = 1/60`) up to ~107 s of look-ahead, then
coarsening linearly. Cost stays bounded regardless of horizon.

The step is *intentionally* the same as the live `PHYSICS_DT` for short
horizons. That's the key invariant: predictor output ≡ live integrator
output, modulo chaos.

### Body-time sampling

Bodies are queried at the matching time via `body.position_at(t)` —
closed-form Keplerian, doesn't share state with the live sim, so the
predictor can run safely without disturbing simulation state. This
matters because the predictor runs *during render*, after live physics
has already advanced.

### Burn injection

The predictor accepts a `pending_burns` list of
`(t_apply, burn_dir, duration_signed)` tuples. The integrator inserts
each kick at the step boundary that contains its apply-time, mirroring
how live `Ship.apply_pending_maneuvers` fires them. This is what makes
the orange plan-mode chain trajectory faithful to what Enter will
actually deliver.

### Path-hold snapshot

When a chain is committed, the predictor is run once more with
`out_velocities` populated, and the resulting `(t, pos, vel)` samples
are stored on the ship (`set_planned_trajectory`). The path-hold
autopilot's PD controller looks up the planned state at `sim_time` by
linear interpolation between bracketing samples.

The snapshot extends past the last burn by
`PATH_HOLD_POSTBURN_SECONDS = 60 s` so path-hold has somewhere to track
to *after* the chain finishes — otherwise it would auto-disengage the
moment the last burn fired.

### Live cyan = post-burn trajectory

The cyan predict line that runs every frame folds
`ship.pending_maneuvers` into its prediction, so the line shows the
trajectory the ship *will* fly post-burns rather than a counterfactual
"if I don't burn" path. Chevrons are drawn at each scheduled burn
point; as burns fire and pop from `pending_maneuvers`, the
corresponding chevron evaporates and the line straightens for that
segment automatically. The horizon stretches past the last pending
burn using `PLAN_CHAIN_LOOKAHEAD_SCALE` so the user can see what the
chain results in.

Apsides, closest-approach marker, and SOI crossings annotate this
post-burn trajectory, so after committing a Hohmann insertion the
peri/apo dots immediately reflect the *resulting* orbit, not the
pre-burn ellipse.

### Predict cache

The full cyan pipeline (`predict_trajectory` + `find_apsides` +
`find_soi_crossings` + `find_closest_approach`) is amortized across
`PREDICT_CACHE_INTERVAL = 3` frames. The cache invalidates whenever:

- `paused` toggles (sim went still or resumed),
- the pending burn count changes (a burn fired or the chain was
  extended via plan-mode commit),
- `predict_seconds` or `predict_target_steps` mutates (`/`, `*`, F5,
  F6),
- the apsis or closest-approach anchor body changes.

When paused, ship state is invariant so the cache stays exact across
arbitrary replay frames; the periodic refresh only matters while
running. The trade-off when running is that the rendered trajectory's
*start* lags the ship by up to (N − 1) frames of motion (~5 px at
default time scale). Set `PREDICT_CACHE_INTERVAL = 1` to disable
caching entirely.

## Brake-assist autopilot

`Ship._brake_assist_accel(pos, vel, bodies)` returns the desired
corrective acceleration. Behaviour:

- **Default mode** — drive `vel - target.vel` toward zero, where
  `target` is the landable body the ship was geometrically closest
  to *at the moment H was pressed* (`nearest_landable(pos, bodies)`).
  "Stop" really means "match the planet"; landings on a moving body
  just work.
- **Sticky-on-engage targeting** — `target` is latched on the first
  frame after toggle and held until brake-assist disengages. Solves
  two things at once: a Moon swooping past a Planet orbit no longer
  lurches hover (target stays on Planet because that's what was
  closest at engage), and Moon landings work normally (fly close,
  press H, target latches on Moon). Retargeting is explicit: tap H
  off, tap H on. Picks geometric nearness rather than mu/r²
  dominance because the dominance threshold for the Moon is a
  ~31 px shell above its surface — too tight for a workable
  approach window.
- **Hover-hold (Shift)** — kill only the *radial* component of relative
  velocity. Altitude locks while tangential drift continues. Useful
  for setting up an approach over a build pad.
- **Damp (Ctrl)** — scale the desired thrust to 0.25×. Gentle approach
  control. Stacks with hover-hold.
- **Fallback** — if no landable body exists, zero absolute velocity.

Output is clamped at `BRAKE_MAX_ACCEL = 3 × SHIP_THRUST = 660 px/s²` so
brake-assist can't deliver more thrust than the engines could.

The PD controller has `BRAKE_KP = 2.0` and uses gravity feed-forward
(`-BRAKE_KP × vel_to_kill - gravity`) so it doesn't fight gravity while
holding station.

## Path-hold autopilot

Different state-space target than brake-assist: instead of "match the
nearest body's velocity", path-hold tracks the previously-committed
plan-mode trajectory.

```
a = PATH_HOLD_KP × (planned_pos - pos) + PATH_HOLD_KD × (planned_vel - vel)
```

Clamped at `PATH_HOLD_MAX_ACCEL = 0.05 × SHIP_THRUST = 11 px/s²` —
deliberately small. If the live trajectory has diverged enough that a
5 %-thrust correction can't catch up in a few seconds, the plan is
probably stale and re-planning is the right answer. Path-hold is
**phase-drift correction**, not "fly anywhere I imagine".

Why mutually exclusive with brake-assist? They'd be a tug-of-war —
brake-assist wants to match the body, path-hold wants to match the
plan, and the plan probably already accounts for body motion. Letting
both run would cost fuel and produce nonsense behaviour.

### One-update caching of the corrective accel

The path-hold accel is computed *once* per `Ship.update()` against
start-of-step state and reused for both leapfrog half-kicks. Computing
fresh per half-kick would compare start-of-step ship pos to end-of-step
plan time — a one-step phase offset the controller would burn fuel
fighting forever. (See [PROGRAM_FLOW.md § Bug-fix
history](PROGRAM_FLOW.md#bug-fix-history) for the version of this fight
that was caught.)

## Plan mode (chained burns)

Spacebar pauses the world entirely — bodies, ship, enemies, bullets,
fuel, refuel — and opens a what-if overlay. Mouse aims a burn direction;
duration is signed (negative = retro from same aim point).

### Why instantaneous Δv?

The model is "instantaneous Δv of `SHIP_THRUST × duration` along the
aimed vector". Real burns happen *over* time. For short burns (a few
seconds) the impulse model is within a hair of reality and keeps the
math one-line. The error grows with burn duration but is bounded by
gravity-gradient effects, which are small for the ship's mass.

### Maneuver chain

- **N** pushes the current preview onto the queue and starts a new
  preview, defaulting to the same fire-time as the just-queued burn
  (camera stays glued).
- **Backspace** pops the most recent queued burn back into the editable
  preview slot, restoring its duration AND fire-time.
- **Enter** commits the full chain. Burn 0 fires immediately
  (`apply_pending_maneuvers` fires anything with `t_apply ≤ sim_time`);
  burn k fires at `sim_time + offset[k]`. The full chain is also fed
  to the predictor with `pending_burns` so the orange line shows
  exactly what Enter will deliver.

### Camera follows the chain

While paused, the camera tracks the planned trajectory to the *current
preview burn's* fire-time, not the ship. Adjusting `,` / `.` slides the
view to where the next burn will fire. With an empty queue and offset
0, this collapses to the ship's current pos so the first burn still
feels ship-anchored.

### Predictor-snapshot on commit

On Enter-commit, `predict_trajectory` is run one final time with
`out_velocities` populated. The resulting `(t, pos, vel)` samples
become the ship's `planned_trajectory` — what J (path-hold) tracks.
Snapshot horizon is `chain_span + PATH_HOLD_POSTBURN_SECONDS`.

## Combat

Enemies and bullets travel in **straight lines** (no gravity), kept
predictable so the player isn't doing 3-body intercepts on top of
everything else. Enemies course-correct toward the ship every
~60 s ± 50 % so they don't sail past harmlessly if the ship has moved.

Missiles are the deliberate exception: they fly **under gravity** with
their own bespoke flight plan computed at launch time (see
"Missile printers" below).

Turrets lead targets with a **single-pass intercept solution**:

```
t_lead = distance / BULLET_SPEED
predicted = target.pos + target.vel * t_lead
```

Then add `±5 % range × random` aim noise per frame for the "dumb
turret" feel. There's no recursive lead-calc — one pass is good enough
for the gameplay budget.

Enemy-ship contact = instant kill (currently). Bullet-enemy contact
gives `ENEMY_KILL_REWARD = 6 ore` per kill. AA-bullet-ship contact is
also instant kill — same damage as a UFO collision. AA-bullet-body
contact (the AA fired through its own planet) silently absorbs the
bullet on impact, so optimistic firing solutions don't grief the player
from the wrong side of a planet.

### Planetary AA batteries

Stationary defenders mounted to landable bodies. Per-world deterministic
roll: `_roll_batteries(bodies, seed)` rolls each landable body with
`BATTERY_SPAWN_PROBABILITY = 0.5` — about half of bodies get one. The
seed is the universe seed XOR'd with `0xBA77E1F` so the same world
always produces the same battery layout.

Each battery has its own intercept solver:

1. While idle, every `BATTERY_SOLVE_INTERVAL = 0.25 s`, run the
   **gravity-affected ship trajectory predictor** forward and look for
   a hit point along the predicted path that a straight-line bullet
   could reach in the matching time. Up to `BATTERY_SOLVE_MAX_ITERS = 6`
   passes with `BATTERY_PREDICT_STEPS = 120` integration steps.
2. **Refuses to converge** while the ship is burning W or S. That's
   the dodge escape hatch — thrust breaks the lock by making the
   gravity-only predictor's path wrong.
3. When the solver converges, paint a **targeting laser** at the
   predicted hit point for `BATTERY_LASER_DURATION = 1 s`, then fire.
4. Cooldown `BATTERY_FIRE_COOLDOWN = 4 s` between shots.

Toggle the system on/off with **Shift+F10**. Disabling drops any
in-flight hostile bullets so a shot already on its way doesn't kill you
mid-air after the toggle.

### Missile printers

Player-built counter to AA batteries (and a longer-range anti-UFO
option). Constructed on a build pad like a turret but pricier
(`MISSILE_PRINTER_COST = 150`), longer-ranged
(`MISSILE_PRINTER_RANGE = 5000`), and slower-firing
(`MISSILE_PRINTER_COOLDOWN = 8 s`). Each shot also costs
`MISSILE_ORE_COST = 30` ore at fire-time, so the structure remains a
sustained drain on the economy rather than fire-and-forget.

Target priority: **AA batteries > UFOs**. Once an AA battery is in
range, every shot goes there until it's gone, then the printer falls
back to UFO duty.

Each missile flies under gravity with **constant thrust toward a
static aim-point computed at launch**. `plan_missile_flight` runs an
intercept solver over the missile's gravity-affected trajectory:

1. Pick an initial aim point (target's predicted future position).
2. Integrate the missile forward `MISSILE_PLAN_HORIZON = 12 s` toward
   that aim point.
3. Find the closest pass to the target's actual predicted trajectory.
4. Re-pick the aim point as the target's position at the closest-pass
   time, repeat (up to `MISSILE_PLAN_SOLVE_ITERS = 5`).

The same gravity sampler and thrust law run in both planner and live
update, so the live missile flight is **bit-equivalent to the planned
line** — no PD path-hold needed, the orange trail draws the actual
flight path. Detonation is `MISSILE_BLAST_RADIUS = 18 px` proximity
on either an AA battery or a UFO.

## Camera

A `Camera` class with `pos` and `zoom`. World-to-screen transform:

```
screen = (world - camera.pos) * zoom + screen_centre
```

HUD renders at native screen pixels; world objects scale. Stars (the
parallax background) are drawn in screen space, not scaled by zoom, so
they always look like single pixels regardless of zoom level.

### Click-drag pan with ease-back

Holding LMB on the playfield drags the camera off the ship in world
space (delta divided by zoom so the world tracks the cursor 1:1). On
release, the offset eases back to zero over `CAM_PAN_RECENTER_SECONDS
= 7 s` with an `easeOutCubic` curve — most of the travel happens early
so the viewport lunges back, then settles gently. The ease-back is
applied on top of whichever camera anchor is active (ship-following or
plan-mode-trajectory-following), so it composes naturally with both.

Disabled while the build menu (B held) or the seed-prompt overlay is
intercepting clicks — those workflows want LMB for their own purposes.

### Wheel-peek zoom with ease-back

Zoom is split into two values that compose multiplicatively:

```
camera.zoom = clamp(cam_zoom_rest × cam_zoom_peek, ZOOM_MIN, ZOOM_MAX)
```

- **`cam_zoom_rest`** — the persistent zoom level the player chooses
  with `+` / `-` / `0`. Survives across frames; the camera's
  "home" zoom.
- **`cam_zoom_peek`** — a transient multiplier driven by the mouse
  wheel. Each tick multiplies/divides by `ZOOM_STEP`; with no wheel
  input it eases back to 1.0.

Every frame the effective `camera.zoom` is rebuilt from the two
values, so any consumer that reads `camera.zoom` (rendering, world-to-
screen transforms) keeps working without knowing about the split.

**Ease-back.** When the wheel stops, `cam_zoom_release_factor`
snapshots the current peek and `cam_zoom_release_elapsed` ticks up
each frame. Over `CAM_ZOOM_RECENTER_SECONDS = 11 s` the peek glides
back to 1.0 with `easeOutCubic` — slower than the pan ease-back
(7 s) because zoom is the more disorienting axis to snap on. A
faster zoom return reads as a jarring scale-change; the longer
ease lets the eye keep tracking world content while the camera
quietly homes back.

**Spam-scroll holds the peek.** Every wheel tick resets
`cam_zoom_release_elapsed = 0.0` and re-snapshots
`cam_zoom_release_factor`, so as long as the player keeps scrolling
the peek doesn't drift. Pausing the wheel kicks off the return.

**Why "peek" and not "zoom"?** The persistent/transient split makes
the keyboard `+/-` keys feel like setting a *resting* zoom for the
session (landing-friendly, say) and the wheel feel like a glance — you
spin out, look at a distant body, let go, and the camera comes back to
the level you set up for the next landing. Two distinct input modes
mapped to the same physical axis, without the wheel destroying your
working zoom level.

## Save / load

State persists to disk via `save_session` / `apply_session`. F3
quicksaves to `saves/quicksave.json` (the legacy single slot); Ctrl+F1..F9
saves to `saves/quicksave_N.json`; Shift+F1..F9 loads from the same
slots; F2 loads the legacy slot.

### Atomic writes

Saves go through `path.tmp` and a `.bak` rotation:

```
1. Write JSON to path.tmp
2. If path exists, rename path → path.bak (rotate previous save)
3. Rename path.tmp → path
```

A crash mid-write can corrupt the `.tmp`, but the active slot stays
intact. Manual recovery from the `.bak` is one rename away.

### Versioning

`SAVE_VERSION = 2` is stored in every save. `apply_session` is
**best-effort with warnings**: if the saved version doesn't match,
loading still happens but a HUD toast tells the player that the save
was partially restored. Fields the new version added default to
sensible values; fields the new version removed are silently ignored.

### Universe in the save

Each save stores the active universe spec. Three shapes:

```json
{"type": "default"}
{"type": "random", "seed": 1234567890}
{"type": "random", "seed": 1234567890, "n_planets": 3}
```

The `n_planets` field is only present for universes rolled via
`Ctrl+Alt+Shift+1..6`. It's optional — older saves (and `Shift+R`
saves) don't carry it, and `spec.get("n_planets")` returns None,
which makes `make_random_solar_system` fall back to its natural
`rng.randint(1, 6)` planet-count roll. Backward compatible.

On load, `build_world_for(spec)` re-seeds the random generator before
applying ship state, so a quickload of a random universe lands you
back on the same world even though the seed was rolled in a previous
session.

Bodies are referenced by `name` (e.g., `"P3M1"`) in the save; on load
they're looked up against the freshly-rebuilt world. Mismatched names
(e.g., trying to load a save into a different world) trigger a partial
restore with a warning toast.

## Coordinates and direction math

pygame screen: +x right, +y **down**. World coords match this convention
(no flip on render). Direction vectors:

```
forward     = ( cos(angle),  sin(angle))
pilot_left  = ( sin(angle), -cos(angle))   # math -90° rotation, but
pilot_right = (-sin(angle),  cos(angle))   # pygame y-flip makes it "left"
```

The pygame y-flip is why "pilot left" is rotated *clockwise* from
forward in math convention but appears counter-clockwise on screen.
The strafe directions are derived once and reused — no run-time sign
flipping.

## Visual conventions

| Element | Rendering |
|---|---|
| Forward thrust | Orange flame, length scales with `√thrust_scale` (so 5× boost has a flame ~2.2× normal size, not 5×) |
| Retro thrust | Small blue-white flame in front of nose |
| Strafe Q/E | Small orange puff on the *opposite* side from motion direction (Newton's 3rd law) |
| Landed | Green ring around ship |
| Brake-assist on | Cyan ring around ship |
| Path-hold on | Orange ring around ship (matches plan trajectory colour) |
| Trajectory line (live) | Cyan → bright red gradient, stride 6, 1→3 px chaos cone |
| Trajectory line (plan) | Orange → bright red gradient, same stride and ramp |
| Trajectory tick marks | Perpendicular line every 5 s, screen-space length |
| Impact marker | Green dot if soft (≤ `LAND_SPEED_MAX`), red dot if hard |
| Periapsis | Peach ringed dot (5 px outline + 2 px filled core) + prograde arrow |
| Apoapsis | Cool-blue ringed dot, same shape + prograde arrow |
| Closest-approach | Magenta diamond outline (different shape from apsis dots) |
| SOI crossing | Small gold outlined ring |
| Chain burn point | Filled chevron (pale orange) + numeric label |
| Plan-mode burn arrow | Orange line from ship in burn direction, length scales with abs(duration) |

The colour palette is deliberately limited: cyan and orange are the two
"I'm a predictor annotation" colours; everything else is world content.
Peach + cool blue distinguish peri from apo without needing a legend.
Magenta and gold are reserved for predictor annotations that aren't
about the orbit anchor.

## Tunable constants

The full list is at the top of `ypilot.py`. The ones most likely to be
tweaked by feel:

| Constant | Value | Purpose / rule of thumb |
|---|---|---|
| `TAKEOFF_LOCK_SECONDS` | 0.30 | Lock window after liftoff; user-tuned by feel |
| `LAUNCH_PAD_HEIGHT` | 5.0 | Pre-takeoff radial bump; must exceed `body.vel × dt + safety` |
| `LATERAL_THRUST_SCALE` | 0.1 | Q/E strafe magnitude |
| `RETRO_THRUST_SCALE` | 0.1 | S retro magnitude (10 %) |
| `RETRO_PRECISION_SCALE` | 0.01 | Ctrl+S retro (1 %) |
| `RETRO_FINE_SCALE` | 0.001 | Ctrl+Shift+S retro (0.1 %) |
| `THRUST_BOOST_SCALE` | 5.0 | Shift+W boost |
| `THRUST_PRECISION_SCALE` | 0.01 | Ctrl+W precision (1 %) |
| `THRUST_FINE_SCALE` | 0.001 | Ctrl+Shift+W extra-fine (0.1 %) |
| `BRAKE_KP` | 2.0 | Brake-assist PD gain |
| `BRAKE_MAX_ACCEL` | 660 | Brake-assist output cap (= 3 × `SHIP_THRUST`) |
| `PATH_HOLD_KP` | 2.0 | Path-hold proportional gain |
| `PATH_HOLD_KD` | 3.0 | Path-hold derivative gain |
| `PATH_HOLD_MAX_ACCEL` | 11 | Path-hold output cap (= 0.05 × `SHIP_THRUST`) |
| `PATH_HOLD_POSTBURN_SECONDS` | 60.0 | Snapshot horizon past last chain burn |
| `LAND_SPEED_MAX` | 35 | Landing rel-speed limit (relative to body) |
| `LAND_ANGLE_TOLERANCE` | 30° | Landing nose-alignment limit |
| `PLANET_MU` | 4 000 000 | Planet's gravitational parameter |
| `SUN_MU` | 8 000 000 | Sun's gravitational parameter |
| `PLANET_ORBIT_RADIUS` | 800 | Planet–Sun distance |
| `MOON_MU` | 200 000 | Moon's gravitational parameter |
| `MOON_ORBIT_RADIUS` | 250 | Moon–Planet distance (well inside Planet's Hill ~441) |
| `MOON_RADIUS` | 25 | Moon body radius |
| `PLANET2_MU` (Ember) | 6 000 000 | Heavier than Planet |
| `PLANET2_ORBIT_RADIUS` | 1800 | Hohmann transfer ~52 s |
| `PLANET3_MU` (Frostbite) | 2 500 000 | Lighter than Planet (~80 % surface gravity) |
| `PLANET3_ORBIT_RADIUS` | 3000 | Hohmann from Planet ~92 s; from Ember ~146 s |
| `PLANET3_RADIUS` | 80 | Smaller than Planet — silhouette reads as "distant" |
| `RANDOM_PLANETS_MIN/MAX` | 1 / 6 | Planet count clamp for `Shift+R` |
| `RANDOM_MOONS_TOTAL_MAX` | 4 | Cap on total moons (predictor cost is per-body-per-step) |
| `RANDOM_MAX_E` | 0.3 | Max eccentricity in random worlds (default world stays at 0) |
| `RANDOM_SPACING_RATIO_MIN/MAX` | 1.7 / 2.4 | Geometric shell-spacing for orbit-no-cross guarantee |
| `RANDOM_SHELL_BUFFER` | 100 | Min gap between adjacent shells' peri/apo |
| `BATTERY_RANGE` | 2400 | AA targeting range (~6.3× turret range) |
| `BATTERY_FIRE_COOLDOWN` | 4.0 | Seconds between AA shots |
| `BATTERY_LASER_DURATION` | 1.0 | Targeting-laser telegraph window before firing |
| `BATTERY_SPAWN_PROBABILITY` | 0.5 | Per-landable-body roll for AA presence |
| `MISSILE_PRINTER_COST` | 150 | Build cost (vs `TURRET_COST = 50`) |
| `MISSILE_PRINTER_RANGE` | 5000 | Hostile-detection range (vs `TURRET_RANGE = 380`) |
| `MISSILE_PRINTER_COOLDOWN` | 8.0 | Seconds between launches |
| `MISSILE_ORE_COST` | 30 | Ore consumed per missile launched |
| `MISSILE_PLAN_HORIZON` | 12.0 | Seconds the at-launch flight planner integrates forward |
| `MISSILE_BLAST_RADIUS` | 18 | Detonation proximity radius |
| `CAM_PAN_RECENTER_SECONDS` | 7.0 | LMB-drag camera ease-back duration |
| `CAM_ZOOM_RECENTER_SECONDS` | 11.0 | Wheel-peek zoom ease-back duration (longer than pan: zoom is more disorienting to snap on) |
| `SAVE_VERSION` | 2 | Save-file format version (best-effort load on mismatch) |
| `HUD_MESSAGE_DURATION` | 2.5 | Toast lifetime (F2/F3, Shift+R, AA toggle, etc.) |
| `PREDICT_MAX_SECONDS` | 1000 | Predictor look-ahead ceiling (~16.7 min) |
| `PREDICT_TARGET_STEPS` | 6400 | Predictor step-cap default (F5/F6 mutate at runtime) |
| `PREDICT_TARGET_STEPS_MIN` | 100 | F5 floor — coarse but legal |
| `PREDICT_TARGET_STEPS_MAX` | 102 400 | F6 ceiling — past `PHYSICS_DT` clamp |
| `PREDICT_CACHE_INTERVAL` | 3 | Frames between cyan-predict refreshes when running. 1 = no caching. |
| `PREDICT_TICK_INTERVAL` | 5.0 s | Seconds between perpendicular tick marks |
| `PREDICT_TICK_HALFLEN` | 5 px | Tick half-length, screen-space (zoom-invariant) |
| `TIME_SCALE_MIN/MAX` | 1/16 / 16 | F7/F8 clamps |

### Derived numbers worth knowing

- Planet orbital speed ≈ 100 px/s; period ≈ 50 s; Hill sphere ≈ 441 px.
- Moon orbital speed (around Planet) ≈ 126.5 px/s; period ≈ 12.4 s;
  Moon's own Hill sphere ≈ 64 px.
- Default player orbit at 370 px (around Planet) sits *just inside*
  Planet's Hill sphere — circular orbits visibly precess due to solar
  tide. Intentional. It's the multi-body experience.

## Notable design choices

- **Soft-landing speed is *relative* to the body, not absolute world-frame
  speed.** The trajectory predictor's impact-color marker uses the same
  rel-speed test, so what you see is what you'll feel.
- **Fuel consumption scales with thrust magnitude.** 5× boost burns 5×
  as fast. Brake-assist and path-hold draw fuel proportional to their
  current corrective acceleration.
- **Brake-assist matches the velocity of a landable body** (latched at
  H-press time) rather than zeroing absolute world velocity. This is
  the difference between "stop" (drift away from a moving planet) and
  "match" (settle onto it). Target is sticky-on-engage, not
  recomputed per frame, so a Moon flyby doesn't yank the autopilot
  off Planet mid-hover.
- **Strafe (Q/E) doesn't cancel autopilot.** Forward (W) and retro (S)
  are "I'm taking control" gestures; strafe is "nudge while autopilot
  holds position". Combining strafe + hover-hold over a build pad is
  the main reason this distinction exists.
- **Plan-mode pauses everything**, including refuel/mining timers. This
  is so the player can take as long as they need to plan a burn without
  losing fuel they were about to top off.

## Educational forks (planned)

This game's simulation is designed to be forkable into educational
variants because the physics it does is genuinely teachable.

### Elementary edition

Resource transactions become arithmetic problems ("you have 47 ore, the
turret costs 50 — how much more?"). Aimed at grade-school. UX-heavy:
encouraging tone, clear feedback, big text. The math is the bookkeeping
the game already does.

### Physics / orbital mechanics edition

Hide some HUD readouts and ask the player to derive them. "Predict
before you act" mode: enter the speed needed to circularize at radius
R; if your answer is within 5 %, the engine fires automatically.
Curriculum could ladder: KE/PE → conservation → Kepler's third law →
escape velocity → Hohmann transfer.

Both forks share the engine (this repo) and add their own quiz overlay
without touching the simulation.

## Deferred TODO

Applies to any fork:

- **Composable multi-part turrets** — base + barrel + ammo crate, faster
  aim, longer range. Reuses the eventual ship-builder grid code.
- **Passive harvest structures** — long-term miners and fuel synthesis
  (H₂O + ore + sunlight). Adds water as a second resource.
- **Build-while-hovering** — "unreliable catch arm" with rubber-seal
  failure flavour. Adds engineering grit.
- **Recursive build pads** — let the player construct their own pads.
- **Multiplayer sync** — v2.0, big project.
- **Player / planet HP and combat consequences** — currently enemy
  and AA-bullet contact are instant death. Add hit points and
  repair-with-ore.
- **Polish pass** — engine trails, particles, sounds, screen shake.
- **Landing pads with compression absorption** — buildable that softens
  hard landings.

### Recently shipped (no longer deferred)

- **Save/load to disk** — done. F2/F3 + Ctrl+F1..F9 / Shift+F1..F9, atomic
  write with `.bak` rotation, `SAVE_VERSION = 2` with best-effort
  cross-version loads. See "Save / load" section above.
- **Tier 4: more bodies** — done via random universes. `Shift+R` rolls
  1–6 planets and up to 4 moons; predictor scales linearly in body count
  (each body is a Kepler-solve per integration step) so the cap is a
  perf decision, not a correctness one.
