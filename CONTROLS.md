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
| **Mouse** | Aims the ship's nose at the cursor. Suppressed while landed (the landed clamp re-snaps the nose to surface-radial every frame); re-engages the instant the ship unlatches. Keep the cursor near the ship at takeoff — the mouse-aim deadzone absorbs small offsets, but a cursor that's meaningfully off-centre will start rotating the nose immediately and the first second of climb gets messy. |
| **A** | Rotate counter-clockwise (keyboard-only fallback; mouse aim usually overrides this every frame in flight). |
| **D** | Rotate clockwise (keyboard-only fallback). |

### Cursor nudge (Left / Right / Up / Down arrow)

Burn angle and ship heading both come from `(mouse_pos - screen_center)`, so the precision-aim mechanism is *nudging the cursor*, not rotating the ship directly. The arrow keys move the cursor by a small number of pixels each frame they're held. At max zoom-out near the screen edge, a 1-pixel cursor delta translates to a hair of angle change — exactly the resolution you want when fine-tuning a Hohmann insertion or lining up a landing.

Hold an arrow for a smooth sweep; tap once for a single-frame nudge. Modifiers scale the step the same way they scale duration / fire-time in plan mode:

| Combo | Step (px/frame) | Sweep speed (60 FPS) |
|---|---|---|
| **arrow** | 4 | ~240 px/s |
| **Shift + arrow** | 12 | ~720 px/s (fast traversal) |
| **Ctrl + arrow** | 2 | ~120 px/s (precision) |
| **Ctrl + Shift + arrow** | 1 | ~60 px/s (pixel-by-pixel) |
| **Alt + arrow** | 1 | ~60 px/s (pixel-by-pixel) |

Works in flight, plan-mode, and build-mode. Disabled while the **Ctrl+Shift+R** seed-prompt overlay is intercepting keystrokes (the cursor would flicker for no reason).

Cross-platform via `pygame.mouse.set_pos()` — SDL2 calls the right platform API under the hood (`SetCursorPos` on Windows, `CGWarpMouseCursorPosition` on macOS, `XWarpPointer` on X11, compositor pointer-locking on Wayland).

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

Takeoff: nominal `SHIP_THRUST` is weaker than surface gravity on every
landable body in the default world (494 px/s² at Planet vs 220 px/s²
nominal), so plain W just pops the ship 5 px on the launch-pad bump
and lets gravity reel it back in. **Hold `Shift+W` to take off** — the
5× boost is enough to climb clear of the gravity well before nominal
physics would matter. The landed clamp keeps the nose snapped to
surface-radial while parked, so the boost vector is automatically
radial at the moment of liftoff. The HUD's LANDED line glows red as a
reminder.

## Retro thrust (S / Down)

Mirrors the forward ladder, no boost step (retro maxes at 10 %):

| Combo | Scale | Use |
|---|---|---|
| **S** | 0.10 | Default brake/retro |
| **Ctrl + S** | 0.01 | Precision retro |
| **Ctrl + Shift + S** | 0.001 | Extra-fine retro |

Pressing S also cancels brake-assist and path-hold.

## Thrust preview (hold Tab)

Hold **Tab** to peek at where a **0.1 s tap** of W or S would put you,
without committing to it. Two faint ghost trajectories fan out of the
ship alongside the cyan prediction:

| Ghost | Colour | Shows |
|---|---|---|
| **W / Up** | green | Path after a 0.1 s forward tap |
| **S / Down** | magenta | Path after a 0.1 s retro tap |

Each ghost is capped with a small dot at its far end — where the three
lines run bundled near the ship, three distinct tips are the clearest
signal that there really are three paths and not one fringed one.

The HUD gains a `THRUST PEEK` line with the exact Δv each tap delivers.
If Tab is held but the overlay can't run, that line says so and why
(`landed`, `build menu open`, `ship destroyed`) rather than showing
nothing — holding a key and getting silence is indistinguishable from
the key not registering.

The overlay **honours the live trim ladder**, so `Shift+Tab` previews
the 5× boost tap and `Ctrl+Tab` the 1 % precision tap — the ghost can
never disagree with what the key would actually do. Any armed maneuver
chain is folded in too, so the ghosts stay directly comparable to the
cyan line.

Expect the two ghosts to be **wildly asymmetric**, and that is the most
useful thing the overlay teaches: forward runs at full `SHIP_THRUST`
while retro runs at 10 % of it, so at nominal trim a W tap is `+22.0`
Δv against a S tap's `-2.2`. The green ghost fans roughly 8× further off
the cyan line than the magenta one.

Deliberately **bare lines** — no apsis dots, SOI rings, closest-approach
diamond or impact marker. Those analyses are where the predictor's
per-frame cost actually lives, and three sets of markers at once would
be unreadable. The point of the overlay is the *fan*, not a second full
forecast.

Notes:

- Airborne only. While landed, use plan mode (Space) instead — it
  handles the launch-pad bump correctly, which this overlay does not
  try to.
- The ghosts refresh on the same cadence as the cyan line
  (`PREDICT_CACHE_INTERVAL`, 3 frames), so the whole picture moves as
  one. The visible cost is that a ghost lags the nose by up to ~9° while
  you sweep it hard; it snaps true the moment you stop turning.
- Costs nothing at all when Tab isn't held.
- The ghosts draw **on top of** the cyan prediction. They were underneath
  in the first cut, and the cyan ribbon painted over the retro ghost
  wherever the two ran close — which, at a tenth of forward thrust, is
  most of the visible trajectory.

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
| **+ / =** | Zoom in. Sets the persistent *resting* zoom that the wheel-peek eases back to. |
| **- / _** | Zoom out. Same — sets the resting zoom. |
| **0** | Reset zoom to 1.0× (rest + peek both snap; mid-peek easings cancel). |
| **Mouse wheel** | "Peek" zoom — multiplies a transient factor off the resting zoom and eases back to the rest over `CAM_ZOOM_RECENTER_SECONDS` (default 11 s, easeOutCubic). Spam-scroll holds the peek (each tick resets the timer); pausing the wheel kicks off the return. Useful for glancing at a far-off body without losing your landing-friendly resting zoom. |
| **LMB drag** | Pan the viewport off-ship for surveys of large systems where max zoom-out still doesn't fit. Release and the camera eases back to the ship over `CAM_PAN_RECENTER_SECONDS` (default 7 s, easeOutCubic). Disabled while build mode (**B**) or the seed prompt is intercepting clicks. |
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
| **Mouse click** | Confirm a build option from the menu. Two options today: **Dumb Turret** (50 ore) — anti-UFO, short range; **Missile Printer** (100 ore) — anti-AA + anti-UFO, 5000-unit range, 10 ore per launch. Each missile gets a bespoke orange flight plan computed at launch and flies it under gravity. Targets AA batteries first, then UFOs. Destroyed hostiles drop wreckage that falls to the surface as grey scrap piles — land beside one and the mining beam salvages it like ore (12 per UFO, 40 per AA battery; HUD shows SALVAGING). Salvage is the only kill reward; nothing is credited at the moment of kill. |
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
| **Shift + C** | Nuke every queued burn — the in-progress plan-mode chain *and* any committed-but-not-yet-fired burns on the ship — and drop the orange path. Works paused or unpaused. Shift-gated so a stray **C** can't wipe a long plan. HUD reports how many burns were cleared. |
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
| **F9** | Toggle video recording. Pipes raw RGB frames to ffmpeg (must be on PATH — `winget install ffmpeg` / `brew install ffmpeg`) and writes a timestamped `.mp4` into `./captures/` (created if missing). |

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
| **F1** | Toggle HUD text overlay. World content (ship, trajectory, build menu, REC tally) stays visible — F1 only hides the text panels. |
| **F2** | Quickload from the default slot (`saves/quicksave.json`). Toasts "QUICKLOADED" or "no quicksave". |
| **F3** | Quicksave to the default slot. Atomic write (`.tmp` → rename, with `.bak` rotation), so a crash mid-write can't corrupt the active slot. Toasts "QUICKSAVED". |
| **Ctrl + F1..F9** | Save to numbered slot 1-9 (`saves/quicksave_N.json`). Bookmarks for distinct expedition states you want to revisit. HUD toasts "SAVED slot N". |
| **Shift + F1..F9** | Load from numbered slot 1-9. HUD toasts "LOADED slot N", or "no save in slot N" if the slot file doesn't exist yet. |
| **F4** | Minimise the window (boss key). The OS handles the un-minimise. |
| **F10** | Toggle enemy spawns. Also clears any in scene. |
| **Shift + F10** | Toggle planetary AA batteries. About 50% of landable bodies are rolled with a body-mounted battery at world build (deterministic from the world seed). Each battery solves a real intercept against your ship's gravity-affected predicted trajectory, paints a 1 s targeting laser to the predicted hit point, then fires a straight-line bullet. The solver refuses to converge while you're burning (W/S) — that's the dodge escape hatch. Same damage as a UFO collision. |
| **F11** | Toggle fullscreen. |
| **F12** | Save a screenshot (PNG) into `./captures/` (created if missing). |
| **R** | Reset the active world. On first launch this is the hand-tuned default system; once you've rolled a random universe with **Shift+R**, **Ctrl+Shift+R**, or **Ctrl+Alt+Shift+1..6** in the current session, **R** rebuilds *that* universe instead. The choice isn't persisted across launches — start the game and you're always back on default. |
| **Shift + R** | Reset to a freshly-rolled random universe. 1–6 planets, optional moons (≤2 per planet, ≤4 total), eccentricity ≤ 0.3. The seed is printed on the HUD as a toast so a memorable roll can be re-summoned later. |
| **Ctrl + Shift + R** | Open the custom-seed prompt — a modal overlay that freezes the sim until you commit (Enter), cancel (Esc), or backspace digits out. Lets you re-summon a specific seed shared by a friend or written down from an earlier run. |
| **Ctrl + Alt + Shift + 1..6** | Roll a fresh random universe with **exactly N planets** (instead of the random 1–6 count that plain Shift+R picks). Same allocation policy as any random universe — innermost gets starter ore + most pads, outermost gets the ore world, middle bodies get forward-base pads. Fresh seed each press; HUD toasts "random universe: N planet(s), seed M". The (seed, n_planets) pair is baked into quicksaves so a save of one of these worlds reproduces it on load. |
| **Esc** | Quit. (While the seed prompt is active, Esc cancels the prompt instead of quitting.) |

## Quick reference card

```
Mouse aim      A/D rotate          W/S thrust (Shift=5x, Ctrl=1%, Ctrl+Shift=0.1%)
Tab (hold) thrust peek -- ghost paths for a 0.1s W / S tap (obeys the trim ladder)
Arrows nudge cursor (Shift=fast, Ctrl=fine, Ctrl+Shift / Alt=pixel)
Q/E strafe     H brake-assist      J path-hold     B (hold) build
+/- zoom       0 reset zoom        / shorter pred  * longer pred
F1 HUD toggle  F2/F3 quickload/save  F4 minimise   F5/F6 steps  F7/F8 time scale
F9 record      F10 enemies           F11 full      F12 shot
Ctrl+F1..F9 save slot N    Shift+F1..F9 load slot N
R reset        Shift+R random universe    Ctrl+Shift+R seed prompt
Ctrl+Alt+Shift+1..6 random universe with N planets         Esc quit

Plan mode (Space):
  Mouse aims burn  [ / ] duration   , / . fire-time
  N queue       Backspace pop       Enter commit chain   Space cancel
  Modifiers: Shift=1.0 leap, Ctrl=0.01, Ctrl+Shift=0.001, Alt=0.0001
```
