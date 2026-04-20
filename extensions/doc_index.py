"""SQLite FTS5 index for Odoo RST documentation.

Replaces the O(n) substring scan in upstream ``search_documentation`` with a
BM25-ranked FTS5 query. The index lives under ``~/.cache/odoo-mcp/`` and is
incrementally refreshed based on file mtime.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from odoo_mcp_server import DOCS_BASE_PATH, ODOO_VERSIONS, current_version

CACHE_DIR = Path("~/.cache/odoo-mcp").expanduser()
_UNDERLINE_CHARS = set("=-~`:'\"^_*+#<>")


def _connect(version: str) -> sqlite3.Connection:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_DIR / f"docs-{version}.db")
    conn.row_factory = sqlite3.Row
    return conn


def _fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _probe USING fts5(x)")
        conn.execute("DROP TABLE _probe")
        return True
    except sqlite3.OperationalError:
        return False


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS docs "
        "USING fts5(path, title, body, tokenize='porter unicode61')"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS file_meta(path TEXT PRIMARY KEY, mtime REAL)"
    )


def _extract_title(text: str) -> str:
    """First non-empty, non-underline line of an RST file."""
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if len(set(s)) == 1 and s[0] in _UNDERLINE_CHARS:
            continue
        return s[:200]
    return ""


def _build_or_refresh_index(version: str) -> dict[str, Any]:
    """Create or incrementally refresh the FTS index for ``version``."""
    conn = _connect(version)
    try:
        if not _fts5_available(conn):
            return {"error": "SQLite FTS5 not available in this Python build"}
        _ensure_schema(conn)

        existing = {
            row["path"]: row["mtime"]
            for row in conn.execute("SELECT path, mtime FROM file_meta")
        }
        base = DOCS_BASE_PATH / version
        on_disk: set[str] = set()
        added = updated = 0

        if base.exists():
            for file_path in base.rglob("*.rst"):
                rel = file_path.relative_to(base).with_suffix("").as_posix()
                on_disk.add(rel)
                mtime = file_path.stat().st_mtime
                prev = existing.get(rel)
                if prev is not None and prev >= mtime:
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                title = _extract_title(text)
                if prev is None:
                    added += 1
                else:
                    conn.execute("DELETE FROM docs WHERE path = ?", (rel,))
                    updated += 1
                conn.execute(
                    "INSERT INTO docs(path, title, body) VALUES(?,?,?)",
                    (rel, title, text),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO file_meta(path, mtime) VALUES(?,?)",
                    (rel, mtime),
                )

        removed = 0
        for rel in set(existing) - on_disk:
            conn.execute("DELETE FROM docs WHERE path = ?", (rel,))
            conn.execute("DELETE FROM file_meta WHERE path = ?", (rel,))
            removed += 1

        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        return {"added": added, "updated": updated, "removed": removed, "total": total}
    finally:
        conn.close()


def _fts_query(raw: str) -> str:
    """Convert a user query into a safe FTS5 expression.

    Splits on non-word chars and quotes each term, so ``api.depends`` becomes
    ``"api" "depends"`` (AND-match). Preserves only FTS5-safe tokens.
    """
    tokens = [t for t in re.split(r"[^\w]+", raw) if t]
    return " ".join(f'"{t}"' for t in tokens)


def _search(version: str, query: str, top_k: int) -> list[dict[str, Any]]:
    fts_q = _fts_query(query)
    if not fts_q:
        return []
    conn = _connect(version)
    try:
        if not _fts5_available(conn):
            return []
        _ensure_schema(conn)
        total = conn.execute(
            "SELECT COUNT(*) FROM docs WHERE docs MATCH ?", (fts_q,)
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT path, bm25(docs) AS rank, "
            "snippet(docs, 2, '<mark>', '</mark>', ' ... ', 32) AS snip "
            "FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?",
            (fts_q, top_k),
        ).fetchall()
        return [
            {"path": r["path"], "rank": r["rank"], "snippet": r["snip"], "total": total}
            for r in rows
        ]
    finally:
        conn.close()


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search_docs_fast(query: str, version: str = "", top_k: int = 5) -> str:
        """Fast BM25 search over Odoo RST docs backed by SQLite FTS5."""
        v = version if version and version in ODOO_VERSIONS else current_version["value"]
        if not query.strip():
            return "Error: query is empty"
        build = _build_or_refresh_index(v)
        if "error" in build:
            return f"Error: {build['error']}"
        try:
            results = _search(v, query, top_k)
        except sqlite3.OperationalError as exc:
            return f"Error: invalid FTS5 query '{query}': {exc}"
        if not results:
            return (
                f"No results for '{query}' in Odoo {v} docs "
                f"(indexed {build['total']} files)"
            )
        total, shown = results[0]["total"], len(results)
        out = [f'# Search: "{query}" (Odoo {v}) \u2014 top {shown} of {total} matches\n']
        for r in results:
            snip = " ".join(r["snippet"].split())
            if len(snip) > 200:
                snip = snip[:200].rstrip() + "..."
            out.append(f"## {r['path']} (bm25: {r['rank']:.2f})")
            out.append(f"> {snip}\n")
        return "\n".join(out)
