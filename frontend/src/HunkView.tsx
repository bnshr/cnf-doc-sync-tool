import type { Hunk } from "./types";

const CLS_COLORS: Record<string, string> = {
  generic: "gen",
  "verizon-specific": "vz",
  mixed: "amb",
};

const CLS_LABELS: Record<string, string> = {
  generic: "Generic",
  "verizon-specific": "VZ-Specific",
  mixed: "Mixed",
};

function parseDiffLines(text: string) {
  const rows: { gutter: string; line: string; cls: string }[] = [];
  for (const line of text.split("\n")) {
    if (line.startsWith("@@")) {
      rows.push({ gutter: " ", line, cls: "ctx" });
    } else if (line.startsWith("+")) {
      rows.push({ gutter: "+", line: line.slice(1), cls: "add" });
    } else if (line.startsWith("-")) {
      rows.push({ gutter: "−", line: line.slice(1), cls: "del" });
    } else {
      rows.push({ gutter: " ", line: line.startsWith(" ") ? line.slice(1) : line, cls: "ctx" });
    }
  }
  return rows;
}

export default function HunkView({ hunk }: { hunk: Hunk }) {
  const rows = parseDiffLines(hunk.diff_text);
  const clsBadge = CLS_COLORS[hunk.classification] || "amb";
  const clsLabel = CLS_LABELS[hunk.classification] || hunk.classification;

  return (
    <div className="hunk-card">
      <div className="hunk-header">
        <code>{hunk.hunk_header}</code>
        <span className={`badge ${clsBadge}`}>{clsLabel}</span>
      </div>

      {hunk.reason && <div className="hunk-reason">{hunk.reason}</div>}

      {hunk.vz_references.length > 0 && (
        <div className="hunk-refs">
          {hunk.vz_references.map((ref, i) => (
            <span key={i} className="hunk-ref-tag">
              {ref}
            </span>
          ))}
        </div>
      )}

      <div className="hunk-diff">
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

      {(hunk.generic_summary || hunk.vz_summary) && (
        <div className="hunk-summary">
          {hunk.generic_summary && <div>Generic: {hunk.generic_summary}</div>}
          {hunk.vz_summary && <div>VZ: {hunk.vz_summary}</div>}
        </div>
      )}
    </div>
  );
}
