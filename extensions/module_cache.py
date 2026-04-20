"""Cache for parsed Odoo module analysis.

Reduces repeat AST parsing cost for large addon workspaces. Cache is JSON at
``~/.cache/odoo-mcp/modules.json`` keyed by absolute module path. Each entry
stores a recursive mtime signature of the module tree; a miss on the signature
invalidates the entry automatically. Safe to wipe — it just rebuilds.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

CACHE_DIR = Path("~/.cache/odoo-mcp").expanduser()
CACHE_FILE = CACHE_DIR / "modules.json"


def _mtime_signature(module_path: Path) -> float:
    """Return the max mtime across all files under ``module_path``.

    Any add/remove/edit anywhere under the module changes this value, so a
    single float is enough to detect staleness without hashing every file.
    """
    latest = 0.0
    if not module_path.is_dir():
        return latest
    for root, _dirs, files in os.walk(module_path):
        for f in files:
            try:
                m = (Path(root) / f).stat().st_mtime
            except OSError:
                continue
            if m > latest:
                latest = m
    return latest


def _load_cache() -> dict[str, dict[str, Any]]:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict[str, dict[str, Any]]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache), encoding="utf-8")
        tmp.replace(CACHE_FILE)
    except OSError:
        pass  # cache failure must not break the tool


def get_or_compute(module_path: Path, builder) -> Any:
    """Return cached entry if fresh, else compute via ``builder(module_path)``."""
    key = str(module_path.resolve())
    sig = _mtime_signature(module_path)
    cache = _load_cache()
    entry = cache.get(key)
    if entry and entry.get("sig") == sig:
        return entry["value"]
    value = builder(module_path)
    cache[key] = {"sig": sig, "value": value}
    _save_cache(cache)
    return value


def invalidate(path: str | None = None) -> int:
    """Clear cache. If ``path`` given, drop only that entry. Returns entries removed."""
    if path is None:
        removed = len(_load_cache())
        try:
            CACHE_FILE.unlink(missing_ok=True)
        except OSError:
            return 0
        return removed
    cache = _load_cache()
    key = str(Path(path).expanduser().resolve())
    if key not in cache:
        return 0
    del cache[key]
    _save_cache(cache)
    return 1


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def invalidate_module_cache(module_path: str = "") -> str:
        """Drop cached module analysis. Empty path = clear all."""
        if module_path:
            n = invalidate(module_path)
            return f"Removed {n} cache entry for {module_path}"
        n = invalidate()
        return f"Cleared module cache ({n} entries)"

    @mcp.tool()
    def module_cache_stats() -> str:
        """Report cache location and entry count."""
        cache = _load_cache()
        return f"Cache at {CACHE_FILE}\nEntries: {len(cache)}"
