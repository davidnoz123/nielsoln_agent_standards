# Profile: python-repl-driven-dev

Repos that use a persistent interactive Python REPL for fast iteration instead of spawning
a fresh process on every test run.

**Repos using this profile:** `geo_tools`, `soc_med_mirror`, `video_annotation`

---

## Purpose

Some workloads have a resource that is expensive to acquire on startup — a WebSocket connection
to Chrome, a model loaded into GPU memory, a database connection pool. Spawning a new Python
process for each test cycle pays that startup cost every time (seconds per cycle). The
persistent-REPL pattern keeps the resource alive across many edit–reload–test cycles, reducing
each cycle to tens of milliseconds.

**The canonical example is CDP automation.** A Chrome DevTools Protocol connection takes ~2 s to
establish. The actual command (e.g. a page reload, a screenshot) takes ~5 ms. The REPL pattern
means you pay the 2 s once per session, not once per edit.

---

## Core mechanism — `runpy._run_module_as_main` re-reads from disk

```python
sys.argv[1:] = ["command"] ; import runpy ; temp = runpy._run_module_as_main("mymodule")
```

`runpy._run_module_as_main` re-reads the `.py` file from disk and re-executes it in the existing
`__main__` namespace on every call. Module-level globals survive across re-runs (the `__main__`
dict is reused, not recreated). Your edits take effect immediately — no restart needed.

**Note:** `runpy._run_module_as_main` is a private CPython implementation detail — it is not part
of the public API and may change without notice. This pattern is for development workflows only;
production code must never call it.

**Important:** `runpy` only re-reads the entry-point module. Any modules it imports are already
cached in `sys.modules` and will **not** pick up disk changes automatically. Use a dedicated
`repl_reload.py` helper (see Rule 5) to reload all project modules in bottom-up order before
each `runpy` call:

```python
import repl_reload ; repl_reload.reload_all()
sys.argv[1:] = ["command"] ; import runpy ; temp = runpy._run_module_as_main("mymodule")
```

---

## Module-local REPL state — use `globals()`

Module `globals()` survives re-runs of the **same** module via `runpy._run_module_as_main`,
because the `__main__` dict is reused. Store REPL state there. Each module owns its own
state; resources are passed as arguments rather than shared cross-module.

```python
_REPL_STATE_KEY = "_repl_state"

def _get_repl_state() -> dict:
    """Return this module's REPL state dict (persists across runpy re-runs)."""
    g = globals()
    if _REPL_STATE_KEY not in g:
        g[_REPL_STATE_KEY] = {}
    return g[_REPL_STATE_KEY]

def get_repl_client(port: int = 9222):
    """Return the cached resource, connecting lazily and rechecking liveness."""
    state = _get_repl_state()
    client = state.get("client")
    if client is None or client.closed.is_set():
        client = _connect(port)
        state["client"] = client
    return client
```

To evict the cache from a REPL prompt:
```python
globals().pop('_repl_state', None)
```

**`builtins` for genuine cross-module sharing (rare):** If an expensive resource created
in module A truly must be accessed from module B in the same session, `builtins` is the
only shared namespace. This is an antipattern unless unavoidable — prefer redesigning
so the resource is passed as an argument.

```python
import builtins as _builtins
_STATE_KEY = "_repl_state_mypackage"  # namespaced — builtins is process-global

def _get_shared_state() -> dict:
    if not hasattr(_builtins, _STATE_KEY):
        setattr(_builtins, _STATE_KEY, {})
    return getattr(_builtins, _STATE_KEY)
```

---

## Rules

1. **`AGENTS.project.md` must document the REPL workflow** for this specific repo: which terminal
   command starts the REPL, which module to run, and the full command dispatch table.

2. **Never spawn a fresh process to test a single command.** Edit the file on disk, then call
   `runpy._run_module_as_main("mymodule")` in the running REPL.

3. **Never close a shared resource inside a command handler.** The resource is shared across all
   re-runs. Only a dedicated teardown command (e.g. `disconnect`) should close it.

4. **Never call `sys.exit()` or `raise SystemExit` anywhere in a REPL module** — not in
   `__main__`, not in helper functions, not in command handlers. Both propagate out of `runpy`
   and kill the interactive session immediately, with no recovery.

   - `__main__` block: call `main()` and log a non-zero return code instead of `raise SystemExit`:
     ```python
     if __name__ == "__main__":
         rc = main()
         if rc:
             _log(f"main() returned {rc}")
     ```
   - Helper functions: return `None` on failure (with a logged error message). Callers must
     check for `None` and propagate with `return 1`:
     ```python
     def _get_cli(port=None):
         if not health.is_alive():
             _log("[chrome] Chrome is not running.")
             return None          # NOT sys.exit(1)
         ...

     def cmd_something() -> int:
         cli = _get_cli()
         if cli is None:
             return 1             # caller propagates the failure
         ...
     ```

   **Why this keeps coming back:** The `sys.exit()` anti-pattern feels natural in CLI code
   (the CLI profile explicitly uses it). REPL modules look similar. The key difference: in a
   CLI the process is disposable; in a REPL it holds expensive resources (open WebSocket,
   loaded model, etc.) that take seconds to re-acquire. Killing the session with `sys.exit()`
   in a helper is silent and hard to diagnose — `runpy` propagates `SystemExit` without any
   message, and the REPL prompt simply disappears.

5. **Reload imported modules before each `runpy` call using an ordered reload helper.**
   `runpy._run_module_as_main` re-reads only the entry-point file; every other module is served
   from `sys.modules` cache. The recommended pattern is a dedicated `repl_reload.py` that lists
   all project modules in bottom-up dependency order (leaves first, entry point last):
   ```python
   # repl_reload.py  — committed to the repo, kept up to date as modules are added
   import importlib
   import mypackage.db, mypackage.utils, mypackage.core

   RELOAD_ORDER = [mypackage.db, mypackage.utils, mypackage.core]

   def reload_all():
       importlib.invalidate_caches()  # pick up any new .py files added since last reload
       for mod in RELOAD_ORDER:
           importlib.reload(mod)
   ```
   Then the REPL one-liner stays clean:
   ```python
   import repl_reload ; repl_reload.reload_all()
   sys.argv[1:] = ["command"] ; import runpy ; temp = runpy._run_module_as_main("mymodule")
   ```
   `repl_reload.py` must be updated whenever a new project module is added. If you forget a
   module, your edits to it will silently have no effect. The explicit ordered list also serves
   as documentation of the project's internal dependency graph.

6. **Use `import module` style, not `from module import name`, in REPL modules.**
   `importlib.reload` mutates the module object in-place inside `sys.modules`. Code that accesses
   `mypackage.db.get_connection()` always resolves through `sys.modules` and sees the reloaded
   version. But `from mypackage.db import get_connection` binds a name directly to the old
   function object in the importing module's namespace — reload of `mypackage.db` does **not**
   update that binding, so the stale version runs silently:
   ```python
   # BAD — get_connection is bound at import time; reload of mypackage.db has no effect here
   from mypackage.db import get_connection
   get_connection()

   # GOOD — resolved through sys.modules on every call; sees the reloaded module
   import mypackage.db
   mypackage.db.get_connection()
   ```

7. **`sys.argv[1:]` — always slice from index 1**, not 0. `sys.argv[0:]` overwrites the module
   name slot used by `runpy` and breaks command dispatch.

8. **The module docstring must include the REPL invocation** so it is discoverable at the start
   of a new session:
   ```python
   """My automation module.

   REPL usage:
       sys.argv[1:] = ["command"] ; import runpy ; temp = runpy._run_module_as_main("mymodule")
   """
   ```

9. **`globals()` is the default for per-module REPL state.** Do not use `builtins` unless
   state genuinely must be shared between two distinct imported modules in the same session
   (rare — prefer passing resources as arguments instead). When `builtins` is unavoidable,
   always namespace the key (e.g. `_repl_state_mypackage`) — the `builtins` namespace is
   process-global and a generic key will collide with other projects.

10. **Old names and old instances can survive a reload.** Re-running `runpy` does not clean
    `__main__` — names deleted from source persist until the session is restarted.
    `importlib.reload` updates the module object but existing instances of classes defined in
    that module still carry the old class's methods and `__dict__` layout. When behaviour is
    inexplicably stale, restart the REPL.

11. **Restart the REPL when reload behaviour becomes confusing.** Reload is additive, not
    restorative. Restart after: installing or upgrading packages; changing `sys.path` or
    `.pth` files; changing class definitions that live objects already reference; any situation
    where an edit demonstrably has no effect despite correct reloading.

12. **Do not call `reload_all()` while background threads or async tasks are running.**
    Reloading a module mid-execution can leave a thread holding references to old function
    objects while new code is only partially applied. Restrict `reload_all()` calls to
    single-threaded command handlers, or stop background tasks before reloading and restart
    them after.

13. **Call `importlib.invalidate_caches()` after adding new files to the project.** Python
    caches filesystem scans for importable modules at startup. New `.py` files added to a
    package directory after the REPL started are invisible to `import` until the cache is
    cleared. `reload_all()` already does this (see Rule 5), but call it manually if you add a
    file between `runpy` invocations without going through `reload_all()`.

---

## Resilient terminal ID tracking (agent guidance)

When an agent's context is refreshed mid-session, the VS Code terminal UUID held in memory is
lost. Without recovery, the agent spawns a redundant REPL terminal and orphans the live one —
along with any expensive resources attached to it (CDP connections, loaded models, DB pools).

**Solution: write the terminal UUID to a workspace-scoped file immediately after creation.**

VS Code injects a unique per-instance token into every terminal via `VSCODE_GIT_IPC_HANDLE`
(e.g. `\\.\pipe\vscode-git-54a36a39f2-sock`). Extracting the hash from this handle gives a
stable per-VS Code-window ID that is available in both user-opened terminals and agent-run
terminals. Multiple VS Code instances have different handles, so their files never collide.

Extract the token with:
```powershell
$vsid = ($env:VSCODE_GIT_IPC_HANDLE -replace '.*vscode-git-([^-]+)-sock.*', '$1')
```

Note: `$env:VSCODE_PID` is **not** reliable — it is not injected in agent-run terminals.

### On creation

After `run_in_terminal` returns a terminal UUID, immediately run in another terminal:

```powershell
$vsid = ($env:VSCODE_GIT_IPC_HANDLE -replace '.*vscode-git-([^-]+)-sock.*', '$1')
Remove-Item .repl_terminal_id_* -ErrorAction SilentlyContinue
"<uuid>" | Set-Content ".repl_terminal_id_$vsid"
```

The `Remove-Item` glob-delete ensures at most one file exists at any time — old files from
previous VS Code sessions (different tokens) are cleaned up on each new terminal creation.

Add `.repl_terminal_id_*` to `.gitignore`. The filename to use should be documented in
`AGENTS.project.md` for the repo.

### On reuse

At the start of any turn that needs the REPL terminal:

1. Read the file:
   ```powershell
   $vsid = ($env:VSCODE_GIT_IPC_HANDLE -replace '.*vscode-git-([^-]+)-sock.*', '$1')
   $id = Get-Content ".repl_terminal_id_$vsid" -ErrorAction SilentlyContinue
   ```
2. If `$id` is non-empty, probe liveness: call `get_terminal_output(id=$id)`.
3. If the probe succeeds (returns output, even empty/idle) — **reuse the terminal. Do not spawn a new one.**
4. If the file is missing or the probe fails — create a new terminal, then immediately run the write step above.

---

## REPL session log capture (`_cmd_capture`)

Every `runpy._run_module_as_main` invocation produces terminal output that accumulates in a 32 KB
scrollback buffer. Agents reading that buffer get a large, noisy blob containing multiple prior
commands. Prompts fed back into interactive `[y/N]` handlers fill the buffer with character-by-character echo.

**Solution: tee `sys.stdout` and `sys.stderr` to a timestamped log file on every invocation.**

### `_TeeStream`

```python
class _TeeStream:
    """Writes to both a primary stream (original stdout/stderr) and a secondary file handle."""
    def __init__(self, primary, secondary):
        self._primary = primary
        self._secondary = secondary

    def write(self, data):
        self._primary.write(data)
        self._primary.flush()
        self._secondary.write(data)
        self._secondary.flush()

    def flush(self):
        self._primary.flush()
        self._secondary.flush()

    def fileno(self):
        return self._primary.fileno()  # subprocess compat
```

### `_cmd_capture`

```python
@contextlib.contextmanager
def _cmd_capture():
    log_dir = os.path.join(REPO_ROOT, "repl_logs")
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    # 10-digit zero-padded PID: covers 32-bit Windows (max 4,294,967,295)
    # and 22-bit Linux (max 4,194,304). Equal-width filenames on all platforms.
    log_path = os.path.join(log_dir, f"{pid:010d}_{ts}.log")
    # Print BEFORE redirect — always visible in REPL terminal buffer
    print(f"[capture] log → {log_path}", flush=True)
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(f"argv: {sys.argv}\n")
        fh.flush()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = _TeeStream(old_out, fh)
        sys.stderr = _TeeStream(old_err, fh)
        try:
            yield log_path
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
```

### Usage in `__main__` block

```python
if __name__ == "__main__":
    safe_local_imports(globals())
    with _cmd_capture():
        try:
            rc = main()
            if rc:
                _log(f"main() returned {rc}")
        except Exception:
            import traceback
            _log(f"FATAL unhandled exception:\n{traceback.format_exc()}")
            raise
```

`safe_local_imports` runs before `_cmd_capture` so that import errors surface in the terminal
before log redirect is active. The FATAL handler logs the full traceback via `_log()` (tee'd to
the file) before re-raising.

### Agent workflow with log files

```powershell
# Read the most recent log after a runpy invocation
Get-ChildItem repl_logs\ | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

The log path is printed to real stdout **before** the tee redirect, so it is always visible in
the REPL terminal buffer — use it to read the file directly instead of parsing scrollback.

> **⛔ Agent rule: NEVER use `get_terminal_output` scrollback to read REPL results.**
>
> After every `runpy._run_module_as_main(...)` call:
> 1. Read the `[capture] log → <path>` line from the terminal buffer (it is always the first line of output).
> 2. Read **that file** with `read_file` or `Get-Content` — it contains the complete, unfragmented output.
>
> `get_terminal_output` scrollback is a 32 KB ring buffer shared across all commands in the
> session. It is truncated, noisy, and may contain output from prior commands.
> Log files are always complete. **Read the log file. Always.**

### Rules

- Add `repl_logs/` to `.gitignore`.
- Add `import contextlib` to the stdlib imports block.
- `_TeeStream` and `_cmd_capture` must be defined at module level, before any function that uses them.
- Log filenames are `{YYYYMMDDTHHMMSS}{ms:03d}_{pid:010d}.log` — datetime-first so directory listings sort chronologically; milliseconds zero-padded without separator; PID zero-padded to 10 digits.
- The `argv:` line is written to the file before stdout/stderr are redirected, so it is always present even if `main()` crashes immediately.
- Do **not** call `_cmd_capture()` from within REPL invocations — it is only for the `__main__` block. Each `runpy._run_module_as_main` re-enters `__main__` and therefore gets a fresh log file automatically.

---

## Patterns

- `_get_repl_state()` using `globals()` for per-module state; `builtins` only when two distinct modules must genuinely share a resource (prefer argument passing instead).
- `get_repl_client()` (or equivalent) that connects lazily and rechecks liveness on every call.
- `sys.argv[1:] = ["command"] ; import runpy ; temp = runpy._run_module_as_main("mod")` in the REPL.
- Command dispatch on `sys.argv[1]` inside `main()`.

---

## Anti-patterns

- `raise SystemExit(main())` in the `__main__` block of a REPL module.
- `sys.exit()` inside any helper function — kills the REPL session silently; use `return None` and check at the call site.
- Closing the shared resource inside a command handler.
- Running `python mymodule.py command` in a terminal instead of re-running in the live REPL.
- `sys.argv[0:] = ["command"]` — corrupts the module name slot.
- `from mypackage.db import name` in REPL modules — reload does not rebind these; edits silently have no effect.
