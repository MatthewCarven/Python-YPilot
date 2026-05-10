# YPilot

A 2D space-flight game in Python + pygame-ce. Orbit a planet under
Newtonian gravity, mine ore from surface deposits, construct auto-aim
turrets and missile printers at build pads, dodge planetary AA fire,
and defend against UFOs that drift in from off-screen.

The default world has four landable bodies, each playing a distinct
role:

- **Planet** at orbit 800 — the main base. Five build pads, two
  starter ore deposits (enough to bootstrap a turret or two; you'll
  need to leave for more).
- **Moon** of Planet at orbit 250, period ~12 s — fast enough to lap
  you, small enough that landings need real precision. Two build pads
  ride the Moon, so any turret you mount here sweeps around Planet as
  a moving anti-air platform.
- **Ember** at orbit 1800 — rust-coloured forward base. Three build
  pads, no ore. Hohmann transfer from Planet takes ~52 s.
- **Frostbite** at orbit 3000 — pale, low-gravity ore world. Six
  deposits and zero defensive infrastructure: it's a destination, not
  a base. Hohmann from Planet ~92 s; from Ember ~146 s. The round
  trip is the whole point of the resource economy.

Or roll a **random universe** with `Shift+R` — 1 to 6 planets, optional
moons, eccentric orbits up to e ≤ 0.3. The seed is printed on the HUD
so memorable rolls can be re-summoned via `Ctrl+Shift+R`'s seed prompt.
Same gameplay arc regardless of layout: innermost planet gets the
starter deposits + most of the pads, outermost gets the bulk of the ore
and zero pads, the middle bodies pick up forward-base pads.

## Run

```
pip install pygame-ce
python ypilot.py
```

Tested on Python 3.14 / pygame-ce 2.5+. Window auto-sizes to your
desktop resolution.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/b26fe13c-2f4b-4020-ae4b-a164926014ae" />
<img width="1920" height="1080" alt="2026-05-04 - 21-14-45" src="https://github.com/user-attachments/assets/a024ba52-82ad-4d8f-a4f5-ec9c5a78a706" />
<img width="1920" height="1080" alt="2026-05-06 - 01-09-40" src="https://github.com/user-attachments/assets/bdd0c7c8-d181-405a-a30e-e3ed909cafd1" />

## What's in the box

- **Multi-body Newtonian gravity** — Sun, Planet, Moon (hierarchical,
  parented to Planet), Ember, and Frostbite by default; up to 6 planets
  + 4 moons in random universes. Symplectic leapfrog integrator, so
  closed orbits stay closed; eccentric Keplerian rails for random worlds
  (default world stays e=0 for bit-identical predictor agreement).
- **Trajectory predictor** with adaptive step, 5-second tick marks,
  periapsis/apoapsis dots with prograde-burn arrows, closest-approach
  marker, sphere-of-influence crossings, and a chaos-cone visualisation.
  The cyan line folds committed burns in, so you can see the trajectory
  you'll *actually* fly post-burns without re-entering plan mode.
- **Plan-mode (Space)** — pause the world, dial a burn with the mouse,
  see the orange "what-if" trajectory before you commit. Supports
  multi-burn chains (queue with **N**, pop with **Backspace**, fire on
  **Enter**) so you can stage a Hohmann insertion as one keypress.
  Re-entering plan mode merges new burns with already-armed ones by
  apply-time, so corrective burns can be slotted in *before* an existing
  pending burn.
- **Two autopilots** — **H** for brake-assist (matches the velocity of
  the nearest landable body at H-press time, sticky-on-engage, with
  hover-hold and damp modifiers) and **J** for path-hold (tracks the
  most-recently-committed plan with a small corrective thrust).
- **Mine, build, defend** — default world ships eight ore deposits
  split Planet (2) / Frostbite (6) and ten build pads spread Planet (5)
  / Ember (3) / Moon (2). Spend ore to construct one of two structures
  per pad: **dumb turrets** (50 ore, anti-UFO, ~380-unit range) or
  **missile printers** (150 ore + 30 ore per missile, anti-AA *and*
  anti-UFO, 5000-unit range — each missile flies its own bespoke
  gravity-aware flight plan). Mining and defending happen on different
  worlds, so cross-system trips have weight.
- **Planetary AA batteries** (toggle with **Shift+F10**) — about half
  of landable bodies are rolled with a body-mounted battery at world
  build, deterministic from the world seed. Each battery solves a real
  intercept against your gravity-affected predicted trajectory, paints
  a 1-second targeting laser, then fires a straight-line bullet. The
  solver refuses to converge while you're burning W or S — that's the
  dodge escape hatch.
- **Save / load** — F3 quicksaves to a default slot, F2 loads it.
  Ctrl+F1..F9 saves to numbered slots 1–9 for bookmarking distinct
  expedition states (apo-burn ready, frostbite return, mid-mining…);
  Shift+F1..F9 loads them. Atomic write with `.bak` rotation, so a
  crash mid-save can't corrupt the active slot. Random-universe seeds
  are baked into the save so a quickload re-seeds the same generator.
- **Click-drag camera pan** — left-click-drag the playfield to slide
  the viewport off-ship for surveys. Release and it eases back to the
  ship over ~7 seconds (easeOutCubic). Disabled while the build menu
  or seed prompt is intercepting clicks.
- **Time-scale control** (F7/F8) from 1/16× to 16× without breaking
  predictor fidelity.
- **Wall-clock-faithful video recording** (F9) — pipes raw frames to
  ffmpeg on a worker thread. Stutters in the game show up as freezes
  in the video, not sped-up footage.

Soft landing requires low relative speed (≤ 35 px/s vs. the body) and
nose pointed away from the planet.

## Documentation

The codebase has accumulated enough lore that I split the docs by topic
rather than packing everything into this README. If you're:

- **Just trying to fly the ship** — see [CONTROLS.md](CONTROLS.md) for
  the full keyboard / mouse reference.
- **Trying to read the cyan and orange lines** — see
  [TRAJECTORY.md](TRAJECTORY.md) for what each marker on the predicted
  trajectory means.
- **Picking up the project to extend it** — see
  [DESIGN.md](DESIGN.md) for the architecture, physics model,
  autopilot designs, tunable constants, and planned forks.
- **Picking up the project to debug it** — see
  [PROGRAM_FLOW.md](PROGRAM_FLOW.md) for the per-frame sequencing,
  state-machine, recorder threading, and bug-fix history (the "don't
  reintroduce" list).

## File layout

```
ypilot.py            # the entire game (~4500 lines)
README.md            # this file
CLAUDE.md            # AI-collaborator guidance (load-bearing invariants)
CONTROLS.md          # full keyboard/mouse reference
DESIGN.md            # architecture, physics, autopilots, tunables
PROGRAM_FLOW.md      # frame loop, state machine, bug-fix history
TRAJECTORY.md        # reading the predicted trajectory
LICENSE.md           # public domain (Unlicense)
.gitignore           # standard Python ignores + captures/ + saves/
captures/            # F9 videos + F12 screenshots (auto-created, gitignored)
saves/               # quicksave slots (auto-created, gitignored)
```

## Working with the project author

Notes for collaborators (human or AI):

- Casual conversational tone; uses `:-{D`-style smileys.
- Strong UX instinct, will sharply call out usability problems.
- Tunes constants by feel via playtesting; subscribes to "near enough
  is good enough" — bespoke craftwork is appreciated but not required.
- Prefers diagnosis-then-patch over blind fixes; appreciates a brief
  explanation of *why* a change is needed before the change is made.
- Will push back if a fix doesn't actually solve the problem; "it
  still does X" is honest feedback worth digging into, not a vague
  complaint.
- Comfortable enough with code to tweak constants directly between
  sessions.
- Recent git history is the most reliable source of truth for what
  changed and why; commit messages have been kept descriptive on
  purpose.

## License

Public domain (Unlicense). See [LICENSE.md](LICENSE.md).
