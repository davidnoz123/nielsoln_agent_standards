# Profile: python-cli

Basic Python command-line utility scripts that run directly from a terminal or are spawned by
another process.

**Repos using this profile:** `excel_tools`, `local_server_tools`, `project_tools`, `chrome_tools`,
`film_restoration_pack`, `geo_tools`

---

## Purpose

Scripts in this category are standalone utilities — they may be run interactively, called from other
scripts, or spawned as background processes. They are not services and do not serve HTTP traffic.

---

## Rules

1. **`safe_local_imports` is mandatory** for any file with `if __name__ == "__main__":` that imports
   non-stdlib modules. See `AGENTS.base.md` for the full pattern.

2. **`if __name__ == "__main__":` guard is mandatory.** Never run side effects at module import time.

3. **Last-resort exception handler** in the `__main__` block:
   ```python
   if __name__ == "__main__":
       safe_local_imports(globals())
       try:
           raise SystemExit(main())
       except SystemExit:
           raise
       except Exception:
           import traceback
           _log(f"FATAL unhandled exception:\n{traceback.format_exc()}")
           raise
   ```

4. **Fallback `_log`** must be defined at module level before `safe_local_imports` is called:
   ```python
   import sys
   _log = lambda msg: print(msg, file=sys.stderr)
   ```
   `safe_local_imports` may replace this with the real logger once imports succeed.

5. **Syntax-check after every edit.** See `AGENTS.base.md`.

---

## Patterns

- `argparse` for CLI arg parsing (or hardcoded `main()` overrides for REPL-style repos).
- Return an integer exit code from `main()` and pass it to `SystemExit`.
- Use `logging` or a simple `_log` function — never bare `print` for diagnostic output.

---

## Anti-patterns

- `if __name__ == "__main__": main()` with no exception handler.
- Non-stdlib imports at module level.
- Bare `except: pass` anywhere.
- `sys.exit()` called deep inside helper functions (use return codes or exceptions instead).
