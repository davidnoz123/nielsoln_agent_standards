# Profile: python-github-admin

Scripts that perform administrative operations on GitHub repositories via the GitHub REST API
(using PyGithub).

**Repos using this profile:** `nielsoln_project_hub`

---

## Purpose

Admin scripts automate repo management tasks — visibility, archiving, topic management, branch
operations, and cross-repo status views. They can make irreversible changes and must guard against
accidental destructive operations.

---

## Rules

### Authentication

1. **`GITHUB_TOKEN` must come from `locals.txt`** — never hardcoded, never logged.
   Read it at the top of `main()` and pass it down. Never store it as a module-level global.

2. **Never log the token** — not in debug output, not in tracebacks, not in error messages.
   If you must reference it in a log, use `"<redacted>"`.

3. Token must have `repo` scope for private repo operations and `delete_repo` scope for deletions.
   Document required scopes in `AGENTS.project.md`.

### PyGithub loading

Load PyGithub inside functions via `versholn.install_and_import()`, never at module level:

```python
def _get_github(token: str):
    github = versholn.install_and_import("PyGithub", import_as="github")
    return github.Github(token)
```

### Destructive operation guard

Before any operation that is hard to reverse (`set_visibility`, `archive`, `delete_branch`),
prompt for explicit confirmation:

```python
def _confirm(msg: str) -> bool:
    resp = input(f"{msg} [y/N] ").strip().lower()
    return resp == "y"
```

**Never skip this guard**, even when running a batch across multiple repos.

### Rate limiting

- Log `g.get_rate_limit().core.remaining` before bulk operations.
- Add `time.sleep(0.1)` between API calls in loops over many repos.
- Log a warning if remaining < 100.

### Error handling per repo

Wrap each repo operation individually so one failure does not abort the batch:

```python
for name in repos:
    try:
        _do_op(repo)
    except Exception:
        _log(f"FAILED {name}: {traceback.format_exc()}")
```

---

## Patterns

- Load token once at the top of `main()`, pass it down — do not re-read locals.txt in every function.
- `versholn.load_repo(path)` to get local SHA/branch state alongside the remote GitHub state.
- Return an integer exit code from every operation function.

---

## Anti-patterns

- Token in source code, in a committed file, or printed to stdout.
- `Github(token)` at module level.
- No confirmation before `delete_branch`, `archive`, or `set_visibility`.
- Silently swallowing rate limit errors.
