"""
compliance.py — Repo compliance checker for the nielsoln/lunk workspace.

Verifies that each repo follows the standards defined in AGENTS.base.md and
the profile system. This script is the single source of truth for what
"compliant" means — reading it teaches you the onboarding requirements.

Usage:
    python compliance.py                    # check all repos in LUNK_REPOS_ROOT
    python compliance.py chrome_tools       # check one repo by name
    python compliance.py --root C:\path     # override LUNK_REPOS_ROOT

Requires LUNK_REPOS_ROOT in locals.txt (or --root flag).

To bring a non-compliant repo into compliance, open it in VS Code and ask
the agent to fix the issues listed in the compliance output.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Locals reader
# ---------------------------------------------------------------------------

def _read_locals(repo_root: Path) -> dict:
    path = repo_root / "locals.txt"
    result = {}
    if not path.exists():
        return result
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


# ---------------------------------------------------------------------------
# Check result
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str           # short check identifier
    passed: bool
    why: str            # why this check exists (onboarding documentation)
    fix: str            # what to do if it fails


@dataclass
class RepoReport:
    repo_name: str
    repo_path: Path
    checks: list = field(default_factory=list)

    @property
    def passed(self):
        return all(c.passed for c in self.checks)

    @property
    def failures(self):
        return [c for c in self.checks if not c.passed]


# ---------------------------------------------------------------------------
# Individual checks
# Each check function takes a Path (repo root) and returns a CheckResult.
# The docstring of this module + the why/fix fields ARE the onboarding docs.
# ---------------------------------------------------------------------------

def check_agents_project_json(repo: Path) -> CheckResult:
    exists = (repo / "AGENTS.project.json").exists()
    valid = False
    if exists:
        try:
            data = json.loads((repo / "AGENTS.project.json").read_text(encoding="utf-8"))
            valid = "profiles" in data and "standards_repo_raw_base" in data
        except Exception:
            pass
    return CheckResult(
        name="AGENTS.project.json",
        passed=exists and valid,
        why=(
            "Declares which agent-standard profiles apply to this repo. "
            "The update_agents.py shim reads this to know which base + profile "
            "files to download from nielsoln_agent_standards and inline into AGENTS.md."
        ),
        fix=(
            "Create AGENTS.project.json with keys 'standards_repo_raw_base' and 'profiles'. "
            "See chrome_tools/AGENTS.project.json for a minimal example. "
            "Choose profiles from: " + ", ".join([
                "profiles/python-cli",
                "profiles/python-integration",
                "profiles/python-excel-vba",
                "profiles/python-chrome-cdp",
                "profiles/python-backend-service",
                "profiles/python-bootstrap-library",
                "profiles/architecture-phased",
                "profiles/openscad-analysis",
                "profiles/python-github-admin",
            ])
        ),
    )


def check_agents_project_md(repo: Path) -> CheckResult:
    exists = (repo / "AGENTS.project.md").exists()
    non_empty = exists and len((repo / "AGENTS.project.md").read_text(encoding="utf-8").strip()) > 10
    return CheckResult(
        name="AGENTS.project.md",
        passed=exists and non_empty,
        why=(
            "Hand-edited project-specific agent instructions. Appended after the "
            "auto-generated base+profile content in AGENTS.md — project rules can "
            "override the universal standards. Without it, agents have no context "
            "about what this specific repo does."
        ),
        fix=(
            "Create AGENTS.project.md with at minimum: project purpose, development "
            "style (REPL vs CLI), and any repo-specific conventions. "
            "See chrome_tools/AGENTS.project.md for a worked example."
        ),
    )


def check_update_agents_py(repo: Path) -> CheckResult:
    path = repo / "update_agents.py"
    exists = path.exists()
    is_shim = False
    if exists:
        content = path.read_text(encoding="utf-8", errors="replace")
        is_shim = "AGENT_STANDARDS_DIR" in content and "nielsoln_agent_standards" in content
    return CheckResult(
        name="update_agents.py",
        passed=exists and is_shim,
        why=(
            "Thin shim that delegates to the real update_agents.py in "
            "nielsoln_agent_standards. Running it regenerates AGENTS.md whenever "
            "the base standards or profiles are updated. Without it, AGENTS.md "
            "can only be updated manually."
        ),
        fix=(
            "Copy update_agents.py from chrome_tools/ — it is a generic shim "
            "that reads AGENT_STANDARDS_DIR from locals.txt and delegates to "
            "the real script. Do not customise it."
        ),
    )


def check_agents_md_autogenerated(repo: Path) -> CheckResult:
    path = repo / "AGENTS.md"
    exists = path.exists()
    is_generated = False
    if exists:
        content = path.read_text(encoding="utf-8", errors="replace")
        is_generated = "AUTO-GENERATED" in content or "Standards SHA" in content
    return CheckResult(
        name="AGENTS.md (auto-generated)",
        passed=exists and is_generated,
        why=(
            "AGENTS.md must be the auto-generated output of update_agents.py, not "
            "a hand-written file. Agents read this as their primary instruction source. "
            "If it is hand-written it will drift from the standards over time."
        ),
        fix=(
            "Run: python update_agents.py\n"
            "This downloads the base + profiles and regenerates AGENTS.md. "
            "Requires AGENT_STANDARDS_DIR in locals.txt pointing to this repo."
        ),
    )


def check_locals_txt_example(repo: Path) -> CheckResult:
    path = repo / "locals.txt.example"
    exists = path.exists()
    has_agent_standards = False
    if exists:
        content = path.read_text(encoding="utf-8", errors="replace")
        has_agent_standards = "AGENT_STANDARDS_DIR" in content
    return CheckResult(
        name="locals.txt.example",
        passed=exists and has_agent_standards,
        why=(
            "Template for the machine-specific locals.txt (gitignored). New contributors "
            "copy this and fill in their paths. Must include AGENT_STANDARDS_DIR so "
            "update_agents.py can find this repo. Without it, a new machine cannot "
            "run update_agents.py."
        ),
        fix=(
            "Create locals.txt.example with at minimum:\n"
            "  PYTHON=..\\lexi\\demos\\venv\\Scripts\\python.exe\n"
            "  VERSHOLN_DIR=..\\versholn\n"
            "  AGENT_STANDARDS_DIR=..\\nielsoln_agent_standards\n"
            "Add any other machine-specific variables the repo needs."
        ),
    )


def check_gitignore_locals(repo: Path) -> CheckResult:
    path = repo / ".gitignore"
    exists = path.exists()
    ignores_locals = False
    ignores_agents_local = False
    if exists:
        content = path.read_text(encoding="utf-8", errors="replace")
        ignores_locals = "locals.txt" in content
        ignores_agents_local = "AGENTS.local.md" in content
    return CheckResult(
        name=".gitignore (locals.txt + AGENTS.local.md)",
        passed=exists and ignores_locals and ignores_agents_local,
        why=(
            "locals.txt contains machine-specific paths and must never be committed. "
            "AGENTS.local.md contains machine-specific agent overrides and must never "
            "be committed. Both are in .gitignore by convention."
        ),
        fix=(
            "Add to .gitignore:\n"
            "  locals.txt\n"
            "  AGENTS.local.md"
        ),
    )


def check_branch_not_main(repo: Path) -> CheckResult:
    """
    All development happens on a <N>.<M> release branch, never directly on main.
    main is production/stable only and is only updated via merges from release branches.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo, capture_output=True, text=True, timeout=10
        )
        branch = result.stdout.strip()
        on_main = branch == "main"
    except Exception:
        branch = "unknown"
        on_main = False  # can't check, don't fail
    return CheckResult(
        name=f"branch (current: {branch})",
        passed=not on_main,
        why=(
            "The branch model requires all development on a <N>.<M> release branch "
            "(e.g. 0.1, 0.2). main is the stable/production branch and must never "
            "be committed to directly. Versions are derived from the branch name + "
            "first-parent commit count by versholn."
        ),
        fix=(
            "Create a release branch: git checkout -b 0.1\n"
            "All future commits go on this branch. Merge to main only when releasing."
        ),
    )


def check_remote_tracking(repo: Path) -> CheckResult:
    """Current branch must have a remote tracking branch set up."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=repo, capture_output=True, text=True, timeout=10
        )
        tracking = result.stdout.strip()
        has_tracking = result.returncode == 0 and bool(tracking)
    except Exception:
        tracking = ""
        has_tracking = False  # can't check, don't fail
    return CheckResult(
        name=f"remote tracking branch ({tracking or 'none'})",
        passed=has_tracking,
        why=(
            "The current branch must be pushed to GitHub and track a remote branch. "
            "Without this, commits exist only locally and are invisible to collaborators "
            "and CI. It also means 'git status' never shows ahead/behind counts."
        ),
        fix=(
            "Push the branch and set tracking:\n"
            "  git push -u origin <branch>\n"
            "Replace <branch> with the current release branch name (e.g. 0.1)."
        ),
    )


# ---------------------------------------------------------------------------
# Check registry — ordered list of all checks to run
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_agents_project_json,
    check_agents_project_md,
    check_update_agents_py,
    check_agents_md_autogenerated,
    check_locals_txt_example,
    check_gitignore_locals,
    check_branch_not_main,
    check_remote_tracking,
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def check_repo(repo_path: Path) -> RepoReport:
    report = RepoReport(repo_name=repo_path.name, repo_path=repo_path)
    for check_fn in ALL_CHECKS:
        report.checks.append(check_fn(repo_path))
    return report


def print_report(report: RepoReport, verbose: bool = False):
    status = "PASS" if report.passed else "FAIL"
    print(f"\n{'='*60}")
    print(f"  {report.repo_name}  [{status}]")
    print(f"  {report.repo_path}")
    print(f"{'='*60}")
    for check in report.checks:
        icon = "OK  " if check.passed else "FAIL"
        print(f"  [{icon}] {check.name}")
        if not check.passed or verbose:
            if not check.passed:
                print(f"         Why required: {check.why}")
                print(f"         Fix: {check.fix}")
            elif verbose:
                print(f"         {check.why}")


def print_summary(reports: list):
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    pass_count = sum(1 for r in reports if r.passed)
    print(f"  {pass_count}/{len(reports)} repos compliant\n")
    for report in reports:
        status = "PASS" if report.passed else f"FAIL ({len(report.failures)} issue(s))"
        print(f"  {'OK  ' if report.passed else 'FAIL'}  {report.repo_name:<35} {status}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Check repo compliance with nielsoln_agent_standards."
    )
    parser.add_argument(
        "repos", nargs="*",
        help="Repo names to check (default: all repos in LUNK_REPOS_ROOT)"
    )
    parser.add_argument(
        "--root", default=None,
        help="Path to parent directory containing all repos (overrides LUNK_REPOS_ROOT)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show why/fix for passing checks too"
    )
    args = parser.parse_args()

    standards_dir = Path(__file__).parent
    locals_data = _read_locals(standards_dir)

    if args.root:
        lunk_root = Path(args.root)
    else:
        lunk_root_str = locals_data.get("LUNK_REPOS_ROOT", "")
        if not lunk_root_str:
            print("ERROR: LUNK_REPOS_ROOT not found in locals.txt", file=sys.stderr)
            print("Add a line like:", file=sys.stderr)
            print("  LUNK_REPOS_ROOT=C:\\analytics\\projects\\git\\lunk", file=sys.stderr)
            print("Or use --root to specify the path directly.", file=sys.stderr)
            sys.exit(1)
        lunk_root = Path(lunk_root_str)

    if not lunk_root.is_dir():
        print(f"ERROR: LUNK_REPOS_ROOT does not exist: {lunk_root}", file=sys.stderr)
        sys.exit(1)

    # Never audit ourselves — this repo IS the standards source; the update_agents.py
    # and AGENTS.md checks are meaningless here and would always fail by design.
    self_repo = standards_dir.resolve()

    if args.repos:
        targets = [lunk_root / name for name in args.repos]
        missing = [p for p in targets if not p.is_dir()]
        if missing:
            for p in missing:
                print(f"ERROR: repo not found: {p}", file=sys.stderr)
            sys.exit(1)
        skipped = [p for p in targets if p.resolve() == self_repo]
        if skipped:
            print(f"(Skipping {skipped[0].name} — cannot audit the standards repo against itself)", file=sys.stderr)
            targets = [p for p in targets if p.resolve() != self_repo]
        if not targets:
            sys.exit(0)
    else:
        # All subdirectories that look like git repos, excluding this repo
        targets = sorted(
            p for p in lunk_root.iterdir()
            if p.is_dir() and (p / ".git").exists() and p.resolve() != self_repo
        )

    reports = []
    for target in targets:
        report = check_repo(target)
        print_report(report, verbose=args.verbose)
        reports.append(report)

    print_summary(reports)

    all_passed = all(r.passed for r in reports)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
