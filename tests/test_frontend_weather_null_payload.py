"""A null weather payload must not take the whole app down.

REPORTED BY THE OWNER, on every boot: `Could not load the app: can't access
property "precipitation_kind", weather is null` -- and, from the same defect,
"for some reason I have to double click stories now to enter them".

ONE BUG, TWO SYMPTOMS. `weatherFxApply` is written to tolerate a null payload
-- `WFX.weather = weather || null`, and `weatherFxVisible` opens with
`if (!weather) return false` -- and then read `weather.precipitation_kind`
unguarded two lines later. Three callers pass null on purpose:

    backdrops.js   weatherFxApply(null)   when the story is deselected
    backdrops.js   weatherFxApply(null)   when there is no chat at all  <- boot
    weather-fx.js  weatherFxApply((state && state.weather) || null)

THE DOUBLE CLICK IS THE SAME THROW. `renderChat()` calls
`backdropResetForRender()`, whose story-switch branch assigns
`BD.chatId = S.chatId` and THEN calls `weatherFxApply(null)`. On the first
click the throw aborts `renderChat` before it can draw the story; on the
second, `BD.chatId` already matches, the branch is skipped, nothing throws and
the story opens. The assignment landing before the throw is what made a crash
look like a click-count problem.

Arrived 2026-09-08 in `40c4f5ab` (wave 5, "weather as axes with a name"),
which added the axis read without a guard.

These tests EXECUTE the file under node rather than grepping it, so they fail
on the behaviour rather than on a phrase someone might reword. The frontend has
no bundler and no browser-test dependency, so node is optional and these skip
without it -- the same arrangement as `tests/test_character_card_sheet_carry.py`.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEATHER_FX = ROOT / "static/js/weather-fx.js"
BACKDROPS = ROOT / "static/js/backdrops.js"
CHAT = ROOT / "static/js/chat.js"
GUARD = "  if (!weather) {\n    weatherFxStop();\n    return;\n  }\n"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed"
)

_HARNESS = Path(__file__).resolve().parent / "_wfx_null_harness.js"


def _apply_null(source_text: str) -> dict:
    """Run `weatherFxApply(null)` against this source, under node.

    A FRESH TEMPORARY DIRECTORY PER CALL, and not a fixed filename in `tests/`.
    The first draft used fixed names and the suite runs in parallel, so the two
    tests below raced on one path: the positive control evaluated the GUARDED
    source its sibling had just written and reported no crash. A test that
    passes serially and lies under `-n auto` is worse than no test.
    """
    with tempfile.TemporaryDirectory(prefix="wfx-null-") as tmp:
        harness = Path(tmp) / "harness.js"
        subject = Path(tmp) / "subject.js"
        harness.write_text(HARNESS_JS, encoding="utf-8")
        subject.write_text(source_text, encoding="utf-8")
        run = subprocess.run(
            ["node", str(harness), str(subject)],
            capture_output=True, text=True, check=True,
        )
    return json.loads(run.stdout)


def test_the_defect_is_real_without_the_guard():
    """The positive control: prove the crash before proving the fix.

    The guard is removed from the shipped source and the same call made. This
    is the exact error the owner saw on every boot -- V8 words it "Cannot read
    properties of null", Firefox "can't access property ... weather is null".
    """
    text = WEATHER_FX.read_text(encoding="utf-8")
    assert GUARD in text, "the guard this test is about is missing"
    result = _apply_null(text.replace(GUARD, "", 1))
    assert result["loaded"], result
    assert result["threw"] and "precipitation_kind" in result["threw"], result


def test_a_null_payload_applies_without_throwing():
    """The fix: boot, and every story switch, pass null and must survive it."""
    result = _apply_null(WEATHER_FX.read_text(encoding="utf-8"))
    assert result["loaded"], result
    assert result["threw"] is None, result["threw"]
    assert result["applied"], result


def test_the_callers_that_pass_null_still_do():
    """Pinned so the guard is never deleted as unreachable. Two of these are
    the boot path: `backdrops.js` clears the sky when a story is deselected and
    again when there is no chat at all."""
    backdrops = BACKDROPS.read_text(encoding="utf-8")
    assert backdrops.count("weatherFxApply(null)") >= 2
    fx = WEATHER_FX.read_text(encoding="utf-8")
    assert "weatherFxApply((state && state.weather) || null)" in fx


def test_the_render_path_that_made_it_look_like_a_double_click():
    """`renderChat` -> `backdropResetForRender` -> the story-switch branch,
    which assigns `BD.chatId` BEFORE calling `weatherFxApply(null)`. That
    ordering is why the second click worked: the branch was already satisfied,
    so nothing threw the second time."""
    chat = CHAT.read_text(encoding="utf-8")
    assert "backdropResetForRender();" in chat
    backdrops = BACKDROPS.read_text(encoding="utf-8")
    branch = backdrops[backdrops.index("if (BD.chatId !== S.chatId) {"):]
    branch = branch[:branch.index("if (!S.chatId) {")]
    assert branch.index("BD.chatId = S.chatId;") < branch.index(
        "weatherFxApply(null)")


HARNESS_JS = _HARNESS.read_text(encoding="utf-8") if _HARNESS.exists() else ""
