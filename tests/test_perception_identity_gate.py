"""Regression tests for the identity-leak floor found during live play
(Dr. Moon / Hinami, two strangers meeting):

perception computed each perceiver's knows_identity correctly and used
_unknown_actor_label correctly in its OWN deterministic injection helpers
-- but the perception LLM's free-text view prose was never checked
against that gate. The payload handed the model the actor's canonical
name unconditionally, so a model (of any strength -- no prompt paragraph
even defined knows_identity) writing "You see Hinami..." for a stranger
walked straight past the gate, and the leaked name then fed the
character agent verbatim (agents/character.py perception.view) and
durable memory minting (commit.py).

Three sibling deterministic channels leaked the same way regardless of
model output: _inject_visible_actor pasted the raw appearance summary
(which routinely LEADS with the canonical name) into a stranger's view,
_unknown_actor_label built its descriptor from that same summary without
dropping the name tokens, and loops.py's deterministic_micro_perception
delivered NPC speech/actions under the canonical actor name with no
recognition check at all.

Fix: _scrub_unknown_identities (agents/common.py) is applied as the last
transform to every view in all three perception stages -- quoted spans
are preserved verbatim (a name legitimately spoken aloud this beat is
sensory signal; recognition still only flips at commit via
validated_introductions), everything outside quotes is scrubbed against
the observer's recognized set -- plus name-token stripping at the
appearance source and recognition gating in the loops.py and fallback
delivery paths.
"""

from __future__ import annotations

import json
import re
import time

from character_schema import default_character_data, default_persona_data
from pipeline_context import ChatData, PipelineContext, TurnData

HINAMI_APPEARANCE = (
    "Hinami, a fox-eared young woman with amber eyes and a white-tipped tail."
)

_QUOTE_RE = re.compile(r'["“][^"“”]+["”]')


def _outside_quotes(text):
    return _QUOTE_RE.sub("", str(text or ""))


def _name_outside_quotes(text, name="hinami"):
    return re.search(
        r"(?<!\w)" + re.escape(name) + r"(?!\w)",
        _outside_quotes(text), re.I,
    ) is not None


def _make_ctx(temp_db, known=None, extra_char=None):
    sheet = default_persona_data("Hinami")
    sheet["embodiment"]["visible"]["summary"] = HINAMI_APPEARANCE
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(sheet), "{}"),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Test", "", time.time(), persona_id),
    )

    def add_character(name):
        csheet = default_character_data(name)
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(csheet), "{}", time.time(),
             f"char_{name.lower().replace(' ', '_').replace('.', '')}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"),
        )
        return char_id

    moon_id = add_character("Dr. Moon")
    extra_id = add_character(extra_char) if extra_char else None

    positions = {"Hinami": "room1", "Dr. Moon": "room1"}
    if extra_char:
        positions[extra_char] = "room1"
    temp_db.wset(chat_id, "scene", {
        "location": "the lab", "time": "day",
        "rooms": {"room1": {"name": "Room 1", "adjacent": []}},
        "positions": positions,
        "entities": {}, "attire": {}, "overlays": {},
    })
    if known is not None:
        temp_db.wset(chat_id, "known", known)

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "step forward", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="step forward", created=time.time()),
        cast=cast, input="step forward",
    )
    ctx["_player_room"] = "room1"
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "flow": {"reactors": [moon_id], "resolution_flags": {}},
    }
    return ctx, moon_id, extra_id


def _stub_views(monkeypatch, views_by_id):
    import agents.perception as perception

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        views = {}
        for p in payload["perceivers"]:
            pid = str(p["id"])
            views[pid] = views_by_id.get(pid, f"You are in {p['room_name']}.")
        if "player" in views_by_id and not any(
            str(p["id"]) == "player" for p in payload["perceivers"]
        ):
            views["player"] = views_by_id["player"]
        return {"views": views}

    monkeypatch.setattr(perception, "_agent_json", fake_agent_json)


ADVERSARIAL = "You see Hinami. Hinami steps forward and Hinami's tail sways."


def test_stranger_view_is_scrubbed_of_canonical_name(temp_db, monkeypatch):
    """The canonical fixture: Dr. Moon has never met Hinami, the model
    writes her name into the view prose anyway -- the floor must catch it."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})
    _stub_views(monkeypatch, {str(moon_id): ADVERSARIAL})

    result = perception.perception_act(ctx, nonce=0)
    view = result["views"][str(moon_id)]

    assert not _name_outside_quotes(view), (
        f"canonical name leaked into a stranger's view: {view!r}"
    )
    assert "fox-eared" in view, (
        "the stranger should get a descriptor label derived from appearance"
    )


def test_unknown_actor_label_drops_name_tokens_from_appearance():
    """An appearance summary that LEADS with the canonical name must not
    smuggle it into the unknown-actor descriptor itself."""
    from agents.common import _unknown_actor_label

    label = _unknown_actor_label("Hinami", HINAMI_APPEARANCE)
    assert "hinami" not in label.lower()
    assert "fox-eared" in label


def test_injected_appearance_is_scrubbed_of_name(temp_db, monkeypatch):
    """_inject_visible_actor pastes the appearance summary into a stranger's
    view -- the deterministic path itself must not print the name."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})
    _stub_views(monkeypatch, {str(moon_id): "You are in Room 1."})

    result = perception.perception_act(ctx, nonce=0)
    view = result["views"][str(moon_id)]

    assert "fox-eared" in view, "stranger should still see the appearance"
    assert not _name_outside_quotes(view), (
        f"appearance injection leaked the canonical name: {view!r}"
    )


def test_recognizing_observer_view_passes_through_unmodified(temp_db, monkeypatch):
    """No false positive: once Dr. Moon legitimately knows Hinami, the same
    adversarial view must survive untouched."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={"Dr. Moon": ["Hinami"]})
    _stub_views(monkeypatch, {str(moon_id): ADVERSARIAL})

    result = perception.perception_act(ctx, nonce=0)
    assert result["views"][str(moon_id)] == ADVERSARIAL


def test_player_own_view_keeps_own_name(temp_db, monkeypatch):
    """The observer IS the actor: the player's own view referring to the
    player by name is legitimate self-knowledge, never scrubbed."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": []}
    player_view = "You step forward. Your name is Hinami and your tail sways."
    _stub_views(monkeypatch, {"player": player_view})

    result = perception.perception_outcome(ctx, nonce=0)
    assert result["views"]["player"] == player_view


def test_outcome_stage_scrubs_stranger_view(temp_db, monkeypatch):
    """The floor applies at the outcome pass too, per-source against the
    observer's recognized set."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": []}
    _stub_views(monkeypatch, {str(moon_id): ADVERSARIAL})

    result = perception.perception_outcome(ctx, nonce=0)
    view = result["views"][str(moon_id)]

    assert not _name_outside_quotes(view), (
        f"canonical name leaked into stranger's outcome view: {view!r}"
    )


def test_introduction_quote_survives_but_bare_name_is_scrubbed(temp_db, monkeypatch):
    """Mid-beat introduction: the name spoken aloud is sensory signal and
    must stay verbatim inside the quote; recognition only flips at commit
    (validated_introductions), so the bare narrative mention in the SAME
    view is still unearned and must be scrubbed."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})
    intro_view = (
        'The fox-eared woman says: "My name is Hinami." Hinami smiles.'
    )
    _stub_views(monkeypatch, {str(moon_id): intro_view})

    result = perception.perception_act(ctx, nonce=0)
    view = result["views"][str(moon_id)]

    assert '"My name is Hinami."' in view, (
        "legitimately heard speech must be preserved verbatim"
    )
    assert not _name_outside_quotes(view), (
        f"bare post-quote name mention survived the scrub: {view!r}"
    )


def test_micro_perception_gates_actor_name_by_recognition(temp_db):
    """loops.py's deterministic NPC-to-NPC delivery had NO recognition check
    at all -- canonical names flowed between mutually-unknown characters."""
    from agents.loops import deterministic_micro_perception
    from scene import get_scene

    ctx, moon_id, kessler_id = _make_ctx(
        temp_db, known={}, extra_char="Kessler")
    scene = get_scene(ctx.chat.id, ctx.chat)
    result = {"sequence": [
        {"type": "speech", "text": "Stay where you are.", "volume": "normal"},
        {"type": "action", "attempt": "raises a hand", "visibility": "overt"},
    ]}

    views, _ = deterministic_micro_perception(ctx, kessler_id, result, scene)
    moon_view = " ".join(views.get(moon_id) or [])
    assert "Stay where you are." in moon_view
    assert not _name_outside_quotes(moon_view, "kessler"), (
        f"canonical NPC name leaked between strangers: {moon_view!r}"
    )

    temp_db.wset(ctx.chat.id, "known", {"Dr. Moon": ["Kessler"]})
    views, _ = deterministic_micro_perception(ctx, kessler_id, result, scene)
    moon_view = " ".join(views.get(moon_id) or [])
    assert "Kessler" in moon_view, "recognized actor should be named"


def test_fallback_views_gate_speaker_name(temp_db):
    """The no-LLM fallback renderer must apply the same recognition gate."""
    from agents.common import _fallback_perception_views

    perceivers = [{"id": 7, "name": "Dr. Moon", "room": "room1",
                   "room_name": "Room 1", "room_notes": ""}]
    dlog = [{"speaker": "Hinami", "exact_quote": '"Hello there."',
             "speaker_room": "room1"}]

    views = _fallback_perception_views(perceivers, dlog, known={})
    assert "Hello there." in views["7"]
    assert not _name_outside_quotes(views["7"]), (
        f"fallback renderer leaked the speaker name: {views['7']!r}"
    )

    views = _fallback_perception_views(
        perceivers, dlog, known={"Dr. Moon": ["Hinami"]})
    assert "Hinami" in views["7"]


def test_single_quoted_spoken_name_survives_the_scrub():
    """A name introduced ALOUD this beat is legitimate sensory signal the
    hearer receives; it must survive the identity scrub verbatim. The
    perception model renders speech with single quotes ('...') as often as
    double, and the double-quote-only span guard let a self-introduction like
    'I-I'm Hinami' get scrubbed out of what the hearer plainly heard -- while a
    third-person narrative reference to the same stranger must still be
    anonymized."""
    from agents.common import _scrub_unknown_identities

    view = ("She mutters, 'Uhm... Hello?' then says clearly, 'I-I'm Hinami.' "
            "Hinami's tails puff as Hinami stands there.")
    out, leaked = _scrub_unknown_identities(
        view,
        allowed_forms=["Dr. Moon"],
        unknown_sources=[{"name": "Hinami",
                          "appearance": "a fox-eared young woman",
                          "aliases": []}],
    )
    # spoken self-introduction preserved
    assert "'I-I'm Hinami.'" in out
    # narrative references (possessive + bare) anonymized
    assert "Hinami's tails" not in out
    assert "as Hinami stands" not in out
    assert leaked == ["Hinami"]


def test_apostrophes_do_not_open_a_protected_span():
    """Contraction/possessive apostrophes ('She's', 'Hinami's') must not be
    mistaken for opening dialogue quotes, or a stranger's name in plain
    narration would slip through the scrub inside a bogus protected span."""
    from agents.common import _scrub_unknown_identities

    view = "She's watching. Hinami's tail sways as Hinami waits. No one speaks."
    out, _ = _scrub_unknown_identities(
        view,
        allowed_forms=["Dr. Moon"],
        unknown_sources=[{"name": "Hinami",
                          "appearance": "a fox-eared young woman",
                          "aliases": []}],
    )
    assert "Hinami" not in out
