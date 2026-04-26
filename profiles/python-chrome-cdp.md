# Profile: python-chrome-cdp

Python code that controls Chrome via the Chrome DevTools Protocol (CDP).

**Repos using this profile:** `soc_med_mirror`, `video_annotation`, `chrome_tools`

---

## Purpose

Chrome is launched and controlled via CDP for automation, recording, and annotation tasks. Multiple
processes sharing the same Chrome debugging WebSocket is a known silent failure mode.

---

## Rules

### Never open a competing CDPClient

Chrome allows multiple processes to connect to the same debugging WebSocket without error, causing
silent cross-talk. Guard against this:

```python
if _port_open(_SERVER_PORT):
    raise RuntimeError(
        "annotation server is running — use server mode, not direct CDPClient"
    )
```

`SingletonProcess` only guards `AppRuntime` — ad-hoc scripts must add this check themselves.

### Never discard CDP responses silently

CDP errors are returned as `exceptionDetails` inside the response dict, not as Python exceptions:

```python
result = session.send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
exc = result.get("exceptionDetails")
if exc:
    desc = exc.get("exception", {}).get("description", str(exc))
    raise RuntimeError(f"JS exception: {desc}")
```

### Always launch Chrome with `headless=False`

Headless mode hides modal dialogs and makes debugging very difficult. Always use visible Chrome.

### Chrome must already be running before connecting

Do not launch a new Chrome instance if one is already running on the target port. Check first and
reuse the existing instance.

---

## Patterns

- `CDPClient` is loaded via `versholn.importx("chrome_tools.CDPClient")` — never at module level.
- Port-open check before creating any CDPClient.
- Always check `exceptionDetails` in CDP responses.
- `ChromeLauncher.start()` with `headless=False`.

---

## Anti-patterns

- `headless=True` for any automation (not just debugging).
- Silently ignoring `exceptionDetails` in CDP responses.
- Opening multiple CDPClient instances on the same port.
- Importing `chrome_tools` at module level.
