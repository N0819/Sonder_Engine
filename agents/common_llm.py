"""The model-call seam and JSON recovery: _agent_json (the strict
validated-JSON path), jparse and the miscounted-closer mender.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import json
import re
from llm.llm_quality import complete_validated_json

def _agent_json(
    role,
    step_key,
    system,
    payload,
    *,
    temperature=None,
    max_tokens=None,   # the configured ceiling; see complete_validated_json
    sampler=None,
    response_format=None,  # this call's own; see providers._role_json_mode
    reasoning_effort=None,  # this call's own; None leaves the role's setting
    **tool_closing,
):
    """The STRICT validated-JSON path every state-mutating pipeline stage
    must use for its primary LLM call. complete_validated_json parses
    strictly, runs schemas.validate_llm_output_strict (Pydantic schema +
    semantic checks for step_key), attempts one temperature-0 repair, then
    walks the role's remaining model candidates -- and RAISES if nothing
    validates, so a hopelessly malformed output surfaces as a normal
    rerunnable step error instead of committing junk. The follow-up
    schemas.validate_llm_output calls some stages make on this function's
    return value are warning-only re-normalization of already-validated
    output, NOT the guard -- do not downgrade a stage to jparse or a bare
    chat_complete for output that reaches commit.py.

    `tool_closing` (`history`, `tools`, `folded_payload`, `first_raw`,
    `first_started`, `rung_system`) is a character's closing round after it
    looked things up (`agents/character_tools.py`):
    passed on only when a tool loop ran, so every other caller -- and every
    test stub of this seam -- sees exactly the call it always did. `prefix`
    is the encoder's: its request as a cached prefix and what follows it
    (`complete_validated_json`), passed on only where the route caches one.
    """
    return complete_validated_json(
        role=role,
        step_key=step_key,
        system=system,
        payload=payload,
        temperature=temperature,
        max_tokens=max_tokens,
        sampler=sampler,
        repair_attempts=1,
        response_format=response_format,
        reasoning_effort=reasoning_effort,
        **{k: v for k, v in tool_closing.items()
           if k in ("history", "tools", "folded_payload", "first_raw", "first_started",
                    "rung_system", "prefix") and v is not None},
    )

#: How many single-bracket edits `_mend_closers` may make to one answer.
#: Each observed answer needed one; a long plan might miscount twice.
MEND_CLOSER_EDITS = 3


def _closer_runs(text, upto):
    """`(start, end)` of each run of closing brackets outside strings up to
    `upto`, whitespace inside a run included."""
    runs, inside, esc, start = [], False, False, None
    for i, ch in enumerate(text[:upto + 1]):
        if inside:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                inside = False
            continue
        if ch == '"':
            inside = True
        if ch in "]}":
            start = i if start is None else start
        elif start is not None and not ch.isspace():
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, min(len(text), upto + 1)))
    return runs


def _mend_closers(text, edits=MEND_CLOSER_EDITS):
    """`text` parsed after mending up to `edits` miscounted closing brackets,
    or None.

    A MODEL MISCOUNTS ITS CLOSERS IN A DEEP ANSWER. Measured 2026-10-11 on
    deepseek v4.1 flash, the Writers' Room's model, answering without JSON
    mode -- which the provider layer turns off for the rest of a process once
    OpenRouter has twice held a JSON-mode answer past the first-token clock:
    two of three plans for five rooms closed a room one brace too many
    (`}}}}}], "reply"`) or never closed the calls list
    (`}}}}, "reply"`), and the Room read each as a step that said nothing,
    losing the plan with it. Its replay of the owner's chat 165 lost two such
    steps in its first reply, 13,051 and 9,843 characters of planned rooms.

    Where the parser stops, one bracket is deleted from, or one inserted
    into, the run of closers before it; the edit that parses is taken, and
    else the one that parses furthest, up to `edits` times. A run holds one
    place where a closer count can be wrong, so the mend reads the answer
    the model wrote rather than guessing at one."""
    for _ in range(edits + 1):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            pos = exc.pos
        runs = _closer_runs(text, pos)
        if not runs:
            return None
        start, end = runs[-1]
        furthest = None
        for k in range(start, end + 1):
            candidates = [text[:k] + c + text[k:] for c in "]}"]
            if k < end and text[k] in "]}":
                candidates.append(text[:k] + text[k + 1:])
            for candidate in candidates:
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as exc:
                    if exc.pos > pos + 1 and (furthest is None or exc.pos > furthest[0]):
                        furthest = (exc.pos, candidate)
        if furthest is None:
            return None
        text = furthest[1]
    return None


def jparse(text, fallback_key="text", required=False):
    t = re.sub(r"^```[a-zA-Z]*\n?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    try:
        repaired = re.sub(r',\s*([}\]])', r'\1', t)
        return json.loads(repaired)
    except Exception:
        pass
    # The FIRST complete object, before the greedy span below. A model that
    # answers and then keeps talking has still answered: observed live, a
    # narrator emitted valid JSON, then "That is my final answer... I am done.
    # Now I will output the JSON as the final message.", then the whole object
    # again, and again. `\{.*\}` is greedy, so it spanned from the first brace
    # to the LAST one across every repetition -- not valid JSON -- and this
    # function fell through to `{fallback_key: <the entire mess>}`, discarding
    # a complete and correct answer the model had already given.
    #
    # `llm_quality.strict_json_parse` has carried a string-aware brace scanner
    # for exactly this since before the loose path existed; reusing it rather
    # than writing a second one keeps the two from disagreeing about what
    # counts as the answer.
    try:
        from llm.llm_quality import strict_json_parse

        first = strict_json_parse(t)
        if isinstance(first, dict):
            return first
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        block = m.group(0)
        try:
            return json.loads(block)
        except Exception:
            pass
        try:
            repaired = re.sub(r',\s*([}\]])', r'\1', block)
            return json.loads(repaired)
        except Exception:
            pass
    # A MISCOUNTED CLOSING BRACKET (`_mend_closers`): the last rung before an
    # answer the model gave is given up as prose
    for candidate in (t, m.group(0) if m else None):
        try:
            mended = _mend_closers(candidate) if candidate else None
        except Exception:
            mended = None
        if isinstance(mended, dict):
            return mended
    if required:
        raise RuntimeError(
            f"LLM returned unparseable JSON (first 200 chars): {(text or '')[:200]}")
    return {fallback_key: text}
