# Controls

Full keyboard and mouse reference. The in-game HUD shows a condensed version
of the most-used keys; this is the complete list, grouped by what they do
rather than by where they sit on the keyboard.

For the *why* behind a particular control (e.g. why strafe doesn't cancel
brake-assist), see [DESIGN.md](DESIGN.md). For the order in which inputs
are read each frame, see [PROGRAM_FLOW.md](PROGRAM_FLOW.md).

## Aiming

| Input | Effect |
|---|---|
| **Mouse** | Aims the ship's nose at the cursor. Suppressed for ~0.3 s after liftoff (`TAKEOFF_LOCK_SECONDS`) so a fresh launch climbs cleanly upward instead of being yanked sideways by an off-centre cursor. |
| **A / Left** | Rotate counter-clockwise (keyboard fallback). |
| **D / Right** | Rotate clockwise (keyboard fallback). |

## Forward thrust (W / Up)

The thrust trim ladder uses Shift / Ctrl / Ctrl+Shift as scale modifiers:

| Combo | Scale | Use |
|---|---|---|
| **W** | 1.0 (nominal) | Day-to-day flying |
| **Shift + W** | 5.0 (boost) | Escape velocity, hard accel |
| **Ctrl + W** | 0.01 (precision) | Tweaking velocity by ~1 % |
| **Ctrl + Shift + W** | 0.001 (extra-fine) | Sub-pixel/sec adjustments |

Pressing W (any modifier) cancels brake-assist and path-hold — those are
"I'm taking control" gestures.

On takeoff from the surface, the ship auto-commits to full-boost forward
thrust for `TAKEOFF_LOCK_SECONDS` regardless of input. One press of W
kicks off a clean climb and the launch-assist holds the line until the
ship is clear.

## Retro thrust (S / Down)

Mirrors the forward ladder, no boost step (retro maxes at 10 %):

| Combo | Scale | Use |
|---|---|---|
| **S** | 0.10 | Default brake/retro |
| **Ctrl + S** | 0.01 | Precision retro |
| **Ctrl + Shift + S** | 0.001 | Extra-fine retro |

Pressing S also cancels brake-assist and path-hold.

## Strafe (Q / E)

| Input | Effect |
|---|---|
| **Q** | Strafe left at 10 % of nominal forward thrust. |
| **E** | Strafe right at 10 %. |

Strafe **does not cancel brake-assist or path-hold.** This is the
hover-hold-plus-align workflow: H + Shift to lock altitude over a build
pad, then Q/E to slide tangentially into position.

## Autopilots

### Brake-assist (H)

Toggles a velocity-matching autopilot. Default mode drives the ship's
velocity toward the velocity of the nearest landable body — so a "stop"
really means "match the planet" rather than "drift away from a moving
planet".

While brake-assist is on, modifiers tweak its behaviour:

| Modifier | Behaviour |
|---|---|
| **Shift** | Hover-hold: kill only the radial component of relative velocity, leave tangential drift alone. Altitude locks; you can slide sideways. |
| **Ctrl** | Damp to 0.25× strength. Gentle approach control. |
| **Shift + Ctrl** | Hover-hold at 0.25× strength. |

Cancelled by W or S. Mutually exclusive with path-hold.

### Path-hold (J)

Toggles a plan-tracking autopilot. After committing a plan-mode burn
chain (Enter from paused), the ship keeps a snapshot of the planned
`(t, pos, vel)` trajectory; J engages a small PD controller (capped at
5 % of nominal thrust) that nulls phase drift and small chaotic
perturbations along that line.

- No-op if there's no committed plan, or if landed/dead/out of fuel.
- Cancelled by W or S like brake-assist.
- Mutually exclusive with brake-assist (they'd fight each other).
- Auto-disengages if `sim_time` runs past the snapshot's last sample.

The ring around the ship is orange while path-hold is active (cyan for
brake-assist, green for landed).

## Camera & predictor

| Input | Effect |
|---|---|
| **+ / =** | Zoom in. |
| **- / _** | Zoom out. |
| **0** | Reset zoom to 1.0×. |
| `/` | Shorter trajectory prediction window (down to 5 s). |
| `*` | Longer prediction window (up to ~16.7 min). |
| **F5** | Halve the predictor's per-frame step budget. Coarser, cheaper, less faithful. |
| **F6** | Double the predictor's step budget. Finer, more accurate, more per-frame work. |

Current predict window and step count both show on the HUD. See
[TRAJECTORY.md](TRAJECTORY.md) for what the line and its markers mean.

## Time scale

| Input | Effect |
|---|---|
| **F7** | Halve the simulation time scale (down to 1/16×). |
| **F8** | Double the simulation time scale (up to 16×). |

Slow-mo helps with landings; fast-forward is good for long Hohmann
coasts. Plan-mode (Space) is unaffected — paused is paused. The HUD
shows the current scale when it's not 1.0×. **R** resets to 1.0×.

The physics step itself stays at `PHYSICS_DT` regardless of time scale;
F7/F8 only change how much wall-time is fed into the accumulator each
frame. This keeps the predictor bit-equivalent to the live integrator
at any speed.

## Building

| Input | Effect |
|---|---|
| **B (hold)** | Open the build menu while landed near an unoccupied build pad. |
| **Mouse click** | Confirm the highlighted build option (currently: dumb turret, 50 ore). |
| **Release B** | Close the menu. |

## Plan-mode (Space)

Pressing Space pauses the entire simulation — bodies, ship, enemies,
bullets, fuel, refuel — and opens a "what-if" overlay. Mouse aims a burn
direction; an orange ghost trajectory shows where the ship would end up
if it received an instantaneous Δv of `SHIP_THRUST × duration` along
that vector.

Press Space again to resume without burning. (Any queued chain is
dropped — re-entering pause starts fresh.)

### Burn duration ([ / ])

`[` shrinks the planned burn duration; `]` grows it. Step ladder:

| Combo | Step |
|---|---|
| **Shift + [ / ]** | 1.0 s (leap) |
| **[ / ]** | 0.1 s (coarse) |
| **Ctrl + [ / ]** | 0.01 s (precision) |
| **Ctrl + Shift + [ / ]** | 0.001 s (extra-fine) |
| **Alt + [ / ]** | 0.0001 s (super-fine) |

Duration is **signed**. Stepping past zero into negatives flips the
impulse vector — a retro burn from the same aim point — so you can A/B
forward vs reverse without spinning the mouse 180°.

### Burn fire-time (, / .)

`,` and `.` (a.k.a. `<` and `>`) shift the *current preview burn's*
fire-time forward/backward along the trajectory. Same precision ladder
as duration. Lets you stage a burn at a specific future point (e.g. apo)
without first expanding the predict window.

| Combo | Step |
|---|---|
| **Shift + , / .** | 1.0 s (leap) |
| **, / .** | 0.1 s |
| **Ctrl + , / .** | 0.01 s |
| **Ctrl + Shift + , / .** | 0.001 s |
| **Alt + , / .** | 0.0001 s |

Floor: the previous queued burn's offset (chain stays monotonic).
Ceiling: `PREDICT_MAX_SECONDS` (~1000 s).

While paused, the camera follows the planned trajectory to the current
preview burn's fire-time, so adjusting `,` / `.` slides the view to
where the next burn will fire — you stay focused on what you're
planning, not on the ship.

### Maneuver chain

Plan mode supports queueing multiple burns in sequence:

| Input | Effect |
|---|---|
| **N** | Push the current preview onto the chain; start planning the next burn. The next preview defaults to the same fire-time as the burn you just queued (camera stays glued to that point). Each queued burn gets a numbered chevron on the orange trajectory. |
| **Backspace** | Pop the last queued burn back into the editable preview slot, restoring its duration AND its fire-time. Useful for retuning without re-planning. |
| **Enter** | Commit the full chain. Burn 0 fires immediately; burn k fires at `sim_time + offset[k]`. Lifts off automatically if landed. With an empty queue this behaves identically to the old single-burn commit. |

After commit, the predicted trajectory is snapshotted (extended past the
last burn by `PATH_HOLD_POSTBURN_SECONDS = 60 s`) and stored on the
ship — ready for **J** to engage path-hold against it.

The **cyan predicted line** also folds the committed chain in: it now
shows the trajectory the ship will *actually* fly post-burns, with
chevrons at each scheduled burn point and the predict horizon extended
to reach past the final burn. As each burn fires, its chevron
evaporates and the line straightens for that segment automatically.
You don't have to re-enter plan mode to see what you set up.

**Extending a committed chain.** Press Space again with burns still
pending and plan mode reopens; the new preview starts back at the
ship (fire-time 0). Use `Shift + ,` / `Shift + .` (1-second leap)
to push the fire-time past the existing pending burns — or anywhere
else you want. Press Enter to add the new burn(s); the integrator
merges the new chain with the existing pending one (sorted by
apply-time) so previously-armed burns aren't wiped out. The `,`
floor stays at 0 by design, so you can also schedule a *corrective*
burn that fires before an already-armed burn — physics deserves
second chances.

## Recording

| Input | Effect |
|---|---|
| **F9** | Toggle video recording. Pipes raw RGB frames to ffmpeg (must be on PATH — `winget install ffmpeg` / `brew install ffmpeg`) and writes a timestamped `.mp4` next to `ypilot.py`. |

Output is 30 fps H.264 / yuv420p, paced against wall-clock. When the game
stutters, the recorder dwells on the previous frame for the right number
of output slots, so a 500 ms hitch shows up as a 500 ms freeze rather
than 17 ms of sped-up footage. Encode runs on a worker thread with a
bounded queue and drop-on-full policy — the game loop never blocks on
ffmpeg.

The HUD shows `REC` plus written / dropped frame counts while active.
The REC indicator appears in the recorded frames too (intentional, like
an OBS tally) — F9 to stop before whatever you're showing if you don't
want it.

## Window & misc

| Input | Effect |
|---|---|
| **F10** | Toggle enemy spawns. Also clears any in scene. |
| **F11** | Toggle fullscreen. |
| **F12** | Save a screenshot (PNG) next to `ypilot.py`. |
| **R** | Reset world. |
| **Esc** | Quit. |

## Quick reference card

```
Mouse aim      A/D rotate          W/S thrust (Shift=5x, Ctrl=1%, Ctrl+Shift=0.1%)
Q/E strafe     H brake-assist      J path-hold     B (hold) build
+/- zoom       0 reset zoom        / shorter pred  * longer pred
F5/F6 steps    F7/F8 time scale    F9 record       F10 enemies   F11 full
F12 shot       R reset             Esc quit

Plan mode (Space):
  Mouse aims burn  [ / ] duration   , / . fire-time
  N queue       Backspace pop       Enter commit chain   Space cancel
  Modifiers: Shift=1.0 leap, Ctrl=0.01, Ctrl+Shift=0.001, Alt=0.0001
```
