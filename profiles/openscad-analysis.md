# Profile: openscad-analysis

Python scripts that generate, analyse, and visualise OpenSCAD geometry, combined with structural
beam/frame modelling.

**Repos using this profile:** `ladder_stand_off`

---

## Purpose

Python drives OpenSCAD via subprocess to render geometry, perform structural analysis, detect
overlaps, annotate a canvas UI, and synchronise parameters with Excel.

---

## Rules

### Coordinate system conventions — know which system you're in

Two coordinate systems coexist in this repo and must never be mixed up:

**`gap_mechanism.scad` local coordinates:**
- `X` = distance away from the guide surface / toward the hanging plate
- `Y` = vertical direction
- `Z` = across the width of the guide / hanging plate / arm stacking direction

**`main.scad` world coordinates (non-standard!):**
- `X` = UP
- `Y` = along the wall
- `Z` = toward the approach

Always comment which coordinate system a function or variable uses if it is not obvious from context.

### Preserve parameter names and coordinate conventions

When moving logic into `main.scad`, preserve parameter names and coordinate conventions unless
there is a strong reason not to. Document the reason in a comment if you deviate.

### Keep `gap_mechanism_test.scad` usable

Keep `gap_mechanism_test.scad` usable as a hinge/arm debug file until the integration is stable.

### When uncertain about geometry

Add temporary debug geometry rather than guessing. Remove it before committing.

### Structural modelling approach

- Use beam/frame modelling, not full 3D FEM initially.
- Map directly to physical members: rails, arms, beams, plates.
- Every element must have a material; mass = density × volume.
- Support single-run analysis with full debuggability (elements, volumes, masses, loads, solver results).

---

## Patterns

- `scad_views.py` — renders `.scad` from 14 directions (6 orthographic + 8 isometric).
- `canvas_api.py` — thin wrapper for canvas HTTP endpoints (annotate, pan_zoom, clear).
- `overlap_check.py` — OBB collision detection across gap range.
- `params_tool.py` — CLI for inspecting/editing Parameters sheet via COM.

---

## Anti-patterns

- Mixing `gap_mechanism.scad` and `main.scad` coordinate systems without explicit conversion.
- Using integer literals for VBA Boolean arguments in Excel COM calls (use `True`/`False`).
- Committing generated SCAD files that are listed in `.gitignore`.
