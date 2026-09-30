# Review UI: what to do

The review screen at `http://localhost:8090` is where you decide which private-repo edits are allowed into the public Kubernetes guide. The classifier has already labeled the changes. Your job is one decision per file, then **Create PR**.

Hunk cards, badges, and the two text columns are evidence. They do not publish anything.

## The decision

Each file ends in one of these states:

| State | How it gets there | Effect on the PR |
|-------|-------------------|------------------|
| Accepted | **Accept**, or **Save & Accept** in the editor | That file's public text is written into the public repo |
| Skipped | **Skip** | Public file stays as it is |
| Excluded | File is in **VZ-only**, or you override it to VZ-specific | Public file stays as it is |
| Pending | You have not chosen yet | Left out of the PR |

**Create PR** turns on as soon as one file is accepted. Pending files can stay pending.

## What to do, in order

1. Work the **To review** list from top to bottom. Pending files (yellow dot) are listed first. After **Accept** or **Skip**, the next pending file opens.
2. Read **Hunk Analysis** to see whether each edit is generic, Verizon-specific, or both.
3. Make one file-level choice:
   - Every hunk is **Generic**, and **Proposed public content** is a complete public file with no Verizon markers: click **Accept**.
   - Any hunk is **Mixed**, or **Proposed public content** is empty: click **Edit & accept**. Keep the generic sentences, delete Verizon markers (VCP, Doors Id, ENSE, SPK, Verizon hostnames), and use `k8s-best-practices-` in headings and cross-references. **Save & Accept** stores the whole file.
   - The change should stay private: click **Skip**. To take it out of the queue, set **Override AI** to **VZ-specific**.
   - There is no **PUBLIC** path: click **Skip**. The publisher cannot create a counterpart.
4. Leave **VZ-only — excluded** collapsed. Open it only to check a file you think was excluded by mistake. If you still want a public version, override it to **Shared**, then **Edit & accept**.
5. Click **Create PR** when the accepted set is the set you want published.

`classify.py` leaves **Proposed public content** empty. On a CLI run, **Accept** marks the file accepted and **Create PR** then drops it because there is no text. Use **Edit & accept** and paste the full public file.

## Screen map

### Top bar

- **private / public** hashes are the commits this review covers.
- **changed** is every file in the data file.
- **VZ-specific** is the excluded group.
- **to review** is your queue.
- The green, red, and pending counts are your decisions so far.
- **Reset all** clears accepts, skips, edits, and classification overrides.
- **Create PR (N files)** publishes the accepted files. The label matches the accepted count, which can be higher than the number of files that actually land in the PR (see below).

### Left list

**To review.** Yellow dot means pending, green means accepted, red means skipped.

The mark at the right of the filename is the file label, separate from the dot. A check means **Shared**. A question mark means **Ambiguous**. A pencil means you overrode the classifier. **Shared** means the file is in your queue. A file with mixed hunks is still labeled Shared.

Checkboxes feed **Accept all** and **Skip all**. Bulk accept publishes whatever public text is already stored. If that text is empty, the files count as accepted and are dropped when the PR is built.

**VZ-only — excluded.** These files were classified as private. **Accept** is hidden. **Edit & accept** is still available if you want to write a public version yourself.

### File panel, top to bottom

1. **PRIVATE** is the source path. **PUBLIC** is the file the PR would replace. No PUBLIC line means there is no counterpart to write.
2. **AI decision** is the file label: **VZ-specific**, **Shared**, or **Ambiguous**. The lit badge is the classifier's choice; the sentence beside it is the reason. **Override AI** moves the file between the two sidebar groups. Choosing VZ-specific excludes it. Choosing Shared or Ambiguous returns an excluded file to **To review**. **Reset to AI** restores the original label. An override does not re-analyze the diff.
3. **Changes in private repo** is the private file before this commit and after it. Green lines were added, red lines were removed.
4. **Proposed public content** is the full text that would be written to the public file, not a second diff. When a draft exists, the subtitle says it was sanitized for the public guide. When it is empty, the column says there is nothing to publish. **Edited public content** replaces this column after you save an edit.
5. **Hunk Analysis (N hunks)** is read-only. A hunk is one contiguous edit, the block that starts with `@@`. **1 hunk** means the file has a single edit region. Each card shows that region's label (**Generic**, **VZ-Specific**, or **Mixed**), the reason, any Verizon markers found, and the added and removed lines. There are no buttons on a hunk. You cannot accept one hunk and skip another.
6. The decision bar:
   - **Accept** publishes the text already in the right column. It is hidden on VZ-specific files. It does nothing useful when that column is empty.
   - **Edit & accept** opens an editor seeded with the proposed text, or an empty box. **Save & Accept** stores your text and marks the file accepted.
   - **Skip** leaves this file out. The status pill says **Skipped**.

A banner on VZ-specific files repeats the same choice: leave the file excluded, or **Edit & accept** a version you wrote.

## What Create PR actually writes

The publisher includes an accepted file only when all of these are true:

- it has a public path
- it has non-empty public text
- if you did not edit the text, it contains no Verizon marker
- if you did not edit the text, it is not a small fragment of a much larger existing public file (under 20% of the current file, when the current file is longer than 100 characters)

Text you edited yourself is included even if a Verizon marker remains. That case is reported as a warning and does not stop the PR. Read the warning before merging.

The publisher checks out `main` in the public guide repo, pulls, creates `sync/vz-<date>`, commits the applied files, pushes, and opens a PR. The public repo needs a clean working tree, and `gh` needs to be logged in. Pending, skipped, and excluded files stay out.

## Two labels that sit next to each other

| | File label | Hunk label |
|--|------------|------------|
| Where | **AI decision**, and the check or question mark in the sidebar | Inside **Hunk Analysis** |
| Values | VZ-specific, Shared, Ambiguous | Generic, VZ-Specific, Mixed |
| What it controls | Which sidebar group the file is in, and whether **Accept** is shown | Nothing. It explains one edit region |

The colored dot is your decision. The check or question mark is the file label. They change independently.
