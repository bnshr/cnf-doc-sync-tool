"""PR creation for CNF Doc Sync — uses local git + gh CLI."""

from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


def _build_vz_regex(data: dict[str, Any]) -> re.Pattern[str] | None:
    """Build VZ marker regex from the JSON data's ``vz_markers`` list.

    Returns None if no markers are configured — callers skip the check.
    """
    markers: list[str] = data.get("vz_markers", [])
    if not markers:
        return None
    escaped = [re.escape(m) for m in markers]
    return re.compile("|".join(escaped), re.IGNORECASE)


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def create_pr(data: dict[str, Any]) -> dict[str, Any]:
    public_repo = data.get("public_repo", "")
    if not public_repo or not Path(public_repo).is_dir():
        return {"error": f"Public repo path not found: {public_repo}"}

    # Check gh CLI is authenticated
    r = _run(["gh", "auth", "status"])
    if r.returncode != 0:
        return {"error": "gh CLI is not authenticated. Run 'gh auth login' first."}

    # Check clean working tree
    r = _run(["git", "status", "--porcelain"], cwd=public_repo)
    if r.stdout.strip():
        return {"error": "Public repo has uncommitted changes. Commit or stash them first."}

    # Collect accepted files
    accepted = [f for f in data["files"] if f["decision"] == "accepted"]
    if not accepted:
        return {"error": "No changes were accepted. Nothing to publish."}

    # Create branch
    today = date.today().isoformat()
    branch = f"sync/vz-{today}"
    _run(["git", "checkout", "main"], cwd=public_repo)
    _run(["git", "pull", "origin", "main"], cwd=public_repo)

    r = _run(["git", "checkout", "-b", branch], cwd=public_repo)
    if r.returncode != 0:
        counter = 2
        while counter <= 10:
            branch = f"sync/vz-{today}-{counter}"
            r = _run(["git", "checkout", "-b", branch], cwd=public_repo)
            if r.returncode == 0:
                break
            counter += 1
        else:
            return {"error": f"Could not create branch {branch}"}

    committed = 0
    skipped = []

    vz_re = _build_vz_regex(data)
    applied_files = []
    warnings: list[str] = []

    for f in accepted:
        public_path = f.get("public_path", "")
        if not public_path:
            skipped.append(f"{f['private_path']} (no public counterpart)")
            continue

        content = f.get("final_content") or f.get("proposed_public_content", "")
        if not content:
            skipped.append(f"{f['private_path']} (no content)")
            continue

        reviewer_edited = (
            bool(f.get("final_content"))
            and f.get("final_content") != f.get("proposed_public_content", "")
        )

        # VZ marker check: warn but never block reviewer-edited content
        if vz_re:
            vz_hit = vz_re.search(content)
            if vz_hit:
                if reviewer_edited:
                    warnings.append(
                        f"{f['private_path']}: VZ marker {vz_hit.group()!r} present "
                        f"in reviewer-edited content (included per reviewer decision)"
                    )
                else:
                    skipped.append(
                        f"{f['private_path']} (blocked: VZ marker found: "
                        f"{vz_hit.group()!r} — edit the content to remove it)"
                    )
                    continue

        target = Path(public_repo) / public_path

        # Fragment check: warn but never block reviewer-edited content
        if target.exists():
            existing_len = len(target.read_text())
            if existing_len > 100 and len(content) < existing_len * 0.2:
                if reviewer_edited:
                    warnings.append(
                        f"{f['private_path']}: content is {len(content)} chars "
                        f"vs existing {existing_len} (included per reviewer decision)"
                    )
                else:
                    skipped.append(
                        f"{f['private_path']} (blocked: content is {len(content)} chars "
                        f"vs existing {existing_len} — looks like a fragment)"
                    )
                    continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        applied_files.append(f)
        committed += 1

    if committed == 0:
        _run(["git", "checkout", "main"], cwd=public_repo)
        _run(["git", "branch", "-D", branch], cwd=public_repo)
        return {"error": "No files could be applied. All accepted files were skipped."}

    # Stage, commit, push
    _run(["git", "add", "modules/"], cwd=public_repo)
    commit_msg = f"sync: apply changes from vz-cnf-best-practices-guide ({today})"
    _run(["git", "commit", "-m", commit_msg], cwd=public_repo)

    r = _run(["git", "push", "-u", "origin", branch], cwd=public_repo)
    if r.returncode != 0:
        return {"error": f"Push failed: {r.stderr.strip()}"}

    # Build PR body — only list files that were actually written
    since = data.get("since_ref", "?")
    head = data.get("head_ref", "HEAD")
    changes_md = ""
    for f in applied_files:
        pp = f.get("public_path", f["private_path"])
        reason = f.get("file_classification_reason", "")
        changes_md += f"- `{pp}` — {reason}\n"

    pr_body = f"""## Summary

Synced documentation changes from vz-cnf-best-practices-guide to the public guide.

**Source:** vz-cnf-best-practices-guide @ `{since}`..`{head}`

## Changes Included

{changes_md}

## Review Process

Changes were classified by AI content analysis and reviewed manually via the CNF Doc Sync Review UI. Verizon-specific content was filtered out."""

    r = _run(
        [
            "gh", "pr", "create",
            "--title", f"Sync changes from VZ CNF guide ({today})",
            "--body", pr_body,
        ],
        cwd=public_repo,
    )

    pr_url = ""
    if r.returncode == 0:
        pr_url = r.stdout.strip()
    else:
        return {
            "committed": committed,
            "skipped": skipped,
            "error": f"PR creation failed: {r.stderr.strip()}",
        }

    return {
        "committed": committed,
        "skipped": skipped,
        "warnings": warnings,
        "pr_url": pr_url,
        "branch": branch,
    }
