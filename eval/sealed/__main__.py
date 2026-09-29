"""Custodian G0 preparation only. No engine execution or automatic official run."""

import argparse
from typing import Any

from eval.gt.__main__ import contained, private_root, read_json
from eval.integrity.hashes import produce
from eval.report import canonical
from eval.sealed import append_ledger, preflight, release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    hashes = subs.add_parser("hashes")
    hashes.add_argument("--manifest", required=True)
    pre = subs.add_parser("preflight")
    pre.add_argument("--artifact", required=True)
    pre.add_argument("--observed-digests", required=True)
    share = subs.add_parser("release")
    share.add_argument("--aggregate", required=True)
    share.add_argument("--public-vocabulary", required=True)
    share.add_argument("--pairs-manifest")
    ledger = subs.add_parser("ledger")
    ledger.add_argument("--receipt", required=True)
    ledger.add_argument("--ledger", required=True)
    for child in (hashes, pre, share, ledger):
        child.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        root = private_root()
        target = contained(root, args.out)
        if target.exists():
            raise ValueError("output already exists")

        def read(relative: str) -> dict[str, Any]:
            value = read_json(contained(root, relative))
            if not isinstance(value, dict):
                raise ValueError("expected JSON object")
            return value

        if args.command == "hashes":
            result = produce(root, read(args.manifest))
        elif args.command == "preflight":
            result = preflight(read(args.artifact), read(args.observed_digests))
        elif args.command == "release":
            pairs = (
                [read(path) for path in read(args.pairs_manifest)["pairs"]]
                if args.pairs_manifest
                else None
            )
            result = release(read(args.aggregate), read(args.public_vocabulary), pairs)
        else:
            result = append_ledger(contained(root, args.ledger), read(args.receipt))
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as stream:
            stream.write(canonical(result))
        print("LOCAL_OUTPUT_CREATED; no engine execution performed")
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("ERROR: invalid private preparation inputs; no private content printed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
