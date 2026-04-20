# Fork Changelog

Fork of [mart337i/odoo-dev-mcp](https://github.com/mart337i/odoo-dev-mcp).
Base commit: `0ce7eda` (main).

## Structure

- `odoo_mcp_server.py` — upstream file, avoid editing directly
- `extensions/` — fork-only additions (tools, validators, scaffolders, cache, graph)
- `server.py` — new entry point that wraps upstream + loads extensions

Keep sync easy with upstream:

```bash
git fetch upstream
git checkout main
git merge upstream/main        # fast-forward if no local edits
git checkout develop
git merge main                 # bring updates into develop
```

## v0.1-fork (2026-04-21)

### Added

- `extensions/introspection.py` — `list_odoo_modules`, `analyze_odoo_module`
- `extensions/scaffolding.py` — `scaffold_module_to_disk`
- `extensions/validators.py` — `validate_manifest`
- `extensions/doc_index.py` — `search_docs_fast` (SQLite FTS5 over Odoo docs)
- `extensions/module_cache.py` — mtime-aware JSON cache + `invalidate_module_cache`, `module_cache_stats`
- `extensions/module_graph.py` — `find_models_inheriting`, `find_dependents`, `get_inherit_chain`, `list_model_fields`
- `server.py` — new entry point

### Fixed (upstream file, merged locally; not yet PR'd)

- `odoo_mcp_server.py` — `<tree>` → `<list>` for Odoo 17+ (`feature/fix-list-tag`)
- `odoo_mcp_server.py` — mutable default args in `create_odoo_module` + `create_security_rules` (`feature/fix-mutable-defaults`)
- `odoo_mcp_server.py` — template injection escaped via `repr()` (Python) and `html.escape()` (XML) (`feature/fix-template-injection`)

### Performance

- Cached `analyze_odoo_module` — ~13× speedup on warm cache (measured on Odoo's `sale` addon: 34.7 ms cold → 2.6 ms warm)
- `search_docs_fast` via SQLite FTS5 replaces linear RST scan; returns ranked snippets (200 char), dramatically smaller AI context

### Tools Count
- Upstream: 7 (`set_odoo_version`, `get_current_version`, `search_documentation`, `get_development_guidelines`, `create_odoo_module`, `create_odoo_model`, `create_odoo_view`, `create_security_rules` — 8 actually)
- Fork extensions: 11 (`list_odoo_modules`, `analyze_odoo_module`, `scaffold_module_to_disk`, `validate_manifest`, `search_docs_fast`, `invalidate_module_cache`, `module_cache_stats`, `find_models_inheriting`, `find_dependents`, `get_inherit_chain`, `list_model_fields`)
- **Total: 19**

## Future Work

- Upstream PRs for the three bug fixes (branches still live on origin)
- `base.menu_custom` hardcoded parent still broken in generator output
- Field type inference beyond `fields.X(...)` attribute access

## Branching

- `main` — mirrors `upstream/main`. No direct commits.
- `develop` — integration branch for fork features. Tag `v0.1-fork` here.
- `feature/*` — feature branches, kept for upstream PR candidacy.
