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

Use `classify.py` with a local or cloud LLM.

When **every** hunk in a file is classified **generic**, `classify.py` also fills
**Proposed public content** (private file after the commit, `cnf-best-practices-`
→ `k8s-best-practices-`, VZ-marker lines stripped). You can **Accept** in the
Review UI without pasting a long file. Mixed or VZ hunks leave proposed content
empty — use **Edit & accept** for those.

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

### Models and API keys

`classify.py` supports three LLM providers. Pass the provider with `--provider` and the model with `--model`. For cloud providers (OpenAI / Anthropic), set a single env var — **`ENMAAS_KEY`** — do not put API keys on the command line.

| Provider | `--provider` | Auth | Default / typical model |
|----------|--------------|------|-------------------------|
| Ollama (local) | `ollama` (default) | None — run `ollama serve` | `qwen2.5:7b` |
| OpenAI | `openai` | `export ENMAAS_KEY=...` | e.g. `glm-5-3` |
| Anthropic | `anthropic` | `export ENMAAS_KEY=...` | e.g. `claude-sonnet-4-6` |

```bash
export ENMAAS_KEY=...

# OpenAI-compatible via ENMAAS_KEY (example model: glm-5-3)
python classify.py 9c00e23 --public-commit 7a8e5c8 \
  --provider openai --model glm-5-3 \
  --private-repo /path/to/vz-cnf-best-practices-guide \
  --public-repo /path/to/guide

# Anthropic-compatible via the same ENMAAS_KEY
python classify.py <private-commit-hash> \
  --provider anthropic --model claude-sonnet-4-6 \
  --private-repo /path/to/vz-cnf-best-practices-guide \
  --public-repo /path/to/guide
```

If `ENMAAS_KEY` is missing, `classify.py` exits with an error that the API key is not set. Only ambiguous hunks (~20%) call the LLM; the rest are handled by filename + VZ-marker regex.

### Regex-only mode (no LLM / no API key)

Most files can be classified by VZ marker regex alone (~80%). Use `--no-llm` to skip LLM calls entirely — ambiguous files are flagged as "mixed" for human review in the UI. No Ollama or `ENMAAS_KEY` required:

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

Repo paths and API keys can all be set via env vars:

| Variable | Purpose |
|----------|---------|
| `CNF_PRIVATE_REPO` | Path to private guide clone |
| `CNF_PUBLIC_REPO` | Path to public guide clone |
| `ENMAAS_KEY` | Required when `--provider openai` or `--provider anthropic` |

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

Use private commit `e9a66a20` ("sync with 1.5 latest") and public commit `7a8e5c8`. That pair is the richest check: mostly Verizon-specific files, with generic DPDK content in `cpu-manager-pinning.adoc` that should stay pending for review. Point the two exports at your local clones.

```bash
cd /path/to/cnf-doc-sync-tool
source .venv/bin/activate
export CNF_PRIVATE_REPO=/path/to/vz-cnf-best-practices-guide
export CNF_PUBLIC_REPO=/path/to/guide
python classify.py e9a66a20 --public-commit 7a8e5c8 --no-llm --output reports/test-tc3.json
python -m cnf_doc_sync_ui --data reports/test-tc3.json
```

The review UI opens at http://localhost:8090. See [docs/review-ui.md](docs/review-ui.md) for what to do on that screen. `reports/test-tc3.json` is gitignored because generated reports contain private guide content.

**Example commits for testing:**

| Private | Public context | Description | Expected |
|---------|----------------|-------------|----------|
| `9c00e23` | `7a8e5c8` | Guaranteed QoS details on cpu-isolation (best private→public sync demo) | 1 generic file; human synced same content to public |
| `e9a66a20` | `7a8e5c8` | Sync with 1.5 latest | Mostly VZ; cpu-manager-pinning has generic DPDK content |
| `f8df6b90` | `445d1d7` | Add SCTP requirement + delete cni-ovn | Generic deletion + mixed SCTP hunks |
| `3e21a42e` | `eb6ec78` | Doors Id → Requirement Id renames | All VZ-specific, zero sync candidates |

For a minimal end-to-end example where private generic content matched a real public sync:

```bash
export ENMAAS_KEY=...
python classify.py 9c00e23 --public-commit 7a8e5c8 \
  --provider openai --model glm-5-3
# or: --no-llm   /   --provider ollama --model qwen2.5:7b
```


```bash
# Test with Ollama (classifies ambiguous hunks via LLM)
ollama serve                    # in another terminal
ollama pull qwen2.5:7b          # one-time download
python classify.py e9a66a20 --public-commit 7a8e5c8 --model qwen2.5:7b \
  --output reports/test-llm.json
# Uses CNF_PRIVATE_REPO and CNF_PUBLIC_REPO from the quick start above,
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

Classification only needs an LLM for the ambiguous ~20% of hunks. Prefer a model that follows JSON instructions reliably.

**Best picks**

| Priority | Model | Provider | When to use |
|----------|-------|----------|-------------|
| **1 — best default** | `glm-5-3` | OpenAI + `ENMAAS_KEY` | Day-to-day runs; good balance of accuracy and ENMAAS availability |
| **2 — best local** | `qwen2.5:7b` | Ollama | Offline / no ENMAAS; CLI default; strong at this JSON classification task |
| **3 — no model** | `--no-llm` | — | Fastest; regex only; mixed hunks go to the UI for you |

**Also fine (cloud, via `ENMAAS_KEY`)**

| Model | When |
|-------|------|
| `gpt-4o` | Highest accuracy if your ENMAAS gateway exposes it |
| `gpt-4o-mini` | Large commits when you want cheaper / faster cloud calls |

**Also fine (Ollama local)**

| Model | RAM | When |
|-------|-----|------|
| `llama3.1:8b` | ~6GB | Mixed hunks need stronger reasoning |
| `mistral:7b` | ~4GB | Faster local JSON extraction |
| `llama3.2:3b` | ~2GB | Low-RAM machines (lower quality) |

```bash
# Best cloud (recommended)
export ENMAAS_KEY=...
python classify.py 9c00e23 --public-commit 7a8e5c8 \
  --provider openai --model glm-5-3

# Best local
ollama serve && ollama pull qwen2.5:7b
python classify.py 9c00e23 --public-commit 7a8e5c8 \
  --provider ollama --model qwen2.5:7b

# No LLM
python classify.py 9c00e23 --public-commit 7a8e5c8 --no-llm
```

---

## Review UI

After classification (from either path), the review UI opens at `http://localhost:8090`. The procedure — which list to work, what a hunk is, and when **Accept** actually publishes text — is in [docs/review-ui.md](docs/review-ui.md).

Work **To review** one file at a time: **Accept**, **Edit & accept**, or **Skip**. **Create PR** turns on once at least one file is accepted. It creates a `sync/vz-YYYY-MM-DD` branch, writes the accepted public files (mapping `cnf-best-practices-*` to `k8s-best-practices-*`), and opens a PR. Pending and skipped files are left out.

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
