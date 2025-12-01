"""
@PURPOSE: Utilities for resolving data/config paths in both source and frozen builds
@OUTLINE:
  - get_runtime_base(): detect project root or PyInstaller temp dir
  - resolve_runtime_path(): convert relative paths to absolute runtime paths
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

USER_DATA_ROOT = Path.home() / "TemuWebPanel"


@lru_cache(maxsize=1)
def get_runtime_base() -> Path:
    """Return the base directory for resolving bundled resources."""

    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base)
    return Path(__file__).resolve().parents[2]


def resolve_runtime_path(path_like: str | Path) -> Path:
    """Resolve ``path_like`` against user overrides, then runtime base, then repo root."""

    candidate = Path(path_like)
    if candidate.is_absolute():
        return candidate

    user_candidate = (USER_DATA_ROOT / candidate).resolve()
    if user_candidate.exists():
        return user_candidate

    base_path = get_runtime_base()
    absolute_candidate = (base_path / candidate).resolve()
    if absolute_candidate.exists():
        return absolute_candidate

    project_root = Path(__file__).resolve().parents[2]
    return (project_root / candidate).resolve()
