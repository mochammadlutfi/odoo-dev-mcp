"""Fork entry point: upstream server + local extensions.

Run this instead of `odoo_mcp_server.py` to get fork-only tools.
Upstream file stays untouched so `git pull upstream main` is trivial.
"""
from odoo_mcp_server import mcp
from extensions import register_all

register_all(mcp)

if __name__ == "__main__":
    mcp.run()
