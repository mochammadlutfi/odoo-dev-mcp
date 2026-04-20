"""Introspect existing Odoo addons on disk.

Tools here read local module directories (manifest, models, views) without
touching upstream server code. Safe for large multi-addon workspaces.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import module_cache


def _parse_manifest(module_path: Path) -> dict[str, Any] | None:
    """Parse __manifest__.py as a literal Python dict via AST (no code exec)."""
    manifest = module_path / "__manifest__.py"
    if not manifest.exists():
        return None
    try:
        tree = ast.parse(manifest.read_text(encoding="utf-8"), mode="eval")
    except SyntaxError:
        return None
    if not isinstance(tree.body, ast.Dict):
        return None
    try:
        return ast.literal_eval(tree.body)
    except (ValueError, TypeError):
        return None


def _extract_model_attrs(py_file: Path) -> list[str]:
    """Find `_name=` / `_inherit=` assignments in model classes."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
                continue
            target = stmt.targets[0]
            if not (isinstance(target, ast.Name) and target.id in {"_name", "_inherit"}):
                continue
            if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                found.append(f"{target.id}={stmt.value.value!r}")
    return found


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_odoo_modules(addons_path: str) -> str:
        """List all Odoo modules under an addons directory with manifest summary."""
        root = Path(addons_path).expanduser()
        if not root.is_dir():
            return f"Error: not a directory: {addons_path}"

        rows: list[str] = []
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            manifest = _parse_manifest(child)
            if manifest is None:
                continue
            rows.append(
                f"- **{child.name}** v{manifest.get('version', '?')} "
                f"installable={manifest.get('installable', True)} "
                f"depends={manifest.get('depends', [])}"
            )

        if not rows:
            return f"No Odoo modules found in {addons_path}"
        return f"# Modules in {addons_path}\n\n" + "\n".join(rows)

    @mcp.tool()
    def analyze_odoo_module(module_path: str) -> str:
        """Summarize a single Odoo module: manifest + model files + view files.

        Results are cached by recursive mtime signature; repeated calls on an
        unchanged module return instantly.
        """
        path = Path(module_path).expanduser()
        if not path.is_dir():
            return f"Error: not a directory: {module_path}"
        return module_cache.get_or_compute(path, _build_module_summary)


def _build_module_summary(path: Path) -> str:
    manifest = _parse_manifest(path)
    if manifest is None:
        return f"Error: no valid __manifest__.py in {path}"

    models_dir = path / "models"
    model_files = sorted(models_dir.glob("*.py")) if models_dir.is_dir() else []
    model_attrs: list[str] = []
    for py in model_files:
        if py.name == "__init__.py":
            continue
        model_attrs.extend(_extract_model_attrs(py))

    views_dir = path / "views"
    view_files = sorted(p.name for p in views_dir.glob("*.xml")) if views_dir.is_dir() else []

    out = [
        f"# Module: {path.name}",
        f"- Display: {manifest.get('name', '?')}",
        f"- Version: {manifest.get('version', '?')}",
        f"- Category: {manifest.get('category', '?')}",
        f"- Depends: {manifest.get('depends', [])}",
        f"- Data entries: {len(manifest.get('data', []))}",
        "",
        f"## Models ({len(model_files)} files, {len(model_attrs)} declarations)",
        *([f"- {a}" for a in model_attrs] or ["_none detected_"]),
        "",
        f"## Views ({len(view_files)} files)",
        *([f"- {f}" for f in view_files] or ["_none_"]),
    ]
    return "\n".join(out)
