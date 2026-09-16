"""Execute the inspector's real lens assignment and perception rendering in Node."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

CHAT_JS = Path(__file__).resolve().parents[1] / "static/js/chat.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

HARNESS = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const request = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = fs.readFileSync(process.argv[1], 'utf8');
const context = vm.createContext({
  t: text => (request.translations || {})[text] || text
});
const start = source.indexOf('function perceiverViews(');
const end = source.indexOf('// What the deterministic layer did', start);
if (start < 0 || end < 0) throw new Error('Pipeline lens functions missing');
vm.runInContext(source.slice(start, end), context);

function freeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}
const content = freeze(JSON.parse(request.raw));
const variant = freeze({content: request.raw, perception_packets: request.packets});
const packetBefore = JSON.stringify(request.packets);
let rendered = '';
const pre = {};
Object.defineProperty(pre, 'textContent', {set(value) { rendered = value; }});
Object.defineProperty(pre, 'innerHTML', {set() { throw new Error('Perception must render as text'); }});
Object.assign(context, {content, variant, pre, lens: request.lens,
  lenses: context.stepLenses(content), p: {perceivers: request.names || {}}});
// Execute the actual drawer branch, including sidecar forwarding and its raw
// JSON alternative, rather than reconstructing that wiring in the test.
const assignment = source.indexOf('pre.textContent = lens === ""');
const assignmentEnd = source.indexOf(';', assignment);
if (assignment < 0 || assignmentEnd < 0) throw new Error('Lens assignment missing');
vm.runInContext(source.slice(assignment, assignmentEnd + 1), context);
process.stdout.write(JSON.stringify({rendered,
  rawAfter: variant.content, prettyRaw: JSON.stringify(content, null, 2),
  packetsUnchanged: JSON.stringify(request.packets) === packetBefore}));
"""


def _render(content, packets=None, *, lens="a", names=None, translations=None):
    raw = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    result = subprocess.run(
        ["node", "-e", HARNESS, str(CHAT_JS)],
        input=json.dumps({"raw": raw, "packets": packets, "lens": lens,
                          "names": names or {"a": "Mira", "b": "Bram"},
                          "translations": translations or {}}),
        capture_output=True, text=True, check=True, timeout=10,
    )
    output = json.loads(result.stdout)
    assert output["rawAfter"] == raw
    assert output["packetsUnchanged"]
    return output


def _row(text, **metadata):
    return {"observed": {"text": text}, **metadata}


def _packet(*, events=(), changes=(), state=(), context=()):
    packet = {"events": list(events), "changes_noticed": list(changes),
              "current_state": list(state)}
    if context:
        packet["unstructured_context"] = list(context)
    return packet


def test_packet_sections_replace_the_paragraph_and_keep_useful_evidence_metadata():
    content = {"views": {"a": "Legacy combined paragraph."}, "observations": {
        "a": [_row("Legacy duplicated observation.", channel="sight")]}}
    packet = _packet(
        events=[_row('"Wait here."', order=1, actor="Bram", kind="speech",
                     channel="hearing", fidelity="fragment", ambiguity=0.55,
                     directed_at_self=True)],
        changes=[_row("Bram's sleeve is now wet.", actor="Bram", channel="sight")],
        state=[_row("A brass key rests on the table.", actor="the table", channel="sight")],
        context=[_row("Older admitted context.", channel="mixed")],
    )
    rendered = _render(content, {"a": packet})["rendered"]

    assert rendered.startswith("Mira (a)\n")
    sections = ["Events (1)", "Changes noticed (1)", "Current state (1)",
                "Additional context (1)"]
    assert [rendered.index(title) for title in sections] == sorted(
        rendered.index(title) for title in sections)
    assert '1. [Bram · speech · hearing · fragment · uncertainty: 0.55 · ← at them] "Wait here."' in rendered
    for text in ("Bram's sleeve is now wet.", "A brass key rests on the table.",
                 "Older admitted context."):
        assert rendered.count(text) == 1
    assert "Legacy" not in rendered


def test_repeated_events_keep_delivery_order_and_are_not_merged_or_resorted():
    packet = _packet(events=[
        _row("A bell rings.", order=7, actor="the bell", channel="hearing"),
        _row("Bram shuts the door.", order=2, actor="Bram", channel="sight"),
        _row("A bell rings.", order=9, actor="the bell", channel="hearing"),
    ])
    rendered = _render({"views": {"a": "Old prose"}}, {"a": packet})["rendered"]

    assert "Events (3)" in rendered
    assert rendered.count("A bell rings.") == 2
    assert rendered.index("7.") < rendered.index("2.") < rendered.index("9.")
    assert "Changes noticed (0)" in rendered and "Current state (0)" in rendered
    assert "Additional context" not in rendered


def test_section_labels_are_translated_before_joining_but_observer_words_are_untouched():
    packet = _packet(
        events=[_row('"Wait here."', actor="Bram", channel="hearing",
                     ambiguity=0.55, directed_at_self=True)],
        context=[_row("Older admitted context.")],
    )
    translations = {"Events": "出来事", "Changes noticed": "気づいた変化",
                    "Current state": "現在の状態", "Additional context": "追加の文脈",
                    "uncertainty: 0.55": "不確実さ: 0.55", "← at them": "← この人物へ",
                    "Bram": "Do not translate observer labels",
                    '"Wait here."': "Do not translate observed text"}
    rendered = _render({"views": {"a": "Old view"}}, {"a": packet},
                       translations=translations)["rendered"]

    for text in ("出来事 (1)", "気づいた変化 (0)", "現在の状態 (0)",
                 "追加の文脈 (1)", "不確実さ: 0.55", "← この人物へ"):
        assert text in rendered
    assert 'Bram · hearing' in rendered and '"Wait here."' in rendered
    assert "Do not translate" not in rendered


@pytest.mark.parametrize("lens,expected,absent", [
    ("a", "Only Mira hears this.", "Only Bram sees this."),
    ("b", "Only Bram sees this.", "Only Mira hears this."),
])
def test_switching_observers_uses_only_the_selected_packet(lens, expected, absent):
    content = {"views": {"a": "Mira's old paragraph", "b": "Bram's old paragraph"}}
    packets = {
        "a": _packet(events=[_row("Only Mira hears this.", channel="hearing")]),
        "b": _packet(state=[_row("Only Bram sees this.", channel="sight")]),
    }
    rendered = _render(content, packets, lens=lens)["rendered"]
    assert expected in rendered
    assert absent not in rendered and "old paragraph" not in rendered


@pytest.mark.parametrize("packets", [None, {}, {"b": _packet()}, {"a": {"events": None}}])
def test_missing_or_unusable_selected_sidecar_keeps_the_legacy_view(packets):
    content = {"views": {"a": "Stored paragraph."}, "observations": {
        "a": [_row("An old observation.", channel="hearing", directed_at_self=True)]}}
    rendered = _render(content, packets)["rendered"]
    assert "Stored paragraph." in rendered
    assert "— observations (1) —" in rendered
    assert "[hearing] An old observation.  ← at them" in rendered
    assert "Events (" not in rendered


@pytest.mark.parametrize("view", [None, ""])
@pytest.mark.parametrize("packets", [None, {"a": _packet(events=[_row("Must not restore a view.")])}])
def test_null_or_empty_view_keeps_the_no_view_answer(view, packets):
    rendered = _render({"views": {"a": view}}, packets)["rendered"]
    assert "(no view — nothing registered, or this mind was not asked)" in rendered
    assert "Must not restore a view." not in rendered
    assert "Events (" not in rendered


def test_raw_json_lens_does_not_include_the_presentation_sidecar():
    content = {"views": {"a": "Original paragraph."}, "observations": {
        "a": [_row("Original observation.", channel="hearing")]}}
    packets = {"a": _packet(events=[_row("Presentation-only row.")])}
    result = _render(content, packets, lens="")

    assert result["rendered"] == result["prettyRaw"]
    assert "Original paragraph." in result["rendered"]
    assert "Presentation-only row." not in result["rendered"]
    assert "perception_packets" not in result["rendered"]


def test_other_lenses_ignore_perception_packets_and_markup_remains_literal_text():
    markup = '<img src=x onerror="unexpected()"> & "spoken words"'
    packet = _packet(events=[_row(markup, channel="hearing")])
    rendered = _render({"views": {"a": "Old paragraph."}}, {"a": packet})["rendered"]
    assert markup in rendered  # written through textContent, never innerHTML

    result = _render({"summary": "Other step's original summary."},
                     {"summary": packet}, lens="summary")
    assert result["rendered"] == "Other step's original summary."
