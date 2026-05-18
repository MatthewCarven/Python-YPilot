# Tasks

Near-term in-progress design decisions and todos. Longer-term direction
lives in [DESIGN.md § Educational forks (planned)](DESIGN.md#educational-forks-planned);
the retired-feature graveyard is in [DESIGN.md § Deferred TODO](DESIGN.md#deferred-todo).

Nothing currently in flight — the last item (takeoff steering lock
rethink) shipped 2026-05-17 as a full retirement of the time-based
lock, replaced with state-based steering gating (`steering_active =
not self.landed`) plus a red HUD prompt while landed that reminds the
player to hold Shift+W for the boost needed to clear surface gravity.
See PROGRAM_FLOW.md "Bug-fix history" for the load-bearing details and
the "don't reintroduce a time-based lock" warning.
