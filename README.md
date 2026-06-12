# CNF Doc Sync

An AI-powered tool that synchronizes documentation changes from the private Verizon CNF best practices guide to the public Red Hat Kubernetes best practices guide. It classifies each change as Verizon-specific or generic, presents them in a review UI for human approval, and creates a pull request with the accepted changes.

## How It Works

```
                  Classification                 Review               Publish
                  ─────────────                  ──────               ───────
  Private Repo    ┌──────────────────┐
  commit hash ──> │ Path A: Claude   │
                  │ Code skill       │──┐
                  └──────────────────┘  │    ┌────────────┐    ┌───────────┐
                                        ├──> │ Review UI  │──> │ Create PR │──> Public Repo
                  ┌──────────────────┐  │    │ :8090      │    │ (gh CLI)  │
  commit hash ──> │ Path B: CLI      │──┘    └────────────┘    └───────────┘
                  │ classify.py      │
                  │ (Ollama/OpenAI/  │
                  │  Anthropic)      │
                  └──────────────────┘
```

Both paths produce the same JSON data file. The Review UI and PR publisher work identically regardless of which path generated the data.

## Prerequisites

| Requirement | Needed For | Install |
|-------------|-----------|---------|
| Python 3.11+ | Both paths | [python.org](https://www.python.org/downloads/) |
| Node.js 18+ | Building the Review UI | [nodejs.org](https://nodejs.org/) |
| GitHub CLI (`gh`) | Creating PRs | [cli.github.com](https://cli.github.com/) |
| Claude Code | Path A only | [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |
| Ollama | Path B (local LLM) | [ollama.com](https://ollama.com/) |

You also need Git access to:
- The private `vz-cnf-best-practices-guide` repo
- The public [`guide`](https://github.com/redhat-best-practices-for-k8s/guide) repo

## Setup

```bash
git clone https://github.com/bnshr/cnf-doc-sync-tool.git
cd cnf-doc-sync-tool
./setup.sh
```

The setup script installs the Python backend (including `httpx` for the standalone CLI), builds the React frontend, and verifies the installation.

---

## Path A: Claude Code Skill

If you have Claude Code installed:

```bash
# Register and install the plugin (one-time)
claude plugin marketplace add ./
claude plugin install cnf-doc-sync
```

Then in any Claude Code session:

```bash
# Classify changes introduced by a specific private repo commit (commit vs parent)
# with public repo files at a specific commit for comparison
/cnf-doc-sync <private-commit-hash> <public-commit-hash>

# Launch review UI for a previously generated data file
/cnf-doc-sync --review reports/cnf-doc-sync-data-YYYY-MM-DD.json
```

---

## Path B: Standalone CLI (no Claude Code required)

Use `classify.py` with a local or cloud LLM:

### With Ollama (local, free)

```bash
# Start Ollama and pull a model
ollama serve
ollama pull qwen2.5:7b

# Classify a private commit
python classify.py <private-commit-hash> \
  --private-repo /path/to/vz-cnf-best-practices-guide \
  --public-repo /path/to/guide \
  --model qwen2.5:7b

# Launch review UI
python -m cnf_doc_sync_ui --data reports/cnf-doc-sync-data-YYYY-MM-DD.json
```

### With OpenAI

```bash
export OPENAI_API_KEY=sk-...
python classify.py <private-commit-hash> \
  --provider openai --model gpt-4o \
  --private-repo /path/to/vz-cnf-best-practices-guide
```

### With Anthropic

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python classify.py <private-commit-hash> \
  --provider anthropic --model claude-sonnet-4-6 \
  --private-repo /path/to/vz-cnf-best-practices-guide
```

### Regex-only mode (no LLM needed)

Most files can be classified by VZ marker regex alone (~80%). Use `--no-llm` to skip LLM calls entirely — ambiguous files are flagged as "mixed" for human review in the UI:

```bash
python classify.py <private-commit-hash> --no-llm \
  --private-repo /path/to/vz-cnf-best-practices-guide
```

### Environment variables

Instead of passing `--private-repo` / `--public-repo` every time:

```bash
export CNF_PRIVATE_REPO=/path/to/vz-cnf-best-practices-guide
export CNF_PUBLIC_REPO=/path/to/guide
python classify.py <commit-hash>
```

### Full CLI reference

```
python classify.py <private-commit> [options]

positional arguments:
  private_commit          Private repo commit hash to analyze

options:
  --public-commit HASH    Public repo commit for context
  --private-repo PATH     Path to private repo (default: . or $CNF_PRIVATE_REPO)
  --public-repo PATH      Path to public repo (default: ../guide or $CNF_PUBLIC_REPO)
  --provider {ollama,openai,anthropic}
                          LLM provider (default: ollama)
  --model MODEL           Model name (default: qwen2.5:7b)
  --ollama-url URL        Ollama API URL (default: http://localhost:11434)
  --output PATH           Output JSON path (default: auto-dated)
  --no-llm                Skip LLM — regex-only, ambiguous hunks marked as mixed
```

### Quick start — test the full flow

```bash
# 1. Activate the venv
cd /path/to/cnf-doc-sync-tool
source .venv/bin/activate

# 2. Set repo paths (adjust to your local clones)
export CNF_PRIVATE_REPO=/path/to/vz-cnf-best-practices-guide
export CNF_PUBLIC_REPO=/path/to/guide

# 3. Classify a commit (regex-only, no LLM needed)
python classify.py 3e21a42e --public-commit eb6ec78 --no-llm \
  --output reports/test-run.json

# 4. Launch the review UI
python -m cnf_doc_sync_ui --data reports/test-run.json
# Opens http://localhost:8090 — review files, accept/reject, create PR
```

**Example commits for testing:**

| Commit | Description | Files | Expected |
|--------|-------------|-------|----------|
| `3e21a42e` | Doors Id → Requirement Id renames | 42 | All VZ-specific, zero sync candidates |
| `f8df6b90` | Add SCTP requirement + delete cni-ovn | 4 | 1 generic (cni-ovn deletion), 1 VZ, 1 mixed |
| `e9a66a20` | Sync with 1.5 latest | 26 | Mostly VZ, cpu-manager-pinning has generic DPDK content |

```bash
# Test with a mixed commit (has both VZ and generic content)
python classify.py e9a66a20 --public-commit 7a8e5c8 --no-llm \
  --output reports/test-tc3.json
python -m cnf_doc_sync_ui --data reports/test-tc3.json

# Test with Ollama (classifies ambiguous hunks via LLM)
ollama serve                    # in another terminal
ollama pull qwen2.5:7b          # one-time download
python classify.py e9a66a20 --public-commit 7a8e5c8 --model qwen2.5:7b \
  --output reports/test-llm.json
# Note: requires CNF_PRIVATE_REPO and CNF_PUBLIC_REPO env vars set (step 2 above),
# or pass --private-repo and --public-repo explicitly

# Clean up test files
rm reports/test-*.json
```

### Path A vs Path B — side-by-side example

The same analysis using commit `e9a66a20` (private) and `7a8e5c8` (public):

| Step | Path A: Claude Code | Path B: Standalone CLI |
|------|--------------------|-----------------------|
| **Classify** | `/cnf-doc-sync e9a66a20 7a8e5c8` | `python classify.py e9a66a20 --public-commit 7a8e5c8 --model qwen2.5:7b` |
| **Repo paths** | Hardcoded in SKILL.md | `--private-repo` / `--public-repo` or env vars |
| **LLM** | Claude (built-in) | Ollama / OpenAI / Anthropic (your choice) |
| **Review UI** | `/cnf-doc-sync --review reports/<file>.json` | `python -m cnf_doc_sync_ui --data reports/<file>.json` |
| **Output** | `reports/cnf-doc-sync-data-YYYY-MM-DD.json` | Same format, same directory |

Both produce identical JSON — the Review UI and PR publisher work the same regardless of which path generated the data.

### Recommended models

| Model | Provider | Size | RAM | Best For |
|-------|----------|------|-----|----------|
| qwen2.5:7b | Ollama | 7B | 5GB | Best overall for classification |
| llama3.1:8b | Ollama | 8B | 6GB | Strongest reasoning |
| mistral:7b | Ollama | 7B | 4GB | Fastest JSON extraction |
| llama3.2:3b | Ollama | 3B | 2GB | Low-resource environments |
| gpt-4o | OpenAI | — | — | Highest accuracy (cloud) |
| claude-sonnet-4-6 | Anthropic | — | — | Best for long documents (cloud) |

---

## Review UI

After classification (from either path), the review UI opens at `http://localhost:8090`:

| UI Element | What It Shows |
|------------|---------------|
| **Left sidebar** | Files grouped into "To Review" and "VZ-only (auto-excluded)" |
| **Main panel** | Side-by-side diff (private changes vs. proposed public content) |
| **Hunk breakdown** | Each change with its AI classification and rationale |
| **Decision buttons** | Accept, Edit & Accept, or Reject per file |

Once all reviewable files have a decision, click **"Create PR in guide repo"**. The tool creates a `sync/vz-YYYY-MM-DD` branch, applies accepted changes (mapping `cnf-best-practices-*` to `k8s-best-practices-*`), and opens a draft PR.

## What Gets Filtered

The AI identifies and excludes Verizon-specific content:

- "Verizon", "VCP", "Verizon Communications"
- `.VCP CNF requirement` / `.VCP CNF recommendation` labels
- Doors IDs / Requirement IDs (Verizon requirements tracking)
- ENSE references (Verizon network fabric)
- SPK references, internal hostnames, IP ranges
- VZ compute specs, naming standards, internal processes

Everything else is classified as generic cloud-native best practice and is eligible for the public repo.

## How Classification Works (three layers)

`classify.py` uses a cost-effective three-layer approach:

1. **Filename pattern** (instant, free): Files matching `*-vz-*` are auto-classified as VZ-specific.
2. **Regex scan** (instant, free): If ALL changed lines in a hunk contain VZ markers, it's classified as VZ-specific without an LLM call.
3. **LLM** (slow, per-token cost): Only triggered for hunks that pass layers 1 and 2 — typically ~20% of files.

This means ~80% of files are classified with zero LLM calls.

## Project Structure

```
cnf-doc-sync-tool/
├── classify.py                 # Standalone CLI classifier (Path B)
├── setup.sh                    # Automated installation
├── pyproject.toml              # Python dependencies
├── reports/                    # Generated classification output
│   ├── sample_data.json        # Sample data for local dev
│   └── cnf-doc-sync-data-*.json/md  # Generated per-run (gitignored)
│
├── skills/cnf-doc-sync/
│   └── SKILL.md                # Claude Code skill (Path A)
├── .claude-plugin/
│   └── marketplace.json        # Claude Code plugin registration
│
├── cnf_doc_sync_ui/            # Review UI backend (Python/FastAPI)
│   ├── server.py               # API server (port 8090)
│   └── publisher.py            # PR creation via git + gh
│
├── frontend/                   # Review UI frontend (React/Vite)
│   └── src/
│       ├── App.tsx             # Main review interface
│       ├── HunkView.tsx        # Diff hunk display
│       └── types.ts            # JSON data format types
│
├── test-results/               # Validation test data
│   ├── validation-report.md    # Test results summary (5 TCs, compared against human sync)
│   ├── ground-truth.json       # Reference commit tuples and human sync diffs
│   └── v2_tc{1-5}_*_cli.json  # Per-test-case classification data
│
└── HANDOVER.md                 # Full handover documentation
```

## Development

For local development with hot-reloading:

```bash
# Terminal 1: Backend
source .venv/bin/activate
python -m cnf_doc_sync_ui --data reports/sample_data.json --no-open --port 8090

# Terminal 2: Frontend
cd frontend && npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies API requests to port 8090.

## License

See [LICENSE](LICENSE) for details.
