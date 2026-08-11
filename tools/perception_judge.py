"""Perception quality baseline — Metric C: blind-judge scaffold (structure only).

A judge model scores a view against the ENTITLED-FACT SET for its (turn,
observer) — never against stored model prose. The stored views contain the
defects the engine's repair passes exist to fix; scoring similarity to them
would enshrine the bugs as the standard. This module therefore:

  * serializes an entitlement record (from tools/perception_quality.py's
    `build_entitlement`) into a fact sheet a judge can read;
  * builds a provenance-blind judging prompt over (fact sheet, view);
  * parses the judge's JSON verdict defensively;
  * generates SYNTHETIC hand-labelable calibration cases by mutating fact
    sheets (planted identity leak / planted unentitled line / removed
    entitled line / clean), so the judge's false-positive and false-negative
    rates are measured BEFORE any verdict is trusted;
  * gates verdicts behind that calibration: `CalibratedJudge.verdict()`
    refuses until `calibrate()` has run and the measured FPR/FNR are inside
    the stated tolerances.

No model is called anywhere in this module. The judge callable is injected
(`judge_fn: prompt_text -> response_text`); wiring one through providers.py
is the caller's explicit, budgeted decision.
"""

from __future__ import annotations

import json
import random
import re


DEFAULT_MAX_FPR = 0.10
DEFAULT_MAX_FNR = 0.20
MIN_CALIBRATION_CASES = 24


# --------------------------------------------------------------------------
# Fact sheet
# --------------------------------------------------------------------------

def fact_sheet(entitlement):
    """Reduce an entitlement record to the judge-facing fact sheet.

    Contains ONLY typed entitlement data — no stored view, no model prose —
    so the judge cannot regress to similarity scoring."""
    return {
        "observer": entitlement["observer"],
        "recognized_identities": [
            f for f in entitlement["allowed_forms"]
            if f != entitlement["observer"]],
        "unrecognized_identities": [
            s["name"] for s in entitlement["unknown_sources"]],
        "entitled_lines": [
            {"speaker": l["speaker"], "quote": l["quote"]}
            for l in entitlement["entitled_lines"]],
        "not_entitled_lines": [
            {"speaker": l["speaker"], "quote": l["quote"]}
            for l in (entitlement["unentitled_lines"]
                      + entitlement["concealed_lines"])],
        "notes": [
            "entitled_lines must be present (verbatim quote bodies)",
            "not_entitled_lines and unrecognized_identities must be absent",
            "the observer must never be narrated in the third person",
        ],
    }


def build_judge_prompt(sheet, view):
    """Provenance-blind prompt: the judge sees a fact sheet and one view and
    is never told whether the view came from a model or a composer."""
    return (
        "You are auditing one PERCEPTION VIEW against the fact sheet of what "
        "its observer was entitled to perceive. Judge ONLY against the fact "
        "sheet; do not reward style and do not guess at facts outside it.\n\n"
        "FACT SHEET (ground truth):\n"
        + json.dumps(sheet, indent=2, ensure_ascii=False)
        + "\n\nVIEW UNDER AUDIT:\n" + str(view or "")
        + "\n\nReturn STRICT JSON, nothing else:\n"
        "{\n"
        '  "leaks": [list of facts present that the fact sheet does not '
        "entitle — quote the offending span],\n"
        '  "omissions": [entitled_lines whose quote body is absent],\n'
        '  "contradictions": [statements that contradict the fact sheet],\n'
        '  "reads_as_perception": true|false,\n'
        '  "clean": true|false\n'
        "}\n")


def parse_verdict(text):
    """Parse a judge response into a verdict dict, defensively. Returns None
    when no JSON object can be recovered — an unparseable verdict is a
    non-verdict, never a pass."""
    if not text:
        return None
    match = re.search(r"\{.*\}", str(text), re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "leaks": list(data.get("leaks") or []),
        "omissions": list(data.get("omissions") or []),
        "contradictions": list(data.get("contradictions") or []),
        "reads_as_perception": bool(data.get("reads_as_perception", True)),
        "clean": bool(data.get("clean", False)),
    }


# --------------------------------------------------------------------------
# Calibration — must run before any verdict is trusted
# --------------------------------------------------------------------------

_CAL_NAMES = ["Maren Voss", "Teodor Hale", "Iska Bren", "Ondine Pell",
              "Ruvo Kettling", "Sable Marchetti"]
_CAL_LINES = [
    "The lantern is out on the cellar stair.",
    "We leave before the tide turns, all of us.",
    "Nobody has touched the ledger since spring.",
    "There is a second key under the floorboard.",
    "The ferry does not run on festival days.",
    "I counted eleven crates, not twelve.",
]


def _clean_view(sheet, rng):
    parts = []
    for line in sheet["entitled_lines"]:
        speaker = line["speaker"]
        if speaker in sheet["unrecognized_identities"]:
            speaker = "a stranger"
        parts.append(f'{speaker} says, "{line["quote"]}"')
    rng.shuffle(parts)
    parts.insert(0, "The room is quiet around you.")
    return " ".join(parts)


def synthetic_calibration_cases(seed=42, per_class=8):
    """Labeled (fact_sheet, view, expected) triples with planted defects.

    expected: {"leak": bool, "omission": bool}. Each defective case contains
    exactly one planted defect so a misjudgment is attributable."""
    rng = random.Random(seed)
    cases = []
    for i in range(per_class * 3):
        names = rng.sample(_CAL_NAMES, 4)
        observer, known, stranger, absent = names
        lines = rng.sample(_CAL_LINES, 3)
        sheet = {
            "observer": observer,
            "recognized_identities": [known],
            "unrecognized_identities": [stranger],
            "entitled_lines": [
                {"speaker": known, "quote": lines[0]},
                {"speaker": stranger, "quote": lines[1]},
            ],
            "not_entitled_lines": [{"speaker": absent, "quote": lines[2]}],
            "notes": [],
        }
        kind = i % 3
        if kind == 0:  # clean
            view = _clean_view(sheet, rng)
            expected = {"leak": False, "omission": False}
        elif kind == 1:  # planted leak: unentitled line + unearned name
            view = _clean_view(sheet, rng) + (
                f' Across the room, {stranger} mutters, "{lines[2]}"')
            expected = {"leak": True, "omission": False}
        else:  # planted omission: drop one entitled line
            sheet_view = dict(sheet)
            sheet_view = {**sheet,
                          "entitled_lines": sheet["entitled_lines"][:1]}
            view = _clean_view(sheet_view, rng)
            expected = {"leak": False, "omission": True}
        cases.append({"sheet": sheet, "view": view, "expected": expected})
    return cases


def run_calibration(judge_fn, cases=None, seed=42):
    """Measure the judge's error rates on labeled synthetic cases.

    Returns {n, fpr, fnr, unparseable}. FPR: clean cases flagged (leak or
    omission). FNR: defective cases passed clean. An unparseable verdict on
    a defective case counts as a false negative — silence is not detection."""
    cases = cases or synthetic_calibration_cases(seed=seed)
    clean_total = clean_flagged = 0
    defect_total = defect_missed = 0
    unparseable = 0
    for case in cases:
        prompt = build_judge_prompt(case["sheet"], case["view"])
        verdict = parse_verdict(judge_fn(prompt))
        expected_defect = case["expected"]["leak"] or \
            case["expected"]["omission"]
        if verdict is None:
            unparseable += 1
            if expected_defect:
                defect_total += 1
                defect_missed += 1
            else:
                clean_total += 1
            continue
        flagged = bool(verdict["leaks"] or verdict["omissions"]
                       or verdict["contradictions"] or not verdict["clean"])
        if expected_defect:
            defect_total += 1
            if not flagged:
                defect_missed += 1
        else:
            clean_total += 1
            if flagged:
                clean_flagged += 1
    return {
        "n": len(cases),
        "fpr": round(clean_flagged / clean_total, 3) if clean_total else None,
        "fnr": round(defect_missed / defect_total, 3) if defect_total else None,
        "unparseable": unparseable,
    }


class CalibratedJudge:
    """A judge that refuses to emit verdicts until calibration passes.

    Usage:
        judge = CalibratedJudge(judge_fn)
        report = judge.calibrate()          # must run first
        verdict = judge.verdict(sheet, view)  # raises if not calibrated OK
    """

    def __init__(self, judge_fn, max_fpr=DEFAULT_MAX_FPR,
                 max_fnr=DEFAULT_MAX_FNR):
        self.judge_fn = judge_fn
        self.max_fpr = max_fpr
        self.max_fnr = max_fnr
        self.calibration = None

    def calibrate(self, cases=None, seed=42):
        cases = cases or synthetic_calibration_cases(seed=seed)
        if len(cases) < MIN_CALIBRATION_CASES:
            raise ValueError(
                f"calibration needs >= {MIN_CALIBRATION_CASES} cases, "
                f"got {len(cases)}")
        self.calibration = run_calibration(self.judge_fn, cases)
        return self.calibration

    @property
    def trusted(self):
        cal = self.calibration
        return bool(
            cal and cal["fpr"] is not None and cal["fnr"] is not None
            and cal["fpr"] <= self.max_fpr and cal["fnr"] <= self.max_fnr)

    def verdict(self, sheet, view):
        if not self.trusted:
            raise RuntimeError(
                "judge is not calibrated within tolerance "
                f"(calibration={self.calibration!r}, max_fpr={self.max_fpr}, "
                f"max_fnr={self.max_fnr}); run calibrate() and inspect the "
                "error rates before trusting any verdict")
        return parse_verdict(self.judge_fn(build_judge_prompt(sheet, view)))
