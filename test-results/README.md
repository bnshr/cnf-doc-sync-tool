# Test Results

This directory stores JSON and Markdown output from validation runs of the cnf-doc-sync skill.

## File naming convention

Each test run produces a pair of files named by the commit hash range used:

```
<private-short-hash>_<public-short-hash>_data.json
<private-short-hash>_<public-short-hash>_report.md
```

Example:
```
a1b2c3d_e4f5g6h_data.json
a1b2c3d_e4f5g6h_report.md
```

## Contents

- `*_data.json` — Raw analysis data (classified changes, hunks, metadata)
- `*_report.md` — Human-readable sync review report

All files in this directory (except this README and .gitkeep) are gitignored.
