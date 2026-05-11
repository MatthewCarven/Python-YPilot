"""
build.py — compile YPilot to a standalone Windows .exe via PyInstaller.

Usage:
    python build.py             # build, output goes to dist/YPilot.exe
    python build.py --clean     # also nuke build/ and dist/ first
    python build.py --debug     # build with console attached (prints visible)

What it bundles
---------------
- Python interpreter
- pygame-ce (or pygame, whichever is installed)
- Standard library bits the game touches

What it does NOT bundle
-----------------------
- ffmpeg (F9 video recording). The game silently no-ops F9 if ffmpeg
  isn't on PATH at runtime, so this is graceful. If you want F9 to
  work on a machine without ffmpeg installed system-wide, drop
  ffmpeg.exe next to YPilot.exe — Recorder.start uses Popen("ffmpeg",
  ...) which Windows resolves against the executable's directory
  before PATH.

Cross-compile note
------------------
PyInstaller does NOT cross-compile. To produce a Windows .exe you
must run this script on a Windows machine with Python + pygame-ce
installed. Running on macOS or Linux produces a binary for that OS,
not a .exe.

Where captures/ and saves/ end up
---------------------------------
Next to YPilot.exe. The game's `_app_dir()` helper checks `sys.frozen`
and returns either `sys.executable`'s parent directory (frozen build)
or `__file__`'s parent (normal `python ypilot.py` run). Both F12
screenshots, F9 videos, and Ctrl/Shift+F1..F9 quicksaves write to
`captures/` and `saves/` subfolders alongside the .exe — like any
normal Windows app. Folders are created on first write.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).parent.resolve()
SCRIPT = HERE / "ypilot.py"
DIST_DIR = HERE / "dist"
BUILD_DIR = HERE / "build"
SPEC_FILE = HERE / "YPilot.spec"
ICON_FILE = HERE / "ypilot.ico"           # optional; used if present


def info(msg: str) -> None:
    print(f"[build] {msg}")


def err(msg: str) -> None:
    print(f"[build] ERROR: {msg}", file=sys.stderr)


def ensure_pygame() -> None:
    """Sanity check — if pygame isn't importable, the build will look
    succeed but the resulting .exe will crash on launch. Fail loud here
    instead."""
    try:
        import pygame  # noqa: F401
    except ImportError:
        err("pygame-ce is not installed in this Python environment.")
        err("Run:  pip install pygame-ce")
        sys.exit(1)


def ensure_pyinstaller() -> None:
    """Install PyInstaller on demand. Most folks won't have it sitting
    around, and the alternative ('please pip install pyinstaller and try
    again') is friction that adds nothing."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        info("PyInstaller not installed — installing now.")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "--upgrade", "pyinstaller",
            ])
        except subprocess.CalledProcessError as ex:
            err(f"pip install pyinstaller failed: {ex}")
            sys.exit(1)


def clean_artifacts() -> None:
    """Wipe previous build outputs. Useful when PyInstaller's cache
    misbehaves or when you've changed bundling flags."""
    for path in (DIST_DIR, BUILD_DIR, SPEC_FILE):
        if path.exists():
            info(f"removing {path.relative_to(HERE)}")
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def build(debug: bool) -> Path:
    """Invoke PyInstaller. Returns the path to the produced .exe."""
    if not SCRIPT.exists():
        err(f"ypilot.py not found at {SCRIPT}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                 # single .exe (slower cold start but tidy)
        "--name", "YPilot",
        "--clean",                   # fresh build, ignore PyInstaller cache
        "--noconfirm",               # don't prompt before overwriting dist/
    ]
    if debug:
        # Keep the console window open so print() / tracebacks are
        # visible. Useful for diagnosing "exe opens then disappears"
        # mystery crashes.
        cmd.append("--console")
    else:
        # Production: no console window pops up behind the game.
        cmd.append("--windowed")

    if ICON_FILE.exists():
        cmd += ["--icon", str(ICON_FILE)]
        info(f"using icon {ICON_FILE.name}")

    cmd.append(str(SCRIPT))

    info("running: " + " ".join(cmd[1:]))
    try:
        subprocess.check_call(cmd, cwd=HERE)
    except subprocess.CalledProcessError as ex:
        err(f"PyInstaller failed with exit code {ex.returncode}")
        sys.exit(ex.returncode)

    # PyInstaller names the binary 'YPilot.exe' on Windows, plain
    # 'YPilot' on Linux/mac. Look for both so cross-platform dev
    # builds at least surface a useful path.
    candidates = [DIST_DIR / "YPilot.exe", DIST_DIR / "YPilot"]
    for c in candidates:
        if c.exists():
            return c
    err(f"build finished but no binary found in {DIST_DIR}")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile YPilot into a standalone executable.",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Nuke build/, dist/, and YPilot.spec before building.",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Build with a console window attached (shows print / tracebacks).",
    )
    args = parser.parse_args()

    info(f"working dir: {HERE}")

    if args.clean:
        clean_artifacts()

    ensure_pygame()
    ensure_pyinstaller()

    exe = build(args.debug)
    size_mb = exe.stat().st_size / (1024 * 1024)
    info(f"done — {exe}  ({size_mb:.1f} MB)")
    if sys.platform != "win32":
        info("(note: this is a non-Windows binary because PyInstaller can't"
             " cross-compile. Run on Windows to get a .exe.)")


if __name__ == "__main__":
    main()
