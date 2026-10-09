"""Queue payload: empirical profile fitting and resumable generated-block audit."""

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import xmlschema
import yaml

from training.data.production_audit import audit
from training.data.production_plan import plan_block
from training.data.production_rhythm import fit
from training.data.production_xml import generate
from training.data.rhythm_groups import kl_divergence
from training.data.smoke import write_json
from training.jobs.context import Context


def schema() -> xmlschema.XMLSchema10:
    root = Path("src/clavis/export/schemas/musicxml-4.0").resolve()
    return xmlschema.XMLSchema(
        root / "musicxml.xsd",
        locations={
            "http://www.w3.org/XML/1998/namespace": str(root / "xml.xsd"),
            "http://www.w3.org/1999/xlink": str(root / "xlink.xsd"),
        },
        allow="local",
        defuse="always",
        use_fallback=False,
    )


def source_digest() -> str:
    """Reject a queued run if generator/config/dependency bytes changed after submit."""
    paths = sorted(
        [
            *Path("training/data").rglob("*.py"),
            *Path("configs/data").glob("*.yaml"),
            *Path("configs/data").glob("*.json"),
            Path("uv.lock"),
        ]
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def load() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    profile, notation, rhythm = (
        yaml.safe_load(Path(f"configs/data/leadgen-{name}.yaml").read_text(encoding="utf-8"))
        for name in ("production", "notation", "rhythm")
    )
    path = Path(profile["rhythm"]["target_artifact"])
    payload = path.read_bytes()
    target = json.loads(payload)
    canonical = json.dumps(target, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != profile["rhythm"]["target_sha256"]:
        raise ValueError("Empirical target digest mismatch")
    return profile, notation, rhythm, target


def accumulate(state: dict[str, Any], result: dict[str, Any], profile: dict[str, Any]) -> None:
    for name, value in result["initial"].items():
        totals = Counter(state.setdefault("initial_distribution", {}).get(name, {}))
        totals[value] += 1
        state["initial_distribution"][name] = dict(totals)
    features = result["features"]
    for group, values in (
        ("instances", features),
        ("songs", {k: int(v > 0) for k, v in features.items()}),
    ):
        totals = Counter(state[group])
        totals.update(values)
        state[group] = dict(totals)
    for meter, counts in result["counts"].items():
        totals = Counter(state["counts"].get(meter, {}))
        totals.update({k: v for k, v in counts.items() if k.startswith("note:")})
        state["counts"][meter] = dict(totals)
    for name, definition in profile["features"].items():
        if not features.get(name):
            continue
        if definition.get("within_denominator") == "measures":
            numerator, denominator = result["measure_features"][name], result["measures"]
        elif name == "grace":
            numerator, denominator = features[name], result["pitched_including_grace"]
        else:
            continue
        ratio = numerator / denominator
        record = state["conditional"].setdefault(
            name,
            {"songs": 0, "numerator": 0, "denominator": 0, "min": 1.0, "max": 0.0, "outside": 0},
        )
        record["songs"] += 1
        record["numerator"] += numerator
        record["denominator"] += denominator
        record["min"], record["max"] = min(record["min"], ratio), max(record["max"], ratio)
        low, high = definition["within_range"]
        record["outside"] += int(not low <= ratio <= high)


def summarize(
    state: dict[str, Any], profile: dict[str, Any], target: dict[str, Any]
) -> dict[str, Any]:
    total = state["next"]
    categories = profile["block_acceptance"]["p0_categories"]
    p0 = {
        name: {
            "songs": state["songs"].get(name, 0),
            "instances": state["instances"].get(name, 0),
            "song_ratio": state["songs"].get(name, 0) / total,
        }
        for name in categories
    }
    failures = [
        name
        for name, v in p0.items()
        if v["song_ratio"] < profile["block_acceptance"]["p0_min_song_ratio"]
        or v["instances"] < profile["block_acceptance"]["p0_min_instances"]
    ]
    meters = {}
    for meter, counts in state["counts"].items():
        reference = {k: v for k, v in target["counts"][meter].items() if k.startswith("note:")}
        kl = kl_divergence(counts, reference)
        denominator = sum(counts.values())
        rare32 = sum(v for k, v in counts.items() if ":32nd:" in k) / denominator
        rare_dots = sum(v for k, v in counts.items() if k.endswith("dots=2")) / denominator
        meters[meter] = {
            "noteheads": denominator,
            "kl_generated_target": kl if math.isfinite(kl) else "Infinity",
            "ratio_32nd": rare32,
            "ratio_double_dot": rare_dots,
        }
        if (
            rare32 < profile["rhythm"]["min_32nd_note_ratio"]
            or rare_dots < profile["rhythm"]["min_double_dot_note_ratio"]
        ):
            failures.append(f"rare_floor:{meter}")
    rates = {
        name: {
            "songs": state["songs"].get(name, 0),
            "denominator": total,
            "ratio": state["songs"].get(name, 0) / total,
            "target": definition["song_probability"],
        }
        for name, definition in profile["features"].items()
    }
    for name, rate in rates.items():
        if rate["songs"] != round(total * rate["target"]):
            failures.append(f"song_rate:{name}")
    for name, record in state["conditional"].items():
        if record["outside"]:
            failures.append(f"conditional:{name}")
    if state["invalid"]:
        failures.append("invalid_xml_or_notation")
    status = (
        "PREVIEW"
        if total != profile["block_acceptance"]["songs"]
        else "FAIL"
        if failures
        else "PASS"
    )
    return {
        "status": status,
        "training_admission": "BLOCKED_OR_003",
        "source_manifest_digest": target["manifest_digest"],
        "target_sha256": profile["rhythm"]["target_sha256"],
        "p0": p0,
        "meters": meters,
        "song_rates": rates,
        "conditional": state["conditional"],
        "failures": failures,
        "state": state,
    }


def run(output: Path, seed: str, limit: int, context: Context) -> dict[str, Any] | None:
    profile, notation, rhythm, target = load()
    plans = plan_block(seed, profile)
    if not 1 <= limit <= len(plans):
        raise ValueError("Invalid block audit limit")
    output.mkdir(parents=True, exist_ok=True)
    profiles = {
        meter: fit(meter, {k: v for k, v in counts.items() if k.startswith("note:")}, rhythm)
        for meter, counts in target["counts"].items()
    }
    write_json(
        output / "fitted-profile.json",
        {
            "target_sha256": profile["rhythm"]["target_sha256"],
            "manifest_digest": target["manifest_digest"],
            "meters": {
                m: {
                    "patterns": [
                        [[v.key for v in group] for group in pattern] for pattern in p.patterns
                    ],
                    "probabilities": p.probabilities,
                    "fitted_note_probabilities": p.fitted_note_probabilities,
                }
                for m, p in profiles.items()
            },
        },
    )
    validator = schema()
    state = context.load() or {
        "next": 0,
        "invalid": {},
        "songs": {},
        "instances": {},
        "counts": {},
        "conditional": {},
        "xml_chain_digest": "0" * 64,
    }
    for plan in plans[state["next"] : limit]:
        if context.stopping():
            context.save(state)
            return None
        try:
            xml = generate(plan, profiles, notation, profile)
            validator.validate(xml)
            result = audit(xml)
            accumulate(state, result, profile)
            state["xml_chain_digest"] = hashlib.sha256(
                bytes.fromhex(state["xml_chain_digest"]) + xml.encode("utf-8")
            ).hexdigest()
            if state["next"] < profile["block_acceptance"]["saved_preview_scores"]:
                (output / f"preview-{state['next']}.musicxml").write_text(xml, encoding="utf-8")
        except (ValueError, xmlschema.XMLSchemaException) as error:
            name = type(error).__name__
            state["invalid"][name] = state["invalid"].get(name, 0) + 1
        state["next"] += 1
        context.save(state)
    result = summarize(state, profile, target)
    write_json(output / "report.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--limit", type=int, default=10000)
    args = parser.parse_args()
    context = Context()
    request = json.loads((context.directory / "request.json").read_text(encoding="utf-8"))
    expected = request["config"].get("sourceDigest")
    if expected is not None and expected != source_digest():
        raise ValueError("Queued generator source digest changed")
    result = run(args.output, args.seed, args.limit, context)
    if result is not None:
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "songs": result["state"]["next"],
                    "failures": result["failures"],
                }
            )
        )
        if result["status"] == "FAIL":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
