# Worklog

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
