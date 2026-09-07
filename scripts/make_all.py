"""Run both projects in order and rebuild the portfolio index.

This is the one command that takes a fresh clone with downloaded data all the way
to finished output:

    python scripts/download.py
    python scripts/make_all.py

Each project is run in its own process so that a failure in one is reported
clearly rather than leaving the other half finished.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ["adult-variation", "childrens-workforce"]


def run(command: list[str], working_directory: Path) -> None:
    """Run one command and stop the whole build if it fails."""
    print(f"\n=== {' '.join(command)}  (in {working_directory.relative_to(ROOT)})")
    subprocess.run(command, cwd=working_directory, check=True)


def main() -> int:
    """Run every project, then rebuild the top level README."""
    manifest = ROOT / "data" / "raw" / "MANIFEST.json"
    if not manifest.exists():
        raise FileNotFoundError(
            "data/raw/MANIFEST.json is missing. Run 'python scripts/download.py' "
            "first, because nothing here reads anything except downloaded files."
        )

    for project in PROJECTS:
        run([sys.executable, "make_all.py"], ROOT / "projects" / project)

    run([sys.executable, "render_readme.py"], ROOT)
    print("\nEverything rebuilt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
