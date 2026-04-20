"""Validate Odoo module manifests and structure."""
from __future__ import annotations

import ast
from pathlib import Path

from mcp.server.fastmcp import FastMCP


_REQUIRED_KEYS = {"name", "version", "depends"}
_RECOMMENDED_KEYS = {"license", "category", "summary", "author"}


def _load_manifest_dict(manifest_file: Path) -> tuple[dict | None, str | None]:
    try:
        source = manifest_file.read_text(encoding="utf-8")
        tree = ast.parse(source, mode="eval")
    except (OSError, SyntaxError) as exc:
        return None, f"cannot parse manifest: {exc}"
    if not isinstance(tree.body, ast.Dict):
        return None, "manifest root is not a dict literal"
    try:
        data = ast.literal_eval(tree.body)
    except (ValueError, TypeError) as exc:
        return None, f"manifest contains non-literal values: {exc}"
    return data, None


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def validate_manifest(module_path: str) -> str:
        """Check __manifest__.py for required keys, valid types, and data files on disk."""
        path = Path(module_path).expanduser()
        manifest_file = path / "__manifest__.py"
        if not manifest_file.exists():
            return f"Error: {manifest_file} not found"

        manifest, err = _load_manifest_dict(manifest_file)
        if manifest is None:
            return f"Error: {err}"

        issues: list[str] = []

        missing_required = _REQUIRED_KEYS - manifest.keys()
        if missing_required:
            issues.append(f"Missing required keys: {sorted(missing_required)}")

        missing_recommended = _RECOMMENDED_KEYS - manifest.keys()
        if missing_recommended:
            issues.append(f"Missing recommended keys: {sorted(missing_recommended)}")

        depends = manifest.get("depends", [])
        if not isinstance(depends, list):
            issues.append(f"'depends' must be a list, got {type(depends).__name__}")

        for rel in manifest.get("data", []):
            if not (path / rel).exists():
                issues.append(f"data file missing on disk: {rel}")

        if not issues:
            return f"OK: {manifest_file} is valid"
        return f"# Manifest issues in {path.name}\n\n" + "\n".join(f"- {i}" for i in issues)
