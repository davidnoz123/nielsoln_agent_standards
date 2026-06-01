#!/usr/bin/env python3
"""update_agents.py — Generate AGENTS.md from nielsoln_agent_standards profiles.

This is the CENTRAL script that lives in the nielsoln_agent_standards repo.
It is invoked via the thin shim update_agents.py in each project repo.

Run from a project repo root (via the shim):

    python update_agents.py              # write AGENTS.md
    python update_agents.py --dry-run    # print to stdout, do not write
    python update_agents.py --output PATH  # write to a specific path

Reads AGENTS.project.json from the project repo root to determine which profiles to download.
"""

import sys
import os
import json
import subprocess
import shutil
import urllib.request
import urllib.error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_repo_root():
    """Return the current working directory (expected to be the project repo root)."""
    return os.getcwd()


def _read_locals(repo_root):
    """Parse locals.txt from repo_root. Returns {key: value} dict."""
    result = {}
    path = os.path.join(repo_root, "locals.txt")
    if not os.path.exists(path):
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


def _read_project_config(repo_root):
    """Read and validate AGENTS.project.json from repo_root."""
    path = os.path.join(repo_root, "AGENTS.project.json")
    if not os.path.exists(path):
        print(f"ERROR: AGENTS.project.json not found in {repo_root}", file=sys.stderr)
        print("       Create it with a 'standards_repo_raw_base' and 'profiles' key.", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    if "standards_repo_raw_base" not in config:
        print("ERROR: AGENTS.project.json missing 'standards_repo_raw_base'", file=sys.stderr)
        sys.exit(1)
    if "profiles" not in config or not isinstance(config["profiles"], list):
        print("ERROR: AGENTS.project.json missing or invalid 'profiles' list", file=sys.stderr)
        sys.exit(1)
    return config


def _download(url, timeout=15):
    """Download text from url. Returns content string. Raises RuntimeError on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "update_agents/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError(f"Unexpected error fetching {url}: {exc}") from exc


def _get_standards_sha(standards_dir):
    """Return the short HEAD SHA of the standards repo, or 'unknown'."""
    if not standards_dir or not os.path.isdir(standards_dir):
        return "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=standards_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _ensure_project_md(repo_root):
    """Create a minimal AGENTS.project.md if one does not already exist."""
    path = os.path.join(repo_root, "AGENTS.project.md")
    if os.path.exists(path):
        return
    content = """\
# AGENTS.project.md — Project-Specific Agent Instructions

<!-- Edit this file freely. It is NOT auto-generated. -->
<!-- Rules here override the central standards in AGENTS.md. -->

## Project Overview

> TODO: Describe this project's purpose and structure.

## Project-Specific Rules

> TODO: Add rules that are specific to this project.

## Environment Setup

> TODO: Document environment-specific setup steps (venv, locals.txt variables, etc.).
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [created] AGENTS.project.md (minimal template)")


def _ensure_gitignore_entry(repo_root):
    """Ensure AGENTS.local.md is listed in .gitignore."""
    entry = "AGENTS.local.md"
    gitignore_path = os.path.join(repo_root, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path, encoding="utf-8") as f:
            content = f.read()
        if entry in content:
            return  # already present
        addition = f"\n# Agent local overrides (machine-specific, must not be committed)\n{entry}\n"
        with open(gitignore_path, "a", encoding="utf-8") as f:
            if not content.endswith("\n"):
                f.write("\n")
            f.write(addition)
        print(f"  [updated] .gitignore — added {entry}")
    else:
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(f"# Agent local overrides (machine-specific, must not be committed)\n{entry}\n")
        print(f"  [created] .gitignore with {entry}")


# ---------------------------------------------------------------------------
# AGENTS.md generation
# ---------------------------------------------------------------------------

def _section_heading(profile_name):
    """Return the markdown heading for a profile section."""
    if profile_name == "AGENTS.base":
        return "Base Agent Rules"
    stem = profile_name.split("/")[-1]
    return f"Profile: {stem}"


def _build_content(sections, config, standards_sha):
    """Assemble the full AGENTS.md string from downloaded sections."""
    raw_base = config["standards_repo_raw_base"].rstrip("/")
    github_url = raw_base.replace(
        "https://raw.githubusercontent.com/", "https://github.com/"
    ).replace("/main", "")

    lines = []

    # Header
    lines += [
        "# AGENTS.md",
        "",
        "<!-- AUTO-GENERATED by update_agents.py. DO NOT EDIT DIRECTLY. -->",
        f"<!-- Standards SHA: {standards_sha} -->",
        "",
        "---",
        "",
        "## Source",
        "",
        f"Generated from: {github_url}",
        "",
        "Profiles loaded:",
    ]
    for p in config["profiles"]:
        lines.append(f"- `{p}`")
    lines += ["", "---", ""]

    # Inline each downloaded section
    for profile_name, content in sections.items():
        heading = _section_heading(profile_name)
        lines += [
            f"## {heading}",
            "",
            content.strip(),
            "",
            "---",
            "",
        ]

    # Reference sections (not inlined)
    lines += [
        "## Project-Specific Instructions",
        "",
        "**Before proceeding, read `AGENTS.project.md` in this directory.**",
        "",
        "Its rules take precedence over the central standards above. It describes project",
        "structure, architecture, domain-specific conventions, and environment setup.",
        "",
        "---",
        "",
        "## Local Private Instructions",
        "",
        "**If `AGENTS.local.md` exists in this directory, read it.**",
        "",
        "Its rules take precedence over everything else (central standards and project-specific",
        "instructions). It is machine-specific and must NOT be committed.",
        "",
        "---",
        "",
        "## Agent Workflows",
        "",
        "### Push: Promote a rule to `nielsoln_agent_standards`",
        "",
        "To promote a rule from `AGENTS.project.md` to the central standards:",
        "",
        "1. Read `AGENTS.project.md` and identify the rule to promote.",
        "2. Read `locals.txt` to find `AGENT_STANDARDS_DIR`.",
        "3. Determine which file the rule belongs to:",
        "   - Universal (applies to all Python repos) → `AGENTS.base.md`",
        "   - Domain-specific → `profiles/<name>.md`",
        "   - New domain not yet represented → create `profiles/<new-name>.md`",
        "4. Read the target file from `<AGENT_STANDARDS_DIR>/` on disk.",
        "5. Insert the rule in the appropriate section.",
        "6. **Show the diff and ask for confirmation before saving.**",
        "7. After confirmation, save the file and `git commit` in `AGENT_STANDARDS_DIR`.",
        "   Do NOT `git push` until the user says so.",
        "",
        "### Pull: Update `AGENTS.md` from `nielsoln_agent_standards`",
        "",
        "To regenerate `AGENTS.md` with the latest central standards:",
        "",
        "1. Run: `python update_agents.py --output AGENTS.md.new`",
        "2. Diff `AGENTS.md.new` against the current `AGENTS.md`.",
        "3. **Show the diff to the user and ask for confirmation before overwriting.**",
        "4. If confirmed: replace `AGENTS.md` with `AGENTS.md.new`, delete `AGENTS.md.new`.",
        "5. Do NOT commit automatically — let the user review the result first.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    # Parse arguments
    output_path = None
    dry_run = False
    cli_standards_dir = None
    i = 0
    while i < len(argv):
        if argv[i] == "--dry-run":
            dry_run = True
            i += 1
        elif argv[i] in ("--output", "-o") and i + 1 < len(argv):
            output_path = argv[i + 1]
            i += 2
        elif argv[i] == "--standards-dir" and i + 1 < len(argv):
            cli_standards_dir = argv[i + 1]
            i += 2
        else:
            print(f"ERROR: Unknown argument: {argv[i]}", file=sys.stderr)
            print("Usage: python update_agents.py [--dry-run] [--output PATH] [--standards-dir PATH]", file=sys.stderr)
            return 1

    repo_root = _find_repo_root()
    print(f"Repo root  : {repo_root}")

    # Read project config
    config = _read_project_config(repo_root)
    raw_base = config["standards_repo_raw_base"].rstrip("/")
    profiles = config["profiles"]
    print(f"Standards  : {raw_base}")
    print(f"Profiles   : {profiles}")

    # Try to get the local standards repo SHA for the metadata footer
    # Priority: --standards-dir CLI arg > locals.txt > env var AGENT_STANDARDS_DIR
    if cli_standards_dir:
        standards_dir = os.path.abspath(cli_standards_dir)
    else:
        locals_data = _read_locals(repo_root)
        standards_dir = locals_data.get("AGENT_STANDARDS_DIR") or os.environ.get("AGENT_STANDARDS_DIR", "")
        if standards_dir and not os.path.isabs(standards_dir):
            standards_dir = os.path.normpath(os.path.join(repo_root, standards_dir))
    standards_sha = _get_standards_sha(standards_dir)

    # Download all profiles
    sections = {}
    for profile in profiles:
        url = f"{raw_base}/{profile}.md"
        print(f"  downloading {profile} ... ", end="", flush=True)
        try:
            sections[profile] = _download(url)
            print("OK")
        except RuntimeError as exc:
            print(f"FAILED\n  ERROR: {exc}", file=sys.stderr)
            return 1

    # Build output content
    content = _build_content(sections, config, standards_sha)

    if dry_run:
        print("\n" + "=" * 72)
        print("DRY RUN — AGENTS.md would be written as follows:")
        print("=" * 72 + "\n")
        print(content)
        return 0

    # Determine output file
    if output_path is None:
        output_path = os.path.join(repo_root, "AGENTS.md")
    elif not os.path.isabs(output_path):
        output_path = os.path.join(repo_root, output_path)

    # Write atomically via temp file
    tmp_path = output_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        shutil.move(tmp_path, output_path)
    except Exception as exc:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        print(f"ERROR: could not write {output_path}: {exc}", file=sys.stderr)
        return 1

    print(f"\n  [wrote]   {output_path}")
    print(f"  Standards SHA : {standards_sha}")

    # Housekeeping (idempotent)
    _ensure_project_md(repo_root)
    _ensure_gitignore_entry(repo_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
