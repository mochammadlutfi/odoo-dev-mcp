"""Scaffold new Odoo modules directly to disk (no copy-paste)."""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP


_MANIFEST_TEMPLATE = """{{
    'name': {display_name!r},
    'version': '{odoo_version}.1.0.0',
    'category': {category!r},
    'summary': {summary!r},
    'author': {author!r},
    'license': 'LGPL-3',
    'depends': {depends!r},
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}}
"""


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def scaffold_module_to_disk(
        target_dir: str,
        module_name: str,
        display_name: str,
        summary: str = "",
        author: str = "Lutfi",
        category: str = "Uncategorized",
        depends: list[str] | None = None,
        odoo_version: str = "18.0",
    ) -> str:
        """Write a minimal Odoo module skeleton to disk.

        Creates directory tree, __manifest__.py, __init__.py files, and
        an empty ir.model.access.csv. Refuses to overwrite existing module.
        """
        if depends is None:
            depends = ["base"]
        if not module_name.replace("_", "").isalnum() or not module_name.islower():
            return f"Error: module_name must be lowercase_with_underscores, got {module_name!r}"

        root = Path(target_dir).expanduser() / module_name
        if root.exists():
            return f"Error: {root} already exists, refusing to overwrite"

        (root / "models").mkdir(parents=True)
        (root / "views").mkdir()
        (root / "security").mkdir()
        (root / "static" / "description").mkdir(parents=True)

        manifest = _MANIFEST_TEMPLATE.format(
            display_name=display_name,
            odoo_version=odoo_version,
            category=category,
            summary=summary or display_name,
            author=author,
            depends=depends,
        )
        (root / "__manifest__.py").write_text(manifest, encoding="utf-8")
        (root / "__init__.py").write_text("from . import models\n", encoding="utf-8")
        (root / "models" / "__init__.py").write_text("", encoding="utf-8")
        (root / "security" / "ir.model.access.csv").write_text(
            "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n",
            encoding="utf-8",
        )

        return f"Created module at {root}\n\nNext: add models under {root}/models/ and import them in __init__.py"
