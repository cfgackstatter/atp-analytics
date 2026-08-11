"""In-process job tracking with scrapes running in a dedicated subprocess."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Repo root (…/atp-analytics) so ``python -m backend.jobs.cli`` can import the package.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MAX_COMPLETED_JOBS = 50

_lock = threading.Lock()
active_jobs: dict[str, dict[str, Any]] = {}
completed_jobs: list[dict[str, Any]] = []
_worker_thread: threading.Thread | None = None


def _now_iso() -> str:
    return datetime.now().isoformat()


def is_busy() -> bool:
    with _lock:
        return bool(active_jobs)


def list_jobs() -> dict[str, list[dict[str, Any]]]:
    with _lock:
        return {
            "active": list(active_jobs.values()),
            "completed": list(completed_jobs[-20:]),
        }


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        if job_id in active_jobs:
            return dict(active_jobs[job_id])
        for job in reversed(completed_jobs):
            if job.get("job_id") == job_id:
                return dict(job)
    return None


def _finish_locked(job_id: str, **meta: Any) -> None:
    active = active_jobs.pop(job_id, {})
    completed_jobs.append(
        {
            "job_id": job_id,
            "type": active.get("type"),
            "started": active.get("started"),
            "completed": _now_iso(),
            **{k: v for k, v in active.items() if k not in {"status", "started"}},
            **meta,
        }
    )
    if len(completed_jobs) > _MAX_COMPLETED_JOBS:
        del completed_jobs[:-_MAX_COMPLETED_JOBS]


def _parse_child_payload(stdout: str, stderr: str, exit_code: int) -> dict[str, Any]:
    """Parse the last JSON line from the child process stdout."""
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "ok" in payload:
            return payload

    detail = stderr.strip() or stdout.strip() or f"exit {exit_code}"
    return {"ok": False, "error": f"Scrape subprocess failed: {detail}"}


def _run_worker(job_id: str, job_type: str, params: dict[str, Any]) -> None:
    """Background thread: own a subprocess so Playwright never blocks gunicorn."""
    cmd = [
        sys.executable,
        "-m",
        "backend.jobs.cli",
        job_type,
        json.dumps(params),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    try:
        logger.info("Starting scrape subprocess job_id=%s cmd=%s", job_id, cmd)
        # Capture stdout for the JSON result line; inherit stderr so scrape
        # progress shows up in uvicorn / EB logs.
        completed = subprocess.run(
            cmd,
            cwd=_PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            check=False,
            env=env,
        )
        payload = _parse_child_payload(
            completed.stdout or "", "", completed.returncode
        )
        with _lock:
            if payload.get("ok"):
                _finish_locked(job_id, status="completed", **(payload.get("result") or {}))
            else:
                _finish_locked(
                    job_id,
                    status="failed",
                    error=payload.get("error") or "Unknown scrape error",
                )
                logger.error(
                    "Scrape failed job_id=%s exit=%s",
                    job_id,
                    completed.returncode,
                )
    except Exception as exc:
        logger.exception("Job manager failed for %s", job_id)
        with _lock:
            if job_id in active_jobs:
                _finish_locked(job_id, status="failed", error=str(exc))


def submit_job(job_type: str, params: dict[str, Any], **meta: Any) -> str:
    """
    Start a scrape job in a subprocess.

    Raises HTTP 409 if another scrape is already running (single-flight).
    """
    global _worker_thread

    job_id = f"{job_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with _lock:
        if active_jobs:
            running = next(iter(active_jobs.values()))
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A scrape job is already running "
                    f"({running.get('job_id', 'unknown')}). Try again later."
                ),
            )

        active_jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "type": job_type,
            "started": _now_iso(),
            **meta,
            **params,
        }

        thread = threading.Thread(
            target=_run_worker,
            args=(job_id, job_type, params),
            name=f"job-waiter-{job_id}",
            daemon=True,
        )
        _worker_thread = thread
        thread.start()

    return job_id
