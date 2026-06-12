#!/usr/bin/env python3
"""
CNF Doc Sync — Standalone Classifier

Analyzes changes in a private repo commit and classifies each as
Verizon-specific or generic. Produces a JSON data file compatible
with the Review UI (python -m cnf_doc_sync_ui --data <file>).

Works with Ollama (local), OpenAI, or Anthropic as the LLM backend.
Most files are classified without an LLM call at all (filename pattern
+ regex matching handles ~80% of cases).

Usage:
    python classify.py <private-commit> [options]

Examples:
    # Ollama (default)
    python classify.py e9a66a20 --model qwen2.5:7b

    # OpenAI
    python classify.py e9a66a20 --provider openai --model gpt-4o

    # Anthropic
    python classify.py e9a66a20 --provider anthropic --model claude-sonnet-4-6
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# VZ marker detection
# ---------------------------------------------------------------------------

VZ_PATTERN = re.compile(
    r"("
    r"\.VCP\s+CNF\s+(requirement|recommendation)"
    r"|Doors\s+Id"
    r"|Requirement\s+Id\s+\d+"
    r"|Verizon"
    r"|\bVCP\b"
    r"|\bWebscale\b|\bWebScale\b"
    r"|\bENSE\b"
    r"|\bSPK\b"
    r"|CPI\s*810"
    r")",
    re.IGNORECASE,
)

HUNK_HEADER_RE = re.compile(r"^@@\s+.*\s+@@")

# ---------------------------------------------------------------------------
# LLM Providers
# ---------------------------------------------------------------------------


class OllamaProvider:
    def __init__(self, model: str = "qwen2.5:7b", url: str = "http://localhost:11434"):
        self.model = model
        self.url = url.rstrip("/")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{self.url}/api/tags")
                return r.status_code == 200
        except httpx.ConnectError:
            return False

    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                f"{self.url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            return r.json()["response"]

    def name(self) -> str:
        return f"ollama/{self.model}"


class OpenAIProvider:
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    async def health_check(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    def name(self) -> str:
        return f"openai/{self.model}"


class AnthropicProvider:
    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    async def health_check(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]

    def name(self) -> str:
        return f"anthropic/{self.model}"


PROVIDERS = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git(repo: str, *args: str) -> str:
    r = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=False
    )
    return r.stdout.strip()


def commit_exists(repo: str, ref: str) -> bool:
    r = subprocess.run(
        ["git", "-C", repo, "cat-file", "-t", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.stdout.strip() == "commit"


def get_commit_msg(repo: str, ref: str) -> str:
    return git(repo, "log", "--format=%s", "-1", ref)


def get_changed_files(repo: str, commit: str) -> list[tuple[str, str]]:
    raw = git(repo, "diff", f"{commit}^..{commit}", "--name-status")
    result = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0][0]
        filepath = parts[-1]
        result.append((status, filepath))
    return result


def get_diff(repo: str, commit: str, filepath: str) -> str:
    return git(repo, "diff", f"{commit}^..{commit}", "--", filepath)


def get_file_at(repo: str, ref: str, filepath: str) -> str:
    return git(repo, "show", f"{ref}:{filepath}")


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

CLASSIFICATION_PROMPT = """You are analyzing a diff from a private Verizon CNF documentation repo to determine if the content is safe to sync to a public Red Hat Kubernetes best practices repo.

**File:** `{filename}`
**Classification so far:** `{file_class}`

{public_context}

**Diff hunks to classify:**
```diff
{diff}
```

**Verizon-Specific Markers — classify as VZ-specific if ANY of these appear:**
- "Verizon", "VCP", "Verizon Communications", "Verizon VCP"
- "Doors Id" or "Doors ID" (Verizon requirements tracking IDs)
- ".VCP CNF requirement" or ".VCP CNF recommendation" (admonition labels)
- "ENSE" (Verizon network fabric)
- "SPK" when used in context of Verizon-specific ingress/egress/load balancing
- Internal hostnames, URLs, or IP ranges
- References to "core ENSE", "edge ENSE" network fabric
- VZ core/edge compute specs (specific hardware references)
- Internal approval processes or Verizon organizational references
- VZ-specific container naming/labeling standards
- References to "CPI 810" or similar Verizon-internal standards

**For EACH hunk, classify as one of:**
- **generic**: Cloud-native best practice. No VZ markers. Safe for public.
- **verizon-specific**: Contains one or more VZ markers. Must stay private.
- **mixed**: Contains BOTH generic content AND VZ-specific content interleaved in the same hunk.

**Respond with ONLY a JSON array, one entry per hunk:**
```json
[
  {{
    "hunk_number": 1,
    "classification": "generic|verizon-specific|mixed",
    "reason": "One sentence explaining why",
    "vz_references": ["list of VZ markers found, empty if generic"],
    "generic_summary": "Brief description of the generic content (if any)",
    "vz_summary": "Brief description of the VZ-specific content (if any)"
  }}
]
```"""


def split_hunks(diff_text: str) -> list[dict]:
    hunks = []
    current_header = None
    current_lines: list[str] = []

    for line in diff_text.splitlines():
        if HUNK_HEADER_RE.match(line):
            if current_header is not None:
                hunks.append(
                    {"header": current_header, "text": "\n".join(current_lines)}
                )
            current_header = line
            current_lines = [line]
        elif current_header is not None:
            current_lines.append(line)

    if current_header is not None:
        hunks.append({"header": current_header, "text": "\n".join(current_lines)})

    return hunks


def extract_changed_lines(diff_text: str) -> list[str]:
    return [
        line
        for line in diff_text.splitlines()
        if line.startswith(("+", "-"))
        and not line.startswith(("+++", "---"))
        and line.strip() not in ("+", "-")
    ]


def parse_llm_json(text: str) -> list[dict]:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts[1:]:
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


async def classify_file(
    provider, filename: str, diff_text: str, file_class: str, public_content: str,
    skip_llm: bool = False,
) -> list[dict]:
    """Three-layer classification: filename → regex → LLM."""

    hunks = split_hunks(diff_text)
    if not hunks:
        return []

    # Layer 1: VZ-prefixed filename
    if "-vz-" in filename:
        return [
            {
                "id": f"h{i+1}",
                "hunk_header": h["header"],
                "diff_text": h["text"],
                "classification": "verizon-specific",
                "reason": "VZ-prefixed file — auto-classified",
                "vz_references": ["filename pattern *-vz-*"],
                "generic_summary": "",
                "vz_summary": "Entire file is Verizon-specific",
            }
            for i, h in enumerate(hunks)
        ]

    # Layer 2: Regex scan per hunk
    all_regex_classified = True
    regex_results = []
    for i, hunk in enumerate(hunks):
        changed = extract_changed_lines(hunk["text"])
        if not changed:
            regex_results.append(None)
            all_regex_classified = False
            continue

        vz_count = sum(1 for l in changed if VZ_PATTERN.search(l))
        total = len(changed)

        if vz_count == total:
            regex_results.append(
                {
                    "id": f"h{i+1}",
                    "hunk_header": hunk["header"],
                    "diff_text": hunk["text"],
                    "classification": "verizon-specific",
                    "reason": "All changed lines contain VZ markers (regex layer)",
                    "vz_references": list(
                        {
                            m.group()
                            for l in changed
                            for m in VZ_PATTERN.finditer(l)
                        }
                    ),
                    "generic_summary": "",
                    "vz_summary": "VZ marker content only",
                }
            )
        elif vz_count == 0:
            regex_results.append(
                {
                    "id": f"h{i+1}",
                    "hunk_header": hunk["header"],
                    "diff_text": hunk["text"],
                    "classification": "generic",
                    "reason": "No VZ markers found (regex layer)",
                    "vz_references": [],
                    "generic_summary": "Generic cloud-native content",
                    "vz_summary": "",
                }
            )
        else:
            regex_results.append(None)
            all_regex_classified = False

    if all_regex_classified:
        return [r for r in regex_results if r is not None]

    # Layer 3: LLM for hunks that regex couldn't resolve
    if skip_llm:
        return [
            r if r is not None else {
                "id": f"h{i+1}",
                "hunk_header": hunks[i]["header"],
                "diff_text": hunks[i]["text"],
                "classification": "mixed",
                "reason": "Regex inconclusive, LLM skipped (--no-llm mode)",
                "vz_references": [],
                "generic_summary": "",
                "vz_summary": "",
            }
            for i, r in enumerate(regex_results)
        ]

    public_ctx = ""
    if public_content:
        public_ctx = f"**Current public file content (for reference):**\n```\n{public_content}\n```\n"

    prompt = CLASSIFICATION_PROMPT.format(
        filename=filename,
        file_class=file_class,
        public_context=public_ctx,
        diff=diff_text,
    )

    print(f"  [LLM] Classifying {filename} ({len(hunks)} hunks)...")
    response = await provider.generate(prompt)
    llm_results = parse_llm_json(response)

    # Merge: use regex results where available, LLM for the rest
    final = []
    llm_idx = 0
    for i, hunk in enumerate(hunks):
        if regex_results[i] is not None:
            final.append(regex_results[i])
        elif llm_idx < len(llm_results):
            r = llm_results[llm_idx]
            llm_idx += 1
            final.append(
                {
                    "id": f"h{i+1}",
                    "hunk_header": hunk["header"],
                    "diff_text": hunk["text"],
                    "classification": r.get("classification", "mixed"),
                    "reason": r.get("reason", "LLM classification"),
                    "vz_references": r.get("vz_references", []),
                    "generic_summary": r.get("generic_summary", ""),
                    "vz_summary": r.get("vz_summary", ""),
                }
            )
        else:
            final.append(
                {
                    "id": f"h{i+1}",
                    "hunk_header": hunk["header"],
                    "diff_text": hunk["text"],
                    "classification": "mixed",
                    "reason": "Defaulting to mixed — LLM did not return enough results",
                    "vz_references": [],
                    "generic_summary": "",
                    "vz_summary": "",
                }
            )

    return final


def file_level_classification(hunks: list[dict]) -> str:
    if not hunks:
        return "vz_specific"
    classifications = {h["classification"] for h in hunks}
    if classifications == {"verizon-specific"}:
        return "vz_specific"
    if classifications == {"generic"}:
        return "shared"
    return "shared"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def run(args: argparse.Namespace) -> None:
    private_repo = os.path.abspath(args.private_repo)
    public_repo = os.path.abspath(args.public_repo)
    commit = args.private_commit

    # Validate
    if not commit_exists(private_repo, commit):
        print(f"ERROR: Commit {commit} not found in {private_repo}")
        print(f"  Pass --private-repo /path/to/vz-cnf-best-practices-guide")
        print(f"  Or set: export CNF_PRIVATE_REPO=/path/to/vz-cnf-best-practices-guide")
        sys.exit(1)

    if args.public_commit and not commit_exists(public_repo, args.public_commit):
        print(f"ERROR: Commit {args.public_commit} not found in {public_repo}")
        print(f"  Pass --public-repo /path/to/guide")
        print(f"  Or set: export CNF_PUBLIC_REPO=/path/to/guide")
        sys.exit(1)

    # Build provider
    provider_cls = PROVIDERS[args.provider]
    kwargs = {"model": args.model}
    if args.provider == "ollama":
        kwargs["url"] = args.ollama_url
    provider = provider_cls(**kwargs)

    if not args.no_llm and not await provider.health_check():
        if args.provider == "ollama":
            print(f"ERROR: Ollama not reachable at {args.ollama_url}")
            print("Start it with: ollama serve")
        else:
            print(f"ERROR: {args.provider} API key not set")
        sys.exit(1)

    commit_msg = get_commit_msg(private_repo, commit)
    print(f"Analyzing private commit: {commit[:8]} \"{commit_msg}\"")
    print(f"LLM provider: {provider.name()}")

    # Get changed files
    changes = get_changed_files(private_repo, commit)

    print(f"Files changed: {len(changes)} total")

    # Classify each file
    files_data = []
    stats = {"auto_skip": 0, "vz_specific": 0, "shared": 0, "llm_calls": 0}
    sem = asyncio.Semaphore(4)

    async def process_file(status: str, filepath: str) -> dict:
        async with sem:
            is_vz = "-vz-" in filepath

            # Map private path to public counterpart
            if filepath.startswith("modules/cnf-best-practices-") and not is_vz:
                topic = re.sub(r"^modules/cnf-best-practices-", "", filepath)
                public_path = f"modules/k8s-best-practices-{topic}"
            elif is_vz:
                public_path = ""
            else:
                # Non-module files: check if same path exists in public repo
                public_path = filepath

            # Check public counterpart exists
            has_public = False
            if public_path:
                check = subprocess.run(
                    ["git", "-C", public_repo, "cat-file", "-e",
                     f"{args.public_commit or 'HEAD'}:{public_path}"],
                    capture_output=True, check=False,
                )
                has_public = check.returncode == 0
                if not has_public and filepath.startswith("modules/"):
                    # Module file with no k8s counterpart — try same filename
                    check2 = subprocess.run(
                        ["git", "-C", public_repo, "cat-file", "-e",
                         f"{args.public_commit or 'HEAD'}:{filepath}"],
                        capture_output=True, check=False,
                    )
                    if check2.returncode == 0:
                        public_path = filepath
                        has_public = True

            file_class = "vz_specific" if is_vz else ("shared" if has_public else "ambiguous")

            # Get diff
            diff_text = get_diff(private_repo, commit, filepath)

            # Get public content for context
            public_content = ""
            if args.public_commit and has_public:
                public_content = get_file_at(public_repo, args.public_commit, public_path)

            # Classify hunks
            hunks = await classify_file(
                provider, filepath, diff_text, file_class, public_content,
                skip_llm=args.no_llm,
            )

            if is_vz:
                stats["auto_skip"] += 1
                print(f"  [AUTO] {filepath} → vz_specific")
            elif all(h["classification"] == "verizon-specific" for h in hunks):
                stats["vz_specific"] += 1
                print(f"  [REGEX] {filepath} → verizon-specific")
            else:
                stats["shared"] += 1
                cls_set = {h["classification"] for h in hunks}
                label = "mixed" if len(cls_set) > 1 else cls_set.pop()
                print(f"  [{'LLM' if any('LLM' in h.get('reason','') for h in hunks) else 'REGEX'}] {filepath} → {label}")

            # Read file content before/after
            content_before = ""
            content_after = ""
            if status != "A":
                content_before = get_file_at(private_repo, f"{commit}^", filepath)
            if status != "D":
                content_after = get_file_at(private_repo, commit, filepath)

            overall = file_level_classification(hunks)

            return {
                "id": f"f{len(files_data)+1}",
                "private_path": filepath,
                "public_path": public_path,
                "file_classification": overall if not is_vz else "vz_specific",
                "file_classification_reason": (
                    "VZ-prefixed filename"
                    if is_vz
                    else hunks[0]["reason"] if hunks else "No hunks"
                ),
                "private_content_before": content_before,
                "private_content_after": content_after,
                "proposed_public_content": "",
                "final_content": "",
                "decision": "auto_excluded" if is_vz or overall == "vz_specific" else "pending",
                "reviewer_classification": "",
                "hunks": hunks,
            }

    tasks = [process_file(s, f) for s, f in changes]
    results = await asyncio.gather(*tasks)
    files_data = sorted(results, key=lambda f: f["private_path"])

    # Reassign sequential IDs
    for i, f in enumerate(files_data):
        f["id"] = f"f{i+1}"
        for j, h in enumerate(f["hunks"]):
            h["id"] = f"f{i+1}-h{j+1}"

    # Build output
    head_short = git(private_repo, "rev-parse", "--short", commit)
    data = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "private_repo": private_repo,
        "public_repo": public_repo,
        "since_ref": head_short,
        "head_ref": head_short,
        "public_ref": args.public_commit[:7] if args.public_commit else "",
        "files": files_data,
    }

    reports_dir = Path(private_repo).parent / "cnf-doc-sync-tool" / "reports"
    if not reports_dir.exists():
        reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    output = args.output or str(reports_dir / f"cnf-doc-sync-data-{datetime.now():%Y-%m-%d}.json")
    Path(output).write_text(json.dumps(data, indent=2))

    # Summary
    pending = sum(1 for f in files_data if f["decision"] == "pending")
    excluded = sum(1 for f in files_data if f["decision"] == "auto_excluded")
    print(f"\nClassification complete:")
    print(f"  Total files:        {len(files_data)}")
    print(f"  VZ auto-skip:       {stats['auto_skip']}")
    print(f"  VZ (regex/LLM):     {stats['vz_specific']}")
    print(f"  Pending review:     {pending}")
    print(f"  Auto-excluded:      {excluded}")
    print(f"\nOutput: {output}")
    print(f"\nLaunch review UI:")
    print(f"  python -m cnf_doc_sync_ui --data {output}")


def main():
    p = argparse.ArgumentParser(
        description="CNF Doc Sync — Standalone Classifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python classify.py e9a66a20 --model qwen2.5:7b
  python classify.py e9a66a20 --provider openai --model gpt-4o
  python classify.py e9a66a20 --public-commit 7a8e5c8 --output results.json
        """,
    )
    p.add_argument("private_commit", help="Private repo commit hash to analyze")
    p.add_argument(
        "--public-commit", default="", help="Public repo commit for context"
    )
    p.add_argument(
        "--private-repo",
        default=os.environ.get("CNF_PRIVATE_REPO", "."),
        help="Path to private repo (default: . or $CNF_PRIVATE_REPO)",
    )
    p.add_argument(
        "--public-repo",
        default=os.environ.get("CNF_PUBLIC_REPO", "../guide"),
        help="Path to public repo (default: ../guide or $CNF_PUBLIC_REPO)",
    )
    p.add_argument(
        "--provider",
        choices=list(PROVIDERS.keys()),
        default="ollama",
        help="LLM provider (default: ollama)",
    )
    p.add_argument(
        "--model", default="qwen2.5:7b", help="Model name (default: qwen2.5:7b)"
    )
    p.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama API URL (default: http://localhost:11434)",
    )
    p.add_argument("--output", help="Output JSON path (default: auto-dated)")
    p.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM calls — use regex only, classify ambiguous hunks as mixed",
    )
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
