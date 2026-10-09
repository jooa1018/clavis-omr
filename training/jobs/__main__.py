"""Local CPU queue: submit, status, pause, resume, run."""

import argparse
import json
from pathlib import Path

from training.jobs.model import JobSpec
from training.jobs.runner import run
from training.jobs.store import Queue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, help="Queue state directory; machine lock remains global"
    )
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("submit").add_argument("request", type=Path)
    commands.add_parser("status")
    commands.add_parser("pause")
    commands.add_parser("resume")
    commands.add_parser("run").add_argument(
        "--manual", action="store_true", help="Explicit manual start outside the 01:00-07:00 window"
    )
    args = parser.parse_args()
    queue = Queue(args.root)
    if args.action == "submit":
        spec = JobSpec.model_validate_json(args.request.read_text(encoding="utf-8"))
        result: object = {"jobId": queue.submit(spec)}
    elif args.action == "pause":
        queue.pause()
        result = {"paused": True}
    elif args.action == "resume":
        queue.resume()
        result = {"paused": False, "note": "run must be started separately"}
    elif args.action == "run":
        result = run(queue, manual=args.manual)
    else:
        result = [{k: v for k, v in row.items() if k != "spec"} for row in queue.rows()]
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
