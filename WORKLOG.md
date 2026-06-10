# Worklog

## 2026-06-10

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
