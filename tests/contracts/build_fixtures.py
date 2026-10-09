"""Author synthetic contract mocks; does not render, recognize, or read a corpus."""

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from clavis.contracts import DOCUMENT_MODELS, canonical_json

ROOT = Path(__file__).resolve().parents[1] / "fixtures/contracts"
IR = "clavis-ir-0.1.1"


def digest(label):
    return hashlib.sha256(label.encode()).hexdigest()


def frac(n, d=1):
    value = Fraction(n, d)
    return {"n": value.numerator, "d": value.denominator}


def author():
    producer = {
        "name": "authored-contract-mock",
        "version": "0.1",
        "sha256": digest("mock producer"),
    }
    frame = {
        "id": "clavis:frame:0",
        "pageIndex": 0,
        "coordinateSpace": "original-pixels",
        "widthPixels": 880,
        "heightPixels": 1180,
        "imageDigest": digest("mock bytes; no raster exists"),
    }
    processed = {**frame, "id": "processed:0", "coordinateSpace": "processed-pixels"}
    page = {
        "schema": IR,
        "id": "pg0",
        "pageIndex": 0,
        "source": {"kind": "image", "mime": "image/png", "bytesSha256": frame["imageDigest"]},
        "original": {"width": 880, "height": 1180, "pixelsSha256": digest("mock pixels")},
        "frames": [frame, processed],
        "transforms": [
            {
                "id": "pg0-h0",
                "fromFrameId": frame["id"],
                "toFrameId": processed["id"],
                "kind": "homography",
                "matrix": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            }
        ],
    }
    quality = {
        "schema": IR,
        "id": "pg0",
        "blurBp": 2300,
        "perspectiveBp": 0,
        "glareBp": 0,
        "cropRiskBp": 200,
        "estimatedStaffSpacePixels": 10.0,
        "status": "warn",
        "reasons": ["RESOLUTION_TOO_LOW"],
        "contrastBp": 7800,
        "noiseBp": 800,
        "jpegQualityEstimate": 75,
        "interlineSpreadBp": 0,
        "expectedBurdenBucket": "medium",
    }
    layout = {
        "schema": IR,
        "id": "pg0",
        "staves": [],
        "systems": [],
        "strips": [],
        "readingOrder": [],
        "oodFlags": [],
        "nonStaffMask": {
            "frameId": "processed:0",
            "width": 880,
            "height": 1180,
            "counts": [0, 880 * 190, 880 * 90, 880 * 190, 880 * 90, 880 * 190, 880 * 90, 880 * 340],
        },
    }
    score = {
        "schema": IR,
        "id": "score0",
        "meta": {"title": "세 줄의 연습", "tempo": {"text": "Moderato"}},
        "engine": {"version": "mock-0.1", "buildDigest": digest("mock build")},
        "parts": [
            {
                "partId": "P1",
                "name": "Melody",
                "staffCount": 1,
                "staffSlots": [
                    {"staffInPart": 1, "staffIds": [f"pg0-sy{s}-st0" for s in range(3)]}
                ],
            }
        ],
        "measures": [],
        "flow": {
            "repeats": [{"startMeasureId": "P1-m0", "endMeasureId": "P1-m5", "times": 2}],
            "endings": [],
            "navigation": [],
        },
        "status": "complete",
        "diagnostics": [{"code": "MOCK_FIXTURE", "severity": "info"}],
    }
    texts = {"schema": IR, "id": "pg0", "items": []}
    evidence = {
        "schema": "clavis-evidence-0.1",
        "granularity": "measure",
        "frames": [frame],
        "transforms": [],
        "evidence": [],
        "extensions": {"staffPolygons": [], "measureBoxes": []},
    }
    confidences = {"schema": "clavis-confidence-0.1", "elements": []}
    graphs, lattices = [], []
    # Notation is authored data, not a recognition rule or a corpus-derived answer.
    plans = [
        [
            ("note", "quarter", 1, 3, 2, "E", 4),
            ("note", "eighth", 0, 1, 2, "F", 5),
            ("note", "quarter", 0, 1, 1, "G", 6),
            ("note", "quarter", 0, 1, 1, "A", 7),
        ],
        [
            ("note", "quarter", 0, 1, 1, "G", 6),
            ("note", "quarter", 0, 1, 1, "F", 5),
            ("note", "half", 0, 2, 1, "E", 4),
        ],
        [
            ("note", "half", 0, 2, 1, "E", 4),
            ("note", "quarter", 0, 1, 1, "D", 3),
            ("rest", "quarter", 0, 1, 1, None, 4),
        ],
        [
            ("note", "eighth", 0, 1, 2, "D", 3),
            ("note", "eighth", 0, 1, 2, "E", 4),
            ("note", "quarter", 1, 3, 2, "F", 5),
            ("note", "eighth", 0, 1, 2, "G", 6),
            ("note", "quarter", 0, 1, 1, "E", 4),
        ],
        [
            ("rhythm", "quarter", 0, 1, 1, None, 4),
            ("rest", "quarter", 0, 1, 1, None, 4),
            ("note", "quarter", 0, 1, 1, "G", 6),
            ("note", "quarter", 0, 1, 1, "F", 5),
        ],
        [("note", "whole", 0, 4, 1, "C", 2)],
    ]
    chord_data = [
        ("C", "C", "major"),
        ("Am7", "A", "minor-seventh"),
        ("F", "F", "major"),
        ("G7", "G", "dominant"),
        ("N.C.", None, "none"),
        ("C/E", "C", "major"),
    ]
    lyric_words = iter("아 침 빛 따 라 한 걸 음 씩 가 요".split())
    text_counter = 0

    def text_item(text, role, staff_id, x, y, **extra):
        nonlocal text_counter
        tid = f"temporary-text-{text_counter}"
        text_counter += 1
        item = {
            "textId": tid,
            "pageIndex": 0,
            "boxProcessed": [float(x), float(y), float(max(16, len(text) * 12)), 16.0],
            "role": role,
            "roleProbs": {role: 9700, "other": 300},
            "text": text,
            "alternatives": [],
            "confidenceBp": 9700,
            "staffLink": {
                "staffId": staff_id,
                "relation": "below" if role == "lyric" else "above",
                "distanceSpaces": 3.0,
            },
            **extra,
        }
        texts["items"].append(item)
        return tid

    def add_evidence(target, granularity, box, confidence=9700):
        eid = f"ev-{target}-{granularity}"
        evidence["evidence"].append(
            {
                "id": eid,
                "vendorTargetId": target,
                "granularity": granularity,
                "box": {
                    "frameId": frame["id"],
                    **dict(
                        zip(
                            ["xMu", "yMu", "widthMu", "heightMu"],
                            [int(v * 1000000) for v in box],
                            strict=True,
                        )
                    ),
                },
                "confidenceBp": confidence,
                "vendorId": "clavis",
            }
        )
        return eid

    def conf(target, kind, bp=9700, **extra):
        confidences["elements"].append(
            {"id": target, "kind": kind, "confidenceBp": bp, "flagged": bp < 8000, **extra}
        )

    text_item("세 줄의 연습", "title", "pg0-sy0-st0", 310, 60)
    tempo_id = text_item("Moderato", "tempo", "pg0-sy0-st0", 80, 150)
    for s, ytop in enumerate([220.0, 500.0, 780.0]):
        staff = f"pg0-sy{s}-st0"
        system = f"pg0-sy{s}"
        layout["readingOrder"].append(system)
        layout["staves"].append(
            {
                "staffId": staff,
                "systemId": system,
                "lines": [[[80.0, ytop + 10 * i], [840.0, ytop + 10 * i]] for i in range(5)],
                "interlinePx": 10.0,
                "interlineProfile": [
                    {"x": 80.0, "interlinePx": 10.0},
                    {"x": 840.0, "interlinePx": 10.0},
                ],
                "lineThicknessPx": 1.0,
                "bbox": [80.0, ytop, 760.0, 40.0],
                "lineCount": 5,
                "confidenceBp": 9850,
            }
        )
        layout["systems"].append(
            {
                "systemId": system,
                "staffIds": [staff],
                "groups": [{"type": "none", "staffIds": [staff]}],
                "barlines": [
                    {
                        "xProcessed": 80 + (100 if s == 0 and u == 0 else u) * 0.625,
                        "uByStaff": {staff: float(100 if s == 0 and u == 0 else u)},
                        "spanStaffIds": [staff],
                        "styleGuess": "final" if s == 2 and u == 1215 else "regular",
                        "confidenceBp": 9800,
                    }
                    for u in [0, 608, 1215]
                ],
            }
        )
        layout["strips"].append(
            {
                "stripId": staff,
                "sStar": 16.0,
                "width": 1216,
                "height": 240,
                "marginAboveSpaces": 6.0,
                "marginBelowSpaces": 5.0,
                "mesh": {
                    "uStep": 8.0,
                    "x": [80.0 + u * 0.625 for u in range(0, 1217, 8)],
                    "yTop": [ytop] * 153,
                    "interline": [10.0] * 153,
                },
                "pixelsSha256": digest(f"mock strip {s}"),
            }
        )
        evidence["extensions"]["staffPolygons"].append(
            {
                "staffId": staff,
                "frameId": frame["id"],
                "pointsMu": [
                    [80000000, int(ytop * 1000000)],
                    [840000000, int(ytop * 1000000)],
                    [840000000, int((ytop + 40) * 1000000)],
                    [80000000, int((ytop + 40) * 1000000)],
                ],
            }
        )
        graph = {
            "schema": IR,
            "id": staff,
            "stripId": staff,
            "producer": producer,
            "symbols": [],
            "relations": [],
            "rejectedCandidates": [],
        }
        items = []

        def symbol(cls, u, v, w=16.0, h=12.0, attrs=None, graph=graph):
            sid = f"temporary-symbol-{len(graph['symbols'])}"
            graph["symbols"].append(
                {
                    "symbolId": sid,
                    "sources": ["template" if cls.startswith("note") else "cc"],
                    "classTopK": [[cls, 9700], ["reject", 300]],
                    "boxStrip": [float(u), float(v), w, h],
                    "centerStrip": [u + w / 2, v + h / 2],
                    "attrs": attrs or {},
                }
            )
            observed = graph["symbols"][-1]
            if "posTopK" in observed["attrs"]:
                observed["posTopK"] = observed["attrs"].pop("posTopK")
            if not observed["attrs"]:
                observed.pop("attrs")
            return sid

        clef = symbol("clefG", 16.0, 80.0, 24.0, 90.0)
        items.append(
            {
                "item": {"type": "clef", "sign": "G2"},
                "attrTopK": {},
                "spanU": [16.0, 40.0],
                "itemProbBp": 9800,
                "symbolIds": [clef],
            }
        )
        if s == 0:
            time_symbol = symbol("timeCommon", 64.0, 105.0, 24.0, 44.0)
            items.append(
                {
                    "item": {"type": "time", "beats": 4, "beatType": 4, "symbol": "common"},
                    "attrTopK": {},
                    "spanU": [64.0, 88.0],
                    "itemProbBp": 9800,
                    "symbolIds": [time_symbol],
                }
            )
        for local in range(2):
            m = 2 * s + local
            mid = f"P1-m{m}"
            smid = f"{mid}-s1"
            mb = [80.0 + local * 380, ytop - 55, 380.0, 140.0]
            meid = add_evidence(mid, "measure", mb)
            evidence["extensions"]["measureBoxes"].append(
                {"staffMeasureId": smid, "box": copy.deepcopy(evidence["evidence"][-1]["box"])}
            )
            conf(mid, "measure")
            measure = {
                "measureId": mid,
                "partId": "P1",
                "index": m,
                "number": str(m + 1),
                "implicit": False,
                "pageIndex": 0,
                "systemId": system,
                "capacity": frac(4),
                "staffMeasures": [],
                "harmonies": [],
                "directions": [],
            }
            events, onset = [], Fraction(0)
            bar_u = 100.0 if m == 0 else float(local * 608)
            bar = symbol("barline", bar_u, 96.0, 2.0, 64.0)
            items.append(
                {
                    "item": {"type": "bar", "style": "repeatStart" if m == 0 else "regular"},
                    "attrTopK": {},
                    "spanU": [bar_u, bar_u + 2.0],
                    "itemProbBp": 9800,
                    "symbolIds": [bar],
                }
            )
            for j, (kind, dur, dots, n, d, step, pos) in enumerate(plans[m]):
                pos -= 4  # G2 bottom line is E4 (CONTRACTS 5.1).
                u = float(local * 608 + 120 + j * 100)
                v = float(160 - 8 * pos)
                eid = f"{smid}-v1-e{j}"
                flagged = m == 3 and j == 0
                bp = 7200 if flagged else 9700
                cls = (
                    "restQuarter"
                    if kind == "rest"
                    else "noteheadSlash"
                    if kind == "rhythm"
                    else "noteheadWhole"
                    if dur == "whole"
                    else "noteheadHollow"
                    if dur == "half"
                    else "noteheadFilled"
                )
                head = symbol(
                    cls,
                    u,
                    v,
                    attrs={
                        "dotsTopK": [[dots, 9700]],
                        "posTopK": [[pos, 9600], [pos + 1, 400]],
                        "voiceTopK": [[1, 9700], [2, 300]],
                    },
                )
                ids = [head]
                if dur != "whole" and kind != "rest":
                    stem = symbol(
                        "stem",
                        u + 14,
                        v - 42,
                        2.0,
                        48.0,
                        {
                            "stemDir": [["up", 9800]],
                            "beamCountTopK": [[1 if dur == "eighth" else 0, 9700]],
                        },
                    )
                    ids.append(stem)
                    graph["relations"].append(
                        {"kind": "stemOf", "from": stem, "to": head, "probBp": 9700}
                    )
                    if dur == "eighth":
                        beam = symbol("beam", u + 14, v - 42, 25.0, 5.0)
                        ids.append(beam)
                        graph["relations"].append(
                            {
                                "kind": "beamOf",
                                "from": beam,
                                "to": stem,
                                "probBp": 7200 if flagged else 9600,
                            }
                        )
                if dots:
                    dot = symbol("augDot", u + 22, v + 4, 4.0, 4.0)
                    ids.append(dot)
                    graph["relations"].append(
                        {"kind": "dotOf", "from": dot, "to": head, "probBp": 9650}
                    )
                tie_start, tie_stop = m == 1 and j == 2, m == 2 and j == 0
                if tie_start or tie_stop:
                    curve = symbol("curve", u, v + 20, 30.0, 8.0)
                    ids.append(curve)
                    graph["relations"].append(
                        {
                            "kind": "tieFrom" if tie_start else "tieTo",
                            "from": curve,
                            "to": head,
                            "probBp": 9300,
                        }
                    )
                event_ev = add_evidence(
                    eid, "symbol", [80 + u * 0.625, ytop + (v - 138) * 0.625, 28.0, 45.0], bp
                )
                event = {
                    "eventId": eid,
                    "kind": kind,
                    "onset": frac(onset),
                    "duration": frac(n, d),
                    "notated": {"type": dur, "dots": dots},
                    "chordWithPrev": False,
                    "pos": pos,
                    "tie": {"start": tie_start, "stop": tie_stop},
                    "slur": {"start": False, "stop": False},
                    "fermata": m == 5,
                    "measureRest": False,
                    "lyrics": [],
                    "evidenceIds": [event_ev],
                    "confidenceBp": bp,
                    "flags": ["LOW_CONFIDENCE_DURATION"] if flagged else [],
                }
                if step:
                    event["pitch"] = {"step": step, "alter": 0, "octave": 4}
                    if m == 4 and j == 3:
                        event["pitch"]["alter"] = 1
                        event["accidentalVisible"] = "sharp"
                        acc = symbol("accSharp", u - 18, v - 10, 12.0, 30.0)
                        ids.append(acc)
                        graph["relations"].append(
                            {"kind": "accidentalOf", "from": acc, "to": head, "probBp": 9550}
                        )
                if kind == "note" and not tie_stop and m < 4:
                    word = next(lyric_words, None)
                    if word:
                        tid = text_item(
                            word,
                            "lyric",
                            staff,
                            80 + u * 0.625,
                            ytop + 75,
                            verse=1,
                            syllables=[
                                {
                                    "text": word,
                                    "box": [80 + u * 0.625, ytop + 75, 16.0, 16.0],
                                    "hyphenAfter": False,
                                    "extender": False,
                                }
                            ],
                        )
                        event["lyrics"] = [
                            {
                                "verse": 1,
                                "text": word,
                                "syllabic": "single",
                                "extend": False,
                                "textId": tid,
                            }
                        ]
                        conf(f"{eid}-l1", "lyric")
                events.append(event)
                conf(eid, "event", bp)
                li = {
                    "type": "rest" if kind == "rest" else "note",
                    "dur": dur,
                    "dots": dots,
                    "v": 1,
                    "pos": pos,
                }
                if kind != "rest":
                    li["head"] = "slash" if kind == "rhythm" else "normal"
                    if m == 4 and j == 3:
                        li["acc"] = "sharp"
                    if tie_start or tie_stop:
                        li["tie"] = "start" if tie_start else "stop"
                items.append(
                    {
                        "item": li,
                        "attrTopK": {"dur": [[dur, bp], ["16th", 2600]]} if flagged else {},
                        "spanU": [u, u + 40],
                        "itemProbBp": bp,
                        "symbolIds": ids,
                    }
                )
                onset += Fraction(n, d)
            sm = {
                "staffMeasureId": smid,
                "staffId": staff,
                "voices": [{"voice": 1, "events": events}],
                "evidenceIds": [meid],
                "confidenceBp": 7200 if m == 3 else 9700,
                "status": "flagged" if m == 3 else "ok",
                "barlineRight": {"style": "repeatEnd" if m == 5 else "regular"},
            }
            if local == 0:
                sm["clef"] = {"sign": "G2"}
                conf(f"{smid}-clef", "clef", parentId=mid, path="attributes[1]/clef[1]")
            if m == 0:
                sm.update(
                    key={"fifths": 0},
                    time={"beats": 4, "beatType": 4},
                    barlineLeft={"style": "repeatStart"},
                )
                conf(f"{smid}-key", "key", parentId=mid, path="attributes[1]/key[1]")
                conf(f"{smid}-time", "time", parentId=mid, path="attributes[1]/time[1]")
                measure["directions"].append(
                    {
                        "directionId": f"{mid}-d0",
                        "onset": frac(0),
                        "kind": "tempo",
                        "value": {"text": "Moderato"},
                        "textId": tempo_id,
                        "confidenceBp": 9700,
                    }
                )
                add_evidence(f"{mid}-d0", "symbol", [80.0, 150.0, 96.0, 16.0])
                conf(f"{mid}-d0", "flow")
            bar_index = 0
            for side in ("barlineLeft", "barlineRight"):
                if side in sm:
                    bar_index += 1
                    conf(f"{smid}-{side}", "flow", parentId=mid, path=f"barline[{bar_index}]")
                    if sm[side]["style"] in ("repeatStart", "repeatEnd"):
                        conf(
                            f"{smid}-{side}-repeat",
                            "flow",
                            parentId=mid,
                            path=f"barline[{bar_index}]/repeat[1]",
                        )
            normalized, root, ckind = chord_data[m]
            chord = {
                "normalized": normalized,
                "kind": ckind,
                "kindText": "m7" if m == 1 else "7" if m == 3 else "",
                "degrees": [],
            }
            if root:
                chord["root"] = {"step": root, "alter": 0}
            if m == 5:
                chord["bass"] = {"step": "E", "alter": 0}
            tid = text_item(normalized, "chord", staff, 155.0 + 380 * local, ytop - 42, chord=chord)
            hid = f"{mid}-h0"
            hev = add_evidence(
                hid,
                "symbol",
                [155.0 + 380 * local, ytop - 42, float(max(16, len(normalized) * 12)), 16.0],
            )
            measure["harmonies"] = [
                {k: v for k, v in chord.items() if k != "normalized"}
                | {
                    "harmonyId": hid,
                    "staffInPart": 1,
                    "onset": frac(0),
                    "sourceText": normalized,
                    "textId": tid,
                    "confidenceBp": 9700,
                    "evidenceIds": [hev],
                }
            ]
            conf(hid, "harmony")
            measure["staffMeasures"] = [sm]
            score["measures"].append(measure)
        lastbar = symbol("barline", 1214.0, 96.0, 2.0, 64.0)
        items.append(
            {
                "item": {"type": "bar", "style": "repeatEnd" if s == 2 else "regular"},
                "attrTopK": {},
                "spanU": [1214.0, 1216.0],
                "itemProbBp": 9800,
                "symbolIds": [lastbar],
            }
        )
        graph["symbols"].sort(key=lambda x: (x["centerStrip"][0], x["centerStrip"][1]))
        mapping = {obj["symbolId"]: f"{staff}-s{i}" for i, obj in enumerate(graph["symbols"])}
        for obj in graph["symbols"]:
            obj["symbolId"] = mapping[obj["symbolId"]]
        for r in graph["relations"]:
            r["from"] = mapping[r["from"]]
            r["to"] = mapping[r["to"]]
        for item in items:
            item["symbolIds"] = [mapping[i] for i in item["symbolIds"]]
        graph["rejectedCandidates"] = [
            {
                "symbolId": f"{staff}-s{len(graph['symbols'])}",
                "sources": ["cc"],
                "classTopK": [["reject", 6500], ["noteheadFilled", 3500]],
                "boxStrip": [1200.0, 195.0, 10.0, 8.0],
            }
        ]
        items.sort(key=lambda item: item["spanU"][0])
        lattice = {
            "schema": IR,
            "id": staff,
            "stripId": staff,
            "producer": producer,
            "hypotheses": [{"rank": 0, "logProbMicro": -210000, "items": items}],
        }
        if s == 1:
            alt = copy.deepcopy(lattice["hypotheses"][0])
            alt["rank"] = 1
            alt["logProbMicro"] = -920000
            next(i for i in alt["items"] if i["attrTopK"])["item"]["dur"] = "16th"
            lattice["hypotheses"].append(alt)
        graphs.append(graph)
        lattices.append(lattice)
    # Resolve deterministic page text IDs by reading order.
    texts["items"].sort(key=lambda x: (x["boxProcessed"][1], x["boxProcessed"][0]))
    remap = {t["textId"]: f"pg0-t{i}" for i, t in enumerate(texts["items"])}

    def rewrite(obj):
        if isinstance(obj, dict):
            return {k: (remap[v] if k == "textId" else rewrite(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [rewrite(v) for v in obj]
        return obj

    texts, score = rewrite(texts), rewrite(score)
    target = "P1-m3-s1-v1-e0"
    hints = {
        "schema": "clavis-hints-0.1",
        "thresholdArtifactDigest": None,
        "hints": [
            {
                "hintId": f"hint-{target}-LOW_CONFIDENCE_DURATION",
                "target": {"kind": "event", "id": target},
                "reasonCode": "LOW_CONFIDENCE_DURATION",
                "severity": "warning",
                "confidenceBp": 7200,
                "alternatives": [
                    {
                        "alternativeId": "a0",
                        "labelKo": "16분음표 대안 검토",
                        "patch": {"kind": "duration", "duration": frac(1, 4)},
                        "confidenceBp": 2600,
                    }
                ],
                "evidenceIds": [f"ev-{target}-symbol"],
            }
        ],
    }
    all_events = [
        e
        for m in score["measures"]
        for sm in m["staffMeasures"]
        for v in sm["voices"]
        for e in v["events"]
    ]
    report = {
        "schema": "clavis-report-0.1",
        "engine": {
            "name": "Clavis mock",
            "version": "0.1",
            "gitSha": "0" * 40,
            "buildDigest": digest("mock build"),
        },
        "models": [],
        "configDigest": digest("mock config"),
        "input": {
            "pages": [
                {
                    "pageIndex": 0,
                    "bytesSha256": frame["imageDigest"],
                    "width": 880,
                    "height": 1180,
                    "sourceKind": "image",
                }
            ]
        },
        "quality": [quality],
        "status": "complete",
        "counts": {
            "systems": 3,
            "staves": 3,
            "measures": 6,
            "events": len(all_events),
            "harmonies": 6,
            "lyrics": sum(len(e["lyrics"]) for e in all_events),
            "hintsBySeverity": {"blocking": 0, "warning": 1, "info": 0},
        },
        "diagnostics": [{"code": "MOCK_FIXTURE", "severity": "info"}],
    }
    runtime = {
        "schema": "clavis-runtime-0.1",
        "threads": 1,
        "elapsedMs": 0,
        "cpuMs": 0,
        "peakRssBytes": 0,
        "stages": [
            {"stageId": "mock", "threads": 1, "elapsedMs": 0, "cpuMs": 0, "peakRssBytes": 0}
        ],
        "platform": {"os": "mock", "pythonVersion": "3.12"},
    }
    return [
        ("PageInput", "page-input", page),
        ("QualityReport", "quality", quality),
        ("PageLayout", "layout", layout),
        *[("SymbolGraph", f"symbols-{s}", v) for s, v in enumerate(graphs)],
        *[("StaffLattice", f"lattice-{s}", v) for s, v in enumerate(lattices)],
        ("TextIR", "text", texts),
        ("ScoreIR", "score", score),
        ("EvidenceBundle", "evidence", evidence),
        ("ReviewHints", "hints", hints),
        ("ElementConfidence", "confidence", confidences),
        ("Report", "report", report),
        ("RuntimeReport", "runtime", runtime),
    ]


def build():
    ROOT.mkdir(parents=True, exist_ok=True)
    models = {m.__name__: m for m in DOCUMENT_MODELS}
    manifest = []
    for name, stem, data in author():
        model = models[name].model_validate(data)
        path = ROOT / "valid" / f"{stem}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(canonical_json(model))
        manifest.append({"model": name, "path": f"valid/{stem}.json"})
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    build()
