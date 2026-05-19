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

## State sharing across modules — use `builtins`

Module `globals()` survives re-runs of the **same** module, but each module has its own
`globals()` dict. If an expensive resource is created in module A and must be accessible from
module B, the only shared namespace is `builtins`:

```python
import builtins as _builtins

_STATE_KEY = "_repl_state_mypackage"  # namespaced to avoid collisions with other projects

def _get_repl_state() -> dict:
    """Return the process-global REPL state dict, shared across all modules."""
    if not hasattr(_builtins, _STATE_KEY):
        setattr(_builtins, _STATE_KEY, {})
    return getattr(_builtins, _STATE_KEY)

def get_repl_client(port: int = 9222):
    """Return the cached resource, connecting lazily and rechecking liveness."""
    state = _get_repl_state()
    client = state.get("client")
    if client is None or client.closed.is_set():
        client = _connect(port)
        state["client"] = client
    return client
```

Use plain module globals when only one module needs the state. Use `builtins` when the state
must be visible to several modules running in the same REPL session.

---

## Rules

1. **`AGENTS.project.md` must document the REPL workflow** for this specific repo: which terminal
   command starts the REPL, which module to run, and the full command dispatch table.

2. **Never spawn a fresh process to test a single command.** Edit the file on disk, then call
   `runpy._run_module_as_main("mymodule")` in the running REPL.

3. **Never close a shared resource inside a command handler.** The resource is shared across all
   re-runs. Only a dedicated teardown command (e.g. `disconnect`) should close it.

4. **Do not use `raise SystemExit`** in the `__main__` block of REPL modules. `SystemExit`
   propagates out of `runpy` and kills the interactive session. Call `main()` and log a non-zero
   return code instead:
   ```python
   if __name__ == "__main__":
       rc = main()
       if rc:
           _log(f"main() returned {rc}")
   ```

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

9. **Use a namespaced key when storing state in `builtins`.** The `builtins` namespace is
   process-global and shared by every loaded module. A generic key like `_repl_state` will
   collide if multiple projects or libraries are loaded in the same session. Always prefix the
   key with the package name (e.g. `_repl_state_mypackage`).

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

VS Code injects `$env:VSCODE_PID` into every integrated terminal — the PID of the VS Code
window process that spawned it. Using this as part of the filename naturally scopes the file to
one VS Code window; multiple VS Code instances open simultaneously each have a different PID and
therefore a different file, so they cannot interfere with each other.

### On creation

After `run_in_terminal` returns a terminal UUID, immediately run in that terminal:

```powershell
Remove-Item .repl_terminal_id_* -ErrorAction SilentlyContinue
"<uuid>" | Set-Content ".repl_terminal_id_$env:VSCODE_PID"
```

The `Remove-Item` glob-delete ensures at most one file exists at any time — old files from
previous VS Code sessions (different PIDs) are cleaned up on each new terminal creation.

Add `.repl_terminal_id_*` to `.gitignore`. The filename to use should be documented in
`AGENTS.project.md` for the repo.

### On reuse

At the start of any turn that needs the REPL terminal:

1. Read the file: `$id = Get-Content ".repl_terminal_id_$env:VSCODE_PID" -ErrorAction SilentlyContinue`
2. If `$id` is non-empty, probe liveness: call `get_terminal_output(id=$id)`.
3. If the probe succeeds (returns output, even empty/idle) — **reuse the terminal. Do not spawn a new one.**
4. If the file is missing or the probe fails — create a new terminal, then immediately run the write step above.

---

## Patterns

- `_get_repl_state()` using `builtins` for cross-module shared state; plain globals for single-module state.
- `get_repl_client()` (or equivalent) that connects lazily and rechecks liveness on every call.
- `sys.argv[1:] = ["command"] ; import runpy ; temp = runpy._run_module_as_main("mod")` in the REPL.
- Command dispatch on `sys.argv[1]` inside `main()`.

---

## Anti-patterns

- `raise SystemExit(main())` in the `__main__` block of a REPL module.
- Closing the shared resource inside a command handler.
- Running `python mymodule.py command` in a terminal instead of re-running in the live REPL.
- `sys.argv[0:] = ["command"]` — corrupts the module name slot.
- `from mypackage.db import name` in REPL modules — reload does not rebind these; edits silently have no effect.
