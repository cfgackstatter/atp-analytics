"""CLI entrypoint: ``python -m backend.jobs.cli <job_type> '<json params>'``."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from backend.jobs.runner import run_job


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an ATP Analytics scrape job")
    parser.add_argument("job_type", choices=sorted(["rankings", "tournaments", "players"]))
    parser.add_argument(
        "params_json",
        help="JSON object of job parameters",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    try:
        params = json.loads(args.params_json)
        if not isinstance(params, dict):
            raise ValueError("params_json must be a JSON object")
        result = run_job(args.job_type, params)
        print(json.dumps({"ok": True, "result": result}), flush=True)
        return 0
    except Exception as exc:
        logging.exception("Job failed")
        print(json.dumps({"ok": False, "error": str(exc)}), flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
