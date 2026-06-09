import { diffLines } from "diff";
import { useEffect, useRef, useState } from "react";
import "./App.css";
import EditModal from "./EditModal";
import HunkView from "./HunkView";
import {
  createPR,
  getSession,
  getSummary,
  overrideClassification,
  resetAll,
  submitDecision,
} from "./api";
import type {
  Decision,
  FileClassification,
  Summary,
  SyncFile,
} from "./types";

function shortName(p: string) {
  return p.split("/").pop() ?? p;
}

function effectiveClass(f: SyncFile): FileClassification {
  return (f.reviewer_classification as FileClassification) || f.file_classification;
}

// ─── Diff renderer ───────────────────────────────────────────────────────────

function DiffView({ before, after }: { before: string; after: string }) {
  if (!before && !after) return <div className="diff-empty">No content</div>;

  if (!before) {
    const lines = after.split("\n");
    return (
      <div className="diff-scroll">
        <table className="diff-table">
          <tbody>
            {lines.map((line, i) => (
              <tr key={i} className="diff-row add">
                <td className="diff-ln">+</td>
                <td className="diff-code">{line || " "}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const parts = diffLines(before, after);
  const rows: { gutter: string; line: string; cls: string }[] = [];
  for (const part of parts) {
    const lines = part.value.split("\n");
    const trimmed = part.value.endsWith("\n") ? lines.slice(0, -1) : lines;
    for (const line of trimmed) {
      if (part.added) rows.push({ gutter: "+", line, cls: "add" });
      else if (part.removed) rows.push({ gutter: "−", line, cls: "del" });
      else rows.push({ gutter: " ", line, cls: "ctx" });
    }
  }

  return (
    <div className="diff-scroll">
      <table className="diff-table">
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={`diff-row ${r.cls}`}>
              <td className="diff-ln">{r.gutter}</td>
              <td className="diff-code">{r.line || " "}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Classification row ─────────────────────────────────────────────────────

const CLS_OPTIONS: { value: FileClassification; label: string; badge: string }[] = [
  { value: "vz_specific", label: "VZ-specific", badge: "badge vz" },
  { value: "shared", label: "Shared", badge: "badge gen" },
  { value: "ambiguous", label: "Ambiguous", badge: "badge amb" },
];

function ClassificationRow({
  file,
  onOverride,
}: {
  file: SyncFile;
  onOverride: (c: FileClassification) => void;
}) {
  const effective = effectiveClass(file);
  const isOverridden =
    !!file.reviewer_classification &&
    file.reviewer_classification !== file.file_classification;

  return (
    <div className="cls-row">
      <div className="cls-ai">
        <span className="cls-label">AI decision:</span>
        {CLS_OPTIONS.map((o) => (
          <span
            key={o.value}
            className={o.value === file.file_classification ? o.badge : "badge dim"}
          >
            {o.label}
          </span>
        ))}
        <span className="cls-rationale">{file.file_classification_reason}</span>
      </div>
      <div className="cls-override">
        <span className="cls-label">
          {isOverridden ? "Your override:" : "Override AI:"}
        </span>
        {CLS_OPTIONS.map((o) => (
          <button
            key={o.value}
            className={`cls-btn${effective === o.value ? " cls-active" : ""}`}
            onClick={() => onOverride(o.value)}
          >
            {effective === o.value ? `✓ ${o.label}` : o.label}
          </button>
        ))}
        {isOverridden && (
          <button
            className="cls-btn cls-reset"
            onClick={() => onOverride(file.file_classification)}
          >
            Reset to AI
          </button>
        )}
      </div>
    </div>
  );
}

// ─── File detail pane ────────────────────────────────────────────────────────

function FilePane({
  file,
  onDecision,
  onEdit,
  onOverride,
  privateRepoUrl,
  publicRepoUrl,
  sinceRef,
  publicRef,
}: {
  file: SyncFile;
  onDecision: (id: string, d: "accepted" | "rejected", content: string) => void;
  onEdit: () => void;
  onOverride: (id: string, c: FileClassification) => void;
  privateRepoUrl: string;
  publicRepoUrl: string;
  sinceRef: string;
  publicRef: string;
}) {
  const effective = effectiveClass(file);
  const isVZ = effective === "vz_specific";
  const proposed = file.final_content || file.proposed_public_content;
  const isEdited = !!file.final_content && file.final_content !== file.proposed_public_content;

  return (
    <div className="file-pane">
      {/* sticky header */}
      <div className="pane-head">
        <div className="pane-paths">
          <div className="path-row">
            <span className="path-tag private">PRIVATE</span>
            {privateRepoUrl && sinceRef ? (
              <a
                href={`${privateRepoUrl}/blob/${sinceRef}/${file.private_path}`}
                target="_blank"
                rel="noopener noreferrer"
                className="path-link"
              >
                {file.private_path}
              </a>
            ) : (
              <code>{file.private_path}</code>
            )}
          </div>
          {file.public_path && (
            <div className="path-row">
              <span className="path-tag public">PUBLIC</span>
              {publicRepoUrl && publicRef ? (
                <a
                  href={`${publicRepoUrl}/blob/${publicRef}/${file.public_path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="path-link"
                >
                  {file.public_path}
                </a>
              ) : (
                <code>{file.public_path}</code>
              )}
            </div>
          )}
        </div>
      </div>

      {/* classification + override */}
      <ClassificationRow file={file} onOverride={(c) => onOverride(file.id, c)} />

      {/* split view */}
      <div className={`split-view${!isEdited && isVZ && !proposed ? " single" : ""}`}>
        <div className="split-col">
          <div className="col-head">
            <span className="col-title">Changes in private repo</span>
            <span className="col-sub">
              {file.private_content_before ? "green = added, red = removed" : "new file"}
            </span>
          </div>
          <DiffView before={file.private_content_before} after={file.private_content_after} />
        </div>

        {(proposed || isEdited || !isVZ) && (
          <div className="split-col">
            <div className="col-head">
              <span className="col-title">
                {isEdited ? "Edited public content" : "Proposed public content"}
              </span>
              <span className="col-sub">
                {isEdited ? (
                  <span className="edited-badge">manually edited</span>
                ) : isVZ ? (
                  "use Edit & accept to write content for the public repo"
                ) : (
                  "AI-sanitized for public guide"
                )}
              </span>
            </div>
            <div className="diff-scroll proposed-scroll">
              <pre className="proposed-pre">{proposed || "(nothing to publish — use Edit & accept to write content)"}</pre>
            </div>
          </div>
        )}
      </div>

      {/* hunk breakdown */}
      {file.hunks.length > 0 && (
        <div className="hunks-section">
          <div className="hunks-title">
            Hunk Analysis ({file.hunks.length} hunk{file.hunks.length !== 1 ? "s" : ""})
          </div>
          {file.hunks.map((h) => (
            <HunkView key={h.id} hunk={h} />
          ))}
        </div>
      )}

      {/* VZ warning banner */}
      {isVZ && file.decision !== "accepted" && (
        <div className="vz-banner">
          AI-classified as Verizon-proprietary. Use <strong>Edit &amp; accept</strong> to
          write sanitized content for the public guide, or leave as excluded.
        </div>
      )}

      {/* decision bar — always shown */}
      <div className="decision-bar">
        <div className="decision-state">
          {file.decision === "accepted" && (
            <span className="pill accepted">{"✓"} Accepted</span>
          )}
          {file.decision === "rejected" && (
            <span className="pill rejected">Skipped</span>
          )}
          {file.decision === "auto_excluded" && (
            <span className="pill excluded">Auto-excluded</span>
          )}
          {file.decision === "pending" && (
            <span className="pill pending">Pending decision</span>
          )}
        </div>
        <div className="decision-btns">
          {!isVZ && (
            <button
              className={`btn accept${file.decision === "accepted" ? " active" : ""}`}
              onClick={() => onDecision(file.id, "accepted", proposed)}
            >
              {"✓"} Accept
            </button>
          )}
          <button className="btn edit" onClick={onEdit}>
            {"✎"} Edit &amp; accept
          </button>
          <button
            className={`btn reject${file.decision === "rejected" || file.decision === "auto_excluded" ? " active" : ""}`}
            onClick={() => onDecision(file.id, "rejected", "")}
          >
            Skip
</button>
        </div>
      </div>
    </div>
  );
}

// ─── App ────────────────────────────────────────────────────────────────────

export default function App() {
  const [files, setFiles] = useState<SyncFile[]>([]);
  const [summary, setSummary] = useState<Summary>({
    total: 0,
    accepted: 0,
    rejected: 0,
    pending: 0,
    auto_excluded: 0,
  });
  const [sinceRef, setSinceRef] = useState("");
  const [publicRef, setPublicRef] = useState("");
  const [privateRepoUrl, setPrivateRepoUrl] = useState("");
  const [publicRepoUrl, setPublicRepoUrl] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState<SyncFile | null>(null);
  const [prResult, setPrResult] = useState<{ pr_url: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [prLoading, setPrLoading] = useState(false);
  const [bulkSelected, setBulkSelected] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const [vzCollapsed, setVzCollapsed] = useState(true);
  const mainRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getSession()
      .then((session) => {
        setFiles(session.files);
        setSinceRef(session.since_ref);
        setPublicRef(session.public_ref || "");
        setPrivateRepoUrl(session.private_repo_url || "");
        setPublicRepoUrl(session.public_repo_url || "");
        if (session.pr_url) {
          setPrResult({ pr_url: session.pr_url });
          return;
        }
        const first =
          session.files.find((f) => effectiveClass(f) !== "vz_specific") ??
          session.files[0];
        setSelected(first?.id ?? null);
      })
      .catch((e) => setError(String(e)));
    getSummary().then(setSummary).catch(() => {});
  }, []);

  useEffect(() => {
    mainRef.current?.scrollTo(0, 0);
  }, [selected]);

  const isExcluded = (f: SyncFile) =>
    effectiveClass(f) === "vz_specific" || f.decision === "auto_excluded";
  const reviewable = files.filter((f) => !isExcluded(f));
  const vzOnly = files.filter((f) => isExcluded(f));
  const selectedFile = files.find((f) => f.id === selected) ?? null;

  // sort reviewable: pending first, then accepted, then rejected
  const sortedReviewable = [...reviewable].sort((a, b) => {
    const order: Record<string, number> = { pending: 0, accepted: 1, rejected: 2 };
    return (order[a.decision] ?? 3) - (order[b.decision] ?? 3);
  });

  async function handleDecision(
    fileId: string,
    decision: "accepted" | "rejected",
    content: string,
  ) {
    try {
      await submitDecision(fileId, decision, content);
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, decision: decision as Decision, final_content: content } : f,
        ),
      );
      getSummary().then(setSummary).catch(() => {});
      const idx = reviewable.findIndex((f) => f.id === fileId);
      const next = reviewable
        .slice(idx + 1)
        .find((f) => f.decision === "pending");
      if (next) setSelected(next.id);
    } catch {
      setError("Failed to save decision.");
    }
  }

  async function handleOverride(fileId: string, cls: FileClassification) {
    try {
      const file = files.find((f) => f.id === fileId);
      const resetCls = cls === file?.file_classification ? "" : cls;
      await overrideClassification(fileId, resetCls as FileClassification | "");
      setFiles((prev) =>
        prev.map((f) => {
          if (f.id !== fileId) return f;
          const newCls = resetCls;
          const newDecision: Decision =
            (newCls || f.file_classification) === "vz_specific"
              ? "auto_excluded"
              : f.decision === "auto_excluded"
                ? "pending"
                : f.decision;
          return {
            ...f,
            reviewer_classification: newCls,
            decision: newDecision,
            final_content: newDecision === "auto_excluded" ? "" : f.final_content,
          };
        }),
      );
      getSummary().then(setSummary).catch(() => {});
    } catch {
      setError("Failed to save classification override.");
    }
  }

  function toggleBulkSelect(fileId: string) {
    setBulkSelected((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId);
      else next.add(fileId);
      return next;
    });
  }

  function toggleSelectAll() {
    if (bulkSelected.size === reviewable.length) {
      setBulkSelected(new Set());
    } else {
      setBulkSelected(new Set(reviewable.map((f) => f.id)));
    }
  }

  async function handleBulkAction(decision: "accepted" | "rejected") {
    if (bulkSelected.size === 0) return;
    setBulkLoading(true);
    try {
      for (const fileId of bulkSelected) {
        const file = files.find((f) => f.id === fileId);
        const content =
          decision === "accepted"
            ? file?.final_content || file?.proposed_public_content || ""
            : "";
        await submitDecision(fileId, decision, content);
      }
      setFiles((prev) =>
        prev.map((f) =>
          bulkSelected.has(f.id)
            ? {
                ...f,
                decision: decision as Decision,
                final_content:
                  decision === "accepted"
                    ? f.final_content || f.proposed_public_content || ""
                    : "",
              }
            : f,
        ),
      );
      getSummary().then(setSummary).catch(() => {});
      setBulkSelected(new Set());
    } catch {
      setError("Failed to apply bulk decision.");
    } finally {
      setBulkLoading(false);
    }
  }

  async function handleReset() {
    if (!confirm("Reset all decisions? This will clear all accepts, skips, and edits.")) return;
    try {
      await resetAll();
      const session = await getSession();
      setFiles(session.files);
      setPrResult(null);
      getSummary().then(setSummary).catch(() => {});
      const first =
        session.files.find((f) => effectiveClass(f) !== "vz_specific") ??
        session.files[0];
      setSelected(first?.id ?? null);
    } catch {
      setError("Failed to reset.");
    }
  }

  async function handleCreatePR() {
    setPrLoading(true);
    try {
      const result = await createPR();
      if (result.pr_url) {
        setPrResult({ pr_url: result.pr_url });
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setPrLoading(false);
    }
  }

  if (prResult) {
    return (
      <div className="done">
        <div className="done-check">{"✓"}</div>
        <h2>PR Created</h2>
        <p>Draft PR has been created in the public guide repo.</p>
        {prResult.pr_url && (
          <a href={prResult.pr_url} target="_blank" rel="noopener noreferrer">
            {prResult.pr_url}
          </a>
        )}
        <button
          className="btn ghost"
          style={{ marginTop: 16 }}
          onClick={() => setPrResult(null)}
        >
          ← Back to review
        </button>
      </div>
    );
  }

  return (
    <div className="app">
      {/* top nav */}
      <nav className="topnav">
        <span className="nav-title">CNF Doc Sync Review</span>
        <span className="nav-ref">
          private <code>{sinceRef}</code>
          {publicRef && (
            <> · public <code>{publicRef}</code></>
          )}
        </span>
        <div className="nav-stats">
          <span className="s total">{summary.total} changed</span>
          <span className="s vz">{vzOnly.length} VZ-specific</span>
          <span className="s review">{reviewable.length} to review</span>
          <span className="s-sep" />
          <span className="s green">{"✓"} {summary.accepted}</span>
          <span className="s red">{summary.rejected} skipped</span>
          <span className="s muted">{"◌"} {summary.pending} pending</span>
        </div>
        <button className="nav-reset-btn" onClick={handleReset}>
          Reset all
        </button>
        <button
          className={`nav-pr-btn${summary.accepted > 0 ? " ready" : ""}`}
          disabled={summary.accepted === 0 || prLoading}
          onClick={handleCreatePR}
        >
          {prLoading
            ? "Creating PR..."
            : summary.accepted === 0
              ? "No files accepted"
              : `Create PR (${summary.accepted} file${summary.accepted !== 1 ? "s" : ""}) →`}
        </button>
      </nav>

      {error && (
        <div className="err-bar">
          {error} <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <div className="body">
        {/* sidebar */}
        <aside className="sidebar">
          {reviewable.length === 0 && (
            <div className="sidebar-empty">
              No general/ambiguous files found.
              <br />
              All changes are VZ-specific.
            </div>
          )}

          {reviewable.length > 0 && (
            <div className="sidebar-group">
              <div className="group-label">
                To review ({reviewable.length})
                {reviewable.length > 1 && (
                  <label className="select-all" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={bulkSelected.size === reviewable.length}
                      onChange={toggleSelectAll}
                    />
                    <span>All</span>
                  </label>
                )}
              </div>
              {sortedReviewable.map((f) => {
                const ec = effectiveClass(f);
                const overridden =
                  !!f.reviewer_classification &&
                  f.reviewer_classification !== f.file_classification;
                return (
                  <div
                    key={f.id}
                    className={`file-row${selected === f.id ? " sel" : ""}`}
                  >
                    <input
                      type="checkbox"
                      className="file-check"
                      checked={bulkSelected.has(f.id)}
                      onChange={() => toggleBulkSelect(f.id)}
                    />
                    <button
                      className="file-btn"
                      onClick={() => setSelected(f.id)}
                    >
                      <span
                        className={`dot ${
                          f.decision === "accepted"
                            ? "g"
                            : f.decision === "rejected"
                              ? "r"
                              : "y"
                        }`}
                      />
                      <span className="fbname">{shortName(f.private_path)}</span>
                      {overridden && (
                        <span
                          className="fbadge override"
                          title="Classification overridden"
                        >
                          {"✎"}
                        </span>
                      )}
                      <span
                        className={`fbadge ${ec === "ambiguous" ? "amb" : "gen"}`}
                      >
                        {ec === "ambiguous" ? "?" : "✓"}
                      </span>
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {bulkSelected.size > 0 && (
            <div className="bulk-bar">
              <span className="bulk-count">{bulkSelected.size} selected</span>
              <div className="bulk-btns">
                <button
                  className="btn accept sm"
                  disabled={bulkLoading}
                  onClick={() => handleBulkAction("accepted")}
                >
                  {"✓"} Accept all
                </button>
                <button
                  className="btn reject sm"
                  disabled={bulkLoading}
                  onClick={() => handleBulkAction("rejected")}
                >
                  Skip all
                </button>
                <button
                  className="btn ghost sm"
                  onClick={() => setBulkSelected(new Set())}
                >
                  Clear
                </button>
              </div>
            </div>
          )}

          {vzOnly.length > 0 && (
            <div className="sidebar-group">
              <button
                className="group-toggle"
                onClick={() => setVzCollapsed((v) => !v)}
              >
                <span className={`toggle-arrow${vzCollapsed ? "" : " open"}`}>▶</span>
                <span className="group-label dim">
                  VZ-only — excluded ({vzOnly.length})
                </span>
              </button>
              {!vzCollapsed &&
                vzOnly.map((f) => (
                  <button
                    key={f.id}
                    className={`file-btn vz${selected === f.id ? " sel" : ""}`}
                    onClick={() => setSelected(f.id)}
                  >
                    <span className={`dot ${f.decision === "accepted" ? "g" : "locked"}`} />
                    <span className="fbname">{shortName(f.private_path)}</span>
                  </button>
                ))}
            </div>
          )}
        </aside>

        {/* main */}
        <main className="main" ref={mainRef}>
          {selectedFile ? (
            <FilePane
              file={selectedFile}
              onDecision={handleDecision}
              onEdit={() => {
                const latest = files.find((f) => f.id === selected);
                if (latest) setEditing(latest);
              }}
              onOverride={handleOverride}
              privateRepoUrl={privateRepoUrl}
              publicRepoUrl={publicRepoUrl}
              sinceRef={sinceRef}
              publicRef={publicRef}
            />
          ) : (
            <div className="main-empty">Select a file from the list.</div>
          )}
        </main>
      </div>

      {editing && (
        <EditModal
          key={editing.id}
          content={editing.final_content || editing.proposed_public_content}
          onSave={async (c) => {
            const fileId = editing.id;
            setEditing(null);
            await handleDecision(fileId, "accepted", c);
          }}
          onCancel={() => setEditing(null)}
        />
      )}
    </div>
  );
}
