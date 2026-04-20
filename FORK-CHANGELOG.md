# Fork Changelog

Fork of [mart337i/odoo-dev-mcp](https://github.com/mart337i/odoo-dev-mcp).
Base commit: `0ce7eda` (main).

## Structure

- `odoo_mcp_server.py` — upstream file, avoid editing directly
- `extensions/` — fork-only additions (tools, validators, scaffolders)
- `server.py` — new entry point that wraps upstream + loads extensions

To keep sync easy with upstream:

```bash
git fetch upstream
git checkout main
git merge upstream/main        # fast-forward if no local edits
git checkout develop
git merge main                 # bring updates into develop
```

## Added (fork-only)

- `extensions/introspection.py` — `list_odoo_modules`, `analyze_odoo_module` (reads manifests + models via AST)
- `extensions/scaffolding.py` — `scaffold_module_to_disk` (actually writes module skeleton to disk)
- `extensions/validators.py` — `validate_manifest` (checks required keys, data file existence)
- `server.py` — new entry point

## Planned upstream PRs (bug fixes)

- [ ] Odoo 17+ uses `<list>`, not `<tree>` (odoo_mcp_server.py views)
- [ ] Mutable default args on `create_odoo_module`, `create_security_rules`
- [ ] XML/Python injection via f-string templates in generators
- [ ] `base.menu_custom` hardcoded parent menu doesn't exist

## Branching

- `main` — mirrors `upstream/main`. No direct commits.
- `develop` — integration branch for fork features.
- `feature/*` — PR-candidate branches for upstream contributions.
