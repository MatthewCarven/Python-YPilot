# Tasks

Near-term in-progress design decisions and todos. Longer-term forks /
"may never happen" items live in [DESIGN.md § Deferred TODO](DESIGN.md).

---

## Takeoff steering lock — rethink for plan-mode-initiated launches

**Problem.** `TAKEOFF_LOCK_SECONDS = 0.30` suppresses mouse aim + turn
keys and forces full boost forward for 0.3s after liftoff. Originally
fixes the "ship skitters tangentially if cursor is off-vertical at
liftoff" bug (see PROGRAM_FLOW.md § Bug-fix history). But when the
player uses plan-mode to take off, the lock overrides the planned burn
direction — the orange line lies about where the ship will actually
go.

(The launch-pad bump `LAUNCH_PAD_HEIGHT = 5.0` is a *separate* fix for
the trailing-side re-grounding loop. That stays regardless.)

### Options

**Option 1 — Yank the lock entirely.** Bad-cursor takeoffs skitter
horizontally for ~1s until centrifugal effect spins them free. Annoying
but not fatal. Plan-mode takeoffs become honest. Survival-of-the-fittest
vibe. ~3 lines.

**Option 2 — Reduce duration to ~0.10–0.15s.** Half-measure. Probably
feels mushy in both directions. Skip this one.

**Option 3 — Skip the lock when `pending_maneuvers` is non-empty.**
Surgical fix for the actual complaint: trust the player when they've
shown intent via the planner, hand-hold when they haven't. ~3 lines.

**Option 4 — Pre-load the takeoff burn into plan-mode.** Combines with
option 3. Two sub-flavors:
- **4A (preferred): pre-set preview burn duration** to the takeoff
  equivalent (~1.5s = `TAKEOFF_LOCK_SECONDS × THRUST_BOOST_SCALE`) on
  plan-mode-entry while landed. Mouse still aims the burn; orange line
  immediately shows takeoff trajectory. Single-burn takeoff = Space,
  aim, Enter. ~5 lines + option 3.
- **4B: auto-push takeoff to queue.** Pushes a radial-out 1.5s burn
  onto `maneuver_queue` on plan-mode-entry while landed; preview slot
  becomes the second burn. Downside: mouse now aims a future burn
  immediately, not the takeoff — feels wrong if the player entered
  plan-mode specifically to plan the takeoff. ~15 lines + option 3.

### Current recommendation

Start with **option 4A + option 3**. Smallest change that solves the
"orange line is honest about takeoff" goal without changing what the
mouse means in plan-mode. If after playtesting you want simultaneous
takeoff + next-burn planning without an N press, promote to 4B — the
queue infrastructure already supports it.

### Next step

Playtest current behavior end-to-end (especially Frostbite expedition
takeoff from Planet), then pick option. The bug-fix-history concern
about "ship skitters tangentially" may not survive contact with current
tunings — current launch-pad bump + sticky-on-engage brake-assist might
already cover the worst case.

---

## Persistent universe choice across launches

**Problem.** `current_universe` is held only in memory. If you roll a
fun seed with `Shift+R`, play for a while, then quit, the next launch
starts on the default world and the seed is gone unless you wrote it
down. Slightly frustrating after a memorable roll.

### Sketch

A small `saves/last_universe.json` (or `.last_universe.json` in repo
root) that holds the current universe spec:

```json
{"type": "random", "seed": 1234567890}
```

or

```json
{"type": "default"}
```

**Write on:** `R` (rebuild current), `Shift+R` (roll new), seed-prompt
commit, and probably on quicksave too (so a load doesn't desync the
"last universe" pointer from what's actually active).

**Read on:** startup, before `build_world_for`. Best-effort: missing
file or corrupt JSON → fall back to `{"type": "default"}`. No version
gating needed — the universe spec format is tiny and stable.

**Reuse:** the atomic-write pattern (`.tmp` + rename) from
`save_session` keeps the file safe across crashes.

### Difficulty

~15 lines. One read on startup, one write helper called from a few
spots. Should not touch the save-slot semantics (numbered slots already
embed the universe in each save file; this is a separate "last active"
pointer).

### Open question

Where does the file live? Options:
- **`saves/last_universe.json`** — fits the existing folder, gitignored
  for free.
- **`.last_universe.json` in repo root** — separate from save slots,
  hidden by `.` prefix. Would need a `.gitignore` line.

Slight lean toward `saves/last_universe.json` for the no-new-gitignore-
line win, but it's arguably misleading to put a non-save in `saves/`.

