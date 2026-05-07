# Profile: python-bootstrap-library

The `versholn` library itself — a zero-dependency bootstrap and lazy import utility used by all
other repos.

**Repos using this profile:** `versholn`

---

## Purpose

`versholn` is a single-file Python library with no third-party dependencies of its own. It provides:

- `importx(symbol_path)` — lazy cross-repo import, cached
- `install_and_import(package)` — install from PyPI if missing, then import
- `setup()` / `doctor()` — clone and verify sibling repos
- `version_info()` — read compat.json and report current SHAs
- Bootstrap sequence for Cloud Run (clone deps at container startup)

---

## Rules

1. **`versholn.py` must have zero third-party dependencies** at module level or anywhere in its
   core. It must be importable with only stdlib.

2. **`importx` and `install_and_import` must be lazy and idempotent.** Repeat calls must return
   the cached result without side effects.

3. **`check_imports(repo_root)`** must accurately detect any non-stdlib symbol imported at module
   level across the repo. It is run by CI to enforce the module-level import rule.

4. **compat.json format changes require a full Docker rebuild** of dependent services — the
   pip-installed `versholn.py` baked into the image must be able to parse the new schema before
   it can self-update. Document this constraint prominently.

5. **Never log credentials, auth tokens, or PII** — not even in debug mode.

---

## Patterns

- Single-file library (`versholn.py`) — no package structure, no `__init__.py`.
- `importx` caches in a module-level dict, not in `sys.modules`.
- All public API functions have a clear docstring explaining the caching behaviour.
- `main()` at the bottom of `versholn.py` provides REPL-style workspace alignment.
  Toggle `OPERATION` before each run:
  ```python
  import runpy ; temp = runpy._run_module_as_main("versholn")
  ```
  See `AGENTS.base.md` § *Workspace Branch State* for full usage.

---

## Anti-patterns

- Adding any third-party `import` to `versholn.py` (even stdlib wrappers with optional deps).
- Changing `importx` signature in a backwards-incompatible way without updating all callers.
- Baking machine-specific paths into `versholn.py` itself.
