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
    Ctrl  + Up/W       thrust forward at 10% normal (precision)
    Down  / S          retro-thrust at 10% of forward power
    Q                  strafe left at 10% of forward power
    E                  strafe right at 10% of forward power
    H                  toggle brake assist (autopilot matches velocity of
                       nearest landable body, or zeroes absolute velocity
                       if no landable body in scene)
    Shift (while H on) hover-hold: zero only radial velocity, leave
                       tangential drift alone (lines you up over a pad)
    Ctrl  (while H on) damp autopilot to 0.25x strength (fine soft landings)
    Shift+Ctrl (H on)  hover-hold at 0.25x strength
    B (hold)           build mode while landed near an unoccupied build pad
    + / =              zoom in
    - / _              zoom out
    0                  reset zoom to 1.0
    /                  shorter trajectory prediction window (down to 5s)
    *                  longer trajectory prediction window (up to 5min)
    F10                toggle enemy spawns (also clears any in scene)
    F11                toggle fullscreen
    F12                save screenshot (PNG) next to ypilot.py
    R                  reset world
    Esc                quit

Run:
    pip install pygame-ce        # or: pip install pygame
    python ypilot.py
"""

import datetime
import math
import os
import random
import sys

import pygame
from pygame.math import Vector2


# --- Display (initialised at startup; defaults are fallback only) -----------
WIDTH, HEIGHT = 1280, 720
FPS = 60
BG = (8, 8, 20)

# --- Zoom -------------------------------------------------------------------
ZOOM_MIN = 0.25
ZOOM_MAX = 4.0
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

# --- Ship -------------------------------------------------------------------
SHIP_THRUST = 220.0
SHIP_TURN_RATE = math.radians(180)
SHIP_LEN = 18.0
SHIP_COLOR = (240, 240, 240)
SHIP_OUTLINE = (40, 40, 60)
FLAME_COLOR = (255, 170, 60)
RETRO_FLAME_COLOR = (180, 200, 255)
LANDED_RING_COLOR = (140, 220, 140)

THRUST_BOOST_SCALE = 5.0
THRUST_PRECISION_SCALE = 0.1
RETRO_THRUST_SCALE = 0.1
LATERAL_THRUST_SCALE = 0.1       # Q / E strafe thrusters; same magnitude
                                 # as retro for symmetric feel

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

# --- Trajectory prediction --------------------------------------------------
PREDICT_SECONDS = 30.0           # default look-ahead
PREDICT_MIN_SECONDS = 5.0        # `/` key floor
PREDICT_MAX_SECONDS = 1000.0     # `*` key ceiling (~16.7 minutes)
PREDICT_STEP = 1.5               # multiplicative step per `/` or `*` press
PREDICT_DT_MIN = 1.0 / 60.0      # smallest sim step (used for short windows)
PREDICT_TARGET_STEPS = 6400      # cap total steps so 5min predictions stay cheap
PREDICT_DRAW_STRIDE = 6
PREDICT_COLOR = (90, 200, 255)
PREDICT_IMPACT_COLOR = (255, 90, 90)

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
    return [sun, planet]


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
    """Closest landable body to `pos`, or None if there isn't one in scene.

    Used by the brake-assist autopilot so it matches velocity to whatever
    you're actually flying toward (the sun is not a viable landing target).
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


def spawn_enemy(planet: Body) -> Enemy:
    a = random.uniform(0.0, 2.0 * math.pi)
    radial = Vector2(math.cos(a), math.sin(a))
    pos = planet.pos + radial * ENEMY_SPAWN_DISTANCE
    inward = (planet.pos - pos).normalize()
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
        self.brake_assist = False
        self.brake_assist_scale = 1.0
        self.hover_hold = False
        self.takeoff_lock_timer = 0.0
        self.fuel = MAX_FUEL
        self.ore = 0.0
        self.mining_target = None
        self.landed = False
        self.landed_body = None
        self.landed_radial = 0.0
        self.alive = True
    
    def toggle_brake_assist(self) -> None:
        if self.alive and not self.landed and self.fuel > 0.0:
            self.brake_assist = not self.brake_assist
    
    def update(self, dt: float, keys, mods: int, deposits: list[Deposit],
               bodies: list[Body], mouse_pos: tuple[int, int] | None = None,
               mouse_aim_active: bool = True) -> None:
        if not self.alive:
            return

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

        if self.landed and self.landed_body is not None:
            self.brake_assist = False
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

        burn = 0.0
        if self.thrusting:
            burn += self.thrust_scale * dt
        if self.retro_thrusting:
            burn += RETRO_THRUST_SCALE * dt
        if self.strafing_left:
            burn += LATERAL_THRUST_SCALE * dt
        if self.strafing_right:
            burn += LATERAL_THRUST_SCALE * dt
        if self.brake_assist:
            desired = self._brake_assist_accel(self.pos, self.vel, bodies)
            burn += (desired.length() / SHIP_THRUST) * dt
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

        self.thrusting = False
        self.retro_thrusting = False
        self.strafing_left = False
        self.strafing_right = False

        if forward_pressed:
            self.brake_assist = False
            if mods & pygame.KMOD_SHIFT:
                self.thrust_scale = THRUST_BOOST_SCALE
            elif mods & pygame.KMOD_CTRL:
                self.thrust_scale = THRUST_PRECISION_SCALE
            else:
                self.thrust_scale = 1.0
            self.thrusting = True

        if reverse_pressed:
            self.brake_assist = False
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
        # forward thrust isn't pressed -- Shift/Ctrl are also forward-
        # thrust scale modifiers, so we'd have a conflict otherwise.
        # Strafe and retro don't use Shift/Ctrl, so they don't conflict.
        if self.brake_assist and not forward_pressed:
            self.hover_hold = bool(mods & pygame.KMOD_SHIFT)
            self.brake_assist_scale = 0.25 if (mods & pygame.KMOD_CTRL) else 1.0
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
            accel -= forward_dir * (SHIP_THRUST * RETRO_THRUST_SCALE)

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
            return Vector2(0.0, 0.0)

        target = nearest_landable(pos, bodies)
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

    def predict_trajectory(self, bodies: list[Body], t_start: float,
                           seconds: float = PREDICT_SECONDS,
                           dt: float | None = None) -> tuple[list[Vector2], float | None]:
        # Scale dt with prediction length so cost stays bounded. For short
        # windows we use the sim's native dt; for very long windows we step
        # in larger jumps (sacrificing precision for predictive reach -- the
        # 3-body system is chaotic over long horizons anyway).
        if dt is None:
            dt = max(PREDICT_DT_MIN, seconds / PREDICT_TARGET_STEPS)
        n = max(2, int(seconds / dt))
        pos = Vector2(self.pos)
        vel = Vector2(self.vel)
        points = [Vector2(pos)]
        impact_speed = None
        for i in range(n):
            t0 = t_start + i * dt
            t2 = t_start + (i + 1) * dt
            a0 = gravity_at_t(pos, t0, bodies)
            v_half = vel + a0 * (dt * 0.5)
            pos = pos + v_half * dt
            a1 = gravity_at_t(pos, t2, bodies)
            vel = v_half + a1 * (dt * 0.5)
            points.append(Vector2(pos))
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
        return points, impact_speed

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


def draw_trajectory(surf: pygame.Surface, camera: Camera, points: list[Vector2], impact_speed: float | None) -> None:
    if len(points) < 2:
        return
    n = len(points)
    bg_r, bg_g, bg_b = BG
    base_r, base_g, base_b = PREDICT_COLOR
    stride = PREDICT_DRAW_STRIDE
    last_screen = None
    for i in range(0, n, stride):
        sp = camera.world_to_screen_int(points[i])
        if last_screen is not None:
            t = i / (n - 1)
            r = int(base_r * (1 - t) + bg_r * t)
            g = int(base_g * (1 - t) + bg_g * t)
            b = int(base_b * (1 - t) + bg_b * t)
            pygame.draw.line(surf, (r, g, b), last_screen, sp, 1)
        last_screen = sp

    if impact_speed is not None:
        ip = camera.world_to_screen_int(points[-1])
        color = LANDED_RING_COLOR if impact_speed <= LAND_SPEED_MAX else PREDICT_IMPACT_COLOR
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


def draw_hud(surf: pygame.Surface, font: pygame.font.Font, ship: Ship, planet: Body, sun: Body,
             enemies: list[Enemy], turrets: list[Turret], build_prompt: bool,
             zoom: float, predict_seconds: float,
             kills: int, enemies_enabled: bool) -> None:
    if ship.alive:
        r_planet = (ship.pos - planet.pos).length()
        altitude = max(0.0, r_planet - planet.radius)
        rel_vel = ship.vel - planet.vel
        speed_rel = rel_vel.length()
        v_circ = circular_orbit_speed(planet, r_planet) if r_planet > 0 else 0.0
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
            f"Altitude:    {altitude:7.1f}    (vs planet)",
            f"Rel speed:   {speed_rel:7.1f}    (vs planet)",
            f"v_circ here: {v_circ:7.1f}",
            f"Sun dist:    {d_sun:7.0f}",
            f"Fuel:        {ship.fuel:6.2f} / {MAX_FUEL:.0f}",
            f"Ore:         {ship.ore:6.1f}",
            f"Turrets:     {live_turrets}    Enemies: {live_enemies}{'' if enemies_enabled else ' (off)'}",
            f"Kills:       {kills}",
            f"Zoom:        x{zoom:.2f}    Predict: {predict_seconds:.0f}s",
        ]
        if thrust_label:
            lines.append(thrust_label)
        if ship.retro_thrusting:
            lines.append("Retro:       on (10%)")
        if ship.brake_assist:
            target = nearest_landable(ship.pos, [sun, planet])
            mode = f"matching {target.name}" if target is not None else "zeroing velocity"
            extras = []
            if ship.hover_hold:
                extras.append("HOVER (Shift)")
            if ship.brake_assist_scale < 1.0:
                extras.append(f"damp x{ship.brake_assist_scale:g} (Ctrl)")
            extra_str = "  " + "  ".join(extras) if extras else ""
            lines.append(f"BRAKE ASSIST: on  ({mode}){extra_str}  (cancels on W/S)")
        if ship.landed:
            if ship.mining_target is not None:
                lines.append(f"LANDED  -  refueling + MINING ({MINING_RATE:.0f}/s)")
            else:
                lines.append("LANDED  -  refueling")
        if ship.fuel <= 0.0 and not ship.landed:
            lines.append("OUT OF FUEL")
        if build_prompt:
            lines.append(">> hold B to open build menu <<")
        lines += [
            "",
            "Mouse aim  W/S/Shift/Ctrl thrust  H brake  B build",
            "+/- zoom  0 reset zoom  / shorter * longer predict",
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
    update_bodies(bodies, 0.0)
    deposits = generate_deposits(planet)
    pads = generate_buildpads(planet)
    return bodies, planet, sun, deposits, pads, [], [], []


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

    camera = Camera()
    camera.zoom = 1.0

    fullscreen = False
    predict_seconds = PREDICT_SECONDS

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

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
                elif event.key == pygame.K_F10:
                    enemies_enabled = not enemies_enabled
                    if not enemies_enabled:
                        for e in enemies:
                            e.alive = False
                        enemies = []
                elif event.key == pygame.K_h:
                    ship.toggle_brake_assist()
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
                    out_dir = os.path.dirname(os.path.abspath(__file__))
                    pygame.image.save(screen, os.path.join(out_dir, f"{stamp}.png"))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_clicked = True

        keys = pygame.key.get_pressed()
        mods = pygame.key.get_mods()

        build_held = bool(keys[pygame.K_b])
        candidate_pad = nearest_unoccupied_pad(ship, pads)
        in_build_mode = build_held and candidate_pad is not None

        if not in_build_mode:
            sim_time += dt
            update_bodies(bodies, sim_time)

            mouse_aim_active = not build_held
            ship.update(dt, keys, mods, deposits, bodies,
                        mouse_pos=mouse_pos, mouse_aim_active=mouse_aim_active)

            if enemies_enabled:
                enemy_spawn_timer -= dt
                if enemy_spawn_timer <= 0.0:
                    enemies.append(spawn_enemy(planet))
                    enemy_spawn_timer = ENEMY_SPAWN_INTERVAL

            ship_pos = ship.pos if ship.alive else None
            for e in enemies:
                if not e.alive:
                    continue
                e.update(dt, bodies, ship_pos)
                if ship.alive and (e.pos - ship.pos).length() <= ENEMY_RADIUS + SHIP_LEN * 0.6:
                    e.alive = False
                    ship.alive = False

            for t in turrets:
                t.update(dt, enemies, bullets)

            for b in bullets:
                if not b.alive:
                    continue
                b.update(dt)
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

        # Camera tracks the ship in world space; zoom is independent.
        camera.pos = Vector2(ship.pos)

        # --- Render ------------------------------------------------------
        screen.fill(BG)
        stars.draw(screen, camera)

        for body in bodies:
            draw_orbit_path(screen, camera, body)

        if ship.alive and not ship.landed and not in_build_mode:
            traj, impact_speed = ship.predict_trajectory(
                bodies, sim_time, seconds=predict_seconds
            )
            draw_trajectory(screen, camera, traj, impact_speed)

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
        draw_hud(screen, font, ship, planet, sun, enemies, turrets,
                 build_prompt, camera.zoom, predict_seconds,
                 kills, enemies_enabled)

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

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
