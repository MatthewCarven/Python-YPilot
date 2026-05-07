# Reading the trajectory

The cyan line ahead of the ship — orange while paused in plan-mode — is
the predictor's best guess at the ship's future path. Several markers
turn it into a navigation instrument rather than just a pretty line.

This document explains how to read each marker. For the math behind the
prediction (adaptive dt, body-time sampling, chaos cone) see
[DESIGN.md § Trajectory predictor](DESIGN.md#trajectory-predictor).

## The line itself

The line is drawn as a series of short segments at stride
`PREDICT_DRAW_STRIDE = 6`, with two visual cues layered on top.

**Colour shift.** Cool blue at the ship end, lerping to bright red at
the horizon. Both endpoints are at full brightness — no darkening fade
— so the tip of the line stays readable against the dark background.
Plan-mode trajectories use orange → red instead of cyan → red.

**Thickness ramp.** The line thickens from 1 px near the ship to 3 px
at the horizon. This is the **chaos cone**: even with bit-faithful
integration, a 3-body trajectory's true position diverges exponentially
with horizon. The thickening ribbon expresses "how far ahead is
trustworthy" without trying to compute a real error envelope.

Past 2–3 planetary periods (~150 s) the line is mathematically real but
informationally fictional — you're past Lyapunov time. The chaos cone
makes that visible at a glance.

## Tick marks

Perpendicular tick marks every `PREDICT_TICK_INTERVAL = 5 s`. Use them
to read off "where will I be in 10 / 15 / 20 s".

- Closer-spaced ticks = slower (you're near apoapsis).
- Widely-spaced ticks = faster (you're near periapsis).

Tick length is screen-space — they stay constant pixels at any zoom.
They share the line's colour gradient and thickness ramp, so a tick at
the far end honours the same uncertainty cone as the line under it.

## Apsis dots and prograde arrows

Two ringed dots mark the first periapsis and apoapsis ahead of the ship,
anchored to whichever landable body is currently closest. Same visual
grammar as the impact end-marker — 5 px outline + 2 px filled core — so
the eye reads them as "predictor annotations" rather than world objects.

| Marker | Meaning | What to do with it |
|---|---|---|
| **Peach dot — periapsis (peri)** | Predicted closest point of the orbit to the anchor body. **Where you're moving fastest.** | To make orbit *less* eccentric: burn retrograde at peri. To go *more* eccentric: burn prograde at peri. |
| **Cool-blue dot — apoapsis (apo)** | Predicted farthest point. **Where you're moving slowest.** | To make orbit *less* eccentric: burn prograde at apo. To go *more* eccentric: burn retrograde at apo. |

**Prograde arrow.** Each apsis dot has a small arrow attached, pointing
in the direction the ship will be moving as it passes through the
apsis. Tangential burns at apsides are the most efficient way to
reshape an orbit — all your Δv goes into reshaping rather than
rotating.

If the orbit is nearly circular, peri ≈ apo and you may not see a
distinct extremum within the predicted window — both dots can disappear.
That's fine; near-circular orbits don't have a useful "burn here" point.

The HUD line `Peri / Apo: <peri_alt> / <apo_alt> (vs <body>)` shows the
current values numerically.

## Closest-approach diamond

A magenta diamond outline marks the predicted closest pass to the
*nearest non-anchor* landable body — different shape from the peri/apo
dots so it doesn't compete visually.

With three landable bodies (Planet, Moon, Ember), the marker picks the
most useful "next destination":

- Near Planet → marker tracks the Moon.
- Near Moon → marker tracks Planet.
- Near Ember → marker tracks the Planet system.

The HUD label `(vs <body>)` tells you which one. To set up a Hohmann
transfer: burn prograde at apo (or peri, whichever is on the right
side), watch the magenta diamond slide toward your target on the orange
ghost trajectory, fine-tune with the burn-duration ladder, commit.

## SOI crossing rings

Small gold rings mark **sphere-of-influence (SOI) crossings** — points
where the gravitationally dominant body changes along the predicted
path.

Inside one body's SOI you can think of your orbit as essentially a
2-body ellipse around it; outside, the next body takes over. These
rings mark the hand-off points and tend to be where orbits visibly
precess or transfer hand-offs happen.

The default 370 px circular orbit sits *just inside* the planet's Hill
sphere (~441 px), so circular-ish orbits visibly wobble due to solar
tide near the SOI boundary. That's intentional — it's the multi-body
experience.

## Impact dot

The end of the line gets a coloured dot if the trajectory hits something
within the prediction window:

- **Green** — soft impact, within `LAND_SPEED_MAX = 35 px/s` relative
  to the body. You'd land successfully.
- **Red** — hard impact. You'd crash.

Soft-landing speed is *relative* to the body, not absolute world-frame
speed. The trajectory predictor's impact-color marker also uses relative
speed — what you see is what you'll feel on touchdown.

## Chain burn chevrons (plan-mode)

When planning a multi-burn chain (paused, with N to queue burns), each
scheduled burn point gets a small filled chevron on the orange
trajectory, plus a numeric label (1, 2, 3, …). The chevrons sit on top
of the apsis dots and the line itself so they read above everything.

The current preview burn (the one you're editing with `[`/`]` and
`,`/`.`) gets the highest-numbered label, so the chain reads naturally
from where you are now to where the chain ends.

## Plan-mode (orange) vs live (cyan)

The plan-mode line gets the same annotations as the live line — same
ticks, same apsis dots, same closest-approach diamond, same SOI rings
— so trimming a Hohmann is "step `]` until the orange diamond touches
your target" rather than mental arithmetic.

The two lines are drawn in different colours so live-vs-planned can be
compared at a glance: the cyan line is "where I'm headed if I do
nothing"; the orange line is "where I'd end up if I commit this burn
chain".

While paused, the camera follows the planned trajectory to the current
preview burn's fire-time (rather than glueing to the ship), so the view
slides toward where the *next burn* will fire as you adjust `,`/`.`.
That keeps your eye on what you're planning, not on the ship.
