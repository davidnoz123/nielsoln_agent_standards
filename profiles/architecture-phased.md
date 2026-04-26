# Profile: architecture-phased

Repos that follow a contract-driven, phased development approach where public APIs, class
aggregation, and implementation phases are defined in TSV files.

**Repos using this profile:** `video_annotation`, `ladder_stand_off`

---

## Purpose

Phased development prevents feature creep and ensures that each phase produces a minimal runnable
proof before the next phase begins. TSV contracts define the public API surface and class
relationships, making architectural drift visible.

---

## Rules

### Phase discipline

- Implement one phase at a time per `03_capture_phased_plan.tsv` (or equivalent).
- Only implement classes from the current phase.
- Do not introduce future-phase classes early, even if convenient.
- Each phase must produce a minimal runnable proof before moving to the next.

### Method surface contract

- Public APIs are documented in `01_method_surface.tsv` (or equivalent).
- Do not introduce new public methods unless explicitly requested or the TSV is updated first.
- Class dependencies must respect `02_class_aggregation.tsv` (or equivalent).

### Module layout contract

Do not invent new modules — place classes in the designated files defined in the project's module
layout contract. Your `AGENTS.project.md` defines the specific layout for this repo.

### No feature creep

- Do not add features beyond the current phase.
- Do not expand public APIs beyond the contract.
- Do not introduce cross-layer coupling.
- Do not add hidden global state.
- Do not introduce premature async frameworks.

### TSV contracts are source of truth

If there is a conflict between the TSV contracts and the code, flag it — do not silently resolve
it in favour of the code. The TSV may need updating, or the code may have drifted.

---

## Patterns

- Read TSV contracts before implementing any new class or method.
- Verify phase boundaries before starting implementation.
- Minimal runnable proof at end of each phase (not just unit tests, but an actual run).

---

## Anti-patterns

- Implementing classes from a future phase "just to get the structure in place".
- Adding public methods not in the TSV contract without updating the contract first.
- Cross-layer coupling (e.g. capture layer calling into runtime layer directly).
- Expanding module layout beyond the designated file structure.
