# Profile: python-backend-service

FastAPI services deployed on Google Cloud Run, with a versholn bootstrap sequence that clones
application code and installs dependencies at container startup.

**Repos using this profile:** `nielsoln_site`

---

## Purpose

The backend is a FastAPI app running on Cloud Run. The container image is stable (bakes only Python
deps + `entrypoint.py`). Application code is cloned at startup from a specific git SHA. This gives
a fast two-speed deploy: code changes require no Docker rebuild.

---

## Rules

### Module-level imports in site code

`be/sites/*/be/*.py` must **not** import any package at module level unless it is baked into
`be/requirements.txt`.

| Dep type | How to import |
|---|---|
| Git-repo dep (versholn, geo_tools, …) | `versholn.importx("pkg.module.symbol")` inside the function |
| Light PyPI dep (not in requirements.txt) | `versholn.install_and_import("package")` inside the function |
| Heavy PyPI dep (osmnx, geopandas, …) | Already baked — `import osmnx` at module level is fine |

**Rationale:** `bootstrap()` runs before uvicorn in production, but local dev skips bootstrap
entirely. Module-level imports of unlisted packages crash the local server silently.

### Two-speed deploy model

- **Code-only deploy** (app code, sites, routes changed): `git push` then
  `gcloud run deploy --image <existing-image> --set-env-vars APP_SHA=<new-sha>`. No Docker rebuild.
  Total time ~30s.
- **Full rebuild** (only when `be/requirements.txt` or `be/entrypoint.py` changed):
  `gcloud builds submit` then `gcloud run deploy`.

**Must push to remote first** — the container clones at `APP_SHA` on startup. If the SHA isn't on
the remote yet, the container crashes.

### Environment variables

| Variable | Local | Production |
|---|---|---|
| `VERSHOLN_COMPAT_URL` | Not needed (bootstrap skipped) | Set via `--set-env-vars` |
| `GITHUB_PAT` | Not needed | Mounted from Secret Manager |
| `APP_SHA` | Not needed | Full 40-char SHA of deployed commit |

### Logging format

Stdlib `logging` with JSON formatter, output to stdout:

```json
{"schema": 1, "level": "...", "logger": "...", "msg": "..."}
```

- **stdout:** `INFO` / `DEBUG`
- **stderr:** `WARNING` and above (Cloud Run auto-flags as error-severity)
- **Never log:** credentials, full git URLs with auth, PII, full tracebacks in minimal mode

### Local/remote parity

The local dev server (`uvicorn`) must behave identically to the production stack (Vercel +
Cloud Run). Any routing or URL behaviour that works in production must also work locally.

---

## Patterns

- `versholn.importx()` for cross-repo deps inside route handlers.
- `versholn.install_and_import()` for light PyPI deps not in `requirements.txt`.
- `scan_deps.py` to auto-update `compat.json` pip section after adding a new dep.

---

## Anti-patterns

- Non-`requirements.txt` package imported at module level in site code.
- Pushing to `main` after `gcloud run deploy` (push must happen first, not after).
- Hardcoding secrets or paths that differ between local and production.
