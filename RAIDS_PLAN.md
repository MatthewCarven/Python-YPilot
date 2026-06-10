# Raids plan (gameplay arc, step 2) — design doc, no code yet

Drafted 2026-06-10 with Claude while step 1 (scrap economy) awaits
playtest. Nothing here is committed design until Matthew signs off on
the open questions at the bottom.

## Why raids

Right now hostiles only threaten **the ship**. Turrets and printers
are pure convenience — nothing in the game can take them away from
you, so once built they're solved content. The defense economy has a
supply side (mine, salvage) but no real demand side.

Raids invert that: waves that target **structures** make every turret
a thing you can lose, every repair a recurring cost, and every quiet
orbit a decision about whether you're hoarding ore or spending it on
walls. It pairs with the scrap economy on purpose — bigger waves shed
more wreckage, so the system feeds the player the resources to answer
the pressure it applies. Self-balancing by construction.

## What exists today (constraints to build on)

- One `Enemy` type: straight-line flier, `ENEMY_SPEED = 32`,
  course-corrects toward the ship every ~60 s ± 50 %. Contact with the
  ship is an instant kill; contact with terrain leaves a scrap pile.
- Flat spawn clock: one UFO every `ENEMY_SPAWN_INTERVAL = 9 s`, around
  whichever landable body the ship is nearest. No escalation.
- Player structures (`Turret`, printer) have **no HP** and no damage
  path. AA batteries are the only destructible structure (missile
  proximity), collapsing into a 40-ore scrap pile.
- `F10` toggles enemy spawns and clears the scene; `Shift+F10` does
  the same for AA batteries. Save format is v2 and round-trips
  enemies, scrap piles, and in-flight debris.
- Combat convention: enemies and bullets fly straight (no gravity);
  missiles are the deliberate exception. Keep it — raiders shouldn't
  require the player to do 3-body intercepts either.

## Proposed design

### 1. Structure HP

Turrets and printers get hit points (working number:
`STRUCTURE_HP = 3`). Damage sources: raider impact (below). Batteries
keep their existing one-missile death — they're the enemy's stuff,
symmetry not required.

A destroyed player structure collapses into a scrap pile worth a
fraction of build cost (working: 40 % — turret 20, printer 40), at its
pad's angle. The pad itself survives and frees up. Losing a turret
should sting but refund a head start on the rebuild; total-loss
punishment makes players quit raids off (F10) instead of engaging.

Damaged structures show it: HP pips over the structure when below
full, plus a flash on hit, so a glance at the fortress reads its
health. No HUD clutter when everything's intact.

**Repair:** land near a damaged structure and the mining beam runs in
reverse — `REPAIRING` on the HUD, ore drains at `REPAIR_COST_PER_HP`
(working: 5 ore), HP ticks back up. Reuses the deposit-proximity
machinery and keeps the "physical economy, you go there" theme — no
remote repair button.

### 2. Raider enemy

A second intent for the same Enemy chassis, not a new class
hierarchy: a `raider` flag (or `target` field). Raiders pick the
nearest **player structure** at spawn, course-correct toward it on the
same ~60 s cadence chasers use toward the ship, and **kamikaze**: on
terrain impact, any structure within a small arc distance (working:
`RAID_BLAST_ARC = 18` arc-px) takes 1 HP, and the wreck leaves the
usual `SCRAP_VALUE = 12` pile at the impact point — every attack
delivers its own partial compensation.

Kamikaze over shooting for v1: it reuses the existing crash-detection
path, needs no enemy ballistics, and turret intercept math doesn't
change. A shooting raider variant can be a later escalation tier.

Raiders ignore the ship entirely (no contact kill exemption though —
flying into one still hurts). Chasers stay exactly as they are. Waves
mix the two, so the player is splitting attention between dodging and
defending — that split IS the gameplay.

If a raider's target dies before arrival it re-targets the nearest
surviving structure; if none exist anywhere, it converts to a chaser.
No structures built = raids degenerate to today's behavior, so the
system is inert until the player opts into building. Early game
untouched.

### 3. Wave director

Replaces the flat 9 s clock (which becomes the *between-waves
trickle*, slowed — working: 18 s). State machine:

```
CALM (trickle) → WARNING (10 s telegraph) → RAID (burst spawn) → CALM
```

- **Threat level** `T` drives wave size. Proposal: `T` derives from
  **structures built + total ore banked over the run** (mined and
  salvaged), NOT wall-clock time. Defense provokes offense; a player
  who never builds never sees a raid; turtling on a fat ore pile
  escalates. Exact formula is a tuning question, working sketch:
  `T = n_structures + total_ore_earned / 100`, wave size
  `N = WAVE_BASE_SIZE + floor(T * WAVE_SIZE_PER_THREAT)` with
  working values 2 + T×0.5, capped (working: 8) so late game is
  intense, not unplayable.
- **Mix:** mostly raiders with a chaser escort (working: 70/30).
- **Target body:** the landable body carrying the most player
  structures (ties → random among tied, seeded per-wave). Frostbite
  expeditions stay calm unless you fortify Frostbite — mining trips
  remain about orbital mechanics, not tower defense.
- **Telegraph:** during WARNING, HUD banner `RAID INBOUND — <body>`
  plus an edge-of-screen direction marker, matching the existing HUD
  conventions. 10 s is enough to commit to a burn home, not enough to
  fly home from Frostbite — sometimes you eat the loss, that's the
  point.
- Wave spawns burst from one approach bearing (± jitter) rather than
  the all-around ring, so a raid reads as a *formation* and turret
  placement on the approach side matters.

### 4. F10 and pacing controls

`F10` keeps its exact semantics — kills the trickle AND the wave
director, clears live enemies; the warning state cancels. Pressure
stays opt-in. Save/load round-trips the director state (phase, timer,
threat, pending wave) the same way `enemy_spawn_timer` already does.

### 5. Scrap interaction

Nothing new needed — raider wrecks use the existing pile machinery.
Two watch-items: `SCRAP_MAX_PILES = 30` may need a bump or a per-body
cap once an 8-ship wave dies on one planet, and pile merging
(`SCRAP_MERGE_DIST = 14`) means a defended fortress accumulates a few
fat piles, which is the desired look. Defer both to playtest.

### 6. Save format

v2 → v3: per-structure `hp`, per-enemy `kind`/`target`, wave director
block. Loaders default missing fields (full HP, chaser, CALM at
mid-trickle) so v2 saves keep working — same pattern the deposit
loader already uses.

## Proposed tunables (all open to feel-tuning)

| Constant | Working value | Note |
| --- | --- | --- |
| `STRUCTURE_HP` | 3 | raider hits to kill a turret/printer |
| `STRUCTURE_SCRAP_FRACTION` | 0.4 | of build cost, dropped on death |
| `REPAIR_COST_PER_HP` | 5 | ore, beam-repair while landed near |
| `RAID_BLAST_ARC` | 18 | arc-px, kamikaze damage radius |
| `WAVE_BASE_SIZE` / `WAVE_SIZE_PER_THREAT` / `WAVE_MAX_SIZE` | 2 / 0.5 / 8 | |
| `WAVE_RAIDER_FRACTION` | 0.7 | rest are chasers |
| `RAID_WARNING_LEAD` | 10 s | telegraph window |
| `TRICKLE_INTERVAL` | 18 s | between-wave spawn clock (was 9) |

## Phasing (one session each, per working agreement)

- **Phase A — HP plumbing.** Structure HP + hit flash + pips +
  scrap-on-destruction + beam repair + save v3. No new enemies; wire a
  debug damage key (temporary) to playtest the repair loop in
  isolation.
- **Phase B — raider intent.** Spawn flag, structure targeting,
  kamikaze damage, re-target/convert rules. Trickle can rarely roll a
  raider so it's testable without the director.
- **Phase C — wave director.** Threat, state machine, telegraph HUD,
  formation spawning, F10 integration, save round-trip.

Each phase is independently shippable and playtestable; B and C only
start after the previous phase has a playtest verdict, same as the
scrap economy gate.

## Open questions for Matthew

1. **Threat driver:** structures + lifetime ore (proposed) — or
   simple elapsed time, or kills? Lifetime-ore means mining quietly
   still escalates eventually; is that wanted?
2. **Repair:** beam-repair at 5 ore/HP (proposed), free-but-slow
   auto-regen between waves, or no repair (rebuild only)?
3. **Raider lethality vs ship:** keep raider-ship contact as instant
   kill (proposed, consistent), or make raiders harmless to the ship
   so dodging stays a chaser-only problem?
4. **Wave target:** most-fortified body (proposed) — or follow the
   ship like spawns do today? Most-fortified means you can lure raids
   away by decentralizing; following the ship punishes being home.
5. **Cap feel:** is 8 simultaneous hostiles the right ceiling for the
   current turret/bullet budget, or should `WAVE_MAX_SIZE` scale with
   built turrets so defense can actually keep up?
