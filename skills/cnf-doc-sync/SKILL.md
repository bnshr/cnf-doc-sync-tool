---
name: cnf-doc-sync
description: |-
  Sync documentation changes from the private vz-cnf-best-practices-guide repo to the public Red Hat K8s guide repo.
  Use when the user wants to compare commits between private and public CNF/K8s guide repos, classify changes as Verizon-specific vs generic, generate a sync review report, launch the review UI, or create a PR from a reviewed report.
  Trigger on: doc sync, CNF sync, VZ guide sync, guide repo comparison, private-to-public sync, cnf-doc-sync, or any mention of syncing vz-cnf-best-practices-guide with guide.
---

# CNF Doc Sync

Synchronize documentation changes from the private Verizon CNF best practices repo to the public Red Hat K8s best practices repo. Changes are classified using AI content analysis, presented in a reviewable markdown report, and optionally turned into a PR on the public repo.

## Repos

| Repo | Local Path | File Prefix | Role |
|------|-----------|-------------|------|
| `vz-cnf-best-practices-guide` | `/Users/bmandal/work/ai/vz-cnf-best-practices-guide` | `cnf-best-practices-*` | Private (source) |
| `guide` | `/Users/bmandal/work/ai/guide` | `k8s-best-practices-*` | Public (target) |

Verizon-specific modules use the `cnf-best-practices-vz-*` naming pattern. Shared modules map by topic: `cnf-best-practices-<topic>.adoc` in private corresponds to `k8s-best-practices-<topic>.adoc` in public.

## Invocation

### Mode 1: Generate Report

```
/cnf-doc-sync <private-commit-hash> [public-commit-hash]
```

- `private-commit-hash` (required): Commit in the private repo. Diff is from this commit to HEAD.
- `public-commit-hash` (optional): Commit in the public repo. Used as context — read public files at this commit to check if a change already exists.

### Mode 2: Launch Review UI

```
/cnf-doc-sync --review <path-to-json-data>
```

Launches the web-based review UI for a previously generated JSON data file. Opens a browser for interactive accept/reject/edit decisions and PR creation.

### Mode 3: Create PR from Reviewed Report (legacy)

```
/cnf-doc-sync --create-pr <path-to-reviewed-report.md>
```

Parses the reviewed markdown report and creates a PR on the public repo with accepted changes.

## Argument Parsing

Parse the `args` string to determine the mode:

- If args starts with `--review`, extract the JSON data path after it. Enter **Mode 2**.
- If args starts with `--create-pr`, extract the report path after it. Enter **Mode 3**.
- Otherwise, the first argument is the `private-commit-hash` (required). The second argument, if present, is the `public-commit-hash` (optional). Enter **Mode 1**.

If no args are provided, tell the user the usage and stop.

---

## Mode 1 Procedure: Generate Report

### Phase 1: Git Diff Extraction

Run these commands in the private repo (`/Users/bmandal/work/ai/vz-cnf-best-practices-guide`):

1. Validate the commit hash exists:
   ```
   git -C /Users/bmandal/work/ai/vz-cnf-best-practices-guide cat-file -t <private-commit-hash>
   ```
   If this fails, tell the user: "Commit `<hash>` not found in vz-cnf-best-practices-guide. Please provide a valid commit hash." and stop.

2. Get the list of changed files:
   ```
   git -C /Users/bmandal/work/ai/vz-cnf-best-practices-guide diff <private-commit>..HEAD --name-status
   ```

3. Get the full diff content:
   ```
   git -C /Users/bmandal/work/ai/vz-cnf-best-practices-guide diff <private-commit>..HEAD
   ```

4. If a `public-commit-hash` was provided, validate it in the public repo:
   ```
   git -C /Users/bmandal/work/ai/guide cat-file -t <public-commit-hash>
   ```
   If this fails, tell the user: "Commit `<hash>` not found in guide repo. Please provide a valid commit hash or omit it." and stop.

5. If no files changed, tell the user: "No changes detected between `<commit>` and HEAD." and stop.

6. Parse the diff output. Group changes by file. For each file, extract individual diff hunks (sections starting with `@@`).

### Phase 2: Auto-Classification

Classify each changed file into an initial bucket by filename pattern:

1. **Verizon-only**: Files matching `*-vz-*` (e.g., `cnf-best-practices-vz-networking-overview.adoc`). These are auto-classified — skip AI analysis. They go directly into the "Verizon-Specific Changes" section of the report.

2. **Shared**: Files that have a matching counterpart in the public repo. To check, strip the `cnf-best-practices-` prefix from the private filename and look for `k8s-best-practices-<same-topic>.adoc` in `/Users/bmandal/work/ai/guide/modules/`. Run:
   ```
   ls /Users/bmandal/work/ai/guide/modules/k8s-best-practices-<topic>.adoc
   ```
   If the file exists, classify as Shared. These need AI content analysis.

3. **Ambiguous**: Non-VZ files with no matching public counterpart. These also need AI content analysis.

Also classify non-module files:
- `main.adoc` changes: Classify as **Shared** (both repos have a `main.adoc`).
- `.github/`, `scripts/`, `images/`, `README.md`, `CLAUDE.md`, `AGENTS.md`: Classify as **Verizon-only** unless the change is clearly generic infrastructure. Use judgment.

Count the files in each bucket for the report summary.

### Phase 3: AI Content Analysis

For each file classified as **Shared** or **Ambiguous**, dispatch a parallel Agent subagent to analyze the diff hunks. Use one Agent per file. Dispatch all agents in a single message for parallel execution.

If a `public-commit-hash` was provided and a matching public file exists, read the public file content at that commit:
```
git -C /Users/bmandal/work/ai/guide show <public-commit>:modules/k8s-best-practices-<topic>.adoc
```

**Agent prompt template** (substitute the actual values for each file):

> You are analyzing a diff from a private Verizon CNF documentation repo to determine if the content is safe to sync to a public Red Hat Kubernetes best practices repo.
>
> **File:** `<FILENAME>`
> **Classification so far:** `<SHARED or AMBIGUOUS>`
>
> <If public file content is available>
> **Current public file content (for reference):**
> ```
> <CONTENT OF PUBLIC FILE>
> ```
> </If>
>
> **Diff hunks to classify:**
> ```diff
> <PASTE ALL HUNKS FOR THIS FILE>
> ```
>
> **Verizon-Specific Markers — classify as VZ-specific if ANY of these appear:**
> - "Verizon", "VCP", "Verizon Communications", "Verizon VCP"
> - "Doors Id" or "Doors ID" (Verizon requirements tracking IDs)
> - ".VCP CNF requirement" or ".VCP CNF recommendation" (admonition labels)
> - "ENSE" (Verizon network fabric)
> - "SPK" when used in context of Verizon-specific ingress/egress/load balancing
> - Internal hostnames, URLs, or IP ranges
> - References to "core ENSE", "edge ENSE" network fabric
> - VZ core/edge compute specs (specific hardware references)
> - Internal approval processes or Verizon organizational references
> - VZ-specific container naming/labeling standards
> - References to "CPI 810" or similar Verizon-internal standards
>
> **For EACH hunk, classify as one of:**
> - **generic**: Cloud-native best practice. No VZ markers. Safe for public.
> - **verizon-specific**: Contains one or more VZ markers. Must stay private.
> - **mixed**: Contains BOTH generic content AND VZ-specific content interleaved in the same hunk.
>
> **Respond with a JSON array, one entry per hunk:**
> ```json
> [
>   {
>     "hunk_number": 1,
>     "classification": "generic|verizon-specific|mixed",
>     "reason": "One sentence explaining why",
>     "vz_references": ["list of VZ markers found, empty if generic"],
>     "generic_summary": "Brief description of the generic content (if any)",
>     "vz_summary": "Brief description of the VZ-specific content (if any)"
>   }
> ]
> ```

Wait for all agents to complete. Parse the JSON responses.

If an agent fails or returns unparseable output, classify that file's hunks as **mixed** (safest default — forces manual review).

Aggregate results:
- All hunks generic → file goes to "Public-Eligible Changes"
- All hunks verizon-specific → file goes to "Verizon-Specific Changes"
- Any hunk mixed, or mix of generic + vz-specific hunks → affected hunks go to "Mixed Changes"

### Phase 4: Generate Report

Write the report to `reports/cnf-doc-sync-report-<YYYY-MM-DD>.md` (relative to this tool's repo root). Create the `reports/` directory if it doesn't exist. Use today's date.

Use this exact structure:

```markdown
# CNF Doc Sync Report

**Date:** <YYYY-MM-DD>
**Private repo:** vz-cnf-best-practices-guide @ `<private-commit-short>`..`HEAD`
**Public repo:** guide @ `<public-commit-short>` (context) — or "N/A" if not provided

## Summary

- Total files changed: <N>
- Verizon-only (auto-classified): <N>
- Public-eligible: <N>
- Mixed (needs manual review): <N>

---

## Verizon-Specific Changes

Changes that should stay in the private repo only.

<!-- For each VZ-only auto-classified file: -->

### [AUTO] `<filename>`

> Auto-classified: VZ-prefixed file

<details>
<summary>Diff</summary>

\```diff
<paste the diff for this file>
\```

</details>

<!-- For each AI-classified VZ-specific hunk: -->

### [AI] `<filename>` — Hunk <N>

> Contains VZ-specific references: <reason from agent>

\```diff
<paste the diff hunk>
\```

---

## Public-Eligible Changes

Changes that can be synced to the public guide repo.

<!-- For each public-eligible file/hunk: -->

### [AI] `<filename>`

> <classification reason from agent>
> **Public counterpart:** `k8s-best-practices-<topic>.adoc` — or "No matching file in public repo" for Ambiguous files

- [ ] Accept
- [ ] Reject
- **Reviewer Notes:** _<add comments or modified content here>_

\```diff
<paste the diff>
\```

---

## Mixed Changes (Manual Review Required)

Hunks containing both generic and VZ-specific content.

<!-- For each mixed hunk: -->

### `<filename>` — Hunk <N>

> **Generic portion:** <generic_summary from agent>
> **VZ-specific portion:** <vz_summary from agent>

- [ ] Accept generic portion only
- [ ] Accept with modifications
- [ ] Skip entirely
- **Reviewer Notes:** _<add comments here>_
- **Modified Content (if accepting with modifications):**

\```text
<reviewer pastes rewritten content for public repo here>
\```

\```diff
<paste full diff hunk>
\```

---

## Actions

When your review is complete, invoke the skill with the report path:

\```
/cnf-doc-sync --create-pr reports/cnf-doc-sync-report-<YYYY-MM-DD>.md
\```

This will:
1. Parse your Accept/Reject decisions and reviewer notes
2. Create a branch `sync/vz-<YYYY-MM-DD>` on the public guide repo
3. Apply accepted changes (using modified content where provided)
4. Create a PR with a summary of all included changes
```

After writing the markdown report, also generate a JSON data file at `reports/cnf-doc-sync-data-<YYYY-MM-DD>.json` for the review UI. Create the `reports/` directory if it doesn't exist. Use this structure:

```json
{
  "version": 1,
  "created_at": "<ISO-8601 timestamp>",
  "private_repo": "/Users/bmandal/work/ai/vz-cnf-best-practices-guide",
  "public_repo": "/Users/bmandal/work/ai/guide",
  "since_ref": "<private-commit-short>",
  "head_ref": "<HEAD-short>",
  "public_ref": "<public-commit-short or empty>",
  "files": [
    {
      "id": "<unique-id, e.g. f1>",
      "private_path": "<filename in private repo>",
      "public_path": "<mapped k8s-best-practices-*.adoc filename, or empty>",
      "file_classification": "vz_specific|shared|ambiguous",
      "file_classification_reason": "<reason>",
      "private_content_before": "<full file content before changes>",
      "private_content_after": "<full file content after changes>",
      "proposed_public_content": "<AI-sanitized content for public file, empty for VZ files>",
      "final_content": "",
      "decision": "pending|auto_excluded",
      "reviewer_classification": "",
      "hunks": [
        {
          "id": "<unique-id, e.g. f1-h1>",
          "hunk_header": "<@@ line>",
          "diff_text": "<raw diff text for this hunk>",
          "classification": "generic|verizon-specific|mixed",
          "reason": "<AI rationale>",
          "vz_references": ["<VZ markers found>"],
          "generic_summary": "<brief description of generic content>",
          "vz_summary": "<brief description of VZ content>"
        }
      ]
    }
  ]
}
```

**File content fields:** For each file, read the full content before and after:
- `private_content_before`: `git -C <private-repo> show <since-commit>:<filepath>` (empty string for new files)
- `private_content_after`: `git -C <private-repo> show HEAD:<filepath>` (empty string for deleted files)

**proposed_public_content:** For files with generic hunks, generate the proposed public file content by taking the `private_content_after` and removing all VZ-specific content (VZ admonitions, Doors IDs, VZ-specific paragraphs). Replace `cnf-best-practices-` with `k8s-best-practices-` in any IDs or cross-references. Leave this empty for `vz_specific` files.

**decision:** Set to `"auto_excluded"` for `vz_specific` files, `"pending"` for all others.

After writing both files, tell the user:

"Report generated at `<markdown-path>`.
JSON data generated at `<json-path>`.

To review changes in the web UI, run:
`/cnf-doc-sync --review <json-path>`

Or review the markdown report and run:
`/cnf-doc-sync --create-pr <markdown-path>`"

---

## Mode 2 Procedure: Launch Review UI

When invoked with `--review <json-path>`:

1. Verify the JSON file exists at the given path.
2. Determine the repo root. This skill is installed from a plugin directory that contains both the skill and the review UI. The repo root is two levels up from this SKILL.md file. You can find it by checking where the plugin is installed — look for the directory containing `.claude-plugin/marketplace.json`, `cnf_doc_sync_ui/`, and `frontend/`. Typically this is at `/Users/bmandal/work/ai/cnf-doc-sync-tool/` or wherever the user cloned the repo.
3. Launch the review UI server:
   ```
   cd <repo-root> && source .venv/bin/activate && python -m cnf_doc_sync_ui --data <json-path>
   ```
4. This opens a browser to the review UI at http://localhost:8090
5. Tell the user: "Review UI launched at http://localhost:8090. Review each file, accept or reject changes, and click 'Create PR' when ready."
6. The UI handles all review decisions and PR creation interactively.

**Prerequisites:** The review UI must be set up first. If the `.venv` directory doesn't exist in the repo root, tell the user to run the setup script:
```
cd <repo-root> && ./setup.sh
```

---

## Mode 3 Procedure: Create PR from Reviewed Report (legacy)

When invoked with `--create-pr <report-path>`:

### Step 1: Read and Parse the Report

Read the report file at `<report-path>`. Parse it to extract:

1. **Accepted Public-Eligible changes**: Sections under "Public-Eligible Changes" where `[x] Accept` is checked. Extract:
   - The filename from the section header (e.g., `cnf-best-practices-helm.adoc`)
   - The diff content from the code block
   - Any content from "Reviewer Notes" (text after `**Reviewer Notes:**` that is not the placeholder `_<add comments or modified content here>_`)

2. **Accepted Mixed changes**: Sections under "Mixed Changes" where either `[x] Accept generic portion only` or `[x] Accept with modifications` is checked. Extract:
   - The filename and hunk number from the section header
   - For "Accept with modifications": the content from the "Modified Content" text code block
   - For "Accept generic portion only": the generic portion of the diff (lines without VZ markers)
   - Any content from "Reviewer Notes"

3. **Skipped/Rejected**: Ignore sections where `[x] Reject`, `[x] Skip entirely`, or no checkbox is checked.

If no changes are accepted, tell the user: "No changes were accepted in the report. No PR will be created." and stop.

### Step 2: Verify Public Repo State

```
git -C /Users/bmandal/work/ai/guide status --porcelain
```

If there are uncommitted changes, warn the user: "The public guide repo has uncommitted changes. Please commit or stash them before proceeding." and stop.

### Step 3: Create Sync Branch

```
git -C /Users/bmandal/work/ai/guide checkout main
git -C /Users/bmandal/work/ai/guide pull origin main
git -C /Users/bmandal/work/ai/guide checkout -b sync/vz-<YYYY-MM-DD>
```

Use today's date. If the branch already exists, append a counter: `sync/vz-<YYYY-MM-DD>-2`.

### Step 4: Apply Changes

For each accepted change:

1. Identify the target file. The report shows the private repo filename (e.g., `modules/cnf-best-practices-helm.adoc`). Look up the corresponding public file:
   - Extract the topic: strip `cnf-best-practices-` prefix → `helm.adoc`
   - Public file: `modules/k8s-best-practices-helm.adoc`
   - Tell the user which file mapping is being used: "`cnf-best-practices-helm.adoc` → `k8s-best-practices-helm.adoc`"

2. If "Accept with modifications" — the reviewer provided rewritten content in the "Modified Content" block. Read the current public file, find the location where the change applies (use surrounding context from the diff), and apply the reviewer's modified content using the Edit tool.

3. If plain "Accept" — the reviewer accepted the original diff. Read the current public file, apply the diff changes using the Edit tool. The diff is from the private repo so content references like IDs and cross-references may need to match the public repo's conventions — flag any `cnf-best-practices` references in the applied content and warn the user.

4. If the target public file does not exist (Ambiguous file with no counterpart), tell the user: "File `<filename>` has no counterpart in the public repo. Skipping — manual creation required." and skip it.

### Step 5: Commit Changes

```
git -C /Users/bmandal/work/ai/guide add modules/
git -C /Users/bmandal/work/ai/guide status
```

Review what will be committed. Then commit:

```
git -C /Users/bmandal/work/ai/guide commit -m "sync: apply changes from vz-cnf-best-practices-guide (<YYYY-MM-DD>)"
```

### Step 6: Push and Create PR

```
git -C /Users/bmandal/work/ai/guide push -u origin sync/vz-<YYYY-MM-DD>
```

Build the PR body from the accepted changes. For each accepted change include:
- Filename (private → public mapping)
- Classification reason
- Reviewer notes (if any)

Create the PR:

```
cd /Users/bmandal/work/ai/guide && gh pr create --title "Sync changes from VZ CNF guide (<YYYY-MM-DD>)" --body "$(cat <<'EOF'
## Summary

Synced documentation changes from vz-cnf-best-practices-guide to the public guide.

**Source:** vz-cnf-best-practices-guide @ `<private-commit-range from report header>`

## Changes Included

<For each accepted change, list:>
### `<public-filename>`
- **Source:** `<private-filename>`
- **Classification:** <reason>
- **Reviewer Notes:** <notes or "None">

## Review Process

Changes were classified by AI content analysis and reviewed manually using the cnf-doc-sync skill. Verizon-specific content was filtered out. Mixed content was either stripped of VZ references or rewritten by the reviewer.
EOF
)"
```

### Step 7: Report Result

Tell the user the PR URL and a summary:
- Number of files changed
- Branch name
- Any files that were skipped (no public counterpart, or errors)
- Any warnings about `cnf-best-practices` references that may need manual cleanup in the PR
