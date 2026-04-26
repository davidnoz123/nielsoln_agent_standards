# nielsoln_agent_standards

Centralised agent instruction standards for the `lunk` workspace.

## Contents

| File | Purpose |
|---|---|
| `AGENTS.base.md` | Universal rules that apply to all Python repos |
| `profiles/` | Domain-specific rule sets |
| `update_agents.py` | Script that generates `AGENTS.md` in a project repo |

## Profiles

| Profile | Used by |
|---|---|
| `profiles/python-cli.md` | Basic Python CLI utilities |
| `profiles/python-integration.md` | Multi-repo integration scripts |
| `profiles/python-excel-vba.md` | Excel/VBA automation via win32com |
| `profiles/python-chrome-cdp.md` | Chrome DevTools Protocol automation |
| `profiles/python-bootstrap-library.md` | The versholn library itself |
| `profiles/python-backend-service.md` | FastAPI/Cloud Run microservices |
| `profiles/openscad-analysis.md` | OpenSCAD geometry + Python structural analysis |
| `profiles/architecture-phased.md` | Contract-driven phased development |

## How it works

Each project repo has:

- `AGENTS.project.json` — declares which profiles to include
- `AGENTS.project.md` — project-specific rules (hand-edited, not auto-generated)
- `update_agents.py` — thin shim that calls the real script here
- `AGENTS.md` — auto-generated (do not edit)
- `AGENTS.local.md` — optional machine-specific overrides (gitignored)

Running `python update_agents.py` in any project repo:

1. Reads `AGENTS.project.json` to find the profile list
2. Downloads `AGENTS.base.md` + selected profiles from this repo via GitHub raw URLs
3. Generates `AGENTS.md` with base + profiles inlined, then references to `AGENTS.project.md`
   and `AGENTS.local.md` at the end (later rules override earlier rules)
4. Records the generation timestamp and standards repo SHA in the file header

## Adding a new project repo

1. Add `update_agents.py` (shim) to the project repo root
2. Create `AGENTS.project.json` with the appropriate profile list
3. Add `AGENT_STANDARDS_DIR=..\nielsoln_agent_standards` to `locals.txt.example`
4. Run `python update_agents.py`

## Adding a new profile

1. Create `profiles/<name>.md` in this repo
2. Commit + push
3. Add `"profiles/<name>"` to `AGENTS.project.json` in the project repos that need it
4. Run `python update_agents.py` in those repos

## Promoting a rule from a project to the standards

Use the **Push** workflow described in any project repo's `AGENTS.md` under **Agent Workflows**.
