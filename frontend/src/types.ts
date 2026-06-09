export type FileClassification = "vz_specific" | "shared" | "ambiguous";
export type HunkClassification = "generic" | "verizon-specific" | "mixed";
export type Decision = "pending" | "accepted" | "rejected" | "auto_excluded";

export interface Hunk {
  id: string;
  hunk_header: string;
  diff_text: string;
  classification: HunkClassification;
  reason: string;
  vz_references: string[];
  generic_summary: string;
  vz_summary: string;
}

export interface SyncFile {
  id: string;
  private_path: string;
  public_path: string;
  file_classification: FileClassification;
  file_classification_reason: string;
  private_content_before: string;
  private_content_after: string;
  proposed_public_content: string;
  final_content: string;
  decision: Decision;
  reviewer_classification: string;
  hunks: Hunk[];
}

export interface SessionData {
  version: number;
  created_at: string;
  private_repo: string;
  public_repo: string;
  private_repo_url?: string;
  public_repo_url?: string;
  since_ref: string;
  head_ref: string;
  public_ref: string;
  files: SyncFile[];
  pr_url?: string;
}

export interface Summary {
  total: number;
  accepted: number;
  rejected: number;
  pending: number;
  auto_excluded: number;
}
