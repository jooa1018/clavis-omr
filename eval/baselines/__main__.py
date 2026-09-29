"""Manual OR-001 one-page baseline invocation; no automatic model downloads."""

import argparse
import subprocess

from eval.baselines import run
from eval.gt.__main__ import contained, private_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=("audiveris", "homr", "oemer"))
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--dataset-digest", required=True)
    parser.add_argument("--manual-or001", action="store_true", required=True)
    args = parser.parse_args()
    try:
        root = private_root()
        result = run(
            args.engine,
            args.image_id,
            contained(root, args.input),
            contained(root, args.cache),
            args.dataset_digest,
        )
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        print("NOT_RUN: baseline environment, provenance or private paths unavailable")
        return 2
    print(result["status"] + ": " + result["reason"])
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
