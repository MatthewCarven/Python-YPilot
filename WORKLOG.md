# Worklog

## 2026-08-21

- **Threading + per-frame-CPU audit** (Matthew asked what background work
  the game is actually doing). Answer: there is exactly **one** thread in
  the whole program -- `VideoRecorder._writer`, the daemon that drains an
  8-slot bounded queue into ffmpeg's stdin (F9 recording). It is idle
  unless recording. Nothing else is threaded; every predictor runs on the
  main thread. Inventory of the predictor calls, cheapest-first:
  - `Ship.predict_trajectory` callers: battery intercept solver, plan-mode
    commit snapshot, camera lookahead (paused only), the cyan live
    predict, and the orange plan-mode overlay.
  - The **cyan live predict** is the biggest single consumer (up to
    `PREDICT_TARGET_STEPS = 6400` leapfrog steps, each 2x `gravity_at_t`
    over every body plus a collision sweep, then three full point-list
    walks for SOI / apsides / closest-approach) -- but it is already
    well-behaved: the `predict_cache` dirty-check amortises it over
    `PREDICT_CACHE_INTERVAL = 3` frames and force-refreshes on any state
    divergence. **Left alone deliberately.**
  - The **actual waste was `PlanetaryBattery._solve_intercept`** (below).
- **Battery solver: added a range gate.** `_solve_intercept` runs a
  120-step gravity-aware `predict_trajectory` and only then bails if the
  converged intercept lies outside `BATTERY_RANGE`. Since ~50% of landable
  bodies roll a battery, every battery in the system -- including ones on
  the far side of the sun -- was paying for a full predict every
  `BATTERY_SOLVE_INTERVAL` purely to throw the result away. Now gated on
  `reach = BATTERY_RANGE + ship.vel.length() * horizon * 1.5` against a
  squared-distance check before the predict. Conservative by construction
  (a solve can only succeed if the ship's predicted path enters
  `BATTERY_RANGE` of the battery's *current* position, and ship
  displacement over the horizon is bounded by speed x horizon; the 1.5x
  is headroom for gravitational speed-up mid-horizon), so it can only ever
  skip solves that were already doomed to fail. **No gameplay change.**
- **Battery solver: tracking no longer re-solves every physics tick.**
  `PlanetaryBattery.update` is called from inside the *physics* loop, not
  the frame loop -- so a battery in `tracking` was running that 120-step
  predict 60x a second, each. Now gated on new
  `BATTERY_TRACK_SOLVE_INTERVAL = 0.05` (~20 Hz), reusing the existing
  `solve_age` accumulator (already zeroed on the idle->tracking
  transition, so the first cadence window is correct). Aim point holds
  between solves. Gameplay delta: the burn-to-dodge escape now drops the
  lock within 50 ms of the player's thrust instead of within 17 ms --
  invisible against a 1.0 s telegraph laser. 3x fewer solves while a
  battery is locked on.
- Both changes compile clean (`py_compile`). **Not playtested** -- no
  display in this session. Worth a field check that the AA telegraph
  still reads smoothly and that dodging still drops the lock (Shift+F10
  toggles batteries).
- **Built: thrust-preview ghosts (hold Tab).** Matthew picked the
  two-fixed-0.1s-ghosts option over the single-scalable-ghost
  alternative. Dim green = a 0.1 s W tap, dim magenta = a 0.1 s S tap,
  drawn *before* the cyan predict so the real forecast stays the
  dominant line. HUD gains a `THRUST PEEK` line with both dv numbers.
  New `compute_thrust_preview` / `draw_thrust_preview` pair; bound to
  held `K_TAB`, gated on alive + airborne + not-in-build-menu + not
  seed-prompt.
- **Refactor that fell out of it: the thrust trim ladders are now a
  single source of truth.** Lifted the Shift/Ctrl/Ctrl+Shift ladders out
  of `Ship._read_thrust_input` into module-level `forward_thrust_scale`
  / `retro_thrust_scale`. Both the live input path and the overlay call
  them, so the ghost can't preview a scale the key wouldn't apply -- and
  `Shift+Tab` / `Ctrl+Tab` preview the boost and precision taps for
  free. Verified headless that all four rungs of both ladders still
  produce identical `thrust_scale` / `retro_scale` through the live
  reader.
- **The retro asymmetry is worth knowing about**: forward runs at full
  `SHIP_THRUST`, retro at `RETRO_THRUST_SCALE` (10%), so a nominal W tap
  is +22.0 dv against S's -2.2 and the green ghost fans ~8x further off
  the cyan line. This was NOT what the original pitch assumed (it
  reasoned about a symmetric 22 u/s both ways). Left honest rather than
  normalised, and the HUD prints both numbers because that ratio is the
  least obvious thing on screen.
- **Perf work this needed -- the first cut was too expensive.** At the
  originally-proposed 400 steps, computing both ghosts fresh every frame
  measured **25 ms/frame**, against a 16.7 ms budget at 60 FPS. Fixed in
  two moves: dropped to `THRUST_PREVIEW_TARGET_STEPS = 150` (chosen from
  measured endpoint error vs a full `dt = PHYSICS_DT` reference -- worst
  case low fast orbit: 60 steps = 8.5% of the fan, 100 = 4.5%, 150 =
  2.8%, 200 = 2.0%), and gave the ghosts their own cache on the existing
  `PREDICT_CACHE_INTERVAL` cadence. Final: **~3.5 ms/frame while held**,
  ~18% on top of the cyan line. Cache is a separate dict from
  `predict_cache` so the cyan line's invalidation conditions stay
  untouched; `ship.angle` is deliberately *not* in the key (including it
  refreshes every frame during a turn, the expensive case) at the price
  of up to 3 frames / ~9 deg of ghost lag while sweeping the nose.
- **Thrust ghosts failed their first playtest -- "couldn't distinguish a
  second or 3rd line anywhere" -- and the cause was rendering, not the
  0.1 s tap length.** Matthew's own guess was the tap being too short;
  that turned out to be wrong, and worth recording because it was a
  convincing wrong answer. Diagnosis was done by rendering real frames
  headless to PNG (`SDL_VIDEODRIVER=dummy` + `pygame.image.save`) and
  looking at them, which is a much better tool for "is this visible?"
  than any amount of reading the code. Three faults, all in the draw:
  1. **Ghosts were drawn *underneath* the cyan predict.** The retro
     ghost runs 2-12 px from the cyan line across the whole visible
     trajectory (it is a tenth of forward thrust), and the cyan ribbon
     is 1-3 px wide -- so it painted straight over the magenta line.
     Ghosts now draw after the cyan block. The compute still happens in
     the old spot; only the draw call moved.
  2. **1 px was too thin.** Beside the cyan ribbon a 1 px ghost reads as
     colour fringing on the cyan line rather than a line of its own.
     Now `THRUST_PREVIEW_WIDTH = 2`.
  3. **The palette was too dim** for 1-2 px on a near-black field --
     (80,210,120)/(210,90,200) -> (120,255,140)/(255,120,240).
  Also added endpoint pips, so where the lines bundle near the ship you
  can still see three distinct tips.
- **Tap length reverted to 0.1 s after a detour to 0.5 s.** With the draw
  fixed, rendered comparison sheets at 0.10 / 0.25 / 0.50 s show 0.1 s is
  not merely adequate but *best*: at 0.5 s (110 dv) the forward ghost
  leaves the frame within a couple of seconds, so you lose the shape of
  the orbit it puts you in, which is the whole point of the overlay.
- **Added an always-on feedback path for the peek key.** Holding Tab now
  always produces a HUD line: either the dv readout, or
  `THRUST PEEK unavailable: <reason>` (landed / build menu open / ship
  destroyed). Previously a suppressed peek drew and said nothing, which
  is indistinguishable from Tab not registering at all -- and that
  ambiguity is precisely what made this playtest report hard to act on.
  Worth generalising: any held-key overlay should say why it is doing
  nothing.
- Verified by rendering at the default start state at zoom 0.25, 1.0 and
  2.0: three clearly separated lines at all three. **Still not played in
  a real window by me** -- Matthew's next run is the real test.
- **Playtest #2 on the thrust ghosts: "estimation too low quality and
  maybe too much thrust ... how many points are we devoting?" Both
  complaints had one root cause -- the ghosts inherited the cyan line's
  30 s horizon.** Answer to the question as it stood: 150 points per
  ghost, but drawn at `THRUST_PREVIEW_STRIDE = 8`, so only **18
  segments** ever reached the screen against the cyan line's 300. That
  is the visible kinking. The stride had been copied from
  `PREDICT_DRAW_STRIDE` without adjusting for the ghost having a twelfth
  as many points to spend.
- **The deeper fault was worse than the kinking.** Spending 150 steps
  over 30 s forces `dt = 0.2 s`, twelve times `PHYSICS_DT`. Measured a
  **zero-thrust** ghost against the cyan line: it missed by **265.7 u**
  on integration error alone. That is a false-deviation floor -- for a
  0.02 s tap the true deviation is 411 u, so ~65% of what the overlay
  drew was its own error. The step-budget curve is also a cliff, not a
  slope: 150 -> 265.7 u, 300 -> 249.2, 600 -> 244.1, then 1200 -> 2.2.
  Nothing short of near-`PHYSICS_DT` is trustworthy over 30 s.
- **Fix: decouple the ghost horizon from `predict_seconds` and run it at
  the live physics step.** New `THRUST_PREVIEW_SECONDS = 5.0`, passed as
  `dt=PHYSICS_DT` rather than a step budget, replacing
  `THRUST_PREVIEW_TARGET_STEPS` entirely. Stride 8 -> 1. Results, all
  three complaints at once and for no extra CPU:
  - 18 on-screen segments -> **300**, matching the cyan line exactly.
  - False-deviation floor 265.7 u -> **0.000000 u**. The ghost is now
    bit-equivalent to the cyan integrator (PROGRAM_FLOW invariant 3), so
    every visible pixel of deviation is thrust.
  - "Too much thrust" fixed without touching the tap: a 22 dv kick over
    30 s puts the forward ghost in a different orbit off the top of the
    screen; the *same* kick over 5 s is a small clean deviation that
    stays beside the cyan line. The tap was never the problem -- the
    extrapolation was. `THRUST_PREVIEW_BURN_SECONDS` stays 0.1.
  - Cost 3.44 -> **3.46 ms/frame**. Essentially free, because a short
    horizon at fine dt costs about what a long horizon at coarse dt did.
  Cost is now bounded by an absolute cap rather than tracking
  `predict_seconds`, so pushing the cyan predict out with `*` no longer
  drags the ghosts' bill up with it.
- Verified by rendering the default start state at zoom 0.25 / 1.0 / 2.0:
  smooth curves, three clearly distinct lines, ghosts staying next to the
  ship. **Open item for Matthew:** the magenta retro ghost deviates only
  ~3 px at zoom 0.25 (12.5 px at 1.0), because retro genuinely is a tenth
  of forward thrust. No single tap length fixes both ends of a 10:1
  ratio. Left honest; if it needs to read at low zoom the options are a
  bigger `THRUST_PREVIEW_BURN_SECONDS` (both ghosts grow) or a separate
  retro multiplier (ghosts then show different tap lengths, which needs a
  clearer HUD label).
- **Measurement worth flagging to Matthew, unrelated to this feature:**
  on this box (Python 3.14 / pygame-ce 2.5.7) the *existing* cyan
  predict costs ~57 ms per refresh, i.e. ~19 ms/frame amortized, which
  already exceeds the 16.7 ms 60 FPS budget on its own. Root cause is
  `predict_trajectory` doing ~15 `Body.position_at` evaluations per step
  (2x `gravity_at_t` over every body plus the collision sweep), each
  recursive + trig, at ~32 us/step for 1800 steps. Not touched this
  session -- it's a real optimisation (share one body-position sample
  per timestep across all three trajectories) but it lands squarely on
  the invariants in PROGRAM_FLOW.md, so it wants its own session.
- Headless-verified: both ghosts render in their own colours, 151
  samples each, W-fan/S-fan ratio 7.6:1, all four trim rungs feed
  through to the drawn path, `draw_hud` renders the new line at every dv
  magnitude, and `compute_thrust_preview` on a landed ship returns
  cleanly. **Still not playtested in a real window** -- no display this
  session.
- **Discussed, not built: live thrust-preview ghosts** -- HUD lines
  showing where you would end up if you held W or S for 0.1 s. Verdict
  and proposed shape recorded in TASKS.md; the short version is that
  plan mode already does exactly this (`PLAN_BURN_DURATION_DEFAULT` is
  literally `0.1`), so the feature is "plan mode, live, locked to
  prograde/retro", and it should be a *held peek* rather than always-on.
- Note for Matthew: your working tree still has two uncommitted tweaks I
  deliberately did **not** fold into this commit -- `Camera.__init__`
  zoom `1.0 -> 0.25`, and a stray blank-line pair in `main()` near the
  closest-approach target pick. Left them for you to keep or drop.

## 2026-08-17

- **All three random-universe HUD readouts now report planets + moons +
  seed** (were: quick-roll showed planets + seed; Shift+R and Ctrl+Shift+R
  showed seed only). Unified behind a new module-level helper
  `random_universe_hud_text(bodies, sun, seed)` (defined right after
  `build_world_for`) so the three entry vectors -- Shift+R, Ctrl+Shift+R
  custom seed, Ctrl+Alt+Shift+N quick-roll -- can't drift apart. Counts
  are derived from the freshly-built world: planets = sun's direct
  children, moons = everything orbiting a non-sun body (sub-moons
  included; moon total caps at `RANDOM_MOONS_TOTAL_MAX = 4`).
  Pluralisation per-count.
- **Shift+R message moved to after `build_world_for`.** It used to be
  built *before* the rebuild, so it read the outgoing world's `bodies`
  (fine when it only printed the seed, wrong now that it counts bodies).
  Guarded on a `rolled_fresh` flag; plain R (rebuild, no Shift) stays
  silent exactly as before.
- Compiles clean (`py_compile`); playtest-observed only, no physics/
  logic path touched. Change is in `ypilot.py`; uncommitted pending
  Matthew's native commit.

## 2026-06-10

- **Drafted RAIDS_PLAN.md (gameplay arc step 2) -- design only, no
  code.** Core calls proposed: turrets/printers get `STRUCTURE_HP = 3`
  and collapse into 40%-of-cost scrap (pad survives); beam-repair at
  5 ore/HP while landed near; new kamikaze raider *intent* on the
  existing Enemy chassis (targets nearest structure, 1 HP damage in an
  18 arc-px blast, converts to chaser if no structures exist -- system
  inert until the player builds); wave director CALM -> 10 s WARNING
  telegraph -> RAID burst, threat driven by structures + lifetime ore
  (not wall-clock), waves target the most-fortified body so Frostbite
  runs stay calm; trickle slows 9 s -> 18 s between waves; F10
  semantics preserved; save v2 -> v3 with defaulted fields. Phased
  A (HP plumbing) / B (raider) / C (director), one session each,
  playtest-gated. Five open questions for Matthew at the bottom of the
  doc; TASKS.md step-2 bullet now points there and is marked blocked
  on those answers + the step-1 playtest.
- **Bonus ore sprinkle at universe generation** (Matthew's ask: more
  random ore overall, current arrangement intact, exploration still
  driven). New `roll_bonus_deposits()` in `build_world_for`: middle
  planets roll 0–2 bonus deposits (40/35/25), landable moons 0–1
  (35%), starter/destination quotas (2/6) untouched. Salted seeded RNG
  (`seed ^ 0x0DE5EF8`, battery convention) — same seed, same layout;
  salt picked so the default world (seed 0) rolls Ember 1 / Moon 0,
  softening Ember's "no ore" rule per Matthew's "both worlds" call.
  Monte Carlo over 3000 seeds: mean +2.03 bonus, 38% roll zero (mostly
  small systems with no middle bodies), max +10 on 6-planet sprawls.
  Bonus deposits append after fixed quotas so by-index save restore
  stays compatible (old saves load; bonus deposits arrive full).
  Noted in passing: base deposit *angles* jitter from the global RNG,
  so they were never seed-deterministic — pre-existing, only counts
  and bonus angles are pinned. DESIGN.md body-roles + allocation
  sections updated. Awaiting playtest alongside the scrap economy.
- **Jun-7 truncated blob had also been PUSHED.** Matthew's `git push`
  bounced (non-fast-forward): remote tip `74037da` turned out to be the
  truncated-WORKLOG commit from the 2026-06-07 stale-cache incident --
  its blob ends mid-sentence ("earlier a", no trailing newline) and
  drops the back half of the 2026-05-19 section. Local `ef48073` is the
  good redo; local main is the correct lineage. Resolution: do NOT
  pull/merge (would resurrect the truncated file) -- force-push over
  it. Handed Matthew `git push --force-with-lease origin main`.


## 2026-06-08

- **Shipped step 1 of the gameplay-elements arc: scrap economy +
  missile rebalance** (planned with Matthew 2026-06-07; his pitch:
  "shot craft drop materials that fall back onto the surface as
  scrap"). Kills no longer credit `ENEMY_KILL_REWARD = 6` instantly --
  constant retired. Destroyed UFOs shed a `Debris` chunk (ballistic,
  same leapfrog + `gravity_at_t` as missiles) that lands as a minable
  scrap pile (`SCRAP_VALUE = 12`); terrain-crash kills pile up directly
  at the impact point; missile-killed AA batteries collapse into a
  `SCRAP_VALUE_BATTERY = 40` pile at their mount. Piles merge within
  `SCRAP_MERGE_DIST = 14` arc-px, cap at `SCRAP_MAX_PILES = 30`,
  vanish when emptied; save/load round-trips piles + in-flight chunks.
  Missiles: `MISSILE_PRINTER_COST` 150 -> 100, `MISSILE_ORE_COST`
  30 -> 10 (was -24 ore net per kill vs the +6 credit = never built;
  now ~break-even per kill if salvaged, profitable on blast
  multi-kills). HUD says SALVAGING over scrap. DESIGN.md (new "Scrap
  economy" section + tunables table), CONTROLS.md build-menu row, and
  TASKS.md (arc status) updated.
- **Verified headless only** (no display in the Cowork session):
  py_compile + AST, then a runtime suite against the staged module --
  enemy terrain-crash -> pile, debris fall -> land -> merge, pile cap
  with smallest-culled, ship salvage via `_mine`, save/load round-trip
  incl. falling debris. **Not playtested.** Feel-tuning knobs flagged
  in TASKS.md.
- **Sandbox landmine #2: stale attribute cache (and a truncated blob
  in history).** After Windows-side edits (Claude's file tools), bash's
  mount view keeps the OLD byte size -- reads truncate at it, and `git
  add` commits truncated blobs. Yesterday's `74037da` worklog commit
  was exactly that: blob cut at the stale 2302-byte size (fixed today
  by amending the tip with the correct blob before stacking this
  session's commit). ypilot.py edits were verified around the bug by
  staging a fresh-inode copy and diffing against `git show
  HEAD:ypilot.py` -- which also caught a one-word transcription error.
  Safe patterns now documented in CLAUDE.md ("Cowork sandbox
  landmines"); doc edits this session were done bash-side
  (temp + rm + mv = fresh inode) to keep bash authoritative.

## 2026-06-07

- **`BRAKE_KP = 4.0` verdict: keeping it.** Matthew reports no
  overshoot/oscillation near zero relative velocity after ~3 weeks of
  play since the 2026-05-19 bump. The "back off to ~3.0 if it hunts"
  watch-item is closed.
- **Added `.gitattributes` (`* text=auto`, `*.bat eol=crlf`, binary
  rules) and committed as `5de7c40`.** Fixes the phantom whole-file
  diffs (CRLF worktree vs LF-in-repo with nothing bridging them) that
  appeared after the Jun 5 exe rebuild. Renormalize staged zero files --
  repo blobs were already LF -- so this is purely a compare-filter fix,
  no content rewrite.
- **Sandbox/git landmine discovered (future Claude sessions, read
  this):** the Cowork sandbox mounts this folder with delete-protection
  -- `unlink` fails with EPERM and, worse, **rename-over-an-existing-file
  zero-fills the target**. Any porcelain index write (`git add`,
  `git commit`) renames over `.git/index` and corrupts it
  ("bad signature 0x00000000"). Recovery + working pattern:
  1. Request file-delete permission (`allow_cowork_file_delete`) FIRST.
  2. `rm .git/index .git/index.lock` then `git reset` -- rebuilding
     works because rename-to-a-NEW-path is fine.
  3. Commit via plumbing with a temp index outside the mount:
     `GIT_INDEX_FILE=/tmp/idx git read-tree HEAD` -> `git add` ->
     `git write-tree` -> `git commit-tree` -> `rm .git/refs/heads/main`
     -> `git update-ref refs/heads/main <new>` -> `rm .git/index` ->
     `git reset`. Every `.git` write is then create-new, never
     rename-over.
  Or just hand the commit commands to Matthew to run natively.

## 2026-05-19

- **Bumped `BRAKE_MAX_ACCEL` from `SHIP_THRUST * 3.0` → `SHIP_THRUST * 5.0`** (line 371).
  Matthew was having trouble landing on heavy bodies — H-hold was hitting the
  3× ceiling and couldn't fully cancel gravity + approach velocity in time.
  Trade-off: fuel burn rate now caps at 5× the W-key rate when the clamp is
  active (mostly during initial high-speed braking and low-altitude hovers
  near big planets).
- **Bumped `BRAKE_KP` from `2.0` → `4.0`** (line 370) in the same session,
  follow-up to the ceiling bump above. Doubles how hard the brake-assist
  controller pulls per unit of velocity error, so deceleration starts
  earlier and is sharper. Watch for overshoot/oscillation near zero
  relative velocity — if it hunts visibly, back off to ~3.0.
- **Added `MAX_LANDABLE_SURFACE_GRAVITY` (= `BRAKE_MAX_ACCEL * 0.6` ≈ 660)**
  and constrained `make_random_solar_system` so no planet or moon rolls a
  surface gravity above it. Default world is unaffected (max default
  surface g ≈ 496). Random planets clamp `mu` upper bound given rolled
  radius; random moons additionally bump radius up if the parent is heavy
  enough that even the min mu-fraction would overshoot. Single-knob
  escape hatch for a "gas-giants" fork: raise the constant or set it to
  `math.inf` to disable the check; nothing else in the generator needs
  changing. Monte-Carlo verified 0/20000 rolls exceed cap.
- **Updated DESIGN.md** to reflect the brake-assist tunes and the new
  landability cap: rewrote the brake-assist clamp paragraph (the old
  "can't deliver more thrust than the engines could" justification no
  longer holds at 5× — reframed as "matches Shift+W boost ceiling"),
  refreshed the Tunable constants table (`BRAKE_KP`, `BRAKE_MAX_ACCEL`,
  new `MAX_LANDABLE_SURFACE_GRAVITY` row), and added a Random
  universes § Layout bullet documenting the (mu, radius) constraint
  alongside the existing eccentricity and shell-spacing rules.
- **Fixed CLAUDE.md** -- it said "the repo root is not a git repository",
  which is wrong (it is, with a remote at MatthewCarven/Python-YPilot).
  The .git folder being hidden by Windows default is what fooled the
  doc's author. Noted the `ls -la` workaround and that commit history
  is a primary source of truth.
