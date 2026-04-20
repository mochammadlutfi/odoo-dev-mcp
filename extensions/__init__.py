"""Fork-only extensions for odoo-dev-mcp.

Kept separate from upstream `odoo_mcp_server.py` so that `git pull upstream main`
stays conflict-free. Add new tools here via `register_all(mcp)`.
"""
from mcp.server.fastmcp import FastMCP


def register_all(mcp: FastMCP) -> None:
    from . import doc_index, introspection, module_cache, scaffolding, validators

    introspection.register(mcp)
    scaffolding.register(mcp)
    validators.register(mcp)
    doc_index.register(mcp)
    module_cache.register(mcp)
