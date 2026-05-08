"""
YPilot - Tier 2: simple solar system
====================================
A small XPilot / Escape Velocity-inspired space game.

Flight + survival in a multi-body system: a sun at world origin and a planet
that orbits it on circular Keplerian rails. The ship feels gravity from
*both* bodies. Land on the planet to refuel, mine ore from spike outcrops,
construct turrets at build pads, defend against UFOs that drift in from
off-screen.

Window auto-sizes to the user's desktop resolution. Zoom in/out with +/-.

Controls:
    Mouse              aims the ship's nose at the cursor (primary aim;
                       suppressed for ~0.75s after liftoff -- the ship
                       fires full boost vertically during this window
                       regardless of input, then steering returns to you)
    Left  / A          rotate counter-clockwise (keyboard fallback)
    Right / D          rotate clockwise        (keyboard fallback)
    Up    / W          thrust forward
    Shift + Up/W       thrust forward at 5x normal (boost - escape velocity)
    Ctrl  + Up/W       thrust forward at 1% normal (precision)
    Ctrl+Shift + Up/W  thrust forward at 0.1% normal (extra-fine trim)
    Down  / S          retro-thrust at 10% of forward power
    Ctrl  + Down/S     retro-thrust at 1% (precision)
    Ctrl+Shift + Down/S retro-thrust at 0.1% (extra-fine trim)
    Q                  strafe left at 10% of forward power
    E                  strafe right at 10% of forward power
    H                  toggle brake assist (autopilot matches velocity of
                       nearest landable body, or zeroes absolute velocity
                       if no landable body in scene)
    Shift (while H on) hover-hold: zero only radial velocity, leave
                       tangential drift alone (lines you up over a pad)
    Ctrl  (while H on) damp autopilot to 0.25x strength (fine soft landings)
    Shift+Ctrl (H on)  hover-hold at 0.25x strength
    J                  toggle path-hold autopilot. Tracks the most-recently-
                       committed plan-mode trajectory using small corrective
                       thrust (capped at 5% of nominal). Nulls phase drift
                       and small chaotic perturbations so you stay glued
                       to the orange-line plan you just fired. Cancels on
                       W/S like brake-assist; mutually exclusive with H.
                       No-op if no plan committed yet, or if landed.
    B (hold)           build mode while landed near an unoccupied build pad
    + / =              zoom in
    - / _              zoom out
    0                  reset zoom to 1.0
    /                  shorter trajectory prediction window (down to 5s)
    *                  longer trajectory prediction window (up to 5min)
    F1                 toggle HUD text overlay (world content stays visible)
    F4                 minimise window (boss key)
    F5 / F6            halve / double the predictor's step budget; coarser
                       steps are cheaper but less faithful, finer steps cost
                       more per frame. Current value shown on HUD.
    F7 / F8            halve / double simulation time scale (1/16x to 16x).
                       Slows down or speeds up live physics + enemies +
                       turrets together. Plan-mode (Space) is unaffected --
                       paused is paused. Current value shown on HUD when
                       not 1.0x. R resets back to 1.0x.
    F10                toggle enemy spawns (also clears any in scene)
    Space              pause + plan-mode "what-if" overlay. Mouse aims a
                       burn direction; an orange ghost trajectory shows where
                       the ship would end up if it received an instantaneous
                       delta-v of (SHIP_THRUST * duration) in that direction.
                       Bodies, ship, enemies, fuel all freeze while paused.
    [ / ]              (paused only) shorten / lengthen the planned burn
                       duration in 0.1s steps; current value shown on HUD.
                       Duration is signed -- step past 0 into negatives to
                       plan a retro burn without flipping the mouse 180°.
    Ctrl + [ / ]       (paused only) duration step at 0.01s (precision)
    Ctrl+Shift + [ / ] (paused only) duration step at 0.001s (extra-fine)
    Alt + [ / ]        (paused only) duration step at 0.0001s (super-fine)
    , / .              (paused only, also < / >) shift the current preview
                       burn's fire-time forward / backward along the
                       trajectory in 0.1s steps. Lets you stage a burn at
                       a specific future point (e.g., apo) without first
                       expanding predict_seconds. Floor is the previous
                       queued burn's offset (chain stays monotonic);
                       ceiling is PREDICT_MAX_SECONDS.
    Ctrl + , / .       (paused only) offset step at 0.01s (precision)
    Ctrl+Shift + , / . (paused only) offset step at 0.001s (extra-fine)
    Alt + , / .        (paused only) offset step at 0.0001s (super-fine)
    Enter              (paused only) commit the planned chain: burn 0
                       fires immediately, queued burns fire on schedule,
                       and the sim resumes. Lifts off automatically if
                       landed. With an empty queue this behaves exactly
                       like the old single-burn commit.
    N                  (paused only) push the current preview onto the
                       maneuver chain and start planning the next burn.
                       The next preview burn defaults to the SAME fire-
                       time as the burn you just queued (camera stays
                       glued to the burn point) -- use , / . afterwards
                       to push it forward in time, or just plan another
                       burn at the same instant for stacked retro+lateral
                       combos. Each chained burn gets a numbered chevron
                       on the orange trajectory.
    Backspace          (paused only) pop the last queued burn back into
                       the editable preview slot, restoring its duration
                       AND its fire-time offset. Useful for retuning a
                       burn without re-planning from scratch.
    F9                 toggle video recording. Pipes raw frames to ffmpeg
                       (must be on PATH) and writes a timestamped .mp4
                       into ./captures/ (created if missing). 30fps
                       H.264/yuv420p output paced against wall-clock --
                       a 500ms stutter shows as a 500ms freeze in the
                       recording, not as sped-up footage. Encode runs
                       on a worker thread so the game loop never
                       blocks. HUD shows REC + frame counts while active.
    F11                toggle fullscreen
    F12                save screenshot (PNG) into ./captures/ (created
                       if missing)
    R                  reset world
    Esc                quit

Run:
    pip install pygame-ce        # or: pip install pygame
    python ypilot.py

    Also
    winget install ffmpeg
    if you want to record video
"""

import datetime
import math
import os
import queue
import random
import subprocess
import sys
import threading
import time

import pygame
from pygame.math import Vector2


# --- Display (initialised at startup; defaults are fallback only) -----------
WIDTH, HEIGHT = 1280, 720
FPS = 60
BG = (8, 8, 20)

# --- Physics timestep -------------------------------------------------------
# Live sim runs in fixed PHYSICS_DT chunks via a wall-time accumulator. The
# predictor uses the same PHYSICS_DT for short/medium horizons so the planned
# orange ghost is bit-equivalent to the trajectory the live integrator will
# fly (ignoring chaos amplification of any residual diffs). MAX_FRAME_DT caps
# the per-frame catch-up after a stall so we don't spiral after a hitch.
PHYSICS_DT = 1.0 / FPS
MAX_FRAME_DT = 0.25

# --- Time scale (F7/F8) -----------------------------------------------------
# Multiplier on the wall-time fed into the physics accumulator each frame.
# 1.0 = real time. < 1.0 = slow-mo (more in-game frames per game-second of
# motion -- handy for landings). > 1.0 = fast-forward (fewer in-game frames
# per game-second -- handy for long Hohmann coasts). Bounds are four
# halvings/doublings each way, mirroring F5/F6's range pattern.
# At very high scales the accumulator caps at MAX_FRAME_DT so 16x effectively
# tops out around ~15x per frame; the cap is there so a stall can't burst.
TIME_SCALE_DEFAULT = 1.0
TIME_SCALE_MIN = 1.0 / 16.0
TIME_SCALE_MAX = 16.0

# --- Zoom -------------------------------------------------------------------
ZOOM_MIN = 0.125
ZOOM_MAX = 8.0
ZOOM_STEP = 1.15

# --- Sun --------------------------------------------------------------------
SUN_RADIUS = 100.0
SUN_MU = 8_000_000.0
SUN_COLOR = (255, 220, 100)
SUN_RIM = (220, 180, 60)
SUN_GLOW_COLOR = (255, 240, 180)

# --- Planet (orbiting the sun) ---------------------------------------------
PLANET_RADIUS = 90.0
PLANET_MU = 4_000_000.0
PLANET_COLOR = (90, 160, 220)
PLANET_RIM = (40, 90, 150)
PLANET_ORBIT_RADIUS = 800.0
PLANET_INITIAL_PHASE = 0.0

# --- Planet 2: Ember (outer wilderness) ------------------------------------
# Heavier, larger, slower, and rust-coloured. Carries forward-base build pads
# but no ore -- you have to haul ore in from elsewhere to fortify here.
# Hohmann transfer from PLANET orbit takes ~52s.
PLANET2_NAME = "Ember"
PLANET2_RADIUS = 110.0
PLANET2_MU = 6_000_000.0
PLANET2_COLOR = (200, 100, 70)
PLANET2_RIM = (140, 60, 40)
PLANET2_ORBIT_RADIUS = 1800.0
PLANET2_INITIAL_PHASE = math.pi * 0.6

# --- Planet 3: Frostbite (the ore world) -----------------------------------
# Pale, distant, lower gravity. The ore-rich destination -- Planet only has
# enough deposits for a starter turret or two, the bulk lives out here.
# Hohmann transfer from PLANET orbit takes ~92s; from Ember ~146s. The round
# trip is the whole point: you commit to a real expedition for ore. No build
# pads (intentionally undefended; lingering here is risky).
# Smaller mu/radius than Planet means surface gravity is ~80% of Planet's --
# easier to land soft, easier to accidentally bounce off too.
PLANET3_NAME = "Frostbite"
PLANET3_RADIUS = 80.0
PLANET3_MU = 2_500_000.0
PLANET3_COLOR = (200, 220, 240)
PLANET3_RIM = (140, 170, 210)
PLANET3_ORBIT_RADIUS = 3000.0
PLANET3_INITIAL_PHASE = math.pi * 1.4

# --- Moon (orbiting Planet) -------------------------------------------------
# Hierarchical orbit: parented to Planet (which itself orbits the Sun).
# Body.position_at recurses through parent so this composes Sun+Planet+Moon
# offsets analytically and gravity_at_t sees a moving moon at the right place.
#
# Sized to sit well inside Planet's Hill sphere (~441px). At r=250 around
# Planet (mu=4e6) the period is T = 2*pi*sqrt(r^3/mu_p) =~ 12.4s and the
# circular orbit speed v = sqrt(mu_p/r) =~ 126.5 px/s. The default player
# orbit at 370px around Planet sits at ~104 px/s, T ~22s -- so the moon
# laps you. Chasing it requires real interception planning, not just turning.
#
# Moon's own Hill sphere is r_hill = a*(mu_m/(3*mu_p))^(1/3) =~ 64px so
# above the moon's surface there's only ~39px before Planet's gravity
# overpowers Moon's. Landings are tight; come in slow.
MOON_NAME = "Moon"
MOON_RADIUS = 25.0
MOON_MU = 200_000.0
MOON_COLOR = (180, 175, 170)
MOON_RIM = (120, 115, 110)
MOON_ORBIT_RADIUS = 250.0
MOON_INITIAL_PHASE = math.pi * 0.5

# --- Ship -------------------------------------------------------------------
SHIP_THRUST = 220.0
SHIP_TURN_RATE = math.radians(180)
SHIP_LEN = 18.0
SHIP_COLOR = (240, 240, 240)
SHIP_OUTLINE = (40, 40, 60)
FLAME_COLOR = (255, 170, 60)
RETRO_FLAME_COLOR = (180, 200, 255)
LANDED_RING_COLOR = (140, 220, 140)

THRUST_BOOST_SCALE = 5.0         # Shift + W/Up
THRUST_PRECISION_SCALE = 0.01    # Ctrl + W/Up        (1% of nominal)
THRUST_FINE_SCALE = 0.001        # Ctrl+Shift + W/Up  (0.1% of nominal)
RETRO_THRUST_SCALE = 0.1         # S/Down             (default retro: 10%)
RETRO_PRECISION_SCALE = 0.01     # Ctrl + S/Down      (1% retro)
RETRO_FINE_SCALE = 0.001         # Ctrl+Shift + S/Down (0.1% retro)
LATERAL_THRUST_SCALE = 0.1       # Q / E strafe thrusters; same magnitude
                                 # as default retro for symmetric feel

MOUSE_AIM_DEADZONE_SQ = 9.0

# --- Fuel -------------------------------------------------------------------
MAX_FUEL = 100.0
REFUEL_RATE = MAX_FUEL / 30.0
LOW_FUEL_FRAC = 0.25
CRITICAL_FUEL_FRAC = 0.05

# --- Landing ----------------------------------------------------------------
LAND_SPEED_MAX = 35.0
LAND_ANGLE_TOLERANCE = math.radians(30)
LAND_ALIGN_DOT = math.cos(LAND_ANGLE_TOLERANCE)
TAKEOFF_LOCK_SECONDS = 0.30      # mouse aim / turn keys are suppressed for
                                 # this long after liftoff so the ship commits
                                 # to a clean vertical climb before steering
                                 # control returns to the player
LAUNCH_PAD_HEIGHT = 5.0          # extra clearance above the surface at the
                                 # moment of liftoff. The body is frozen
                                 # during ship.update, so the ship's first
                                 # leapfrog step drifts ~body.vel*dt toward
                                 # the body's static position (worst case
                                 # ~1.67 px at the planet's orbital speed).
                                 # 5 px gives us comfortable headroom.

# --- Brake assist -----------------------------------------------------------
BRAKE_KP = 2.0
BRAKE_MAX_ACCEL = SHIP_THRUST * 3.0
BRAKE_RING_COLOR = (90, 200, 255)

# --- Path-hold autopilot ---------------------------------------------------
# Tracks the most-recently-committed plan-mode trajectory. At commit time the
# main loop snapshots the predictor's (t, pos, vel) samples and stores them
# on the ship. While engaged (J), every frame the autopilot interpolates the
# planned state at sim_time and applies a small corrective acceleration:
#   a = PATH_HOLD_KP * (planned_pos - pos) + PATH_HOLD_KD * (planned_vel - vel)
# clamped at PATH_HOLD_MAX_ACCEL. This nulls phase drift and small chaotic
# perturbations without trying to chase gravitationally infeasible paths.
# The cap is deliberately small: if the live trajectory has diverged enough
# that a 5%-thrust correction can't catch up in a few seconds, the plan is
# probably stale and re-planning is the right answer.
# Cancelled by W/S like brake-assist (player override). Q/E doesn't cancel,
# matching brake-assist's "strafe + autopilot" workflow. Mutually exclusive
# with brake-assist -- they'd fight each other.
PATH_HOLD_KP = 2.0
PATH_HOLD_KD = 3.0
PATH_HOLD_MAX_ACCEL = SHIP_THRUST * 0.05  # 5% thrust ceiling: phase-drift only
PATH_HOLD_RING_COLOR = (255, 170, 90)     # matches PLAN_COLOR -- "tracking the orange line"
# Lookahead horizon for the saved trajectory: snapshot extends past the last
# scheduled burn by this much, so path-hold has somewhere to track to after
# the chain finishes.
PATH_HOLD_POSTBURN_SECONDS = 60.0

# --- Trajectory prediction --------------------------------------------------
PREDICT_SECONDS = 30.0           # default look-ahead
PREDICT_MIN_SECONDS = 5.0        # `/` key floor
PREDICT_MAX_SECONDS = 1000.0     # `*` key ceiling (~16.7 minutes)
PREDICT_STEP = 1.5               # multiplicative step per `/` or `*` press
PREDICT_TARGET_STEPS = 6400      # cap total steps so 5min predictions stay cheap
PREDICT_TARGET_STEPS_MIN = 100   # F5 halve floor: very coarse but legal
PREDICT_TARGET_STEPS_MAX = 102400  # F6 double ceiling: past PHYSICS_DT clamp
PREDICT_CACHE_INTERVAL = 3  # frames between cyan-predict refreshes when
# running. Set to 1 to disable caching (refresh every frame). The cyan
# trajectory's start point lags the ship by up to (N-1) frames of motion
# during refresh windows -- ~5 px at default time scale -- which is the
# perf trade-off for amortizing the predict cost. When paused, ship
# state is invariant so the cache stays exact regardless of interval.
PREDICT_DRAW_STRIDE = 6
PREDICT_TICK_INTERVAL = 5.0      # seconds between perpendicular tick marks
PREDICT_TICK_HALFLEN = 5         # tick half-length, screen-space pixels
PREDICT_COLOR = (90, 200, 255)
# End-of-trajectory colour: lerp from PREDICT_COLOR (cyan/blue) at the ship
# end of the line to PREDICT_COLOR_END (bright red) at the far horizon end,
# so the tip of the line stays visible at full brightness instead of fading
# into the background. The thickness ramp (still 1->3 px) keeps the chaos
# cone cue without dimming readability.
PREDICT_COLOR_END = (255, 90, 90)
PREDICT_IMPACT_COLOR = (255, 90, 90)
APSIS_PERI_COLOR = (255, 130, 100)   # warm peach: closer to body
APSIS_APO_COLOR = (140, 200, 255)    # cool blue: farther from body
CLOSEST_APPROACH_COLOR = (210, 130, 240)  # magenta diamond: nearest pass to non-anchor body
SOI_CROSSING_COLOR = (220, 200, 90)  # gold ring: dominant gravity changes here

# --- Plan-mode (pause + what-if overlay) -----------------------------------
# Spacebar pauses the world (bodies, ship, enemies, bullets, fuel all freeze).
# While paused, the mouse aims a burn direction and `[` / `]` shorten/lengthen
# the planned burn duration. The overlay draws the trajectory the ship would
# follow if it were given an instantaneous delta-v of (SHIP_THRUST * duration)
# in the aimed direction. Approximation: real burns happen over time, but for
# short burns (< a few seconds) the impulse model is within a hair of reality
# and keeps the math one-line.
# Duration is signed: stepping below 0 flips the impulse vector, equivalent
# to pointing the cursor 180° opposite. Lets you A/B forward vs. retro burns
# from the same aim point (with [ / ] alone) instead of spinning the mouse.
PLAN_BURN_DURATION_DEFAULT = 0.1
PLAN_BURN_DURATION_MAX = 10.0
PLAN_BURN_DURATION_MIN = -PLAN_BURN_DURATION_MAX  # symmetric: negative = retro
PLAN_BURN_DURATION_LEAP_STEP = 1.0           # Shift + [ / ]    (1-s leap)
PLAN_BURN_DURATION_STEP = 0.1                # plain [ / ]
PLAN_BURN_DURATION_PRECISION_STEP = 0.01     # Ctrl + [ / ]
PLAN_BURN_DURATION_FINE_STEP = 0.001         # Ctrl+Shift + [ / ]
PLAN_BURN_DURATION_SUPERFINE_STEP = 0.0001   # Alt + [ / ]
# , / . (i.e. < / >) move the CURRENT preview burn's fire-time along the
# trajectory. Same precision ladder as the duration ladder above. Floor is
# the previous queued burn's offset so chain ordering stays monotonic;
# ceiling is PREDICT_MAX_SECONDS. The offset is *user-controlled* once the
# preview slot is active; auto-fill happens only when the slot resets (entry
# to plan mode, after N, after Backspace).
PLAN_BURN_OFFSET_LEAP_STEP = 1.0           # Shift + , / .    (1-s leap)
PLAN_BURN_OFFSET_STEP = 0.1                # plain , / .
PLAN_BURN_OFFSET_PRECISION_STEP = 0.01     # Ctrl + , / .
PLAN_BURN_OFFSET_FINE_STEP = 0.001         # Ctrl+Shift + , / .
PLAN_BURN_OFFSET_SUPERFINE_STEP = 0.0001   # Alt + , / .
PLAN_COLOR = (255, 170, 90)       # warm orange, distinct from PREDICT cyan
# Same gradient treatment as the predicted line: orange near the ship,
# fading to bright red at the horizon. Full brightness throughout so the
# end of the chained-burn ghost stays readable.
PLAN_COLOR_END = (255, 90, 90)
PLAN_IMPACT_COLOR = (255, 90, 90)
# --- Maneuver chain (multi-burn plan) ---------------------------------------
# Plan mode lets the player queue a sequence of burns instead of just one.
# Press N to push the current preview onto the chain, then plan the next
# burn; press Backspace to pop the last queued; press Enter to commit the
# whole chain (burn 0 fires immediately, burn k fires k * spacing after).
# The default spacing between chained burns is the predict_seconds at the
# moment the burn is added -- so adjusting `*` / `/` lets you stretch or
# compress the gap to taste.
CHAIN_BURN_MARKER_RADIUS = 5     # filled chevron at each scheduled burn point
CHAIN_BURN_MARKER_COLOR = (255, 220, 130)  # paler orange than PLAN_COLOR
PLAN_CHAIN_LOOKAHEAD_SCALE = 1.0  # plan trajectory horizon = (chain_span + this * predict_seconds)

# --- Mining / resources -----------------------------------------------------
NUM_DEPOSITS = 6
DEPOSIT_QTY = 100.0
DEPOSIT_VISUAL = 8.0
DEPOSIT_COLOR = (200, 150, 80)
DEPOSIT_RIM = (140, 100, 50)
DEPOSIT_DEPLETED_COLOR = (90, 80, 65)
MINING_RANGE = 35.0
MINING_RATE = 20.0
MINING_BEAM_COLOR = (240, 220, 110)

# --- Build pads + construction ----------------------------------------------
NUM_BUILDPADS = 5
BUILDPAD_VISUAL = 12.0
BUILDPAD_RANGE = 50.0
BUILDPAD_COLOR = (110, 130, 170)
BUILDPAD_RIM = (170, 200, 240)
BUILDPAD_OCCUPIED_RIM = (140, 220, 140)

# --- Turret ----------------------------------------------------------------
TURRET_COST = 50.0
TURRET_BODY = 9.0
TURRET_BARREL_LEN = 12.0
TURRET_RANGE = 380.0
TURRET_TURN_RATE = math.radians(60)
TURRET_FIRE_COOLDOWN = 1.0
TURRET_AIM_TOLERANCE = math.radians(8)
TURRET_AIM_NOISE = 0.05
TURRET_COLOR = (180, 180, 200)
TURRET_BARREL_COLOR = (120, 120, 140)
TURRET_RING_COLOR = (90, 130, 180)

# --- Bullet ----------------------------------------------------------------
BULLET_SPEED = 280.0
BULLET_LIFETIME = 2.5
BULLET_RADIUS = 2.0
BULLET_COLOR = (255, 230, 130)

# --- Enemy -----------------------------------------------------------------
ENEMY_RADIUS = 7.0
ENEMY_SPEED = 32.0
ENEMY_HP = 1
ENEMY_SPAWN_INTERVAL = 9.0
ENEMY_SPAWN_DISTANCE = 1700.0
ENEMY_KILL_REWARD = 6.0
ENEMY_COLOR = (220, 90, 130)
ENEMY_RIM = (120, 30, 70)
ENEMY_COURSE_CORRECT_MEAN = 60.0
ENEMY_COURSE_CORRECT_RAND = 0.5

# --- Build menu UI ----------------------------------------------------------
BUILD_PANEL_W = 380
BUILD_PANEL_H = 150
BUILD_PANEL_BG = (30, 32, 50)
BUILD_PANEL_BORDER = (90, 200, 255)


# ============================================================================
# Camera
# ============================================================================

class Camera:
    """World-to-screen transform with zoom. The camera is centred on `pos`
    (a world-space point); world objects are rendered relative to that point,
    scaled by `zoom`, and translated so that pos appears at the centre of
    the screen."""

    def __init__(self):
        self.pos = Vector2(0.0, 0.0)
        self.zoom = 1.0

    def world_to_screen(self, p: Vector2) -> tuple[float, float]:
        """Return (x, y) screen-space tuple for a world-space point."""
        return ((p.x - self.pos.x) * self.zoom + WIDTH * 0.5,
                (p.y - self.pos.y) * self.zoom + HEIGHT * 0.5)

    def world_to_screen_int(self, p: Vector2) -> tuple[int, int]:
        sx, sy = self.world_to_screen(p)
        return (int(sx), int(sy))

    def scale(self, s: float) -> float:
        return s * self.zoom


# ============================================================================
# Body (sun, planet, ...)
# ============================================================================

class Body:
    def __init__(self, name: str, radius: float, mu: float,
                 color, rim, parent=None, orbit_radius: float = 0.0,
                 phase: float = 0.0, landable: bool = True):
        self.name = name
        self.radius = radius
        self.mu = mu
        self.color = color
        self.rim = rim
        self.parent = parent
        self.orbit_radius = orbit_radius
        self.phase = phase
        self.landable = landable
        if parent is None or orbit_radius <= 0.0:
            self.omega = 0.0
        else:
            self.omega = math.sqrt(parent.mu / orbit_radius ** 3)
        self.pos = Vector2(0.0, 0.0)
        self.vel = Vector2(0.0, 0.0)
        self.update_at(0.0)

    def update_at(self, t: float) -> None:
        if self.parent is None:
            self.pos = Vector2(0.0, 0.0)
            self.vel = Vector2(0.0, 0.0)
        else:
            angle = self.phase + self.omega * t
            radial = Vector2(math.cos(angle), math.sin(angle))
            tangent = Vector2(-radial.y, radial.x)
            self.pos = self.parent.pos + radial * self.orbit_radius
            self.vel = self.parent.vel + tangent * (self.omega * self.orbit_radius)

    def position_at(self, t: float) -> Vector2:
        if self.parent is None:
            return Vector2(0.0, 0.0)
        angle = self.phase + self.omega * t
        return self.parent.position_at(t) + Vector2(
            math.cos(angle), math.sin(angle)
        ) * self.orbit_radius


def make_solar_system() -> list[Body]:
    sun = Body(
        "Sun", radius=SUN_RADIUS, mu=SUN_MU,
        color=SUN_COLOR, rim=SUN_RIM,
        landable=False,
    )
    planet = Body(
        "Planet", radius=PLANET_RADIUS, mu=PLANET_MU,
        color=PLANET_COLOR, rim=PLANET_RIM,
        parent=sun, orbit_radius=PLANET_ORBIT_RADIUS,
        phase=PLANET_INITIAL_PHASE, landable=True,
    )
    moon = Body(
        MOON_NAME, radius=MOON_RADIUS, mu=MOON_MU,
        color=MOON_COLOR, rim=MOON_RIM,
        parent=planet, orbit_radius=MOON_ORBIT_RADIUS,
        phase=MOON_INITIAL_PHASE, landable=True,
    )
    ember = Body(
        PLANET2_NAME, radius=PLANET2_RADIUS, mu=PLANET2_MU,
        color=PLANET2_COLOR, rim=PLANET2_RIM,
        parent=sun, orbit_radius=PLANET2_ORBIT_RADIUS,
        phase=PLANET2_INITIAL_PHASE, landable=True,
    )
    frostbite = Body(
        PLANET3_NAME, radius=PLANET3_RADIUS, mu=PLANET3_MU,
        color=PLANET3_COLOR, rim=PLANET3_RIM,
        parent=sun, orbit_radius=PLANET3_ORBIT_RADIUS,
        phase=PLANET3_INITIAL_PHASE, landable=True,
    )
    # Order matters for update_bodies(): a child body's update_at reads its
    # parent's current pos/vel, so Sun -> Planet -> Moon -> Ember -> Frostbite
    # keeps the chain consistent within a single physics step. (Moon comes
    # before Ember/Frostbite because it parents to Planet; the rest parent
    # to Sun and order-among-themselves doesn't matter.)
    return [sun, planet, moon, ember, frostbite]


def update_bodies(bodies: list[Body], t: float) -> None:
    for b in bodies:
        b.update_at(t)


# ============================================================================
# Math helpers
# ============================================================================

def circular_orbit_speed(body: Body, radius: float) -> float:
    return math.sqrt(body.mu / radius)


def gravity_at(pos: Vector2, bodies: list[Body]) -> Vector2:
    total = Vector2(0.0, 0.0)
    for body in bodies:
        to_body = body.pos - pos
        r2 = to_body.length_squared()
        if r2 > 1e-3:
            r = math.sqrt(r2)
            total += to_body * (body.mu / (r2 * r))
    return total


def gravity_at_t(pos: Vector2, t: float, bodies: list[Body]) -> Vector2:
    total = Vector2(0.0, 0.0)
    for body in bodies:
        bp = body.position_at(t)
        to_body = bp - pos
        r2 = to_body.length_squared()
        if r2 > 1e-3:
            r = math.sqrt(r2)
            total += to_body * (body.mu / (r2 * r))
    return total


def shortest_angle_diff(target: float, current: float) -> float:
    return (target - current + math.pi) % (2.0 * math.pi) - math.pi


def nearest_landable(pos: Vector2, bodies: list[Body]) -> Body | None:
    """Closest landable body to `pos` by center-to-center distance, or None
    if there isn't one in scene. The sun is not a viable landing target so
    it's filtered out.

    Used by:
      - brake-assist target latching at engage time (sticky thereafter --
        see `_brake_assist_accel`),
      - HUD altitude / rel-speed anchor labelling,
      - apsis-anchor selection,
      - enemy spawn-target selection.

    Geometric nearness is intuitive for the player but can lie about
    "which body am I really orbiting" during a Moon flyby. The hover-
    lurch that earlier motivated trying mu/r^2 dominance is now handled
    by the sticky-on-engage latch in brake-assist, which keeps the
    intuitive geometric pick AND eliminates the mid-hover switch.
    """
    best = None
    best_d2 = float("inf")
    for b in bodies:
        if not b.landable:
            continue
        d2 = (b.pos - pos).length_squared()
        if d2 < best_d2:
            best_d2 = d2
            best = b
    return best


def find_apsides(points: list[Vector2], t_start: float, dt: float,
                 body: Body
                 ) -> tuple[int | None, int | None, float | None, float | None]:
    """First periapsis and apoapsis ahead of the ship, anchored to `body`.

    `points[i]` is the predicted position at t_start + i*dt; body position is
    sampled at the matching time via `position_at` so apsides are honest in a
    moving-body system. Returns (peri_idx, apo_idx, peri_alt, apo_alt). Any
    field is None if not reached within the predicted window (e.g. trajectory
    hits the body before peri, or stays nearly circular and produces no
    detectable extremum)."""
    n = len(points)
    if n < 3 or dt <= 0.0:
        return (None, None, None, None)
    dists = [
        (p - body.position_at(t_start + i * dt)).length()
        for i, p in enumerate(points)
    ]
    peri_idx: int | None = None
    apo_idx: int | None = None
    for i in range(1, n - 1):
        d_prev, d_here, d_next = dists[i - 1], dists[i], dists[i + 1]
        if peri_idx is None and d_here < d_prev and d_here < d_next:
            peri_idx = i
        if apo_idx is None and d_here > d_prev and d_here > d_next:
            apo_idx = i
        if peri_idx is not None and apo_idx is not None:
            break
    peri_alt = max(0.0, dists[peri_idx] - body.radius) if peri_idx is not None else None
    apo_alt = max(0.0, dists[apo_idx] - body.radius) if apo_idx is not None else None
    return peri_idx, apo_idx, peri_alt, apo_alt


def find_closest_approach(points: list[Vector2], t_start: float, dt: float,
                          body: Body
                          ) -> tuple[int | None, float | None]:
    """Index and altitude of the predicted point at which the ship gets
    nearest to `body`, sampling body position at the matching time.

    Used to mark closest-pass to a *different* landable body than the orbit
    anchor -- e.g., when orbiting Planet, this is where the trajectory grazes
    nearest Ember. The marker is meaningful even when the ship isn't on a
    transfer (it's just 'the closest you got within the predicted horizon')."""
    n = len(points)
    if n < 1 or dt <= 0.0:
        return (None, None)
    best_idx = 0
    best_d = float("inf")
    for i, p in enumerate(points):
        d = (p - body.position_at(t_start + i * dt)).length()
        if d < best_d:
            best_d = d
            best_idx = i
    if best_d == float("inf"):
        return (None, None)
    alt = max(0.0, best_d - body.radius)
    return best_idx, alt


def find_soi_crossings(points: list[Vector2], t_start: float, dt: float,
                       bodies: list[Body]) -> list[int]:
    """Indices where the gravitationally dominant body changes along the
    predicted trajectory. Marks Hill-sphere / sphere-of-influence boundaries
    -- the line between 'in planet's gravity well' and 'in sun's gravity
    well', which is intentionally *just outside* the default orbit at 370 px
    (planet's Hill sphere is ~441 px). Crossings tend to be where orbits
    visibly precess or transfer hand-offs happen."""
    n = len(points)
    if n < 2 or dt <= 0.0 or not bodies:
        return []

    def dominant(p: Vector2, t: float) -> int:
        best_g = 0.0
        best_idx = -1
        for bi, b in enumerate(bodies):
            d2 = (p - b.position_at(t)).length_squared()
            if d2 < 1e-3:
                continue
            g = b.mu / d2
            if g > best_g:
                best_g = g
                best_idx = bi
        return best_idx

    crossings: list[int] = []
    prev = dominant(points[0], t_start)
    for i in range(1, n):
        cur = dominant(points[i], t_start + i * dt)
        if cur != prev and cur != -1 and prev != -1:
            crossings.append(i)
        prev = cur
    return crossings


# ============================================================================
# World objects
# ============================================================================

class Deposit:
    def __init__(self, body: Body, angle: float, quantity: float = DEPOSIT_QTY):
        self.body = body
        self.angle = angle
        self.quantity = quantity
        self.max_quantity = quantity

    @property
    def pos(self) -> Vector2:
        return self.body.pos + Vector2(
            math.cos(self.angle), math.sin(self.angle)
        ) * self.body.radius

    @property
    def depleted(self) -> bool:
        return self.quantity <= 0.0


class BuildPad:
    def __init__(self, body: Body, angle: float):
        self.body = body
        self.angle = angle
        self.turret = None

    @property
    def pos(self) -> Vector2:
        return self.body.pos + Vector2(
            math.cos(self.angle), math.sin(self.angle)
        ) * (self.body.radius + 2.0)

    @property
    def occupied(self) -> bool:
        return self.turret is not None and self.turret.alive


class Bullet:
    def __init__(self, pos: Vector2, vel: Vector2):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.lifetime = BULLET_LIFETIME
        self.alive = True

    def update(self, dt: float) -> None:
        self.pos += self.vel * dt
        self.lifetime -= dt
        if self.lifetime <= 0.0:
            self.alive = False


class Enemy:
    def __init__(self, pos: Vector2, vel: Vector2):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.hp = ENEMY_HP
        self.alive = True
        self.course_correct_timer = self._roll_correct_interval()

    @staticmethod
    def _roll_correct_interval() -> float:
        return random.uniform(
            ENEMY_COURSE_CORRECT_MEAN * (1.0 - ENEMY_COURSE_CORRECT_RAND),
            ENEMY_COURSE_CORRECT_MEAN * (1.0 + ENEMY_COURSE_CORRECT_RAND),
        )

    def update(self, dt: float, bodies: list[Body], ship_pos: Vector2 | None = None) -> None:
        self.pos += self.vel * dt

        if ship_pos is not None:
            self.course_correct_timer -= dt
            if self.course_correct_timer <= 0.0:
                to_ship = ship_pos - self.pos
                if to_ship.length_squared() > 1e-3:
                    self.vel = to_ship.normalize() * ENEMY_SPEED
                self.course_correct_timer = self._roll_correct_interval()

        for b in bodies:
            if (self.pos - b.pos).length() <= b.radius + ENEMY_RADIUS:
                self.alive = False
                break


def spawn_enemy(target_body: Body) -> Enemy:
    a = random.uniform(0.0, 2.0 * math.pi)
    radial = Vector2(math.cos(a), math.sin(a))
    pos = target_body.pos + radial * ENEMY_SPAWN_DISTANCE
    inward = (target_body.pos - pos).normalize()
    jitter_angle = random.uniform(-math.radians(15), math.radians(15))
    inward = inward.rotate_rad(jitter_angle)
    return Enemy(pos, inward * ENEMY_SPEED)


class Turret:
    def __init__(self, body: Body, mount_angle: float):
        self.body = body
        self.mount_angle = mount_angle
        self.angle = mount_angle
        self.fire_cooldown = 0.0
        self.alive = True

    @property
    def pos(self) -> Vector2:
        return self.body.pos + Vector2(
            math.cos(self.mount_angle), math.sin(self.mount_angle)
        ) * (self.body.radius + 2.0)

    def update(self, dt: float, enemies: list[Enemy], bullets: list[Bullet]) -> None:
        if not self.alive:
            return

        my_pos = self.pos
        target = None
        best_d2 = TURRET_RANGE * TURRET_RANGE
        for e in enemies:
            if not e.alive:
                continue
            d2 = (e.pos - my_pos).length_squared()
            if d2 <= best_d2:
                best_d2 = d2
                target = e

        if target is not None:
            distance = math.sqrt(best_d2)
            t_lead = distance / BULLET_SPEED if BULLET_SPEED > 1e-3 else 0.0
            predicted = target.pos + target.vel * t_lead

            err_mag = distance * TURRET_AIM_NOISE * random.random()
            err_angle = random.uniform(0.0, 2.0 * math.pi)
            aim_point = predicted + Vector2(
                math.cos(err_angle), math.sin(err_angle)
            ) * err_mag

            to_aim = aim_point - my_pos
            desired = math.atan2(to_aim.y, to_aim.x)
            diff = shortest_angle_diff(desired, self.angle)
            max_step = TURRET_TURN_RATE * dt
            if diff > max_step:
                self.angle += max_step
            elif diff < -max_step:
                self.angle -= max_step
            else:
                self.angle = desired

            self.fire_cooldown -= dt
            if abs(diff) < TURRET_AIM_TOLERANCE and self.fire_cooldown <= 0.0:
                self._fire(bullets)
                self.fire_cooldown = TURRET_FIRE_COOLDOWN
        else:
            self.fire_cooldown = max(0.0, self.fire_cooldown - dt)

    def _fire(self, bullets: list[Bullet]) -> None:
        muzzle_dir = Vector2(math.cos(self.angle), math.sin(self.angle))
        muzzle_pos = self.pos + muzzle_dir * TURRET_BARREL_LEN
        bullets.append(Bullet(muzzle_pos, muzzle_dir * BULLET_SPEED))


def generate_deposits(body: Body, n: int = NUM_DEPOSITS) -> list:
    out = []
    for i in range(n):
        base = (i / n) * (2.0 * math.pi)
        jitter = random.uniform(-math.radians(20), math.radians(20))
        out.append(Deposit(body, base + jitter))
    return out


def generate_buildpads(body: Body, n: int = NUM_BUILDPADS) -> list[BuildPad]:
    out = []
    for i in range(n):
        base = (i / n) * (2.0 * math.pi) + math.pi / n
        jitter = random.uniform(-math.radians(15), math.radians(15))
        out.append(BuildPad(body, base + jitter))
    return out


# ============================================================================
# Ship
# ============================================================================

class Ship:
    def __init__(self, planet: Body):
        self.reset(planet)

    def reset(self, planet: Body) -> None:
        start_r = planet.radius + 280.0
        v_rel = circular_orbit_speed(planet, start_r)
        self.pos = planet.pos + Vector2(start_r, 0.0)
        self.vel = planet.vel + Vector2(0.0, -v_rel)
        self.angle = -math.pi / 2
        self.thrusting = False
        self.retro_thrusting = False
        self.strafing_left = False
        self.strafing_right = False
        self.thrust_scale = 1.0
        self.retro_scale = RETRO_THRUST_SCALE
        self.brake_assist = False
        self.brake_assist_scale = 1.0
        self.brake_assist_target: Body | None = None  # latched on engage
        self.hover_hold = False
        self.takeoff_lock_timer = 0.0
        self.fuel = MAX_FUEL
        self.ore = 0.0
        self.mining_target = None
        self.landed = False
        self.landed_body = None
        self.landed_radial = 0.0
        self.alive = True
        # Scheduled maneuvers (chained-burn plan committed via Enter): each
        # entry is (apply_at_sim_time, burn_dir_unit_vector, duration_signed).
        # apply_pending_maneuvers fires any whose time has been reached.
        self.pending_maneuvers = []
        # Path-hold autopilot state. planned_trajectory is a parallel list of
        # (t, pos, vel) samples produced by the predictor at commit time.
        # _path_hold_hint caches the last-found bracket index so per-frame
        # lookup is O(1) typical instead of O(n) (the trajectory can have
        # thousands of samples on long chains).
        self.path_hold = False
        self.planned_trajectory = []
        self._path_hold_hint = 0
        self.path_hold_error = 0.0     # last frame's pos-error magnitude (HUD)
        self._sim_time = 0.0           # cached by update() for _compute_accel
        # Cached corrective accel from the path-hold controller. Computed
        # ONCE per update() against start-of-step state, reused for both
        # leapfrog half-kicks. Computing fresh per half-kick would compare
        # start-of-step ship pos to end-of-step plan time -- a one-step
        # phase offset the controller would burn fuel fighting forever.
        self._path_hold_cached_accel = Vector2(0.0, 0.0)

    def apply_pending_maneuvers(self, sim_time: float) -> None:
        """Fire any scheduled maneuvers whose apply-time has been reached.

        Reuses commit_planned_burn so each chain step matches what the
        plan-mode predictor showed (same fuel cost, same impulse model,
        same nose-direction snap). If a burn aborts (out of fuel / dead),
        the rest of the chain is dropped -- no point firing into the void.
        """
        while self.pending_maneuvers and self.pending_maneuvers[0][0] <= sim_time:
            _t, burn_dir, duration_signed = self.pending_maneuvers.pop(0)
            if not self.commit_planned_burn(burn_dir, duration_signed):
                self.pending_maneuvers.clear()
                return

    def toggle_brake_assist(self) -> None:
        if self.alive and not self.landed and self.fuel > 0.0:
            self.brake_assist = not self.brake_assist
            if self.brake_assist:
                # Brake-assist and path-hold are different state-space
                # targets (match-body vs match-plan). Letting them both run
                # would be a tug-of-war; only one autopilot at a time.
                self.path_hold = False

    def toggle_path_hold(self) -> bool:
        """Toggle the path-hold autopilot. Returns True if engaged after the
        toggle, False otherwise. No-op (returns current state) if there's no
        committed plan to track, or if landed / dead / out of fuel."""
        if not self.alive or self.landed or self.fuel <= 0.0:
            return self.path_hold
        if self.path_hold:
            self.path_hold = False
            return False
        if not self.planned_trajectory:
            return False  # nothing to track
        self.path_hold = True
        self.brake_assist = False
        self._path_hold_hint = 0
        return True

    def set_planned_trajectory(self,
                               samples: list[tuple[float, Vector2, Vector2]]
                               ) -> None:
        """Replace the saved plan-mode trajectory with a fresh snapshot.
        Called by the main loop on Enter-commit. Resets the bracket-search
        hint so the next path-hold frame searches from sample 0."""
        self.planned_trajectory = samples
        self._path_hold_hint = 0

    def _path_hold_accel(self, sim_time: float) -> Vector2:
        """PD correction toward the planned (pos, vel) at sim_time.

        Linear-interpolates between the two trajectory samples that bracket
        sim_time. Caches the search-bracket index across frames since
        sim_time only ever moves forward -- O(1) typical, O(n) worst case
        on a re-engage. If sim_time is past the last sample (plan stale),
        auto-disengage path-hold so the player isn't surprised by a silent
        no-op autopilot. If the plan hasn't started yet (sim_time before
        the first sample, e.g. you somehow time-travelled), clamp to the
        first sample -- shouldn't happen in normal flow.
        """
        if not self.path_hold or not self.planned_trajectory:
            return Vector2(0.0, 0.0)
        samples = self.planned_trajectory
        if sim_time >= samples[-1][0]:
            self.path_hold = False  # plan exhausted
            return Vector2(0.0, 0.0)
        # Walk forward from the cached hint until we bracket sim_time.
        i = max(0, min(self._path_hold_hint, len(samples) - 2))
        while i + 1 < len(samples) and samples[i + 1][0] < sim_time:
            i += 1
        # Edge case: sim_time before the first sample. Use sample 0.
        if sim_time <= samples[0][0]:
            target_pos = Vector2(samples[0][1])
            target_vel = Vector2(samples[0][2])
        else:
            t0, p0, v0 = samples[i]
            t1, p1, v1 = samples[i + 1]
            span = t1 - t0
            u = (sim_time - t0) / span if span > 1e-9 else 0.0
            target_pos = p0.lerp(p1, u)
            target_vel = v0.lerp(v1, u)
        self._path_hold_hint = i
        pos_err = target_pos - self.pos
        vel_err = target_vel - self.vel
        self.path_hold_error = pos_err.length()
        desired = pos_err * PATH_HOLD_KP + vel_err * PATH_HOLD_KD
        mag = desired.length()
        if mag > PATH_HOLD_MAX_ACCEL:
            desired *= (PATH_HOLD_MAX_ACCEL / mag)
        return desired


    def update(self, dt: float, keys, mods: int, deposits: list[Deposit],
               bodies: list[Body], mouse_pos: tuple[int, int] | None = None,
               mouse_aim_active: bool = True,
               sim_time: float = 0.0) -> None:
        if not self.alive:
            return
        # Cached for _compute_accel so path-hold can look up the planned
        # state at the right time without changing _compute_accel's
        # signature (kept matching the leapfrog's per-half-step contract).
        self._sim_time = sim_time

        # Tick down the post-liftoff steering lock. While > 0, mouse aim and
        # turn keys are suppressed so a fresh boost climbs cleanly upward
        # instead of being yanked sideways into the surface by an off-centre
        # cursor.
        self.takeoff_lock_timer = max(0.0, self.takeoff_lock_timer - dt)
        steering_active = self.takeoff_lock_timer <= 0.0

        if steering_active and mouse_aim_active and mouse_pos is not None:
            dx = mouse_pos[0] - WIDTH / 2
            dy = mouse_pos[1] - HEIGHT / 2
            if dx * dx + dy * dy >= MOUSE_AIM_DEADZONE_SQ:
                target = math.atan2(dy, dx)
                diff = shortest_angle_diff(target, self.angle)
                max_step = SHIP_TURN_RATE * dt
                if diff > max_step:
                    self.angle += max_step
                elif diff < -max_step:
                    self.angle -= max_step
                else:
                    self.angle = target

        if steering_active:
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.angle -= SHIP_TURN_RATE * dt
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.angle += SHIP_TURN_RATE * dt

        self._read_thrust_input(keys, mods)

        # Launch assist: while the takeoff lock is active, force full boost
        # forward regardless of what the player is (or isn't) holding. One
        # press commits to the climb; the ship handles the rest until it's
        # clear of the surface. Cancels retro and brake-assist for the same
        # window so nothing else fights the launch.
        if self.takeoff_lock_timer > 0.0:
            self.thrusting = True
            self.retro_thrusting = False
            self.strafing_left = False
            self.strafing_right = False
            self.thrust_scale = THRUST_BOOST_SCALE
            self.brake_assist = False
            self.path_hold = False

        if self.landed and self.landed_body is not None:
            self.brake_assist = False
            self.path_hold = False
            body = self.landed_body
            radial = Vector2(math.cos(self.landed_radial),
                             math.sin(self.landed_radial))
            self.pos = body.pos + radial * (body.radius + 1.0)
            self.vel = Vector2(body.vel)
            # Nose locked to surface-radial while parked, so mouse drift
            # can't tilt the ship before liftoff. Mouse aim resumes the
            # frame after thrust unlatches us from the surface.
            self.angle = self.landed_radial

            if self.thrusting or self.retro_thrusting:
                # Lift ship to launch-pad height before unlatching so the
                # first frame's tangential drift (ship inherits body.vel
                # while body is frozen during ship.update) can't carry the
                # ship back into the body's static position. Without this,
                # trailing-side launches re-land every frame until orbital
                # geometry shifts enough to break the loop.
                self.pos = body.pos + radial * (body.radius + LAUNCH_PAD_HEIGHT)
                self.landed = False
                self.landed_body = None
                self.mining_target = None
                self.takeoff_lock_timer = TAKEOFF_LOCK_SECONDS
            else:
                self.fuel = min(MAX_FUEL, self.fuel + REFUEL_RATE * dt)
                self._mine(deposits, dt)
                return

        self.mining_target = None

        if self.fuel <= 0.0:
            self.thrusting = False
            self.retro_thrusting = False
            self.brake_assist = False
            self.path_hold = False

        # Compute the path-hold correction ONCE for this update, against the
        # plan time that matches start-of-step ship state (sim_time - dt --
        # main() advances sim_time before calling update()). _compute_accel
        # then reads the cached value for both leapfrog half-kicks. This
        # avoids the constant ~vel*dt position bias that would otherwise
        # have the controller burning fuel to chase the next frame's plan.
        if self.path_hold:
            self._path_hold_cached_accel = self._path_hold_accel(
                self._sim_time - dt
            )
        else:
            self._path_hold_cached_accel = Vector2(0.0, 0.0)

        burn = 0.0
        if self.thrusting:
            burn += self.thrust_scale * dt
        if self.retro_thrusting:
            burn += self.retro_scale * dt
        if self.strafing_left:
            burn += LATERAL_THRUST_SCALE * dt
        if self.strafing_right:
            burn += LATERAL_THRUST_SCALE * dt
        if self.brake_assist:
            desired = self._brake_assist_accel(self.pos, self.vel, bodies)
            burn += (desired.length() / SHIP_THRUST) * dt
        if self.path_hold:
            burn += (self._path_hold_cached_accel.length() / SHIP_THRUST) * dt
        self.fuel = max(0.0, self.fuel - burn)

        a0 = self._compute_accel(self.pos, self.vel, bodies)
        v_half = self.vel + a0 * (dt * 0.5)
        self.pos = self.pos + v_half * dt
        a1 = self._compute_accel(self.pos, v_half, bodies)
        self.vel = v_half + a1 * (dt * 0.5)

        self._check_body_contact(bodies)

    def _check_body_contact(self, bodies: list[Body]) -> None:
        for body in bodies:
            to_body = self.pos - body.pos
            r = to_body.length()
            if r <= body.radius:
                if body.landable:
                    self._resolve_surface_contact(body, to_body, r)
                else:
                    self.alive = False
                return

    def _mine(self, deposits: list[Deposit], dt: float) -> None:
        best = None
        best_d2 = MINING_RANGE * MINING_RANGE
        for dep in deposits:
            if dep.depleted:
                continue
            d2 = (dep.pos - self.pos).length_squared()
            if d2 <= best_d2:
                best = dep
                best_d2 = d2

        self.mining_target = best
        if best is not None:
            amount = min(MINING_RATE * dt, best.quantity)
            best.quantity -= amount
            self.ore += amount

    def _resolve_surface_contact(self, body: Body, to_body: Vector2, r: float) -> None:
        rel_vel = self.vel - body.vel
        rel_speed = rel_vel.length()
        up_dir = to_body / r if r > 1e-3 else Vector2(0.0, -1.0)
        forward_dir = Vector2(math.cos(self.angle), math.sin(self.angle))
        nose_alignment = forward_dir.dot(up_dir)

        if rel_speed <= LAND_SPEED_MAX and nose_alignment >= LAND_ALIGN_DOT:
            self.landed = True
            self.landed_body = body
            self.landed_radial = math.atan2(up_dir.y, up_dir.x)
            self.vel = Vector2(body.vel)
            self.pos = body.pos + up_dir * (body.radius + 1.0)
        else:
            self.alive = False

    def _read_thrust_input(self, keys, mods: int) -> None:
        forward_pressed = bool(keys[pygame.K_UP] or keys[pygame.K_w])
        reverse_pressed = bool(keys[pygame.K_DOWN] or keys[pygame.K_s])
        strafe_left_pressed = bool(keys[pygame.K_q])
        strafe_right_pressed = bool(keys[pygame.K_e])

        shift = bool(mods & pygame.KMOD_SHIFT)
        ctrl  = bool(mods & pygame.KMOD_CTRL)

        self.thrusting = False
        self.retro_thrusting = False
        self.strafing_left = False
        self.strafing_right = False

        # Forward thrust trim ladder:
        #   plain         = 1.0         (nominal)
        #   Shift         = 5.0         (boost, for escape velocity)
        #   Ctrl          = 0.01        (precision)
        #   Ctrl+Shift    = 0.001       (extra-fine)
        if forward_pressed:
            self.brake_assist = False
            self.path_hold = False
            if ctrl and shift:
                self.thrust_scale = THRUST_FINE_SCALE
            elif shift:
                self.thrust_scale = THRUST_BOOST_SCALE
            elif ctrl:
                self.thrust_scale = THRUST_PRECISION_SCALE
            else:
                self.thrust_scale = 1.0
            self.thrusting = True

        # Retro thrust trim ladder (mirrors forward, no boost step):
        #   plain         = RETRO_THRUST_SCALE      (10%)
        #   Ctrl          = RETRO_PRECISION_SCALE   (1%)
        #   Ctrl+Shift    = RETRO_FINE_SCALE        (0.1%)
        if reverse_pressed:
            self.brake_assist = False
            self.path_hold = False
            if ctrl and shift:
                self.retro_scale = RETRO_FINE_SCALE
            elif ctrl:
                self.retro_scale = RETRO_PRECISION_SCALE
            else:
                self.retro_scale = RETRO_THRUST_SCALE
            self.retro_thrusting = True

        # Strafe does NOT cancel brake-assist. Forward and retro are
        # "I'm taking control" gestures, but strafe is "nudge the position
        # autopilot is holding". Combining strafe + hover-hold over a
        # build pad is the main reason this distinction exists.
        if strafe_left_pressed:
            self.strafing_left = True
        if strafe_right_pressed:
            self.strafing_right = True

        # Trim modifiers (Shift hover-hold, Ctrl damp) only apply when
        # neither forward nor reverse is pressed -- Shift/Ctrl double as
        # thrust scale modifiers in those cases, so we'd have a conflict.
        # Strafe doesn't use Shift/Ctrl, so it never conflicts here.
        if self.brake_assist and not forward_pressed and not reverse_pressed:
            self.hover_hold = shift
            self.brake_assist_scale = 0.25 if ctrl else 1.0
        else:
            self.hover_hold = False
            self.brake_assist_scale = 1.0

    def _compute_accel(self, pos: Vector2, vel: Vector2,
                       bodies: list[Body]) -> Vector2:
        accel = Vector2(0.0, 0.0)
        forward_dir = Vector2(math.cos(self.angle), math.sin(self.angle))

        if self.thrusting:
            accel += forward_dir * (SHIP_THRUST * self.thrust_scale)
        if self.retro_thrusting:
            accel -= forward_dir * (SHIP_THRUST * self.retro_scale)

        # Lateral strafe thrusters: perpendicular to the nose. In pygame
        # screen coords (+y down), -90 deg rotation of forward gives
        # the pilot's left direction.
        if self.strafing_left or self.strafing_right:
            pilot_left_dir = Vector2(math.sin(self.angle), -math.cos(self.angle))
            if self.strafing_left:
                accel += pilot_left_dir * (SHIP_THRUST * LATERAL_THRUST_SCALE)
            if self.strafing_right:
                accel -= pilot_left_dir * (SHIP_THRUST * LATERAL_THRUST_SCALE)

        accel += self._brake_assist_accel(pos, vel, bodies)
        # Path-hold contribution was computed once per update() against
        # start-of-step state; we just add the cached value here so both
        # leapfrog half-kicks see the same correction. Re-computing per
        # half-kick would introduce a one-PHYSICS_DT phase bias.
        if self.path_hold:
            accel += self._path_hold_cached_accel
        accel += gravity_at(pos, bodies)
        return accel

    def _brake_assist_accel(self, pos: Vector2, vel: Vector2,
                            bodies: list[Body]) -> Vector2:
        """Desired brake-assist thrust acceleration (clamped at BRAKE_MAX_ACCEL).

        Default mode: drag relative velocity toward the nearest landable
        body's velocity, so a "stop" really means "match the planet" --
        landings on a moving body converge naturally instead of needing
        manual under-correction.

        Hover-hold (Shift): kill only the radial component of relative
        velocity, leaving tangential drift untouched. Altitude locks while
        you slide sideways -- handy for lining up over a build pad.

        Falls back to zeroing absolute velocity if no landable body exists
        (e.g. you've drifted into deep space far from the system).
        """
        if not self.brake_assist:
            # Clear the latched target so the next engage picks fresh.
            self.brake_assist_target = None
            return Vector2(0.0, 0.0)

        # Sticky-on-engage targeting: lock onto the geometrically nearest
        # landable at the moment brake-assist first runs after toggle, and
        # hold that body until brake-assist toggles off. Solves two
        # problems with one mechanism:
        #   (1) Moon swooping past a high Planet orbit no longer lurches
        #       hover -- the target was latched on Planet at engage and
        #       doesn't switch mid-flight regardless of who's geometrically
        #       closest now.
        #   (2) Moon landings work as before -- fly close to the Moon,
        #       press H, target latches on Moon, brake-assist matches its
        #       126 px/s tangential velocity from a comfortable distance.
        # To retarget, toggle H off and on -- explicit pilot intent rather
        # than a silent autopilot guess.
        if self.brake_assist_target is None:
            self.brake_assist_target = nearest_landable(pos, bodies)
        target = self.brake_assist_target
        if target is not None:
            rel_vel = vel - target.vel
            if self.hover_hold:
                up = pos - target.pos
                if up.length_squared() > 1e-6:
                    up = up.normalize()
                    vel_to_kill = up * rel_vel.dot(up)
                else:
                    vel_to_kill = rel_vel
            else:
                vel_to_kill = rel_vel
        else:
            vel_to_kill = vel

        desired = (-BRAKE_KP * vel_to_kill - gravity_at(pos, bodies)) \
            * self.brake_assist_scale
        mag = desired.length()
        if mag > BRAKE_MAX_ACCEL:
            desired *= (BRAKE_MAX_ACCEL / mag)
        return desired

    def commit_planned_burn(self, burn_dir: Vector2, duration: float) -> bool:
        """Apply an instantaneous delta-v of (SHIP_THRUST * duration) along
        burn_dir, matching what the plan-mode predictor showed.

        duration is signed: a negative value flips the impulse vector and the
        post-burn nose direction, equivalent to aiming the cursor 180°
        opposite. Fuel cost is abs(duration) -- a retro burn costs fuel like
        any other burn.

        Returns False if the ship is dead or out of fuel. If fuel is short
        of |duration|, delivers a proportionally smaller impulse so the
        burn never costs fuel the ship doesn't have. Unlatches cleanly
        from the surface if landed, bypassing takeoff_lock_timer -- the
        player has already chosen the burn direction, the launch-assist
        would only fight that choice."""
        if not self.alive:
            return False
        if self.fuel <= 0.0:
            return False

        fuel_cost = min(abs(duration), self.fuel)
        sign = 1.0 if duration >= 0.0 else -1.0
        dv_mag = SHIP_THRUST * fuel_cost * sign

        if self.landed and self.landed_body is not None:
            body = self.landed_body
            radial = Vector2(math.cos(self.landed_radial),
                             math.sin(self.landed_radial))
            # Same pad-height bump as the W-press launch path -- protects
            # against re-grounding when ship inherits frozen body.vel.
            self.pos = body.pos + radial * (body.radius + LAUNCH_PAD_HEIGHT)
            self.vel = Vector2(body.vel)
            self.landed = False
            self.landed_body = None
            self.mining_target = None
            self.takeoff_lock_timer = 0.0  # no lock: player owns direction

        self.vel = self.vel + burn_dir * dv_mag
        # Face the actual impulse direction (flips for negative durations).
        self.angle = math.atan2(burn_dir.y * sign, burn_dir.x * sign)
        self.fuel = max(0.0, self.fuel - fuel_cost)
        return True

    def predict_trajectory(self, bodies: list[Body], t_start: float,
                           seconds: float = PREDICT_SECONDS,
                           dt: float | None = None,
                           pos0: Vector2 | None = None,
                           vel0: Vector2 | None = None,
                           target_steps: int = PREDICT_TARGET_STEPS,
                           pending_burns: list[tuple[float, Vector2, float]] | None = None,
                           burn_indices: list[int] | None = None,
                           out_velocities: list[Vector2] | None = None,
                           ) -> tuple[list[Vector2], float | None, float]:
        # Use PHYSICS_DT so the integrator matches the live sim step-for-step
        # over short/medium horizons -- the predicted ghost is then bit-
        # equivalent to what the live integrator will fly. Only coarsen for
        # very long windows where the step budget would blow up; chaos already
        # dominates those horizons regardless of dt.
        # Body-time sampling: live evaluates gravity_at(body.pos) where bodies
        # are pinned to sim_time = step end (update_bodies runs before
        # ship.update). We mirror that here by sampling bodies at t_end for
        # both half-kicks of the leapfrog, so the force model is identical.
        # pos0/vel0 override the ship's current state -- used by plan-mode
        # to predict from a hypothetical post-burn velocity.
        # pending_burns is an optional list of (t_apply, burn_dir, duration_signed):
        # the integrator inserts each kick at the step boundary that contains
        # its apply-time, mirroring how live ship.apply_pending_maneuvers fires
        # them (each kick = SHIP_THRUST * duration_signed in burn_dir, same
        # impulse the live commit_planned_burn applies). Used by plan-mode
        # chain previews. burn_indices, if provided, is filled with the
        # points-list index at which each burn was applied (same length and
        # order as pending_burns), so the caller can put a marker on each
        # burn point. out_velocities, if provided, is filled in lockstep
        # with `points` so callers can capture the full state-space
        # trajectory (used by path-hold autopilot to track planned vel).
        if dt is None:
            dt = max(PHYSICS_DT, seconds / target_steps)
        n = max(2, int(seconds / dt))
        pos = Vector2(pos0) if pos0 is not None else Vector2(self.pos)
        vel = Vector2(vel0) if vel0 is not None else Vector2(self.vel)
        points = [Vector2(pos)]
        if out_velocities is not None:
            out_velocities.append(Vector2(vel))
        impact_speed = None
        # Apply burns lazily: walk a pointer through the list, applying any
        # whose t_apply has been reached at the start of the next step.
        burns = list(pending_burns) if pending_burns else []
        burn_idx = 0
        for i in range(n):
            t1 = t_start + i * dt
            t2 = t_start + (i + 1) * dt
            # Apply any burns scheduled within (t1, t2] (and any "fire now"
            # burns at t == t_start fire at the first step). Push the
            # corresponding burn-point indices into burn_indices so the
            # caller can mark them on the trajectory.
            while burn_idx < len(burns) and burns[burn_idx][0] <= t2:
                _, b_dir, b_dur = burns[burn_idx]
                vel = vel + b_dir * (SHIP_THRUST * b_dur)
                if burn_indices is not None:
                    burn_indices.append(len(points) - 1)
                burn_idx += 1
            a0 = gravity_at_t(pos, t2, bodies)
            v_half = vel + a0 * (dt * 0.5)
            pos = pos + v_half * dt
            a1 = gravity_at_t(pos, t2, bodies)
            vel = v_half + a1 * (dt * 0.5)
            points.append(Vector2(pos))
            if out_velocities is not None:
                out_velocities.append(Vector2(vel))
            hit = False
            for body in bodies:
                bp = body.position_at(t2)
                if (pos - bp).length() <= body.radius:
                    hit = True
                    if body.landable:
                        eps = 1e-3
                        bp_next = body.position_at(t2 + eps)
                        bv = (bp_next - bp) / eps
                        impact_speed = (vel - bv).length()
                    else:
                        impact_speed = vel.length()
                    break
            if hit:
                break
        return points, impact_speed, dt

    def draw(self, surf: pygame.Surface, camera: Camera) -> None:
        if not self.alive:
            return

        cx, cy = camera.world_to_screen(self.pos)
        z = camera.zoom

        nose = Vector2(math.cos(self.angle), math.sin(self.angle)) * SHIP_LEN * z
        left_wing = Vector2(
            math.cos(self.angle + 2.4), math.sin(self.angle + 2.4)
        ) * (SHIP_LEN * 0.7 * z)
        right_wing = Vector2(
            math.cos(self.angle - 2.4), math.sin(self.angle - 2.4)
        ) * (SHIP_LEN * 0.7 * z)

        body = [
            (cx + nose.x, cy + nose.y),
            (cx + left_wing.x, cy + left_wing.y),
            (cx + right_wing.x, cy + right_wing.y),
        ]
        pygame.draw.polygon(surf, SHIP_COLOR, body)
        pygame.draw.polygon(surf, SHIP_OUTLINE, body, max(1, int(z)))

        if self.landed:
            pygame.draw.circle(surf, LANDED_RING_COLOR,
                               (int(cx), int(cy)),
                               max(1, int(SHIP_LEN * 1.6 * z)), 1)
        elif self.path_hold:
            # Path-hold has priority over brake-assist (mutually exclusive
            # state-wise, but if both somehow set, ring shows path-hold).
            pygame.draw.circle(surf, PATH_HOLD_RING_COLOR,
                               (int(cx), int(cy)),
                               max(1, int(SHIP_LEN * 1.6 * z)), 1)
        elif self.brake_assist:
            pygame.draw.circle(surf, BRAKE_RING_COLOR,
                               (int(cx), int(cy)),
                               max(1, int(SHIP_LEN * 1.6 * z)), 1)

        if self.thrusting:
            back = Vector2(-math.cos(self.angle), -math.sin(self.angle))
            base = Vector2(cx, cy) + back * (SHIP_LEN * 0.4 * z)
            length_scale = min(3.0, 0.5 + math.sqrt(self.thrust_scale))
            flicker = SHIP_LEN * z * length_scale * (0.8 + random.random() * 0.6)
            tip = base + back * flicker
            side = Vector2(-back.y, back.x) * (SHIP_LEN * 0.35 * z * min(2.0, length_scale))
            pygame.draw.polygon(surf, FLAME_COLOR, [tip, base + side, base - side])

        if self.retro_thrusting:
            fwd = Vector2(math.cos(self.angle), math.sin(self.angle))
            base = Vector2(cx, cy) + fwd * (SHIP_LEN * 1.0 * z)
            flicker = SHIP_LEN * z * (0.3 + random.random() * 0.2)
            tip = base + fwd * flicker
            side = Vector2(-fwd.y, fwd.x) * (SHIP_LEN * 0.18 * z)
            pygame.draw.polygon(surf, RETRO_FLAME_COLOR, [tip, base + side, base - side])

        # Strafe puffs: exhaust comes from the OPPOSITE side of the ship
        # from the direction of force, since reaction thrust shoots mass
        # the way you don't want to go.
        fwd = Vector2(math.cos(self.angle), math.sin(self.angle))
        if self.strafing_left:
            pilot_right = Vector2(-math.sin(self.angle), math.cos(self.angle))
            base = Vector2(cx, cy) + pilot_right * (SHIP_LEN * 0.4 * z)
            flicker = SHIP_LEN * z * (0.2 + random.random() * 0.15)
            tip = base + pilot_right * flicker
            side = fwd * (SHIP_LEN * 0.12 * z)
            pygame.draw.polygon(surf, RETRO_FLAME_COLOR, [tip, base + side, base - side])
        if self.strafing_right:
            pilot_left = Vector2(math.sin(self.angle), -math.cos(self.angle))
            base = Vector2(cx, cy) + pilot_left * (SHIP_LEN * 0.4 * z)
            flicker = SHIP_LEN * z * (0.2 + random.random() * 0.15)
            tip = base + pilot_left * flicker
            side = fwd * (SHIP_LEN * 0.12 * z)
            pygame.draw.polygon(surf, RETRO_FLAME_COLOR, [tip, base + side, base - side])


# ============================================================================
# Starfield
# ============================================================================

class Starfield:
    """Parallax stars rendered in screen space, NOT scaled by zoom (so they
    always look like single pixels regardless of zoom level)."""

    def __init__(self, count: int = 220):
        self.stars = []
        self._regen(count)

    def _regen(self, count: int) -> None:
        self.stars = []
        for _ in range(count):
            self.stars.append([
                random.uniform(0, WIDTH),
                random.uniform(0, HEIGHT),
                random.uniform(0.15, 0.85),
                random.randint(120, 230),
            ])

    def draw(self, surf: pygame.Surface, camera: Camera) -> None:
        cx, cy = camera.pos.x, camera.pos.y
        for sx, sy, depth, bright in self.stars:
            x = (sx - cx * depth) % WIDTH
            y = (sy - cy * depth) % HEIGHT
            surf.set_at((int(x), int(y)), (bright, bright, bright))


# ============================================================================
# Drawing helpers
# ============================================================================

def draw_body(surf: pygame.Surface, camera: Camera, body: Body) -> None:
    sx, sy = camera.world_to_screen(body.pos)
    r_screen = camera.scale(body.radius)
    margin = r_screen + 200
    if sx + margin < 0 or sx - margin > WIDTH:
        return
    if sy + margin < 0 or sy - margin > HEIGHT:
        return

    if not body.landable:
        # Sun halo
        for hr_factor, alpha in ((1.5, 30), (1.2, 60)):
            hr = int(r_screen * hr_factor)
            if hr <= 0:
                continue
            halo = pygame.Surface((hr * 2, hr * 2), pygame.SRCALPHA)
            pygame.draw.circle(halo, SUN_GLOW_COLOR + (alpha,), (hr, hr), hr)
            surf.blit(halo, (int(sx) - hr, int(sy) - hr))
    pygame.draw.circle(surf, body.color, (int(sx), int(sy)), max(1, int(r_screen)))
    pygame.draw.circle(surf, body.rim, (int(sx), int(sy)), max(1, int(r_screen)),
                       max(1, int(camera.scale(2))))


def draw_orbit_path(surf: pygame.Surface, camera: Camera, body: Body, segments: int = 96) -> None:
    if body.parent is None or body.orbit_radius <= 0.0:
        return
    parent_pos = body.parent.pos
    pts = []
    for i in range(segments):
        a = (i / segments) * 2.0 * math.pi
        p = parent_pos + Vector2(math.cos(a), math.sin(a)) * body.orbit_radius
        pts.append(camera.world_to_screen_int(p))
    for i in range(0, segments, 2):
        a = pts[i]
        b = pts[(i + 1) % segments]
        pygame.draw.line(surf, (50, 60, 90), a, b, 1)


def draw_deposit(surf: pygame.Surface, camera: Camera, dep: Deposit) -> None:
    body = dep.body
    radial = Vector2(math.cos(dep.angle), math.sin(dep.angle))
    tangent = Vector2(-radial.y, radial.x)
    base = body.pos + radial * body.radius
    tip = body.pos + radial * (body.radius + DEPOSIT_VISUAL)
    half_base = DEPOSIT_VISUAL * 0.6

    p_left = base - tangent * half_base
    p_right = base + tangent * half_base

    pts = [
        camera.world_to_screen(p_left),
        camera.world_to_screen(tip),
        camera.world_to_screen(p_right),
    ]
    fill = DEPOSIT_DEPLETED_COLOR if dep.depleted else DEPOSIT_COLOR
    pygame.draw.polygon(surf, fill, pts)
    pygame.draw.polygon(surf, DEPOSIT_RIM, pts, 1)

    if dep.quantity < dep.max_quantity:
        bar_w = max(2, int(DEPOSIT_VISUAL * 2 * camera.zoom))
        bar_h = 2
        tip_sx, tip_sy = camera.world_to_screen(tip)
        bx = tip_sx - bar_w / 2
        by = tip_sy - 6
        pygame.draw.rect(surf, (60, 60, 80), (bx, by, bar_w, bar_h), 1)
        if dep.quantity > 0:
            frac = dep.quantity / dep.max_quantity
            pygame.draw.rect(
                surf, (200, 220, 100),
                (bx + 1, by + 1, max(0, int((bar_w - 2) * frac)), bar_h - 2),
            )


def draw_buildpad(surf: pygame.Surface, camera: Camera, pad: BuildPad) -> None:
    body = pad.body
    radial = Vector2(math.cos(pad.angle), math.sin(pad.angle))
    tangent = Vector2(-radial.y, radial.x)
    centre = body.pos + radial * (body.radius + 1.0)

    half_w = BUILDPAD_VISUAL
    half_h = BUILDPAD_VISUAL * 0.4

    corners = [
        centre + tangent * half_w + radial * half_h,
        centre - tangent * half_w + radial * half_h,
        centre - tangent * half_w - radial * half_h,
        centre + tangent * half_w - radial * half_h,
    ]
    pts = [camera.world_to_screen(c) for c in corners]
    pygame.draw.polygon(surf, BUILDPAD_COLOR, pts)
    rim = BUILDPAD_OCCUPIED_RIM if pad.occupied else BUILDPAD_RIM
    pygame.draw.polygon(surf, rim, pts, 1)


def draw_turret(surf: pygame.Surface, camera: Camera, t: Turret) -> None:
    if not t.alive:
        return
    sx, sy = camera.world_to_screen(t.pos)
    body_r = max(1, int(camera.scale(TURRET_BODY)))
    pygame.draw.circle(surf, TURRET_COLOR, (int(sx), int(sy)), body_r)
    pygame.draw.circle(surf, TURRET_RING_COLOR, (int(sx), int(sy)), body_r, 1)
    bd = Vector2(math.cos(t.angle), math.sin(t.angle))
    end = t.pos + bd * TURRET_BARREL_LEN
    ex, ey = camera.world_to_screen(end)
    pygame.draw.line(surf, TURRET_BARREL_COLOR,
                     (int(sx), int(sy)), (int(ex), int(ey)),
                     max(1, int(camera.scale(3))))


def draw_bullet(surf: pygame.Surface, camera: Camera, b: Bullet) -> None:
    sx, sy = camera.world_to_screen(b.pos)
    pygame.draw.circle(surf, BULLET_COLOR, (int(sx), int(sy)),
                       max(1, int(camera.scale(BULLET_RADIUS))))


def draw_enemy(surf: pygame.Surface, camera: Camera, e: Enemy) -> None:
    sx, sy = camera.world_to_screen(e.pos)
    r = max(1, int(camera.scale(ENEMY_RADIUS)))
    pygame.draw.circle(surf, ENEMY_COLOR, (int(sx), int(sy)), r)
    pygame.draw.circle(surf, ENEMY_RIM, (int(sx), int(sy)), r, 1)


def _ghost_thickness(t: float) -> int:
    # Fattening ribbon expresses chaos uncertainty: even with bit-faithful
    # integration, a 3-body trajectory's true position spreads exponentially
    # with horizon. Colour shifts blue -> red along the line (no brightness
    # fade -- the tip stays readable against the BG); this thickness ramp
    # (1 -> 3 px) layers the "cone of doubt" cue on top.
    return 1 + int(t * 2)


def _draw_prograde_arrow(surf: pygame.Surface, camera: Camera,
                         points: list[Vector2], idx: int,
                         color: tuple[int, int, int]) -> None:
    """Tiny arrow at points[idx] pointing in the local prograde (motion)
    direction. Tangent computed in screen space so arrow length is constant
    in pixels regardless of zoom. Anchored a few pixels off the apsis dot
    so the dot stays visible."""
    n = len(points)
    if not (0 < idx < n - 1):
        return
    ax, ay = camera.world_to_screen(points[idx - 1])
    bx, by = camera.world_to_screen(points[idx + 1])
    dxs, dys = bx - ax, by - ay
    mag = math.hypot(dxs, dys)
    if mag < 1e-6:
        return
    fx, fy = dxs / mag, dys / mag
    cx, cy = camera.world_to_screen(points[idx])
    shaft_start = (cx + fx * 6, cy + fy * 6)
    shaft_end = (cx + fx * 14, cy + fy * 14)
    pygame.draw.line(surf, color, shaft_start, shaft_end, 2)
    tipx, tipy = shaft_end
    perpx, perpy = -fy, fx
    head_back = 4
    head_side = 3
    pygame.draw.polygon(surf, color, [
        (tipx, tipy),
        (tipx - fx * head_back + perpx * head_side,
         tipy - fy * head_back + perpy * head_side),
        (tipx - fx * head_back - perpx * head_side,
         tipy - fy * head_back - perpy * head_side),
    ])


def draw_apsis_markers(surf: pygame.Surface, camera: Camera,
                       points: list[Vector2],
                       peri_idx: int | None, apo_idx: int | None) -> None:
    """Two small ringed dots (peach peri, blue apo) plus a prograde arrow at
    each, pointing in the direction of motion -- the burn axis for raising
    the *opposite* apsis. Same visual grammar as the impact end-marker (5 px
    outline + 2 px filled core) so the eye reads markers as 'predictor
    annotations' rather than world objects."""
    n = len(points)
    if peri_idx is not None and 0 <= peri_idx < n:
        sp = camera.world_to_screen_int(points[peri_idx])
        pygame.draw.circle(surf, APSIS_PERI_COLOR, sp, 5, 1)
        pygame.draw.circle(surf, APSIS_PERI_COLOR, sp, 2)
        _draw_prograde_arrow(surf, camera, points, peri_idx, APSIS_PERI_COLOR)
    if apo_idx is not None and 0 <= apo_idx < n:
        sp = camera.world_to_screen_int(points[apo_idx])
        pygame.draw.circle(surf, APSIS_APO_COLOR, sp, 5, 1)
        pygame.draw.circle(surf, APSIS_APO_COLOR, sp, 2)
        _draw_prograde_arrow(surf, camera, points, apo_idx, APSIS_APO_COLOR)


def draw_closest_approach_marker(surf: pygame.Surface, camera: Camera,
                                 points: list[Vector2],
                                 idx: int | None) -> None:
    """Magenta diamond at the predicted closest-approach point to a
    non-anchor body. Diamond shape distinguishes it from the round
    peri/apo dots."""
    if idx is None or not (0 <= idx < len(points)):
        return
    cx, cy = camera.world_to_screen_int(points[idx])
    s = 5
    diamond = [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)]
    pygame.draw.polygon(surf, CLOSEST_APPROACH_COLOR, diamond, 1)


def draw_soi_markers(surf: pygame.Surface, camera: Camera,
                     points: list[Vector2], indices: list[int]) -> None:
    """Small gold rings where the dominant gravity source flips. Drawn
    smaller than apsis markers so they don't compete visually."""
    for i in indices:
        if 0 <= i < len(points):
            sp = camera.world_to_screen_int(points[i])
            pygame.draw.circle(surf, SOI_CROSSING_COLOR, sp, 4, 1)


def draw_chain_burn_markers(surf: pygame.Surface, camera: Camera,
                            points: list[Vector2],
                            indices: list[int],
                            font: pygame.font.Font | None = None) -> None:
    """Small filled chevrons + index labels at each scheduled burn point.
    Lets the player see where on the chained trajectory each queued burn
    will fire. The first burn (index 0) gets a "1" label so the chain reads
    naturally; queued burns get 2..N, and the current preview burn is
    labelled at indices[-1]. Skipped silently if the indices list is empty
    or the points run out before the burn point (predictor cut short by
    impact)."""
    if not indices:
        return
    s = CHAIN_BURN_MARKER_RADIUS
    for k, i in enumerate(indices):
        if not (0 <= i < len(points)):
            continue
        cx, cy = camera.world_to_screen_int(points[i])
        # Filled chevron (downward-pointing triangle) so it reads as "burn
        # here" without competing visually with the apsis dots/diamonds.
        tri = [(cx, cy - s), (cx + s, cy + s), (cx - s, cy + s)]
        pygame.draw.polygon(surf, CHAIN_BURN_MARKER_COLOR, tri)
        if font is not None:
            label = font.render(str(k + 1), True, CHAIN_BURN_MARKER_COLOR)
            surf.blit(label, (cx + s + 2, cy - s - 2))


def _draw_trajectory_ticks(surf: pygame.Surface, camera: Camera,
                           points: list[Vector2], dt: float,
                           start_color: tuple[int, int, int],
                           end_color: tuple[int, int, int]) -> None:
    """Perpendicular tick marks at every PREDICT_TICK_INTERVAL seconds along
    the trajectory. Tick length is screen-space (zoom-invariant). Color
    lerps from start_color at the ship end to end_color at the horizon
    end, matching the line itself -- both stay at full brightness so the
    end of the trajectory remains readable."""
    n = len(points)
    if n < 3 or dt <= 0.0:
        return
    samples_per_tick = PREDICT_TICK_INTERVAL / dt
    if samples_per_tick < 1.0:
        return
    sr, sg, sb = start_color
    er, eg, eb = end_color
    k = 1
    while True:
        i = int(round(samples_per_tick * k))
        if i >= n - 1:
            break
        # Screen-space tangent, so tick length is constant in pixels.
        ax, ay = camera.world_to_screen(points[max(0, i - 1)])
        bx, by = camera.world_to_screen(points[min(n - 1, i + 1)])
        dxs, dys = bx - ax, by - ay
        mag = math.hypot(dxs, dys)
        if mag < 1e-6:
            k += 1
            continue
        # 90° rotation gives the perpendicular.
        px, py = -dys / mag, dxs / mag
        cx, cy = camera.world_to_screen(points[i])
        t = i / (n - 1)
        r = int(sr * (1 - t) + er * t)
        g = int(sg * (1 - t) + eg * t)
        b_ch = int(sb * (1 - t) + eb * t)
        thickness = _ghost_thickness(t)
        x0 = int(cx + px * PREDICT_TICK_HALFLEN)
        y0 = int(cy + py * PREDICT_TICK_HALFLEN)
        x1 = int(cx - px * PREDICT_TICK_HALFLEN)
        y1 = int(cy - py * PREDICT_TICK_HALFLEN)
        pygame.draw.line(surf, (r, g, b_ch), (x0, y0), (x1, y1), thickness)
        k += 1


def draw_trajectory(surf: pygame.Surface, camera: Camera, points: list[Vector2],
                    impact_speed: float | None, dt: float) -> None:
    if len(points) < 2:
        return
    n = len(points)
    sr, sg, sb = PREDICT_COLOR
    er, eg, eb = PREDICT_COLOR_END
    stride = PREDICT_DRAW_STRIDE
    last_screen = None
    last_t = 0.0
    for i in range(0, n, stride):
        sp = camera.world_to_screen_int(points[i])
        if last_screen is not None:
            t = i / (n - 1)
            r = int(sr * (1 - t) + er * t)
            g = int(sg * (1 - t) + eg * t)
            b = int(sb * (1 - t) + eb * t)
            pygame.draw.line(surf, (r, g, b), last_screen, sp,
                             _ghost_thickness(0.5 * (last_t + t)))
            last_t = t
        last_screen = sp

    _draw_trajectory_ticks(surf, camera, points, dt,
                           PREDICT_COLOR, PREDICT_COLOR_END)

    if impact_speed is not None:
        ip = camera.world_to_screen_int(points[-1])
        color = LANDED_RING_COLOR if impact_speed <= LAND_SPEED_MAX else PREDICT_IMPACT_COLOR
        pygame.draw.circle(surf, color, ip, 5, 1)
        pygame.draw.circle(surf, color, ip, 2)


def draw_plan_trajectory(surf: pygame.Surface, camera: Camera,
                         points: list[Vector2],
                         impact_speed: float | None,
                         dt: float) -> None:
    """Plan-mode counterpart to draw_trajectory: orange ribbon at the ship
    end, lerping to bright red at the horizon end. Same stride and
    thickness ramp; full brightness throughout so the chained-burn ghost
    stays readable past the predict_seconds horizon.

    Drawn separately rather than parameterised onto draw_trajectory because
    the impact end-marker uses a different palette (plan-mode impact is
    purely informational, not a forecast)."""
    if len(points) < 2:
        return
    n = len(points)
    sr, sg, sb = PLAN_COLOR
    er, eg, eb = PLAN_COLOR_END
    stride = PREDICT_DRAW_STRIDE
    last_screen = None
    last_t = 0.0
    for i in range(0, n, stride):
        sp = camera.world_to_screen_int(points[i])
        if last_screen is not None:
            t = i / (n - 1)
            r = int(sr * (1 - t) + er * t)
            g = int(sg * (1 - t) + eg * t)
            b = int(sb * (1 - t) + eb * t)
            pygame.draw.line(surf, (r, g, b), last_screen, sp,
                             _ghost_thickness(0.5 * (last_t + t)))
            last_t = t
        last_screen = sp

    _draw_trajectory_ticks(surf, camera, points, dt,
                           PLAN_COLOR, PLAN_COLOR_END)

    if impact_speed is not None:
        ip = camera.world_to_screen_int(points[-1])
        color = LANDED_RING_COLOR if impact_speed <= LAND_SPEED_MAX else PLAN_IMPACT_COLOR
        pygame.draw.circle(surf, color, ip, 5, 1)
        pygame.draw.circle(surf, color, ip, 2)


def draw_mining_beam(surf: pygame.Surface, camera: Camera, ship_pos: Vector2, target: Deposit) -> None:
    sp = camera.world_to_screen_int(ship_pos)
    dp = camera.world_to_screen_int(target.pos)
    pygame.draw.line(surf, MINING_BEAM_COLOR, sp, dp, max(1, int(camera.scale(2))))


# --- HUD always renders at native screen size; not affected by zoom ---------

def draw_fuel_bar(surf: pygame.Surface, x: int, y: int, w: int, h: int,
                  fuel: float, max_fuel: float) -> None:
    frac = max(0.0, min(1.0, fuel / max_fuel)) if max_fuel > 0 else 0.0
    if frac > LOW_FUEL_FRAC:
        fill_color = (90, 220, 140)
    elif frac > CRITICAL_FUEL_FRAC:
        fill_color = (220, 200, 90)
    else:
        fill_color = (220, 90, 90)
    pygame.draw.rect(surf, (60, 60, 80), (x, y, w, h), 1)
    fill_w = int((w - 2) * frac)
    if fill_w > 0:
        pygame.draw.rect(surf, fill_color, (x + 1, y + 1, fill_w, h - 2))


def _fmt_apsis(alt: float | None) -> str:
    return f"{alt:7.1f}" if alt is not None else "    ---"


def draw_hud(surf: pygame.Surface, font: pygame.font.Font, ship: Ship,
             bodies: list[Body], sun: Body,
             enemies: list[Enemy], turrets: list[Turret], build_prompt: bool,
             zoom: float, predict_seconds: float,
             kills: int, enemies_enabled: bool,
             paused: bool = False, plan_burn_duration: float = 0.0,
             plan_burn_dv: float = 0.0,
             predict_target_steps: int = PREDICT_TARGET_STEPS,
             live_peri_alt: float | None = None,
             live_apo_alt: float | None = None,
             plan_peri_alt: float | None = None,
             plan_apo_alt: float | None = None,
             ca_target_name: str | None = None,
             live_ca_alt: float | None = None,
             plan_ca_alt: float | None = None,
             chain_queue_size: int = 0,
             chain_burn_count: int = 1,
             pending_count: int = 0,
             plan_burn_offset: float = 0.0,
             time_scale: float = 1.0) -> None:
    if ship.alive:
        # Anchor altitude / rel-speed / v_circ to whichever landable body is
        # currently closest. As the player approaches Ember, the HUD silently
        # retargets to it -- no manual switch needed.
        nearest = nearest_landable(ship.pos, bodies)
        if nearest is not None:
            r_body = (ship.pos - nearest.pos).length()
            altitude = max(0.0, r_body - nearest.radius)
            rel_vel = ship.vel - nearest.vel
            speed_rel = rel_vel.length()
            v_circ = circular_orbit_speed(nearest, r_body) if r_body > 0 else 0.0
            body_label = nearest.name
        else:
            altitude = 0.0
            speed_rel = ship.vel.length()
            v_circ = 0.0
            body_label = "(deep space)"
        d_sun = (ship.pos - sun.pos).length()

        if ship.thrusting and ship.thrust_scale != 1.0:
            thrust_label = f"Thrust:      x{ship.thrust_scale:g}"
        elif ship.thrusting:
            thrust_label = "Thrust:      nominal"
        else:
            thrust_label = ""

        live_enemies = sum(1 for e in enemies if e.alive)
        live_turrets = sum(1 for t in turrets if t.alive)

        lines = [
            f"Altitude:    {altitude:7.1f}    (vs {body_label})",
            f"Rel speed:   {speed_rel:7.1f}    (vs {body_label})",
            f"v_circ here: {v_circ:7.1f}",
            f"Sun dist:    {d_sun:7.0f}",
            f"Fuel:        {ship.fuel:6.2f} / {MAX_FUEL:.0f}",
            f"Ore:         {ship.ore:6.1f}",
            f"Turrets:     {live_turrets}    Enemies: {live_enemies}{'' if enemies_enabled else ' (off)'}",
            f"Kills:       {kills}",
            f"Zoom:        x{zoom:.2f}    Predict: {predict_seconds:.0f}s "
            f"({predict_target_steps} steps)"
            + (f"    Time: x{time_scale:g}" if time_scale != 1.0 else ""),
            f"Peri / Apo:  {_fmt_apsis(live_peri_alt)} / {_fmt_apsis(live_apo_alt)}"
            f"    (vs {body_label})",
        ]
        if ca_target_name is not None and live_ca_alt is not None:
            lines.append(f"Closest pass:{_fmt_apsis(live_ca_alt)}    "
                         f"(vs {ca_target_name})")
        if thrust_label:
            lines.append(thrust_label)
        if ship.retro_thrusting:
            lines.append(f"Retro:       on ({ship.retro_scale * 100.0:g}%)")
        if ship.brake_assist:
            target = nearest_landable(ship.pos, bodies)
            mode = f"matching {target.name}" if target is not None else "zeroing velocity"
            extras = []
            if ship.hover_hold:
                extras.append("HOVER (Shift)")
            if ship.brake_assist_scale < 1.0:
                extras.append(f"damp x{ship.brake_assist_scale:g} (Ctrl)")
            extra_str = "  " + "  ".join(extras) if extras else ""
            lines.append(f"BRAKE ASSIST: on  ({mode}){extra_str}  (cancels on W/S)")
        if ship.path_hold:
            n_samp = len(ship.planned_trajectory)
            lines.append(
                f"PATH-HOLD: on  err {ship.path_hold_error:6.1f} px"
                f"  ({n_samp} samples)  (cancels on W/S)"
            )
        if ship.landed:
            if ship.mining_target is not None:
                lines.append(f"LANDED  -  refueling + MINING ({MINING_RATE:.0f}/s)")
            else:
                lines.append("LANDED  -  refueling")
        if ship.fuel <= 0.0 and not ship.landed:
            lines.append("OUT OF FUEL")
        if build_prompt:
            lines.append(">> hold B to open build menu <<")
        if paused:
            lines.append("")
            cur_idx = chain_queue_size + 1
            lines.append(
                f"PLAN MODE  (paused)   burn {cur_idx}/{chain_burn_count}: "
                f"{plan_burn_duration:+.3f}s = dv {plan_burn_dv:+.1f}   "
                f"fires at +{plan_burn_offset:.3f}s"
            )
            lines.append(f"  planned peri/apo: {_fmt_apsis(plan_peri_alt)} / "
                         f"{_fmt_apsis(plan_apo_alt)}")
            if ca_target_name is not None and plan_ca_alt is not None:
                lines.append(f"  planned closest pass:{_fmt_apsis(plan_ca_alt)}"
                             f"    (vs {ca_target_name})")
            lines.append("  mouse aims burn   [ / ] duration   , / . fire-time"
                         "  (Ctrl=0.01, Ctrl+Shift=0.001, Alt=0.0001)")
            if chain_queue_size > 0:
                lines.append(
                    f"  N queue next ({chain_queue_size} queued)   "
                    f"Backspace pop last   Enter fire chain   Space cancel"
                )
            else:
                lines.append("  N queue this burn (chain mode)   "
                             "Enter commit burn   Space resume without burning")
        elif pending_count > 0:
            lines.append("")
            lines.append(f"CHAIN ARMED   {pending_count} burn(s) pending")
        lines += [
            "",
            "Mouse aim  W/S/Shift/Ctrl thrust  H brake  J path-hold  B build",
            "+/- zoom  0 reset zoom  / shorter * longer predict  F5/F6 steps  F7/F8 time x0.5/x2",
            "Space pause+plan   [ ] burn duration   N queue chain   Backspace pop",
            "F11 fullscreen  R reset world  Esc quit",
        ]
        color = (220, 220, 220)
    else:
        lines = ["CRASHED", "press R to reset"]
        color = (255, 120, 120)

    for i, line in enumerate(lines):
        surf.blit(font.render(line, True, color), (16, 16 + i * 22))

    if ship.alive:
        bar_y = 16 + len(lines) * 22 + 4
        draw_fuel_bar(surf, 16, bar_y, 220, 10, ship.fuel, MAX_FUEL)


def draw_build_menu(surf: pygame.Surface, font: pygame.font.Font, ship: Ship) -> tuple[tuple[int, int, int, int], bool]:
    panel_x = (WIDTH - BUILD_PANEL_W) // 2
    panel_y = (HEIGHT - BUILD_PANEL_H) // 2
    pygame.draw.rect(surf, BUILD_PANEL_BG,
                     (panel_x, panel_y, BUILD_PANEL_W, BUILD_PANEL_H))
    pygame.draw.rect(surf, BUILD_PANEL_BORDER,
                     (panel_x, panel_y, BUILD_PANEL_W, BUILD_PANEL_H), 2)

    title = font.render("BUILD MENU  (release B to close)", True, (230, 230, 230))
    surf.blit(title, (panel_x + 16, panel_y + 12))

    btn_x = panel_x + 16
    btn_y = panel_y + 50
    btn_w = BUILD_PANEL_W - 32
    btn_h = 40
    can_afford = ship.ore >= TURRET_COST
    btn_color = (60, 80, 110) if can_afford else (50, 50, 60)
    pygame.draw.rect(surf, btn_color, (btn_x, btn_y, btn_w, btn_h))
    pygame.draw.rect(surf, BUILD_PANEL_BORDER, (btn_x, btn_y, btn_w, btn_h), 1)

    label_color = (220, 220, 220) if can_afford else (140, 140, 140)
    label = font.render(f"Dumb Turret  -  {TURRET_COST:.0f} ore", True, label_color)
    surf.blit(label, (btn_x + 12, btn_y + 10))

    status_y = btn_y + btn_h + 14
    status_color = (200, 220, 100) if can_afford else (220, 100, 100)
    status_text = (f"Ore: {ship.ore:.0f}    Cost: {TURRET_COST:.0f}    "
                   + ("CLICK TO BUILD" if can_afford else "INSUFFICIENT ORE"))
    status = font.render(status_text, True, status_color)
    surf.blit(status, (panel_x + 16, status_y))

    return ((btn_x, btn_y, btn_w, btn_h), can_afford)


# ============================================================================
# Main loop
# ============================================================================

def nearest_unoccupied_pad(ship: Ship, pads: list[BuildPad]) -> BuildPad | None:
    if not ship.alive or not ship.landed:
        return None
    best = None
    best_d2 = BUILDPAD_RANGE * BUILDPAD_RANGE
    for p in pads:
        if p.occupied:
            continue
        d2 = (p.pos - ship.pos).length_squared()
        if d2 <= best_d2:
            best = p
            best_d2 = d2
    return best


def build_world() -> tuple[list[Body], Body, Body, list[Deposit], list[BuildPad], list[Turret], list[Bullet], list[Enemy]]:
    bodies = make_solar_system()
    sun = bodies[0]
    planet = bodies[1]
    moon = bodies[2]
    ember = bodies[3]
    frostbite = bodies[4]
    update_bodies(bodies, 0.0)
    # Ore distribution: 2 starter deposits on Planet, the bulk on Frostbite.
    # The asymmetry forces a real expedition for sustained mining; Planet's
    # 2 deposits are enough to bootstrap a turret or two locally.
    deposits = (generate_deposits(planet, n=2)
                + generate_deposits(frostbite, n=6))
    # Pads: defensive infrastructure spread across the inner system.
    # Frostbite is intentionally pad-less -- it's the destination, not a base.
    pads = (generate_buildpads(planet)            # 5 -- main fortress
            + generate_buildpads(ember, n=3)      # 3 -- forward base
            + generate_buildpads(moon, n=2))      # 2 -- precision-landing
    return bodies, planet, sun, deposits, pads, [], [], []


# ============================================================================
# Video recorder
# ============================================================================

class Recorder:
    """Pipe pygame frames to ffmpeg for real-time video encoding, with
    wall-clock-faithful pacing.

    A worker thread drains a bounded queue of (rgb_bytes, repeat_count)
    chunks and writes them to ffmpeg's stdin. The main thread calls
    feed(surface) after each pygame.display.flip(); the surface->bytes
    conversion happens on the main thread (one memcpy per fed frame), the
    chunk gets pushed onto the queue, and the encode runs in ffmpeg's
    process. If the queue is full (encoder is behind), the chunk is
    dropped rather than blocking the main loop -- recording never
    introduces sim hitching.

    Wall-clock pacing: ffmpeg sees a fixed 30fps stream, but the recorder
    decides at each feed() call how many of those 30fps slots have elapsed
    in real time since the last call, and pushes either zero (game running
    fast, skip), one (game running on-pace), or many copies (game stuttered)
    of the previous on-screen frame plus one of the new frame. Net effect:
    a 0.5s game stutter shows as a 0.5s freeze in the recording instead of
    being compressed to 17ms of footage. Output rate is fixed 30fps but
    the frame *content* is variable, so a stuttering game produces a
    legibly slowed-down video rather than a sped-up one.

    Output codec is H.264/yuv420p, universally playable on Windows /
    browsers / social platforms.

    Requires ffmpeg on PATH (winget install ffmpeg / brew install ffmpeg).
    On spawn failure the recorder silently no-ops after printing a hint
    once, so a missing ffmpeg never crashes the game.
    """

    QUEUE_SIZE = 8       # bounded buffer between main thread and writer
    OUTPUT_FPS = 30      # what gets written to disk

    def __init__(self) -> None:
        self.recording = False
        self.proc: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.queue: queue.Queue | None = None
        self.filename: str | None = None
        self.frames_written = 0   # output frames the writer has pushed to ffmpeg
        self.frames_dropped = 0   # output slots lost to queue.Full
        self._size: tuple[int, int] | None = None
        self._start_wall: float | None = None  # set lazily on first feed
        self._frames_pushed = 0   # output slots accounted for (may be in-queue)
        self._last_data: bytes | None = None  # most recently fed surface bytes

    def start(self, screen_size: tuple[int, int], out_dir: str) -> None:
        if self.recording:
            return
        w, h = screen_size
        stamp = datetime.datetime.now().strftime("%Y-%m-%d - %H-%M-%S")
        path = os.path.join(out_dir, f"{stamp}.mp4")
        # Raw RGB frames in, H.264 yuv420p out. preset=veryfast keeps the
        # encoder ahead of the game loop; crf=23 is the libx264 default and
        # produces a sane size/quality tradeoff for posting online.
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{w}x{h}", "-r", str(self.OUTPUT_FPS),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            path,
        ]
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            print(
                "Recording: ffmpeg not found on PATH. Install ffmpeg "
                "(winget install ffmpeg / brew install ffmpeg) and retry.",
                file=sys.stderr,
            )
            self.proc = None
            return
        self.queue = queue.Queue(maxsize=self.QUEUE_SIZE)
        self.thread = threading.Thread(target=self._writer, daemon=True)
        self.thread.start()
        self.recording = True
        self.filename = path
        self.frames_written = 0
        self.frames_dropped = 0
        self._size = (w, h)
        self._start_wall = None
        self._frames_pushed = 0
        self._last_data = None

    def feed(self, surface: pygame.Surface) -> None:
        if not self.recording or self.queue is None:
            return
        if surface.get_size() != self._size:
            return  # window resized mid-recording; bail rather than scribble
        now = time.monotonic()
        if self._start_wall is None:
            self._start_wall = now
        # How many output slots SHOULD have been written by now, given the
        # target framerate and how long we've been recording? Subtract the
        # ones we've already accounted for to get how many we owe.
        target_total = int((now - self._start_wall) * self.OUTPUT_FPS) + 1
        owed = max(0, target_total - self._frames_pushed)
        if owed == 0:
            return  # game is running faster than OUTPUT_FPS; skip this frame
        # Convert the new frame to bytes (the costly bit on the main thread).
        try:
            new_data = pygame.image.tostring(surface, "RGB")
        except pygame.error:
            return
        # When owed > 1 the game stuttered: the previous on-screen frame was
        # visible for the dwell. Push it for (owed - 1) slots, then push the
        # new frame for the final slot. Net: wall-clock pacing matches reality
        # and the freeze sits on the right frame, not the post-hitch one.
        if owed > 1 and self._last_data is not None:
            prev_count = owed - 1
            try:
                self.queue.put_nowait((self._last_data, prev_count))
            except queue.Full:
                self.frames_dropped += prev_count
            # Advance the pacing counter regardless of whether we enqueued or
            # dropped -- otherwise a single queue-full event would make every
            # subsequent feed think it owes more frames, snowballing.
            self._frames_pushed += prev_count
            owed = 1
        try:
            self.queue.put_nowait((new_data, owed))
        except queue.Full:
            self.frames_dropped += owed
        self._frames_pushed += owed
        self._last_data = new_data

    def stop(self) -> None:
        if not self.recording:
            return
        # Sentinel tells the writer to flush and close ffmpeg's stdin.
        if self.queue is not None:
            try:
                self.queue.put(None, timeout=2.0)
            except queue.Full:
                pass
        if self.thread is not None:
            self.thread.join(timeout=10.0)
        self.recording = False

    def _writer(self) -> None:
        proc = self.proc
        q = self.queue
        try:
            while True:
                item = q.get()
                if item is None:
                    break
                # Each chunk is (data, repeat_count). A long stutter shows up
                # as a single chunk with repeat_count=N rather than N queue
                # entries -- that's how a 5-second pause survives a queue of
                # only QUEUE_SIZE slots without dropping anything.
                data, count = item
                try:
                    for _ in range(count):
                        proc.stdin.write(data)
                except (BrokenPipeError, OSError):
                    break
                self.frames_written += count
        finally:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            # Flip the flag so feed() short-circuits if ffmpeg died on us.
            self.recording = False


# ============================================================================
# Main loop
# ============================================================================

def main() -> None:
    global WIDTH, HEIGHT
    pygame.init()

    # Detect desktop resolution and use it as the window size.
    info = pygame.display.Info()
    WIDTH, HEIGHT = info.current_w, info.current_h
    pygame.display.set_caption("YPilot - Tier 2: solar system")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    # In case the OS gave us a slightly different surface (HiDPI scaling etc.)
    WIDTH, HEIGHT = screen.get_size()

    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,menlo,monospace", 18)

    sim_time = 0.0
    bodies, planet, sun, deposits, pads, turrets, bullets, enemies = build_world()
    ship = Ship(planet)
    stars = Starfield()
    enemy_spawn_timer = ENEMY_SPAWN_INTERVAL * 0.5
    enemies_enabled = True
    kills = 0
    recorder = Recorder()

    camera = Camera()
    camera.zoom = 1.0

    fullscreen = False
    hud_visible = True
    predict_seconds = PREDICT_SECONDS
    predict_target_steps = PREDICT_TARGET_STEPS
    time_scale = TIME_SCALE_DEFAULT

    paused = False
    plan_burn_duration = PLAN_BURN_DURATION_DEFAULT
    # Fire-time of the *current preview* burn, as seconds from chain start
    # (burn 0 fires at offset 0). User-controlled via , / . once the slot
    # is active; auto-filled to (queue[-1].t_offset + predict_seconds), or
    # 0.0 when queue is empty, every time the slot resets (entry to plan
    # mode, after N, after Backspace). Floor enforced at queue[-1].t_offset
    # so chain ordering stays monotonic; ceiling at PREDICT_MAX_SECONDS.
    plan_burn_offset = 0.0
    # Maneuver chain (built up while paused via N, fired on Enter): each
    # entry is (angle, duration_signed, t_offset_from_chain_start). The
    # current preview is treated as one more entry tacked onto the end at
    # render time -- so the orange trajectory always shows the full plan.
    maneuver_queue: list[tuple[float, float, float]] = []

    def _reset_preview_offset() -> float:
        """Auto-fill the current preview burn's fire-time when the slot
        resets. Currently triggered only on plan-mode entry, where
        maneuver_queue is always empty (cleared on every prior exit
        path), so this returns 0.0 in practice. The maneuver_queue
        branch is kept defensively for any future caller that might
        reset the slot mid-planning.

        Important: even when a chain is committed and pending on the
        ship, we deliberately start the new preview at offset 0 (back
        at the ship), NOT auto-anchored past the last pending burn.
        An earlier version of this function did the auto-anchor and
        it caused the camera-follow path (which kicks in whenever
        plan_burn_offset > 0) to predict over a horizon stretching
        to the last pending burn's apply-time on the very first frame
        after Space, tanking the framerate when a long chain was
        pending. Players who want to extend the chain can dial
        forward with Shift+, / Shift+. (1-second leap) or any of the
        finer modifiers; commit will still merge with the existing
        pending burns by apply-time.
        """
        if maneuver_queue:
            return maneuver_queue[-1][2] + predict_seconds
        return 0.0

    # Wall-time accumulator for the fixed-timestep physics loop. Frames feed
    # measured wall time in; physics drains it in PHYSICS_DT chunks. Capped at
    # MAX_FRAME_DT so a stall doesn't cause a burst of catch-up steps.
    physics_accumulator = 0.0

    # Cyan-predict cache: amortizes the predict + apsides + SOI + closest-
    # approach analysis across PREDICT_CACHE_INTERVAL frames. Refresh is
    # forced whenever the cached state diverges from current (paused
    # toggle, pending-burn count change, predict horizon change, anchor
    # body change). Initial age == INTERVAL forces a refresh on frame 1.
    predict_cache: dict = {
        "age": PREDICT_CACHE_INTERVAL,
        "paused": None,
        "pending_count": -1,
        "predict_seconds": -1.0,
        "predict_target_steps": -1,
        "apsis_anchor_id": None,
        "ca_target_id": None,
        "traj": [],
        "impact_speed": None,
        "traj_dt": 0.0,
        "burn_indices": [],
        "soi_indices": [],
        "peri_idx": None, "apo_idx": None, "ca_idx": None,
        "peri_alt": None, "apo_alt": None, "ca_alt": None,
    }

    running = True
    while running:
        frame_dt = clock.tick(FPS) / 1000.0

        mouse_pos = pygame.mouse.get_pos()
        mouse_clicked = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
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
                elif event.key == pygame.K_SPACE:
                    # Leaving plan mode without committing -> drop any
                    # queued chain. Re-entering pause starts fresh.
                    if paused:
                        maneuver_queue.clear()
                        plan_burn_duration = PLAN_BURN_DURATION_DEFAULT
                    paused = not paused
                    if paused:
                        plan_burn_offset = _reset_preview_offset()
                elif event.key == pygame.K_n and paused:
                    # Push the current preview onto the chain at whatever
                    # fire-time the user dialled in (plan_burn_offset).
                    # The next preview defaults to firing AT THE SAME
                    # offset as the just-queued burn (camera stays put,
                    # user can dial forward with > if they want a gap).
                    # Floor-on-, makes monotonicity automatic: once
                    # queued, you can only move the new preview's
                    # fire-time forward, not before the burn you just
                    # locked in.
                    dx = mouse_pos[0] - WIDTH / 2
                    dy = mouse_pos[1] - HEIGHT / 2
                    if dx * dx + dy * dy >= MOUSE_AIM_DEADZONE_SQ:
                        burn_angle_q = math.atan2(dy, dx)
                    else:
                        burn_angle_q = ship.angle
                    maneuver_queue.append(
                        (burn_angle_q, plan_burn_duration, plan_burn_offset)
                    )
                    plan_burn_duration = PLAN_BURN_DURATION_DEFAULT
                    # plan_burn_offset intentionally NOT changed -- camera
                    # stays glued to the burn point you just locked in.
                elif event.key == pygame.K_BACKSPACE and paused:
                    if maneuver_queue:
                        # Pop the most-recently-added burn back into the
                        # editable preview slot, restoring its duration AND
                        # its fire-time so the user can retune without
                        # losing what they had. Angle stays whatever the
                        # mouse points to.
                        _, popped_dur, popped_off = maneuver_queue.pop()
                        plan_burn_duration = popped_dur
                        plan_burn_offset = popped_off
                elif event.key in (pygame.K_LEFTBRACKET,
                                   pygame.K_RIGHTBRACKET) and paused:
                    # Step ladder: Shift = leap (1.0 s), plain = coarse,
                    # Ctrl = precision, Ctrl+Shift = extra-fine, Alt =
                    # super-fine. Shift "boost" matches Shift+W thrust-
                    # boost semantics: Shift makes the step bigger.
                    # Ctrl-family makes it smaller. Lets you sweep across
                    # a long predicted trajectory in seconds AND dial in
                    # a Hohmann burn to tenths of a millisecond.
                    if event.mod & pygame.KMOD_ALT:
                        step = PLAN_BURN_DURATION_SUPERFINE_STEP
                    elif (event.mod & pygame.KMOD_CTRL
                            and event.mod & pygame.KMOD_SHIFT):
                        step = PLAN_BURN_DURATION_FINE_STEP
                    elif event.mod & pygame.KMOD_CTRL:
                        step = PLAN_BURN_DURATION_PRECISION_STEP
                    elif event.mod & pygame.KMOD_SHIFT:
                        step = PLAN_BURN_DURATION_LEAP_STEP
                    else:
                        step = PLAN_BURN_DURATION_STEP
                    if event.key == pygame.K_LEFTBRACKET:
                        plan_burn_duration = max(
                            PLAN_BURN_DURATION_MIN,
                            plan_burn_duration - step,
                        )
                    else:
                        plan_burn_duration = min(
                            PLAN_BURN_DURATION_MAX,
                            plan_burn_duration + step,
                        )
                elif event.key in (pygame.K_COMMA, pygame.K_PERIOD) and paused:
                    # , / .  (a.k.a. < / >) shift the current preview burn's
                    # fire-time along the trajectory. Same ladder as [ / ]:
                    # Shift = leap (1.0 s) for sweeping across long
                    # trajectories, plain / Ctrl / Ctrl+Shift / Alt for
                    # coarse-to-super-fine homing in. Floor: previous
                    # queued burn's offset (chain stays monotonic).
                    # Ceiling: PREDICT_MAX_SECONDS.
                    if event.mod & pygame.KMOD_ALT:
                        step = PLAN_BURN_OFFSET_SUPERFINE_STEP
                    elif (event.mod & pygame.KMOD_CTRL
                            and event.mod & pygame.KMOD_SHIFT):
                        step = PLAN_BURN_OFFSET_FINE_STEP
                    elif event.mod & pygame.KMOD_CTRL:
                        step = PLAN_BURN_OFFSET_PRECISION_STEP
                    elif event.mod & pygame.KMOD_SHIFT:
                        step = PLAN_BURN_OFFSET_LEAP_STEP
                    else:
                        step = PLAN_BURN_OFFSET_STEP
                    floor = maneuver_queue[-1][2] if maneuver_queue else 0.0
                    if event.key == pygame.K_COMMA:
                        plan_burn_offset = max(
                            floor, plan_burn_offset - step
                        )
                    else:
                        plan_burn_offset = min(
                            PREDICT_MAX_SECONDS, plan_burn_offset + step
                        )
                elif (event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
                      and paused):
                    # Commit the full chain: queued burns + the current
                    # preview as the final entry. burn 0 fires immediately
                    # (apply_pending_maneuvers fires anything with t_apply
                    # <= sim_time); burn k fires at sim_time + t_offset[k].
                    # Empty queue + nonzero current preview behaves
                    # identically to the old single-burn commit path.
                    dx = mouse_pos[0] - WIDTH / 2
                    dy = mouse_pos[1] - HEIGHT / 2
                    if dx * dx + dy * dy >= MOUSE_AIM_DEADZONE_SQ:
                        burn_angle = math.atan2(dy, dx)
                    else:
                        burn_angle = ship.angle
                    chain = list(maneuver_queue) + [
                        (burn_angle, plan_burn_duration, plan_burn_offset)
                    ]
                    # Drop zero-duration entries -- they'd burn no fuel and
                    # cost nothing. A user who Backspaces back to zero is
                    # most likely cancelling a burn; honour that.
                    pending = []
                    for ang, dur, off in chain:
                        if dur == 0.0:
                            continue
                        bd = Vector2(math.cos(ang), math.sin(ang))
                        pending.append((sim_time + off, bd, dur))
                    if pending:
                        # Merge with any already-committed chain so that
                        # re-entering plan mode and adding a burn extends
                        # the schedule instead of replacing it. Sort by
                        # apply-time so the predictor's sequential walk
                        # over pending_burns sees a monotonic time series
                        # even when the player backdated the new preview's
                        # fire-time below the existing pending burns. The
                        # `,` floor stays at 0 on purpose -- per design,
                        # the player can sneak a corrective burn in
                        # *before* an already-scheduled burn (e.g. for
                        # a near-miss they spotted after committing).
                        merged = sorted(
                            list(ship.pending_maneuvers) + pending,
                            key=lambda mv: mv[0],
                        )
                        # Snapshot the planned trajectory BEFORE applying the
                        # kicks live, so the predictor sees the same starting
                        # state path-hold will track from. If we're landed,
                        # mirror the launch-pad bump that commit_planned_burn
                        # is about to apply -- otherwise the recorded plan
                        # would start one launch-pad-bump-height below the
                        # actual post-commit state.
                        if ship.landed and ship.landed_body is not None:
                            lbody = ship.landed_body
                            lradial = Vector2(
                                math.cos(ship.landed_radial),
                                math.sin(ship.landed_radial),
                            )
                            snap_pos = lbody.pos + lradial * (
                                lbody.radius + LAUNCH_PAD_HEIGHT
                            )
                            snap_vel = Vector2(lbody.vel)
                        else:
                            snap_pos = Vector2(ship.pos)
                            snap_vel = Vector2(ship.vel)
                        # Span runs to the *latest* burn in the merged list,
                        # which may be either an already-pending burn or one
                        # of the newly added ones depending on insertion order.
                        chain_span = merged[-1][0] - sim_time
                        snap_seconds = chain_span + PATH_HOLD_POSTBURN_SECONDS
                        snap_steps = min(
                            PREDICT_TARGET_STEPS_MAX,
                            int(predict_target_steps
                                * (snap_seconds / max(predict_seconds, 1e-3))),
                        )
                        snap_steps = max(snap_steps, predict_target_steps)
                        snap_vels: list[Vector2] = []
                        snap_pts, _, snap_dt = ship.predict_trajectory(
                            bodies, sim_time, seconds=snap_seconds,
                            pos0=snap_pos, vel0=snap_vel,
                            target_steps=snap_steps,
                            pending_burns=merged,
                            out_velocities=snap_vels,
                        )
                        samples = [
                            (sim_time + i * snap_dt,
                             snap_pts[i], snap_vels[i])
                            for i in range(min(len(snap_pts),
                                               len(snap_vels)))
                        ]
                        ship.set_planned_trajectory(samples)
                        ship.pending_maneuvers = merged
                        ship.apply_pending_maneuvers(sim_time)
                    maneuver_queue.clear()
                    plan_burn_duration = PLAN_BURN_DURATION_DEFAULT
                    plan_burn_offset = 0.0
                    paused = False
                elif event.key == pygame.K_F1:
                    hud_visible = not hud_visible
                elif event.key == pygame.K_F4:
                    pygame.display.iconify()
                elif event.key == pygame.K_F5:
                    predict_target_steps = max(
                        PREDICT_TARGET_STEPS_MIN, predict_target_steps // 2
                    )
                elif event.key == pygame.K_F6:
                    predict_target_steps = min(
                        PREDICT_TARGET_STEPS_MAX, predict_target_steps * 2
                    )
                elif event.key == pygame.K_F7:
                    time_scale = max(TIME_SCALE_MIN, time_scale * 0.5)
                elif event.key == pygame.K_F8:
                    time_scale = min(TIME_SCALE_MAX, time_scale * 2.0)
                elif event.key == pygame.K_F10:
                    enemies_enabled = not enemies_enabled
                    if not enemies_enabled:
                        for e in enemies:
                            e.alive = False
                        enemies = []
                elif event.key == pygame.K_h:
                    ship.toggle_brake_assist()
                elif event.key == pygame.K_j:
                    ship.toggle_path_hold()
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    camera.zoom = min(ZOOM_MAX, camera.zoom * ZOOM_STEP)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    camera.zoom = max(ZOOM_MIN, camera.zoom / ZOOM_STEP)
                elif event.key == pygame.K_0:
                    camera.zoom = 1.0
                elif event.key in (pygame.K_SLASH, pygame.K_KP_DIVIDE):
                    predict_seconds = max(
                        PREDICT_MIN_SECONDS, predict_seconds / PREDICT_STEP
                    )
                elif (event.key == pygame.K_KP_MULTIPLY
                      or event.key == pygame.K_ASTERISK
                      or (event.key == pygame.K_8 and (event.mod & pygame.KMOD_SHIFT))):
                    predict_seconds = min(
                        PREDICT_MAX_SECONDS, predict_seconds * PREDICT_STEP
                    )
                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    flags = pygame.FULLSCREEN if fullscreen else 0
                    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
                    new_w, new_h = screen.get_size()
                    if (new_w, new_h) != (WIDTH, HEIGHT):
                        WIDTH, HEIGHT = new_w, new_h
                elif event.key == pygame.K_F12:
                    stamp = datetime.datetime.now().strftime("%Y-%m-%d - %H-%M-%S")
                    out_dir = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "captures",
                    )
                    os.makedirs(out_dir, exist_ok=True)
                    pygame.image.save(screen, os.path.join(out_dir, f"{stamp}.png"))
                elif event.key == pygame.K_F9:
                    if recorder.recording:
                        recorder.stop()
                    else:
                        out_dir = os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "captures",
                        )
                        os.makedirs(out_dir, exist_ok=True)
                        recorder.start(screen.get_size(), out_dir)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_clicked = True

        keys = pygame.key.get_pressed()
        mods = pygame.key.get_mods()

        build_held = bool(keys[pygame.K_b])
        candidate_pad = nearest_unoccupied_pad(ship, pads)
        in_build_mode = build_held and candidate_pad is not None

        # Plan mode (Space): freeze the entire simulation -- bodies, ship,
        # enemies, bullets, turrets, fuel/refuel. Time t doesn't advance, so
        # body rails stay frozen too. The render block still runs and draws
        # an alternate trajectory based on the planned burn.
        if not in_build_mode and not paused:
            # Feed measured wall time into the accumulator (scaled by
            # time_scale, capped at MAX_FRAME_DT) and run as many fixed
            # PHYSICS_DT ticks as fit. The predictor uses the same
            # PHYSICS_DT, so what you see is what you fly. F7/F8 only
            # change how MUCH wall-time we feed per frame -- the physics
            # step itself stays at PHYSICS_DT, which keeps the integrator
            # bit-equivalent to the predictor regardless of time scale.
            physics_accumulator = min(
                physics_accumulator + frame_dt * time_scale,
                MAX_FRAME_DT,
            )
            while physics_accumulator >= PHYSICS_DT:
                sim_time += PHYSICS_DT
                update_bodies(bodies, sim_time)

                # Fire any chain-scheduled burns whose time has come BEFORE
                # ship.update so the leapfrog uses the post-burn velocity.
                ship.apply_pending_maneuvers(sim_time)

                mouse_aim_active = not build_held
                ship.update(PHYSICS_DT, keys, mods, deposits, bodies,
                            mouse_pos=mouse_pos,
                            mouse_aim_active=mouse_aim_active,
                            sim_time=sim_time)

                if enemies_enabled:
                    enemy_spawn_timer -= PHYSICS_DT
                    if enemy_spawn_timer <= 0.0:
                        # Spawn around whichever landable body the ship is
                        # closest to, so enemies arrive where the action is.
                        spawn_target = (nearest_landable(ship.pos, bodies)
                                        if ship.alive else planet)
                        if spawn_target is None:
                            spawn_target = planet
                        enemies.append(spawn_enemy(spawn_target))
                        enemy_spawn_timer = ENEMY_SPAWN_INTERVAL

                ship_pos = ship.pos if ship.alive else None
                for e in enemies:
                    if not e.alive:
                        continue
                    e.update(PHYSICS_DT, bodies, ship_pos)
                    if ship.alive and (e.pos - ship.pos).length() <= ENEMY_RADIUS + SHIP_LEN * 0.6:
                        e.alive = False
                        ship.alive = False

                for t in turrets:
                    t.update(PHYSICS_DT, enemies, bullets)

                for b in bullets:
                    if not b.alive:
                        continue
                    b.update(PHYSICS_DT)
                    if not b.alive:
                        continue
                    for e in enemies:
                        if not e.alive:
                            continue
                        if (b.pos - e.pos).length() <= ENEMY_RADIUS + BULLET_RADIUS:
                            e.alive = False
                            b.alive = False
                            ship.ore += ENEMY_KILL_REWARD
                            kills += 1
                            break

                enemies = [e for e in enemies if e.alive]
                bullets = [b for b in bullets if b.alive]
                turrets = [t for t in turrets if t.alive]

                physics_accumulator -= PHYSICS_DT
        else:
            # Drain so that resuming from pause / build mode doesn't kick off
            # a burst of catch-up physics ticks.
            physics_accumulator = 0.0

        # Camera tracks the ship in world space, except in plan-mode where
        # it follows the planned trajectory at the current preview burn's
        # fire-time. So pressing N or dialling , / . slides the camera to
        # where the *next* burn will fire instead of yanking back to the
        # ship -- you stay focused on what you're planning. With an empty
        # queue and offset 0 this collapses to "ship's current pos" so the
        # first burn still feels ship-anchored.
        if (paused and ship.alive
                and (maneuver_queue or plan_burn_offset > 1e-6)):
            # Queued portion of the chain only -- camera target is the
            # position JUST BEFORE the current preview burn fires.
            cam_pending = []
            for ang, dur, off in maneuver_queue:
                if dur == 0.0:
                    continue
                bd = Vector2(math.cos(ang), math.sin(ang))
                cam_pending.append((sim_time + off, bd, dur))
            # Mirror the launch-pad bump from commit_planned_burn so the
            # camera target lines up with what the orange line shows.
            if ship.landed and ship.landed_body is not None:
                lbody = ship.landed_body
                lradial = Vector2(math.cos(ship.landed_radial),
                                  math.sin(ship.landed_radial))
                cam_pos0 = lbody.pos + lradial * (lbody.radius
                                                  + LAUNCH_PAD_HEIGHT)
                cam_vel0 = Vector2(lbody.vel)
            else:
                cam_pos0 = Vector2(ship.pos)
                cam_vel0 = Vector2(ship.vel)
            cam_seconds = max(plan_burn_offset, PHYSICS_DT)
            cam_steps = min(
                PREDICT_TARGET_STEPS_MAX,
                max(predict_target_steps,
                    int(cam_seconds / PHYSICS_DT)),
            )
            cam_pts, _, _ = ship.predict_trajectory(
                bodies, sim_time, seconds=cam_seconds,
                pos0=cam_pos0, vel0=cam_vel0,
                target_steps=cam_steps,
                pending_burns=cam_pending,
            )
            camera.pos = Vector2(cam_pts[-1] if cam_pts else ship.pos)
        else:
            camera.pos = Vector2(ship.pos)

        # --- Render ------------------------------------------------------
        screen.fill(BG)
        stars.draw(screen, camera)

        for body in bodies:
            draw_orbit_path(screen, camera, body)

        # Anchor for apsides: whatever landable body the ship is closest to
        # right now. Stays consistent with the HUD's "vs <body>" labelling.
        apsis_anchor = nearest_landable(ship.pos, bodies) if ship.alive else None
        # Closest-approach target: the *nearest* landable body that isn't the
        # apsis anchor. With three landable bodies (Planet, Moon, Ember) this
        # picks the most useful "next destination" -- near Planet you see
        # your closest pass to Moon, near Moon you see Planet, near Ember
        # you see Planet. Falls back to None when the only landable body in
        # scene is the anchor itself.
        ca_target: Body | None = None
        if apsis_anchor is not None:
            best_d2 = float("inf")
            for b in bodies:
                if not b.landable or b is apsis_anchor:
                    continue
                d2 = (b.pos - ship.pos).length_squared()
                if d2 < best_d2:
                    best_d2 = d2
                    ca_target = b
        live_peri_alt: float | None = None
        live_apo_alt: float | None = None
        live_ca_alt: float | None = None
        plan_peri_alt: float | None = None
        plan_apo_alt: float | None = None
        plan_ca_alt: float | None = None

        if ship.alive and not ship.landed and not in_build_mode:
            # Decide whether to refresh the cyan-predict cache or replay
            # the previous frame's result. Refresh whenever:
            #   - cache aged past PREDICT_CACHE_INTERVAL frames
            #   - paused toggled (sim went still or resumed)
            #   - pending burn count changed (a burn fired or chain
            #     was extended via plan-mode commit)
            #   - predict horizon / step budget mutated (/, *, F5, F6)
            #   - apsis or closest-approach anchor body changed
            # When paused, ship state is invariant so the cache stays
            # exact across as many replay frames as we like; the
            # interval-based refresh only matters while running.
            pending_count_now = len(ship.pending_maneuvers)
            apsis_anchor_id = id(apsis_anchor)
            ca_target_id = id(ca_target)
            refresh = (
                predict_cache["age"] >= PREDICT_CACHE_INTERVAL
                or predict_cache["paused"] != paused
                or predict_cache["pending_count"] != pending_count_now
                or predict_cache["predict_seconds"] != predict_seconds
                or predict_cache["predict_target_steps"] != predict_target_steps
                or predict_cache["apsis_anchor_id"] != apsis_anchor_id
                or predict_cache["ca_target_id"] != ca_target_id
            )
            if refresh:
                # Fold any committed maneuver chain (ship.pending_maneuvers)
                # into the cyan predict so the line shows the trajectory the
                # ship will *actually* fly post-burns, with chevrons stamped
                # at each scheduled burn point. As burns fire and pop from
                # pending_maneuvers, their chevron evaporates and the line
                # straightens for that segment on the next refresh -- no
                # separate "armed overlay" needed.
                #
                # Horizon extends past the last burn so the user can see what
                # the chain results in, mirroring plan-mode's PLAN_CHAIN_
                # LOOKAHEAD_SCALE behaviour. Step budget scales with horizon
                # so a long chain doesn't collapse to a coarse line.
                if ship.pending_maneuvers:
                    last_apply = max(t for t, _, _ in ship.pending_maneuvers)
                    live_chain_span = max(0.0, last_apply - sim_time)
                    live_seconds = max(
                        predict_seconds,
                        live_chain_span + predict_seconds * PLAN_CHAIN_LOOKAHEAD_SCALE,
                    )
                    live_steps = min(
                        PREDICT_TARGET_STEPS_MAX,
                        int(predict_target_steps * (live_seconds / predict_seconds)),
                    )
                else:
                    live_seconds = predict_seconds
                    live_steps = predict_target_steps
                live_burn_indices: list[int] = []
                traj, impact_speed, traj_dt = ship.predict_trajectory(
                    bodies, sim_time, seconds=live_seconds,
                    target_steps=live_steps,
                    pending_burns=ship.pending_maneuvers,
                    burn_indices=live_burn_indices,
                )
                soi_indices = find_soi_crossings(traj, sim_time, traj_dt, bodies)
                ca_idx: int | None = None
                if ca_target is not None:
                    ca_idx, live_ca_alt = find_closest_approach(
                        traj, sim_time, traj_dt, ca_target
                    )
                peri_idx: int | None = None
                apo_idx: int | None = None
                if apsis_anchor is not None:
                    peri_idx, apo_idx, live_peri_alt, live_apo_alt = find_apsides(
                        traj, sim_time, traj_dt, apsis_anchor
                    )
                predict_cache.update({
                    "age": 0,
                    "paused": paused,
                    "pending_count": pending_count_now,
                    "predict_seconds": predict_seconds,
                    "predict_target_steps": predict_target_steps,
                    "apsis_anchor_id": apsis_anchor_id,
                    "ca_target_id": ca_target_id,
                    "traj": traj,
                    "impact_speed": impact_speed,
                    "traj_dt": traj_dt,
                    "burn_indices": live_burn_indices,
                    "soi_indices": soi_indices,
                    "peri_idx": peri_idx,
                    "apo_idx": apo_idx,
                    "ca_idx": ca_idx,
                    "peri_alt": live_peri_alt,
                    "apo_alt": live_apo_alt,
                    "ca_alt": live_ca_alt,
                })
            else:
                predict_cache["age"] += 1
                # Replay HUD readouts from cache so the altitude / closest-
                # approach numbers stay populated on non-refresh frames.
                live_peri_alt = predict_cache["peri_alt"]
                live_apo_alt = predict_cache["apo_alt"]
                live_ca_alt = predict_cache["ca_alt"]

            # Render from cache (whether just-refreshed or replayed). The
            # marker draw functions handle None idx / empty indices as
            # no-ops, so this works uniformly.
            cached_traj = predict_cache["traj"]
            if cached_traj:
                draw_trajectory(screen, camera, cached_traj,
                                predict_cache["impact_speed"],
                                predict_cache["traj_dt"])
                # Stack annotation layers under-to-over so the most
                # actionable markers (apsides + prograde arrows) sit on top.
                draw_soi_markers(screen, camera, cached_traj,
                                 predict_cache["soi_indices"])
                draw_closest_approach_marker(screen, camera, cached_traj,
                                             predict_cache["ca_idx"])
                draw_apsis_markers(screen, camera, cached_traj,
                                   predict_cache["peri_idx"],
                                   predict_cache["apo_idx"])
                # Chevrons last so they sit above the predicted line and
                # apsis dots. No-op when burn_indices is empty.
                draw_chain_burn_markers(screen, camera, cached_traj,
                                        predict_cache["burn_indices"], font)

        # Plan-mode "what-if" overlay: walk the predictor through the full
        # maneuver chain (queued burns + the current preview burn), drawing
        # an orange trajectory with chevron markers at each scheduled burn.
        # Drawn even when landed -- planning takeoff burns is a useful case.
        plan_burn_dv = 0.0
        plan_burn_angle = ship.angle
        # +1 for the current preview burn, even if duration is 0 (we still
        # show "burn 1/1" in the HUD so the user knows where they are).
        chain_burn_count = len(maneuver_queue) + 1
        if paused and ship.alive:
            dx = mouse_pos[0] - WIDTH / 2
            dy = mouse_pos[1] - HEIGHT / 2
            if dx * dx + dy * dy >= MOUSE_AIM_DEADZONE_SQ:
                plan_burn_angle = math.atan2(dy, dx)
            plan_burn_dv = SHIP_THRUST * plan_burn_duration
            # Build the full chain: queue entries + the current preview as
            # the final entry. The predictor receives this as pending_burns
            # and inserts each kick at the right step. Current preview's
            # fire-time is plan_burn_offset (user-controlled via , / .).
            full_chain = list(maneuver_queue) + [
                (plan_burn_angle, plan_burn_duration, plan_burn_offset)
            ]
            # When landed, the live commit path bumps to launch-pad height
            # and replaces ship.vel with body.vel before applying burn 0.
            # Mirror that here so the orange line matches what Enter
            # actually delivers.
            if ship.landed and ship.landed_body is not None:
                lbody = ship.landed_body
                lradial = Vector2(math.cos(ship.landed_radial),
                                  math.sin(ship.landed_radial))
                plan_pos0 = lbody.pos + lradial * (lbody.radius + LAUNCH_PAD_HEIGHT)
                plan_vel0 = Vector2(lbody.vel)
            else:
                plan_pos0 = None  # falls back to ship.pos
                plan_vel0 = Vector2(ship.vel)
            pending = []
            for ang, dur, off in full_chain:
                if dur == 0.0:
                    continue
                bd = Vector2(math.cos(ang), math.sin(ang))
                pending.append((sim_time + off, bd, dur))
            # Horizon: extend past the last burn so the user can see what
            # the chain results in. PLAN_CHAIN_LOOKAHEAD_SCALE * predict
            # past the final burn keeps the same feel as a single-burn
            # preview where you see ~predict_seconds beyond the burn.
            chain_span = full_chain[-1][2] if full_chain else 0.0
            plan_seconds = max(
                predict_seconds,
                chain_span + predict_seconds * PLAN_CHAIN_LOOKAHEAD_SCALE,
            )
            # Step budget scales with horizon so very long chains don't
            # collapse to coarse straight lines. Cap at the same max the
            # F5/F6 pair allows so we don't blow past the predictor's
            # design budget on a 4-burn 5-minute chain.
            chain_steps = min(
                PREDICT_TARGET_STEPS_MAX,
                int(predict_target_steps * (plan_seconds / predict_seconds)),
            )
            plan_burn_indices: list[int] = []
            plan_traj, plan_impact, plan_dt = ship.predict_trajectory(
                bodies, sim_time, seconds=plan_seconds,
                pos0=plan_pos0, vel0=plan_vel0,
                target_steps=chain_steps,
                pending_burns=pending,
                burn_indices=plan_burn_indices,
            )
            draw_plan_trajectory(screen, camera, plan_traj, plan_impact, plan_dt)
            plan_soi_indices = find_soi_crossings(plan_traj, sim_time, plan_dt, bodies)
            draw_soi_markers(screen, camera, plan_traj, plan_soi_indices)
            if ca_target is not None:
                p_ca_idx, plan_ca_alt = find_closest_approach(
                    plan_traj, sim_time, plan_dt, ca_target
                )
                draw_closest_approach_marker(screen, camera, plan_traj, p_ca_idx)
            if apsis_anchor is not None:
                p_peri_idx, p_apo_idx, plan_peri_alt, plan_apo_alt = find_apsides(
                    plan_traj, sim_time, plan_dt, apsis_anchor
                )
                draw_apsis_markers(screen, camera, plan_traj, p_peri_idx, p_apo_idx)
            # Chain burn-point chevrons sit on top so they read above the
            # apsis dots and the orange ribbon.
            draw_chain_burn_markers(screen, camera, plan_traj,
                                    plan_burn_indices, font)
            # Burn-vector arrow anchored where the burn actually starts (so
            # when landed it sits at launch-pad height, not on the surface).
            arrow_origin = plan_pos0 if plan_pos0 is not None else ship.pos
            sx, sy = camera.world_to_screen_int(arrow_origin)
            # Arrow flips for negative durations so it shows the actual
            # impulse direction, matching the orange trajectory.
            arrow_sign = 1.0 if plan_burn_duration >= 0.0 else -1.0
            arrow_len = min(80, 12 + abs(plan_burn_duration) * 14)
            ex = int(sx + math.cos(plan_burn_angle) * arrow_len * arrow_sign)
            ey = int(sy + math.sin(plan_burn_angle) * arrow_len * arrow_sign)
            pygame.draw.line(screen, PLAN_COLOR, (sx, sy), (ex, ey), 2)

        for body in bodies:
            draw_body(screen, camera, body)

        for dep in deposits:
            draw_deposit(screen, camera, dep)
        for p in pads:
            draw_buildpad(screen, camera, p)
        for t in turrets:
            draw_turret(screen, camera, t)
        for b in bullets:
            draw_bullet(screen, camera, b)
        for e in enemies:
            draw_enemy(screen, camera, e)

        if ship.alive and ship.mining_target is not None:
            draw_mining_beam(screen, camera, ship.pos, ship.mining_target)

        ship.draw(screen, camera)

        build_prompt = (candidate_pad is not None) and not build_held
        if hud_visible:
            draw_hud(screen, font, ship, bodies, sun, enemies, turrets,
                     build_prompt, camera.zoom, predict_seconds,
                     kills, enemies_enabled,
                     paused=paused, plan_burn_duration=plan_burn_duration,
                     plan_burn_dv=plan_burn_dv,
                     predict_target_steps=predict_target_steps,
                     live_peri_alt=live_peri_alt, live_apo_alt=live_apo_alt,
                     plan_peri_alt=plan_peri_alt, plan_apo_alt=plan_apo_alt,
                     ca_target_name=ca_target.name if ca_target is not None else None,
                     live_ca_alt=live_ca_alt, plan_ca_alt=plan_ca_alt,
                     chain_queue_size=len(maneuver_queue),
                     chain_burn_count=chain_burn_count,
                     pending_count=len(ship.pending_maneuvers),
                     plan_burn_offset=plan_burn_offset,
                     time_scale=time_scale)

        if in_build_mode:
            btn_rect, can_afford = draw_build_menu(screen, font, ship)
            if mouse_clicked and can_afford:
                bx, by, bw, bh = btn_rect
                mx, my = mouse_pos
                if bx <= mx <= bx + bw and by <= my <= by + bh:
                    ship.ore -= TURRET_COST
                    new_t = Turret(candidate_pad.body, candidate_pad.angle)
                    candidate_pad.turret = new_t
                    turrets.append(new_t)

        # Recording indicator: small red dot + counts in the top-right.
        # Drawn after every other UI element so it appears in the recorded
        # frame too -- intentional, like an OBS REC tally; if you don't
        # want it on the video, F9 to stop before whatever you're showing.
        if recorder.recording:
            rec_text = (f"REC  {recorder.frames_written} frames"
                        f"  ({recorder.frames_dropped} dropped)")
            rec_surf = font.render(rec_text, True, (255, 90, 90))
            tx = WIDTH - rec_surf.get_width() - 32
            ty = 16
            pygame.draw.circle(screen, (255, 60, 60),
                               (tx - 14, ty + rec_surf.get_height() // 2), 6)
            screen.blit(rec_surf, (tx, ty))

        pygame.display.flip()

        # Feed AFTER flip so the recording matches what the user just saw.
        recorder.feed(screen)

    recorder.stop()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
