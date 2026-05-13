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

### GitHub access via `gh` CLI

All GitHub API operations use the `gh` CLI (already installed and authenticated). No PyGithub,
no token handling in Python code, no `versholn.install_and_import`.

- Use `gh api <endpoint>` for REST calls not covered by `gh` subcommands.
- Use `gh repo`, `gh pr`, `gh issue` subcommands where available.
- `gh` manages auth via `gh auth login` — no token in `locals.txt` required for GitHub ops.

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

- All GitHub ops via `gh` — no PyGithub, no token in Python code.
- `versholn.load_repo(path)` to get local SHA/branch state alongside the remote GitHub state.
- Return an integer exit code from every operation function.

### Creating a new compliant lunk repo

Use `op_create_repo` in `hub.py` (`nielsoln_project_hub`). It is **idempotent** — safe to re-run
if interrupted. It performs every step automatically:

1. Creates a **private** GitHub repo with `auto_init=True` (skips if already exists).
2. Cuts a `0.1` release branch from `main` on GitHub (skips if already exists).
3. Clones the repo locally under `LUNK_REPOS_ROOT` (skips if already cloned).
4. Checks out `0.1`.
5. Copies scaffold files from `nielsoln_agent_standards/scaffold/` — the canonical source
   for `.gitignore`, `locals.txt.example`, `update_agents.py`, `AGENTS.project.json`,
   and `AGENTS.project.md` (with `__REPO_NAME__` substituted). Skips files already present.
6. Writes `locals.txt` from the example if not present.
7. Runs `update_agents.py` to generate `AGENTS.md`.
8. Commits "Initial compliant scaffold" and pushes to `origin/0.1` (skips if nothing to commit).

To run:
```python
OPERATION   = "create_repo"
TARGET_REPO = "<new_repo_name>"
```

After the operation completes, do these two manual steps in `nielsoln_project_hub`:
1. Add `"<new_repo_name>"` to the `REPOS` list in `hub.py`.
2. Create a stub `repos/<new_repo_name>.md` (Status / Direction / Notes headings).

**Scaffold templates** live in `nielsoln_agent_standards/scaffold/`. Edit them there — never
copy-paste from another repo.

---

## Anti-patterns

- PyGithub or any GitHub API library as a dependency.
- Token in source code, in a committed file, or printed to stdout.
- No confirmation before `delete_branch`, `archive`, or `set_visibility`.
- Silently swallowing rate limit errors.
