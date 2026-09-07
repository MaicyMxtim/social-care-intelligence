"""Filesystem locations used by every script in this repository.

All paths are derived from the location of this file so that scripts work the
same way whether they are run from the repository root or from inside one of the
project folders.
"""
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT = SRC_DIR.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
DOCS_DIR = ROOT / "docs"
PROJECTS_DIR = ROOT / "projects"
MANIFEST_PATH = RAW_DIR / "MANIFEST.json"


def raw(filename: str) -> Path:
    """Return the full path to a file in the raw data directory.

    The function raises an error when the file is missing rather than returning
    a path that does not exist, because a missing raw file always means that
    scripts/download.py has not been run yet and the caller needs to know that
    straight away.
    """
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. Run 'python scripts/download.py' from the "
            f"repository root before running any analysis."
        )
    return path


def ensure_dirs() -> None:
    """Create the data directories if they do not already exist."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
