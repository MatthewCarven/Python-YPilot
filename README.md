# YPilot

A 2D space-flight game in Python + pygame-ce. Orbit a planet under
Newtonian gravity, mine ore from surface deposits, construct auto-aim
turrets at build pads, and defend against UFOs that drift in from
off-screen.

There's also a second planet — **Ember**, a rust-coloured wilderness
world at orbit radius 1800 — for when home gets boring; a Hohmann
transfer takes about 52 seconds. Planet has a small grey **Moon** in a
hierarchical orbit (orbit radius 250, period ~12 s) — fast enough to
lap you, small enough that landings need real precision.

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
  parented to Planet), and Ember. Symplectic leapfrog integrator, so
  closed orbits stay closed.
- **Trajectory predictor** with adaptive step, 5-second tick marks,
  periapsis/apoapsis dots with prograde-burn arrows, closest-approach
  marker, sphere-of-influence crossings, and a chaos-cone visualisation.
- **Plan-mode (Space)** — pause the world, dial a burn with the mouse,
  see the orange "what-if" trajectory before you commit. Supports
  multi-burn chains (queue with **N**, pop with **Backspace**, fire on
  **Enter**) so you can stage a Hohmann insertion as one keypress.
- **Two autopilots** — **H** for brake-assist (matches the velocity of
  the nearest landable body, with hover-hold and damp modifiers) and
  **J** for path-hold (tracks the most-recently-committed plan with a
  small corrective thrust).
- **Mine, build, defend** — six ore deposits and five build pads on
  Planet; spend ore at a build pad to construct a dumb turret that
  leads enemies and fires every second.
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
ypilot.py            # the entire game (~2970 lines)
README.md            # this file
CONTROLS.md          # full keyboard/mouse reference
DESIGN.md            # architecture, physics, autopilots, tunables
PROGRAM_FLOW.md      # frame loop, state machine, bug-fix history
TRAJECTORY.md        # reading the predicted trajectory
LICENSE.md           # public domain (Unlicense)
.gitignore           # standard Python ignores
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
