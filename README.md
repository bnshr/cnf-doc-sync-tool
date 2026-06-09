# CNF Doc Sync

An AI-powered tool that synchronizes documentation changes from the private Verizon CNF best practices guide to the public Red Hat Kubernetes best practices guide. It classifies each change as Verizon-specific or generic, presents them in a review UI for human approval, and creates a pull request with the accepted changes.

## How It Works

```
Private VZ CNF Repo                        Public K8s Guide
        |                                        ^
        v                                        |
   Claude Code Skill ──> Review UI ──> Create PR ─┘
   (AI classification)   (accept/reject/edit)
```

1. You provide a commit range in the private repo
2. AI classifies every change — Verizon-proprietary content is filtered out automatically
3. A web-based review UI opens for you to accept, reject, or edit each change
4. One click creates a draft PR on the public guide repo

## Prerequisites

| Requirement | Install |
|-------------|---------|
| Python 3.11+ | [python.org](https://www.python.org/downloads/) |
| Node.js 18+ | [nodejs.org](https://nodejs.org/) |
| GitHub CLI | [cli.github.com](https://cli.github.com/) |
| Claude Code | [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |

You also need Git access to:
- The private `vz-cnf-best-practices-guide` repo
- The public [`guide`](https://github.com/redhat-best-practices-for-k8s/guide) repo

## Setup

```bash
# 1. Clone this repo
git clone https://github.com/bnshr/cnf-doc-sync-tool.git
cd cnf-doc-sync-tool

# 2. Run the setup script (creates Python venv, installs dependencies, builds frontend)
./setup.sh

# 3. Register this repo as a plugin marketplace and install the plugin
claude plugin marketplace add ./
claude plugin install cnf-doc-sync
```

Step 3 first registers this repo as a local plugin source, then installs the `cnf-doc-sync` skill at user scope — making the `/cnf-doc-sync` command available in Claude Code from **any directory**, not just this repo.

You can also load the plugin for a single session without installing:

```bash
claude --plugin-dir /path/to/cnf-doc-sync-tool
```

## Usage

### Step 1: Generate the classification report

Open Claude Code and run:

```
/cnf-doc-sync <private-commit-hash>
```

This diffs all changes from that commit to HEAD in the private repo and classifies each one. To include public repo context (recommended):

```
/cnf-doc-sync <private-commit> <public-commit>
```

### Step 2: Review changes

After classification, launch the review UI:

```
/cnf-doc-sync --review cnf-doc-sync-data-YYYY-MM-DD.json
```

This opens `http://localhost:8090` in your browser with:

| UI Element | What It Shows |
|------------|---------------|
| **Left sidebar** | Files grouped into "To Review" and "VZ-only (auto-excluded)" |
| **Main panel** | Side-by-side diff (private changes vs. proposed public content) |
| **Hunk breakdown** | Each change with its AI classification and rationale |
| **Decision buttons** | Accept, Edit & Accept, or Reject per file |

### Step 3: Create the PR

Once all reviewable files have a decision, click **"Create PR in guide repo"**. The tool:

1. Creates a `sync/vz-YYYY-MM-DD` branch on the public repo
2. Applies accepted changes (mapping `cnf-best-practices-*` to `k8s-best-practices-*`)
3. Opens a draft pull request on GitHub

## What Gets Filtered

The AI identifies and excludes Verizon-specific content:

- "Verizon", "VCP", "Verizon Communications"
- `.VCP CNF requirement` / `.VCP CNF recommendation` labels
- Doors IDs (Verizon requirements tracking)
- ENSE references (Verizon network fabric)
- SPK references, internal hostnames, IP ranges
- VZ compute specs, naming standards, internal processes

Everything else is classified as generic cloud-native best practice and is eligible for the public repo.

## Development

For local development with hot-reloading:

```bash
# Terminal 1: Backend
source .venv/bin/activate
python -m cnf_doc_sync_ui --data sample_data.json --no-open --port 8090

# Terminal 2: Frontend
cd frontend && npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies API requests to port 8090.

## License

See [LICENSE](LICENSE) for details.
