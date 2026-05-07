# Program flow

How YPilot ticks, in time-order. This document is for future maintainers
— human or AI — picking up the project mid-stream. It captures the
load-bearing sequencing decisions and the bug-fix history so old
mistakes don't get reintroduced.

For *what* each subsystem does, see [DESIGN.md](DESIGN.md). For *what
keys do what*, see [CONTROLS.md](CONTROLS.md).

## One frame, top to bottom

```
main() loop
├── 1. clock.tick(FPS) → frame_dt
├── 2. drain pygame events (key down/up, mouse click, quit)
│        ↳ KEYDOWN handles all the "edge-triggered" inputs:
│          R reset, Space pause, N queue burn, Backspace pop,
│          Enter commit, F-keys, etc.
├── 3. read keys + mods (level-triggered: held W/S/Q/E, B build hold)
├── 4. determine in_build_mode and paused
├── 5. PHYSICS PHASE (skipped if paused or in_build_mode)
│        ↳ feed frame_dt × time_scale into accumulator, capped at MAX_FRAME_DT
│        ↳ while accumulator >= PHYSICS_DT:
│            sim_time += PHYSICS_DT
│            update_bodies(sim_time)               # bodies first!
│            ship.apply_pending_maneuvers(sim_time) # chained burns
│            ship.update(PHYSICS_DT, ...)
│            spawn / advance enemies
│            advance turrets, bullets
│            cull dead entities
│            accumulator -= PHYSICS_DT
├── 6. CAMERA PHASE
│        ↳ if paused with planned chain: camera follows the orange line
│        ↳ otherwise: camera = ship.pos
├── 7. RENDER PHASE
│        ↳ background, stars, orbit rails
│        ↳ live trajectory + markers (cyan)
│        ↳ plan-mode trajectory + chain chevrons (orange, paused only)
│        ↳ bodies, deposits, build pads, turrets, bullets, enemies
│        ↳ mining beam, ship
│        ↳ HUD (always native screen pixels)
│        ↳ build menu (if in_build_mode)
│        ↳ REC indicator (if recording)
├── 8. pygame.display.flip()
└── 9. recorder.feed(screen)            # AFTER flip — records what user saw
```

The phase boundaries are deliberate. Inputs are read once; physics
advances in fixed `PHYSICS_DT` chunks; camera and render happen once per
frame at the *current* sim state. The accumulator drains to zero on
pause/build-mode entry so resume doesn't kick off a burst of catch-up
steps.

## Frame loop order (load-bearing)

The main loop calls `update_bodies(sim_time)` **before** `ship.update(dt,
...)`. During `ship.update`, every `body.pos` and `body.vel` is frozen
at the new sim_time. Several pieces of code depend on this freeze:

- The launch-pad bump (`LAUNCH_PAD_HEIGHT`) calculation assumes the body
  is fixed when the ship lifts off — see "Bug-fix history" below.
- The trajectory predictor uses `body.position_at(t)` so it samples
  bodies at the live `t_end` rather than the frozen `t_start`,
  matching what the live integrator just did.
- The brake-assist controller reads `target.vel` from the live body
  state, expecting it to reflect the new sim_time.

**Don't be tempted to interleave body and ship updates within a single
frame.** The freeze invariant breaks if you do.

## `Ship.update` order of operations

The order inside `ship.update(dt, keys, mods, ...)` is the result of
several debug iterations. Small reorderings break subtle behaviour. If
you change it, retest takeoff (especially trailing-side launches
relative to orbital direction) and landing carefully.

```
 1. Cache sim_time on self for _compute_accel
 2. Decrement takeoff_lock_timer; compute steering_active = (timer ≤ 0)
 3. Mouse aim — gated by steering_active and mouse_aim_active
 4. Turn keys A/D, Left/Right — gated by steering_active
 5. _read_thrust_input(keys, mods) — sets thrust flags + cancels autopilots
 6. Takeoff-lock override — if timer > 0:
       force thrusting=True, retro/strafe=False,
       thrust_scale=BOOST, brake_assist=False, path_hold=False
 7. Landed clamp — if landed:
       glue pos to surface, set vel=body.vel, lock angle to landed_radial
       if thrusting/retro: bump pos to launch-pad height,
                           unlatch, arm takeoff_lock_timer
       else: refuel + mine + return early
 8. Zero thrust if fuel == 0
 9. Compute path-hold accel ONCE (against sim_time - dt to match
    start-of-step state — see "One-update path-hold accel" below)
10. Burn calculation (sums forward, retro, strafe, brake-assist,
    path-hold contributions; consumes fuel)
11. Leapfrog integration (kick-drift-kick, symplectic)
12. _check_body_contact — re-land or crash on impact
```

### Why path-hold accel is computed once per update

The path-hold corrective acceleration is calculated *once* per
`update()` against the start-of-step state, then cached. Both leapfrog
half-kicks read the same value via `_compute_accel`.

If you instead computed it fresh per half-kick, you'd compare
start-of-step ship pos against end-of-step plan time — a one-step phase
offset the controller would burn fuel fighting forever.

The cached value is read in `_compute_accel` (which is called by both
half-kicks of the leapfrog) so the controller behaves like a true
once-per-step input rather than something the integrator can fold into
itself.

## Plan-mode flow

Pressing **Space** flips `paused = True`. While paused:

1. The physics phase is skipped entirely — no `update_bodies`, no
   `ship.update`, no enemy/turret/bullet ticks. `sim_time` stays
   frozen.
2. The render phase runs every frame, drawing both the live cyan
   trajectory (for reference) and the orange plan trajectory.
3. Edge-triggered keys are handled in the event loop:
   - `[` / `]` adjust `plan_burn_duration` (with the modifier ladder).
   - `,` / `.` adjust `plan_burn_offset` (the current preview burn's
     fire-time).
   - `N` pushes the current `(angle, duration, offset)` onto
     `maneuver_queue` and resets the preview slot. The new preview's
     fire-time defaults to the just-queued burn's offset (camera stays
     glued).
   - `Backspace` pops the most-recent queued burn back into the
     editable preview slot.
   - `Enter` commits the chain (see below).
   - `Space` cancels: drops the queue, leaves pause.

### Camera tracking the chain

While paused with a non-empty queue or non-zero offset, the camera
follows the *planned* trajectory to the current preview burn's
fire-time:

```python
cam_pts, _, _ = ship.predict_trajectory(
    bodies, sim_time, seconds=plan_burn_offset,
    pos0=cam_pos0, vel0=cam_vel0,
    pending_burns=cam_pending,  # queued burns only, NOT current preview
)
camera.pos = cam_pts[-1]
```

So adjusting `,` / `.` slides the view to where the next burn will
fire. With an empty queue and offset 0, this collapses to the ship's
current pos and the camera feels ship-anchored.

If the ship is landed, `cam_pos0` mirrors the launch-pad bump that the
live commit will apply, so the camera target lines up with where the
orange line actually starts.

### Enter-commit flow

```
Read mouse → burn_angle (current preview)
Build chain = maneuver_queue + [(burn_angle, duration, offset)]
Drop zero-duration entries (cancellation by Backspace-to-zero)
For each (angle, dur, off) → pending.append((sim_time + off, dir, dur))

If pending is non-empty:
    Compute snapshot start (mirror launch-pad bump if landed)
    Run predict_trajectory with out_velocities populated
    Build (t, pos, vel) sample list, length = predict horizon + 60s
    ship.set_planned_trajectory(samples)        # for path-hold
    ship.pending_maneuvers = pending             # scheduled live burns
    ship.apply_pending_maneuvers(sim_time)       # fire burn 0 immediately

Clear maneuver_queue, reset preview, paused = False
```

The predictor snapshot is taken **before** the live burns are applied,
so path-hold tracks the same starting state the predictor saw. Without
this ordering, the snapshot would be one launch-pad-bump-height below
the actual post-commit ship state.

### apply_pending_maneuvers

Lives on `Ship`. Each frame's physics phase calls it before
`ship.update` so the leapfrog integrates with the post-burn velocity:

```python
while pending_maneuvers and pending_maneuvers[0][0] <= sim_time:
    _t, burn_dir, duration_signed = pending_maneuvers.pop(0)
    if not commit_planned_burn(burn_dir, duration_signed):
        pending_maneuvers.clear()  # OOM/dead — abort the rest
        return
```

`commit_planned_burn` is the same code path used by Enter-commit, so
each scheduled chain step matches what plan-mode predicted (same fuel
cost, same impulse model, same nose-direction snap).

## Path-hold lookup per frame

When `path_hold` is on, every `Ship.update()`:

1. Walks forward from the cached `_path_hold_hint` until the bracketing
   pair of samples around `sim_time` is found. O(1) typical because
   `sim_time` only ever moves forward.
2. Linear-interpolates `(target_pos, target_vel)` between samples.
3. Computes the PD correction:
   ```
   pos_err = target_pos - self.pos
   vel_err = target_vel - self.vel
   desired = pos_err * KP + vel_err * KD
   ```
4. Clamps to `PATH_HOLD_MAX_ACCEL` (5 % of nominal thrust).
5. Caches `pos_err.length()` for the HUD.

If `sim_time` runs past the snapshot's last sample, path-hold
auto-disengages so the player isn't surprised by a silent no-op
autopilot.

## Recorder threading model

`Recorder.feed(surface)` is called once per frame *after*
`pygame.display.flip()`, so the recording matches what the user just
saw. The work is split across two threads:

| Thread | What it does | Where it can block |
|---|---|---|
| **Main** | `pygame.image.tostring(surface, "RGB")` (memcpy), pacing arithmetic, queue.put_nowait | Never — drops on `queue.Full` |
| **Writer** | Drains queue, writes bytes to ffmpeg's stdin | On `proc.stdin.write` (ffmpeg flow control) |

The bounded queue (`QUEUE_SIZE = 8`) plus drop-on-full policy means a
slow encoder can never stall the game loop. Dropped frames are counted
on the HUD.

### Wall-clock pacing

The recorder writes to ffmpeg at a fixed 30 fps stream, but the *content*
of each output slot is decided per-call:

```python
target_total = int((now - start_wall) * OUTPUT_FPS) + 1
owed = max(0, target_total - frames_pushed)
```

- `owed == 0` → game is running faster than 30 fps; skip this frame.
- `owed == 1` → game is on-pace; push the new frame once.
- `owed > 1` → game stuttered; push the *previous* frame for `owed - 1`
  slots (the dwell), then the new frame for the final slot.

Net effect: a 500 ms game stutter shows as a 500 ms freeze in the
recording, sitting on the *correct* frame (the last one before the
hitch). Without dwell injection, a hitch would compress to 17 ms of
sped-up footage.

The pacing counter `_frames_pushed` advances even when frames are
dropped on `queue.Full`, otherwise a single queue-full event would make
every subsequent feed think it owes more frames, and the lag would
snowball.

### ffmpeg spawn

`subprocess.Popen(cmd, stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL)` — if
ffmpeg isn't on PATH, the spawn fails with `FileNotFoundError`, the
recorder prints a hint once, and `recording = False`. F9 is then a
silent no-op until ffmpeg is installed.

## Ship state machine

| State | Set when | Cleared when |
|---|---|---|
| `alive` | reset | hard impact, contact with non-landable body (sun) |
| `landed` | `_resolve_surface_contact` succeeds | landed-clamp's unlatch (W/S thrust) |
| `landed_body`, `landed_radial` | at touchdown | unlatch on takeoff |
| `takeoff_lock_timer > 0` | unlatch on takeoff | per-frame decrement |
| `brake_assist` | `H` toggle | W/S press, takeoff lock arms, fuel == 0 |
| `path_hold` | `J` toggle (after a committed plan) | W/S press, takeoff lock arms, fuel == 0, snapshot exhausted |
| `hover_hold` | derived per-frame from Shift while brake_assist on | forward/reverse pressed (avoids modifier conflict) |
| `brake_assist_scale` | derived per-frame from Ctrl while brake_assist on | forward/reverse pressed |

### State-machine asymmetries to know about

- **`brake_assist` is cancelled by W or S, NOT by Q/E.** That asymmetry
  is deliberate — strafe + autopilot together is the build-pad-alignment
  workflow.
- **`hover_hold` and `brake_assist_scale` only update when neither
  forward nor reverse is pressed.** Shift/Ctrl double as thrust scale
  modifiers in those cases, so the trim modifier reads have to be gated
  to avoid conflict. Strafe doesn't use modifiers, so Q/E never
  suppresses the trim.
- **`path_hold` and `brake_assist` are mutually exclusive.** Toggling
  one off when the other is engaged. Different control targets
  (match-body vs match-plan); letting both run would be a tug-of-war.

## Bug-fix history (don't reintroduce)

The order of operations in `Ship.update` and the launch-pad bump are
both load-bearing because they fix specific bugs. If you change them,
retest the cases below.

### Re-grounding loop on trailing-side launches

Ship inherits `body.vel` at takeoff. `body.pos` is frozen during
`ship.update`. If `landed_radial` is anti-parallel to `body.vel` (ship
landed on the trailing side of the planet's orbit), the ship's
tangential motion *within the frame* carries it into the body's static
position before the leapfrog has a chance to lift it clear. Each frame
the ship re-lands; the lock timer keeps refreshing; the loop only
breaks when orbital geometry shifts enough.

**Fix:** at unlatch, bump `self.pos` to `body.pos + radial × (body.radius
+ LAUNCH_PAD_HEIGHT)`. Pad height must exceed `body.vel.length() × dt`;
for planet at 100 px/s and `dt=1/60`, minimum is ~3.5, so 5.0 leaves
comfortable margin.

### Mouse aim drifted nose off-vertical while parked

Cursor anywhere off screen-center would slowly rotate `self.angle` away
from radial during the parked phase, making takeoff thrust direction
wrong.

**Fix:** set `self.angle = self.landed_radial` inside the landed clamp
every frame, so any aim drift is overwritten while the ship is parked.

### Takeoff sliding tangentially

With nose off-vertical at the moment of liftoff, boost vector wasn't
radial and the ship would skitter along the surface for a second before
centrifugal effect spun it free.

**Fix:** `takeoff_lock_timer` suppresses mouse-aim, turn keys, and
strafe for ~0.3 s post-liftoff, and the lock-override forces full boost
regardless of input — "press W, ship handles the launch."

### Strafe used to cancel autopilot

This made hover-over-build-pad-with-alignment-strafing impossible.

**Fix:** removed `brake_assist = False` for Q/E. Only forward (W) and
retro (S) cancel the autopilot — those are "I'm taking control"
gestures, while strafe is a "nudge while autopilot holds position"
gesture.

### Trim modifiers blocked when any thrust pressed

Hover-hold (Shift) and damp (Ctrl) would deactivate even on Q/E.

**Fix:** gate the trim modifier reads on forward AND retro only — both
use Shift/Ctrl as scale modifiers (forward: Shift=boost, Ctrl=precision,
Ctrl+Shift=extra-fine; retro: Ctrl=precision, Ctrl+Shift=extra-fine).
Strafe doesn't use modifiers, so Q/E never suppresses the trim. Note:
pressing forward or retro already cancels brake-assist, so this gate is
technically defensive — but explicit is better than relying on the
cancel ordering.

### Path-hold burning fuel forever fighting a one-step phase offset

Initially the path-hold accel was computed inside `_compute_accel`,
which the leapfrog calls twice per step. Half-kick 1 saw start-of-step
ship pos vs `sim_time`'s plan; half-kick 2 saw mid-step ship pos vs the
same plan time. Combined with the main loop advancing `sim_time` before
calling `update`, the controller was always one step out of phase and
burnt fuel chasing the next frame.

**Fix:** compute the corrective accel *once* per `Ship.update()`
against `sim_time - dt` (matching start-of-step state), cache it on
`self._path_hold_cached_accel`, and have `_compute_accel` add the
cached value to both half-kicks. The integrator now sees a true
once-per-step input.

### Predictor saw a different starting state than path-hold

On Enter-commit, the predictor was being run *after* `commit_planned_burn`
applied the launch-pad bump and burn-0 kick to the live ship. So the
predictor saw a state that included the bump; path-hold was then asked
to track from a snapshot whose first sample was bump-height above
where the live ship actually started.

**Fix:** snapshot the predictor's starting state *before* applying live
burns. Mirror the launch-pad bump in the snapshot if landed. Now the
snapshot's sample 0 matches the live ship's pos one frame after commit.

### Camera target lagged behind launch-pad bump

The plan-mode camera (which follows the orange line to the current
preview's fire-time) initially used `ship.pos` as its starting point,
but `commit_planned_burn` applies a launch-pad bump on commit. The
result was the camera target sitting one bump-height below where the
orange line actually started, off by a few pixels at high zoom.

**Fix:** when the ship is landed, the camera-target predictor uses
`body.pos + landed_radial × (body.radius + LAUNCH_PAD_HEIGHT)` as
`pos0`, mirroring `commit_planned_burn`'s pre-burn state.

## Reset (R) flow

`R` resets everything to a deterministic starting state:

```python
sim_time = 0.0
bodies, planet, sun, deposits, pads, turrets, bullets, enemies = build_world()
ship.reset(planet)
enemy_spawn_timer = ENEMY_SPAWN_INTERVAL * 0.5
kills = 0
paused = False
plan_burn_duration = PLAN_BURN_DURATION_DEFAULT
maneuver_queue.clear()
plan_burn_offset = 0.0
time_scale = TIME_SCALE_DEFAULT
```

Note that `R` does *not* stop a recording in progress — F9 is a separate
toggle. Predict window, predict step count, zoom, fullscreen, and the
recorder all persist across resets.

## Pause and build-mode skip the physics phase

Both `paused = True` and `in_build_mode = True` cause the physics phase
to be skipped entirely. The accumulator is drained to zero on the same
frame so resuming doesn't kick off a burst of catch-up steps:

```python
if not in_build_mode and not paused:
    physics_accumulator = min(
        physics_accumulator + frame_dt * time_scale, MAX_FRAME_DT
    )
    while physics_accumulator >= PHYSICS_DT:
        ...
        physics_accumulator -= PHYSICS_DT
else:
    physics_accumulator = 0.0
```

`in_build_mode` is `True` only while the player is *holding* B and
there's an unoccupied build pad in range. Releasing B drops back into
the physics phase the next frame. Pause is a toggle — Space once to
enter, Space again to leave (or Enter to commit a chain and leave).
