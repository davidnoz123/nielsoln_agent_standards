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
import re
import urllib.request
import urllib.error
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
    warning: bool = False  # advisory only — shown as [WARN], does not affect PASS/FAIL


@dataclass
class RepoReport:
    repo_name: str
    repo_path: Path
    checks: list = field(default_factory=list)

    @property
    def passed(self):
        """True if all non-warning checks pass (warnings do not affect pass/fail)."""
        return all(c.passed for c in self.checks if not c.warning)

    @property
    def failures(self):
        return [c for c in self.checks if not c.passed and not c.warning]

    @property
    def warnings(self):
        return [c for c in self.checks if not c.passed and c.warning]


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


def check_claude_md(repo: Path) -> CheckResult:
    path = repo / "CLAUDE.md"
    exists = path.exists()
    has_import = False
    if exists:
        content = path.read_text(encoding="utf-8", errors="replace")
        has_import = "@AGENTS.md" in content
    return CheckResult(
        name="CLAUDE.md (@AGENTS.md)",
        passed=exists and has_import,
        why=(
            "Claude Code automatically reads CLAUDE.md at session start. "
            "Without it, the agent instructions in AGENTS.md are invisible to Claude Code "
            "unless the agent manually discovers and reads the file. "
            "A one-line CLAUDE.md containing '@AGENTS.md' bridges the two systems."
        ),
        fix=(
            "Create CLAUDE.md in the repo root containing exactly:\n"
            "  @AGENTS.md\n"
            "This tells Claude Code to load AGENTS.md as its instruction source."
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


def _get_current_branch(repo: Path) -> str:
    """Return current git branch name or 'unknown' if branch cannot be read."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo, capture_output=True, text=True, timeout=10
        )
        branch = result.stdout.strip()
        return branch or "unknown"
    except Exception:
        return "unknown"


def _parse_release_branch(name: str):
    """Return (major, minor) for release branch names like '0.1', else None."""
    m = re.fullmatch(r"(\d+)\.(\d+)", name or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _get_latest_remote_release_branch(repo: Path):
    """Return latest remote release branch name (e.g. '0.2'), or None."""
    import subprocess

    try:
        remote_url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo, capture_output=True, text=True, timeout=10
        ).stdout.strip()
        if not remote_url:
            return None

        ls = subprocess.run(
            ["git", "ls-remote", "--heads", remote_url],
            cwd=repo, capture_output=True, text=True, timeout=30
        )
        if ls.returncode != 0:
            return None

        remote_branches = [
            line.split("refs/heads/", 1)[1].strip()
            for line in ls.stdout.splitlines()
            if "refs/heads/" in line
        ]
        versioned = [b for b in remote_branches if _parse_release_branch(b)]
        if not versioned:
            return None
        return max(versioned, key=_parse_release_branch)
    except Exception:
        return None


def check_branch_not_main(repo: Path) -> CheckResult:
    """
    All development happens on a <N>.<M> release branch, never directly on main.
    main is production/stable only and is only updated via merges from release branches.
    """
    branch = _get_current_branch(repo)
    on_main = branch == "main"
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


def check_on_latest_branch(repo: Path) -> CheckResult:
    """
    The current branch should be the highest-versioned <N>.<M> branch on the remote.
    Uses git ls-remote for a live view (no stale cache). Advisory warning only.
    """
    import subprocess

    try:
        cur = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo, capture_output=True, text=True, timeout=10
        ).stdout.strip()

        latest = _get_latest_remote_release_branch(repo)
        if not latest:
            return CheckResult(
                name=f"latest branch (no versioned remote branches)",
                passed=True, warning=True, why="", fix="",
            )
        on_latest = (cur == latest)
    except Exception:
        return CheckResult(
            name="latest branch (check failed)",
            passed=True, warning=True, why="", fix="",
        )

    return CheckResult(
        name=f"latest branch (current: {cur}, latest remote: {latest})",
        passed=on_latest,
        warning=True,
        why=(
            "Active development should be on the highest-versioned remote branch. "
            "Being on an older branch is usually an oversight after a new release "
            "cycle has started."
        ),
        fix=(
            f"Switch to the latest branch: git checkout {latest}\n"
            "If you intentionally need to patch an older release, ignore this warning."
        ),
    )


def check_stale_branch_modification_risk(repo: Path) -> CheckResult:
    """Warn when work appears to be happening on main/older release branch."""
    import subprocess

    cur = _get_current_branch(repo)
    latest = _get_latest_remote_release_branch(repo)
    if not latest:
        return CheckResult(
            name="stale branch modification risk (no versioned remote branches)",
            passed=True, warning=True, why="", fix="",
        )

    cur_ver = _parse_release_branch(cur)
    latest_ver = _parse_release_branch(latest)
    on_stale_branch = (cur == "main") or (
        cur_ver is not None and latest_ver is not None and cur_ver < latest_ver
    )
    if not on_stale_branch:
        return CheckResult(
            name=f"stale branch modification risk (current: {cur}, latest: {latest})",
            passed=True,
            warning=True,
            why="",
            fix="",
        )

    try:
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo, capture_output=True, text=True, timeout=10
            ).stdout.strip()
        )

        ahead = 0
        ahead_proc = subprocess.run(
            ["git", "rev-list", "--count", "@{u}..HEAD"],
            cwd=repo, capture_output=True, text=True, timeout=10
        )
        if ahead_proc.returncode == 0:
            ahead = int((ahead_proc.stdout or "0").strip() or "0")

        unique_vs_latest = 0
        have_latest_ref = subprocess.run(
            ["git", "show-ref", "--verify", f"refs/remotes/origin/{latest}"],
            cwd=repo, capture_output=True, text=True, timeout=10
        ).returncode == 0
        if have_latest_ref:
            uvl_proc = subprocess.run(
                ["git", "rev-list", "--count", f"origin/{latest}..HEAD"],
                cwd=repo, capture_output=True, text=True, timeout=10
            )
            if uvl_proc.returncode == 0:
                unique_vs_latest = int((uvl_proc.stdout or "0").strip() or "0")

        has_risk = dirty or ahead > 0 or unique_vs_latest > 0
        details = []
        if dirty:
            details.append("dirty working tree")
        if ahead > 0:
            details.append(f"{ahead} unpushed commit(s) on current branch")
        if unique_vs_latest > 0:
            details.append(f"{unique_vs_latest} commit(s) not in origin/{latest}")
        detail_str = "; ".join(details) if details else "no local modifications detected"
    except Exception:
        return CheckResult(
            name=f"stale branch modification risk (current: {cur}, latest: {latest})",
            passed=True, warning=True, why="", fix="",
        )

    return CheckResult(
        name=(
            f"stale branch modification risk (current: {cur}, latest: {latest}; {detail_str})"
        ),
        passed=not has_risk,
        warning=True,
        why=(
            "Changes on main or an older release branch are often intended for the latest "
            "release branch and can be accidentally stranded."
        ),
        fix=(
            f"If this work belongs on {latest}, switch branches and move it there (commit/cherry-pick "
            "or stash/pop), then rerun compliance."
        ),
    )


def check_github_visibility(repo: Path, github_token: str) -> CheckResult:
    """
    Warn if the GitHub repo is public. All lunk repos should be private by default.
    Skipped gracefully if no GITHUB_TOKEN is available or the remote is not GitHub.
    """
    import re
    import subprocess

    if not github_token:
        return CheckResult(
            name="GitHub visibility (no GITHUB_TOKEN in locals.txt — skipped)",
            passed=True, warning=True, why="", fix="",
        )

    try:
        remote_url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        remote_url = ""

    # Parse owner/repo from https or ssh GitHub URLs
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(\.git)?$", remote_url)
    if not m:
        return CheckResult(
            name="GitHub visibility (not a GitHub remote — skipped)",
            passed=True, warning=True, why="", fix="",
        )

    owner, repo_name = m.group(1), m.group(2)
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"

    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        is_private = data.get("private", True)
    except urllib.error.HTTPError as e:
        return CheckResult(
            name=f"GitHub visibility (API error {e.code} — skipped)",
            passed=True, warning=True, why="", fix="",
        )
    except Exception:
        return CheckResult(
            name="GitHub visibility (API call failed — skipped)",
            passed=True, warning=True, why="", fix="",
        )

    return CheckResult(
        name=f"GitHub visibility ({owner}/{repo_name}: {'private' if is_private else 'PUBLIC'})",
        passed=is_private,
        warning=True,
        why=(
            "All lunk repos should be private by default. A public repo exposes "
            "code, commit history, and branch names to anyone on the internet."
        ),
        fix=(
            f"Go to https://github.com/{owner}/{repo_name}/settings \u2192 "
            "'Danger Zone' \u2192 'Change repository visibility' \u2192 Private.\n"
            "Or if this repo is intentionally public (e.g. open-source), ignore this warning."
        ),
    )


# ---------------------------------------------------------------------------
# Check registry — ordered list of all checks to run
# ---------------------------------------------------------------------------

# Checks that are meaningless for the standards repo itself (it IS the source).
# All other checks (git state, branch, tracking, latest) still run on it.
AGENTS_INFRA_CHECKS = {
    check_agents_project_json,
    check_agents_project_md,
    check_update_agents_py,
    check_agents_md_autogenerated,
    check_locals_txt_example,
    check_claude_md,
}

ALL_CHECKS = [
    check_agents_project_json,
    check_agents_project_md,
    check_update_agents_py,
    check_agents_md_autogenerated,
    check_locals_txt_example,
    check_claude_md,
    check_gitignore_locals,
    check_branch_not_main,
    check_remote_tracking,
    check_on_latest_branch,
    check_stale_branch_modification_risk,
    check_github_visibility,
]


# ORIGINAL SIN EXCEPTIONS
# -----------------------
# Keep root-cause gating rules in one place. When an "original sin" is present,
# suppress derivative checks that are expected to fail as a consequence.
# Add future exception rules here so the onboarding output remains concise.
ORIGINAL_SIN_RULES = [
    {
        "id": "on-main-branch",
        "name": "repo is on main branch",
        "predicate": lambda repo: _get_current_branch(repo) == "main",
        "suppress": {
            check_agents_project_json,
            check_agents_project_md,
            check_update_agents_py,
            check_agents_md_autogenerated,
            check_locals_txt_example,
            check_claude_md,
            check_gitignore_locals,
        },
        "why": (
            "On main branch, AGENTS onboarding checks are often noisy derivative failures. "
            "Treat branch state as the root-cause first."
        ),
        "fix": (
            "Switch to or create a release branch first (for example 0.1), then rerun compliance "
            "to see downstream AGENTS setup issues if they still exist."
        ),
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def check_repo(repo_path: Path, is_self: bool = False, github_token: str = "") -> RepoReport:
    report = RepoReport(repo_name=repo_path.name, repo_path=repo_path)

    suppressed = set()
    for rule in ORIGINAL_SIN_RULES:
        try:
            triggered = bool(rule["predicate"](repo_path))
        except Exception:
            triggered = False
        if not triggered:
            continue
        suppressed.update(rule["suppress"])
        report.checks.append(
            CheckResult(
                name=f"original sin ({rule['id']}): {rule['name']}",
                passed=False,
                warning=True,
                why=rule["why"],
                fix=rule["fix"],
            )
        )

    for check_fn in ALL_CHECKS:
        if is_self and check_fn in AGENTS_INFRA_CHECKS:
            continue  # standards repo is exempt from AGENTS infrastructure checks
        if check_fn in suppressed:
            continue
        if check_fn is check_github_visibility:
            report.checks.append(check_github_visibility(repo_path, github_token))
        else:
            report.checks.append(check_fn(repo_path))
    return report


def print_report(report: RepoReport, verbose: bool = False):
    status = "PASS" if report.passed else "FAIL"
    if report.passed and report.warnings:
        status = "PASS (warnings)"
    print(f"\n{'='*60}")
    print(f"  {report.repo_name}  [{status}]")
    print(f"  {report.repo_path}")
    print(f"{'='*60}")
    for check in report.checks:
        if check.passed:
            icon = "OK  "
        elif check.warning:
            icon = "WARN"
        else:
            icon = "FAIL"
        print(f"  [{icon}] {check.name}")
        if not check.passed or verbose:
            if not check.passed and check.why:
                print(f"         Why: {check.why}")
                print(f"         Fix: {check.fix}")
            elif verbose and check.why:
                print(f"         {check.why}")


def print_summary(reports: list):
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    pass_count = sum(1 for r in reports if r.passed)
    print(f"  {pass_count}/{len(reports)} repos compliant\n")
    for report in reports:
        if report.passed and report.warnings:
            icon = "WARN"
            status = f"PASS ({len(report.warnings)} warning(s))"
        elif report.passed:
            icon = "OK  "
            status = "PASS"
        else:
            icon = "FAIL"
            status = f"FAIL ({len(report.failures)} issue(s))"
            if report.warnings:
                status += f" + {len(report.warnings)} warning(s)"
        print(f"  {icon}  {report.repo_name:<35} {status}")
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

    # The standards repo itself is exempt from AGENTS infrastructure checks
    # (it IS the source), but git/branch/tracking checks still apply.
    self_repo = standards_dir.resolve()

    if args.repos:
        targets = [lunk_root / name for name in args.repos]
        missing = [p for p in targets if not p.is_dir()]
        if missing:
            for p in missing:
                print(f"ERROR: repo not found: {p}", file=sys.stderr)
            sys.exit(1)
    else:
        targets = sorted(
            p for p in lunk_root.iterdir()
            if p.is_dir() and (p / ".git").exists()
        )

    github_token = locals_data.get("GITHUB_TOKEN", "")

    reports = []
    for target in targets:
        is_self = target.resolve() == self_repo
        report = check_repo(target, is_self=is_self, github_token=github_token)
        print_report(report, verbose=args.verbose)
        reports.append(report)

    print_summary(reports)

    all_passed = all(r.passed for r in reports)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
