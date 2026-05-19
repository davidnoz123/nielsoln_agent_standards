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

## Onboarding a new project repo

Run `compliance.py` to see what is missing and why each item is required:

```powershell
python compliance.py <repo_name>
```

`compliance.py` is the single source of truth for what "compliant" means — its
checks and their documented `why`/`fix` fields are the onboarding guide.

To bring a non-compliant repo into compliance, open it in VS Code and ask the
agent to fix the issues listed in the compliance output. The agent uses AGENTS.md
and the fix descriptions to scaffold the missing pieces correctly for that repo.

```powershell
# Audit all repos
python compliance.py

# Audit one repo
python compliance.py usb_device_tools

# Override the auto-derived VERSHOLN_REPOS_ROOT
python compliance.py --root C:\analytics\projects\git\lunk
```

## Adding a new profile

1. Create `profiles/<name>.md` in this repo
2. Commit + push
3. Add `"profiles/<name>"` to `AGENTS.project.json` in the project repos that need it
4. Run `python update_agents.py` in those repos

## Promoting a rule from a project to the standards

Use the **Push** workflow described in any project repo's `AGENTS.md` under **Agent Workflows**.
