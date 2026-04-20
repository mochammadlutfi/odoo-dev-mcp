"""Cross-module inspection for Odoo addons.

Answers questions that require walking many modules at once:
- Which modules declare ``_inherit = 'res.partner'``?
- Which modules depend on ``stock``?
- What is the inheritance chain of a model?

Shares the mtime-aware cache with ``introspection.analyze_odoo_module`` so
repeat calls across tools are cheap.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import module_cache
from .introspection import _parse_manifest


def _extract_model_records(py_file: Path) -> list[dict[str, Any]]:
    """Return one record per model class in a file: {_name, _inherit, fields}."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []

    records: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        rec: dict[str, Any] = {"class": node.name, "_name": None, "_inherit": None, "fields": []}
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0]
                if isinstance(target, ast.Name):
                    if target.id in {"_name", "_inherit"} and isinstance(stmt.value, ast.Constant):
                        rec[target.id] = stmt.value.value
                    elif target.id == "_inherit" and isinstance(stmt.value, (ast.List, ast.Tuple)):
                        rec["_inherit"] = [
                            el.value for el in stmt.value.elts
                            if isinstance(el, ast.Constant) and isinstance(el.value, str)
                        ]
                    elif _is_fields_call(stmt.value):
                        rec["fields"].append(target.id)
        if rec["_name"] or rec["_inherit"]:
            records.append(rec)
    return records


def _is_fields_call(value: ast.expr) -> bool:
    """True if ``value`` looks like ``fields.Char(...)``."""
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and isinstance(value.func.value, ast.Name)
        and value.func.value.id == "fields"
    )


def _module_records(module_path: Path) -> dict[str, Any]:
    """Shape used for graph queries. Cacheable."""
    manifest = _parse_manifest(module_path)
    models_dir = module_path / "models"
    records: list[dict[str, Any]] = []
    if models_dir.is_dir():
        for py in sorted(models_dir.glob("*.py")):
            if py.name == "__init__.py":
                continue
            records.extend(_extract_model_records(py))
    return {
        "manifest": manifest or {},
        "models": records,
    }


def _walk_addons(addons_path: str) -> list[tuple[Path, dict[str, Any]]]:
    root = Path(addons_path).expanduser()
    out: list[tuple[Path, dict[str, Any]]] = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not (child / "__manifest__.py").exists():
            continue
        data = module_cache.get_or_compute(child, _module_records)
        out.append((child, data))
    return out


def _inherit_list(rec: dict[str, Any]) -> list[str]:
    inh = rec.get("_inherit")
    if inh is None:
        return []
    return inh if isinstance(inh, list) else [inh]


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def find_models_inheriting(model_name: str, addons_path: str) -> str:
        """List modules that extend a given Odoo model (``_inherit``)."""
        hits: list[str] = []
        for module_path, data in _walk_addons(addons_path):
            for rec in data["models"]:
                if model_name in _inherit_list(rec):
                    hits.append(f"- **{module_path.name}** ({rec['class']})")
                    break
        if not hits:
            return f"No modules in {addons_path} inherit {model_name!r}"
        return f"# Modules inheriting {model_name}\n\n" + "\n".join(hits)

    @mcp.tool()
    def find_dependents(module_name: str, addons_path: str) -> str:
        """List modules that declare ``module_name`` in their depends."""
        hits: list[str] = []
        for module_path, data in _walk_addons(addons_path):
            depends = data["manifest"].get("depends", [])
            if module_name in depends:
                hits.append(f"- **{module_path.name}**")
        if not hits:
            return f"No modules in {addons_path} depend on {module_name!r}"
        return f"# Modules depending on {module_name}\n\n" + "\n".join(hits)

    @mcp.tool()
    def get_inherit_chain(model_name: str, addons_path: str) -> str:
        """Trace the `_inherit` chain upward from the given model.

        Returns the parent path(s) found across all modules. Does not touch
        Odoo's internal registry — pure static analysis.
        """
        chain: list[str] = [model_name]
        seen = {model_name}
        frontier = [model_name]
        records_by_name: dict[str, list[str]] = {}
        for _module_path, data in _walk_addons(addons_path):
            for rec in data["models"]:
                name = rec.get("_name") or (rec.get("_inherit") if isinstance(rec.get("_inherit"), str) else None)
                if not name:
                    continue
                records_by_name.setdefault(name, []).extend(_inherit_list(rec))
        while frontier:
            nxt: list[str] = []
            for n in frontier:
                for parent in records_by_name.get(n, []):
                    if parent not in seen:
                        seen.add(parent)
                        chain.append(parent)
                        nxt.append(parent)
            frontier = nxt
        if len(chain) == 1:
            return f"No parents found for {model_name!r} in {addons_path}"
        return f"# Inherit chain for {model_name}\n\n" + " → ".join(chain)

    @mcp.tool()
    def list_model_fields(model_name: str, addons_path: str) -> str:
        """Aggregate fields declared across every module touching a model."""
        by_module: dict[str, list[str]] = {}
        for module_path, data in _walk_addons(addons_path):
            for rec in data["models"]:
                touches = rec.get("_name") == model_name or model_name in _inherit_list(rec)
                if touches and rec["fields"]:
                    by_module.setdefault(module_path.name, []).extend(rec["fields"])
        if not by_module:
            return f"No fields found for {model_name!r} in {addons_path}"
        lines = [f"# Fields on {model_name} across modules"]
        for mod, fields in sorted(by_module.items()):
            lines.append(f"\n## {mod}")
            lines.extend(f"- {f}" for f in sorted(set(fields)))
        return "\n".join(lines)
