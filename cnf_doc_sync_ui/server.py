"""FastAPI server for CNF Doc Sync Review UI."""

from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .publisher import create_pr

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8090"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_data: dict[str, Any] = {}
_data_path: Path = Path()


def _save() -> None:
    _data_path.write_text(json.dumps(_data, indent=2))


def _find_file(file_id: str) -> dict[str, Any]:
    for f in _data["files"]:
        if f["id"] == file_id:
            return f
    raise HTTPException(404, f"File {file_id} not found")


# ── API endpoints ─────────────────────────────────────────────────────────────


@app.get("/api/session")
def get_session() -> dict[str, Any]:
    return _data


class DecisionBody(BaseModel):
    decision: str
    final_content: str = ""


@app.patch("/api/files/{file_id}/decision")
def patch_decision(file_id: str, body: DecisionBody) -> dict[str, bool]:
    if body.decision not in ("accepted", "rejected"):
        raise HTTPException(422, "decision must be 'accepted' or 'rejected'")
    f = _find_file(file_id)
    f["decision"] = body.decision
    if body.decision == "accepted":
        f["final_content"] = body.final_content
    else:
        f["final_content"] = ""
    _save()
    return {"ok": True}


class ClassificationBody(BaseModel):
    reviewer_classification: str


@app.patch("/api/files/{file_id}/classification")
def patch_classification(file_id: str, body: ClassificationBody) -> dict[str, bool]:
    valid = ("vz_specific", "shared", "ambiguous", "")
    if body.reviewer_classification not in valid:
        raise HTTPException(422, f"reviewer_classification must be one of {valid}")
    f = _find_file(file_id)
    f["reviewer_classification"] = body.reviewer_classification
    if body.reviewer_classification == "vz_specific":
        f["decision"] = "auto_excluded"
        f["final_content"] = ""
    elif f["decision"] == "auto_excluded":
        f["decision"] = "pending"
    _save()
    return {"ok": True}


@app.get("/api/summary")
def get_summary() -> dict[str, int]:
    total = 0
    accepted = 0
    rejected = 0
    pending = 0
    auto_excluded = 0
    for f in _data["files"]:
        total += 1
        d = f["decision"]
        if d == "accepted":
            accepted += 1
        elif d == "rejected":
            rejected += 1
        elif d == "auto_excluded":
            auto_excluded += 1
        else:
            pending += 1
    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "pending": pending,
        "auto_excluded": auto_excluded,
    }


@app.post("/api/reset")
def do_reset() -> dict[str, bool]:
    for f in _data["files"]:
        if f.get("proposed_public_content"):
            f["decision"] = "pending"
        else:
            f["decision"] = "auto_excluded"
        f["final_content"] = ""
        f["reviewer_classification"] = ""
    _data.pop("pr_url", None)
    _save()
    return {"ok": True}


@app.post("/api/create-pr")
def do_create_pr() -> dict[str, Any]:
    result = create_pr(_data)
    if "error" in result:
        raise HTTPException(400, result["error"])
    _data["pr_url"] = result.get("pr_url", "")
    _save()
    return result


# ── Static file serving ──────────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"


def _mount_static() -> None:
    if (static_dir / "index.html").exists():
        @app.get("/")
        def serve_index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        app.mount("/", StaticFiles(directory=str(static_dir)), name="static")


_mount_static()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="CNF Doc Sync Review UI")
    parser.add_argument("--data", required=True, help="Path to JSON data file")
    parser.add_argument("--port", type=int, default=8090, help="Server port")
    parser.add_argument("--no-open", action="store_true", help="Don't open browser")
    args = parser.parse_args()

    global _data, _data_path
    _data_path = Path(args.data).resolve()
    if not _data_path.exists():
        print(f"Error: {_data_path} not found")
        raise SystemExit(1)
    _data = json.loads(_data_path.read_text())

    url = f"http://localhost:{args.port}"
    print(f"Starting CNF Doc Sync Review UI at {url}")
    print(f"Data file: {_data_path}")

    if not args.no_open:
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
