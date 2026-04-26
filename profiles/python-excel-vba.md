# Profile: python-excel-vba

Python code that drives Excel via `win32com`, injects VBA, or interacts with Excel workbooks as a
data store or UI layer.

**Repos using this profile:** `soc_med_mirror`, `video_annotation`, `ladder_stand_off`, `excel_tools`

---

## Purpose

Excel is used both as a persistent data store and as a UI (ribbon buttons, custom sheets). Python
drives it via COM automation. VBA procedures are injected at runtime by Python and call back into
Python via an HTTP command server.

---

## Rules

### Never use `Active*` objects

Avoid `ActiveDocument`, `ActiveSheet`, `ActiveWorkbook`, `ActiveWindow`, `Selection` in both Python
`win32com` code and generated VBA:

```python
# BAD
ws = excel.ActiveSheet

# GOOD
wb = excel.Workbooks("MyWorkbook.xlsm")
ws = wb.Sheets("Data")
```

`Active*` changes silently when the user clicks, when a COM call switches focus, or when
`ScreenUpdating` is toggled.

### PyWin32 COM safety

1. Never hide the application window (`app.Visible = False`).
2. Suppress alerts with try/finally, restoring the original value:
   ```python
   prev = app.DisplayAlerts
   app.DisplayAlerts = 0
   try:
       ...
   finally:
       app.DisplayAlerts = prev
   ```
3. Wrap the entire COM session in try/finally so `Quit()` always runs.
4. Reuse existing instances with `GetActiveObject` rather than spawning new ones.
5. Use `flush=True` on every `print` inside COM loops.

### VBA injection round-trip stability

Excel's VBA engine silently reformats code when storing a procedure. To avoid false-positive diffs:

- Never use integer literals (`0`, `-1`) where VBA expects Boolean arguments — write `False`/`True`.
- After editing any VBA procedure body string, run Refresh twice. If the second Refresh still
  reports a change, that's a real build error.

### Two-channel logging (where applicable)

When both Python and VBA write to the same log file, prefix all log lines:

- `[py]` for Python messages
- `[vba]` for VBA messages

---

## Patterns

- Hold explicit workbook/sheet/range references, never rely on `Active*`.
- COM session lifecycle: open → try → finally Quit.
- VBA code stored as Python string constants with explicit `True`/`False` boolean literals.

---

## Anti-patterns

- `ActiveSheet`, `ActiveWorkbook`, `Selection` anywhere in COM automation code.
- `Application.Visible = False`.
- COM session without a `finally: app.Quit()` guard.
- Integer literals for VBA Boolean arguments (`0`, `-1`).
