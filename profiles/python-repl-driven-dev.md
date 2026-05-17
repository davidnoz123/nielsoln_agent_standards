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

---

## State sharing across modules — use `builtins`

Module `globals()` survives re-runs of the **same** module, but each module has its own
`globals()` dict. If an expensive resource is created in module A and must be accessible from
module B, the only shared namespace is `builtins`:

```python
import builtins as _builtins

def _get_repl_state() -> dict:
    """Return the process-global REPL state dict, shared across all modules."""
    if not hasattr(_builtins, "_repl_state"):
        _builtins._repl_state = {}
    return _builtins._repl_state

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

5. **`sys.argv[1:]` — always slice from index 1**, not 0. `sys.argv[0:]` overwrites the module
   name slot used by `runpy` and breaks command dispatch.

6. **The module docstring must include the REPL invocation** so it is discoverable at the start
   of a new session:
   ```python
   """My automation module.

   REPL usage:
       sys.argv[1:] = ["command"] ; import runpy ; temp = runpy._run_module_as_main("mymodule")
   """
   ```

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
