"""A mind can follow a person it knows only by sight, and is told whom it
follows in its own words.

The read-back offers "follow <person>" over the people this mind's view
named -- a stranger by the view's label ("the tall man in the oilskin") --
and compiled `follow_op.target` as that label; the movement floor resolves a
target only against `scene.positions` keys (`director_movement.
_follow_op_for_actor`), so every follow of a stranger was "Ignored invalid
follow start" and no ledger row was written (review 2026-11-01,
agents_character_background F14). The label is now read back through this
speaker's own label map before the step returns -- the view's company first,
then the floor every payload shares (`director._bodies_addressed_as`, as
`name_concealed_bodies` reads a stranger's label) -- and fails closed where a
label names two bodies. The ledger keeps the body; the mind's payload names
the one it follows as its view does (`self.following.target`).
"""

from __future__ import annotations

from copy import deepcopy

from tests.test_character_continuity import story  # noqa: F401 -- the fixture

STRANGER = "Brennick Vael"
LABEL = "the tall man in the oilskin"


def _scene(**extra_positions):
    return {"location": "Hall", "time": "now",
            "rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Mara": "hall", STRANGER: "hall", **extra_positions},
            "entities": {}, "attire": {}, "overlays": {}}


def _run(story, monkeypatch, temp_db, *, company, scene, following=None):
    import agents.character as character
    from llm import decisions
    from tests.test_character_bare import _answer
    char_id, context, _commit = story
    ctx = context(None, 1)
    if following:
        scene = dict(scene, following=following)
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.perception_act = {
        "views": {str(char_id): f"{LABEL[0].upper()}{LABEL[1:]} shoulders his pack."},
        "observations": {str(char_id): [{
            "observation_id": "current:1:0", "kind": "action", "channel": "sight",
            "phase": "act", "actor": LABEL,
            "observed": {"text": f"{LABEL[0].upper()}{LABEL[1:]} shoulders his pack."},
            "intensity": 0.6, "ambiguity": 0.1}]},
        "company": {str(char_id): company}}
    sent = []

    def model(role, step_key, system, payload, **kwargs):
        sent.append(deepcopy(payload))
        return {"want": "keep him in sight", "held_back": "", "hinge": "he is leaving",
                "unsure": "", "sequence": [{"do": "goes after him"}], "demeanor": "",
                "tells": [], "notebook": [], "changes": [], "note": ""}

    monkeypatch.setattr(decisions, "OVERRIDE",
                        lambda state, questions: _answer([("follow", "start0")])(questions))
    monkeypatch.setattr(character, "_agent_json", model)
    return character.character_step(ctx, char_id, 1), sent, ctx


def test_a_stranger_she_sees_can_be_followed(temp_db, story, monkeypatch):
    result, _sent, _ctx = _run(
        story, monkeypatch, temp_db, scene=_scene(),
        company=[{"name": STRANGER, "label": LABEL}])
    follow = result.get("follow_op") or {}
    assert follow.get("op") == "start" and follow.get("target") == STRANGER


def test_a_label_two_bodies_wear_starts_no_follow(temp_db, story, monkeypatch):
    twin = "Corvin Vael"
    result, _sent, ctx = _run(
        story, monkeypatch, temp_db, scene=_scene(**{twin: "hall"}),
        company=[{"name": STRANGER, "label": LABEL}, {"name": twin, "label": LABEL}])
    assert not result.get("follow_op")
    assert any("follow" in w and LABEL in w for w in ctx.warnings)


def test_whom_she_follows_is_named_as_her_view_names_him(temp_db, story, monkeypatch):
    _result, sent, _ctx = _run(
        story, monkeypatch, temp_db, scene=_scene(),
        company=[{"name": STRANGER, "label": LABEL}],
        following={"Mara": {"target": STRANGER, "since_turn": 0, "reason": "keep him in sight"}})
    shown = sent[0]["self"]["following"]["target"]
    assert shown == LABEL
