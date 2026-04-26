# Profile: python-integration

Complex scripts that integrate multiple sibling repos via the `versholn` bootstrap and import
system. These scripts orchestrate Excel, Chrome, HTTP servers, and other tools together.

**Repos using this profile:** `soc_med_mirror`, `video_annotation`

---

## Purpose

Integration scripts depend on several sibling repos cloned side-by-side. They use `versholn` to
load cross-repo symbols lazily and safely. They often run as long-lived processes spawned by VBA
or other shell callers.

---

## Rules

1. **Never import cross-repo symbols at module level.** Use `versholn.importx()` inside functions.

2. **Use `get_versholn(globals())` pattern** to inject `versholn` into the module globals lazily:
   ```python
   from utils import get_versholn  # safe: same-repo relative import

   def start():
       get_versholn(globals())
       CDPClient = versholn.importx("chrome_tools.CDPClient")
       ...
   ```
   `get_versholn(globals())` is idempotent — safe to call at the top of every function.

3. **Bootstrap dependency loading must be wrapped in try/except** with a logged FATAL message and
   a hint about running `versholn.doctor()` to diagnose missing sibling repos.

4. **Process visibility: no hidden windows.** See `AGENTS.base.md`.

5. **`safe_local_imports` for same-repo local imports** (e.g. `from excel import ExcelLogger`).
   Cross-repo symbols loaded via `versholn.importx()` are already safe — do not duplicate them.

6. **`locals.txt` must list all required sibling repos** (`VERSHOLN_DIR`, etc.). The
   `locals.txt.example` documents which variables are needed.

---

## Patterns

- Module-level fallback `_log` that prints to stderr before real logger is available.
- `versholn.importx()` calls inside the function body, not at module level.
- `SingletonProcess` named-mutex guard to prevent duplicate instances.
- `start_pid_watcher` / `start_file_watcher` for process lifecycle management.

---

## Anti-patterns

- `import versholn` at module level — this crashes the dev server if versholn isn't on sys.path.
- `from chrome_tools import CDPClient` at module level — same problem.
- Skipping the versholn.doctor() hint when dependency load fails.
- Running without a last-resort exception handler.
