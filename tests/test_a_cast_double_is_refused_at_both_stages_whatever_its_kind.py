"""A new body never takes a cast member's identity -- at either stage, under
whatever kind the encoder wrote for it.

The floor (`director_floors._refuse_minted_cast_doubles`, the concept lab's
`ines_calder`, 2026-09-30) had two holes (review 2026-11-01, director core F2
and director floors F3):

  * IT REFUSED ONLY `kind == "person"`. `kind` is free text in the fiction's
    own words (`encoder/entities__new.txt`), so the same stranger minted as
    "woman", "human" or, in a Japanese story, "人物" was kept: a second body
    of a cast member. The engine's own vocabulary names the one case the rule
    excludes -- an inert THING (`persist.commit._INERT_ENTITY_KINDS`, the set
    the sibling binder already reads) -- and everything else is a body.
  * IT NEVER RAN ON THE INTERPRET'S MINTS. It read `state_diff`, which the
    interpret does not have (its channels live in `state_assertions`), so it
    returned before looking; at resolve it ran before the interpret's
    assertions were merged, and the onset preview had already put the mint
    into the scene it treated as held. A double minted at interpret was
    refused at neither stage.
"""

from __future__ import annotations

import json

import pytest

import agents.director as director
from agents.director import _refuse_minted_cast_doubles

from tests.director_fakes import _make_ctx, _speech_interp, encoder_event

INES = {"sheet": json.dumps({"identity": {"name": "Ines Calder", "uid": "ines-uid",
                                          "aliases": ["Dr. Calder"]}})}


def _diff(kind):
    entity = {"name": "a woman with steel-grey hair", "aliases": ["the doctor"]}
    if kind is not None:
        entity["kind"] = kind
    return {"entities": {"ines_calder": entity},
            "positions": {"ines_calder": "clinic"}}


@pytest.mark.parametrize("kind", ["person", "woman", "human", "人物", "Person ", None],
                         ids=["person", "woman", "human", "ja-person", "spaced", "no-kind"])
def test_a_body_filed_under_a_cast_members_id_is_refused_whatever_its_kind(kind):
    sd = _diff(kind)
    got = _refuse_minted_cast_doubles({}, sd, [INES], here_names=["Ines Calder"])
    assert [r["cast"] for r in got] == ["Ines Calder"], kind
    assert sd["entities"] == {} and sd["positions"] == {}


@pytest.mark.parametrize("kind", ["item", "furniture", "vehicle", "Fixture"])
def test_a_thing_is_the_one_case_the_floor_leaves_alone(kind):
    """A boat called the Ines Calder is a thing, and no second body."""
    sd = {"entities": {"ines_calder": {"name": "Ines Calder", "kind": kind}}}
    assert _refuse_minted_cast_doubles({}, sd, [INES], here_names=[]) == []
    assert "ines_calder" in sd["entities"]


def _cast_double_agents(calls, *, interpret_mint=True, resolve_mint=False):
    """Interpret's encoder mints a stranger under Mara's id (Mara is this
    chat's cast member), kind written in the fiction's own words."""
    stranger = {"mara": {"name": "a woman in a grey shawl", "kind": "woman",
                         "aliases": ["the stranger at the door"]}}
    turns = {"encoder": 0}

    def encoder(payload):
        turns["encoder"] += 1
        mints = (interpret_mint if turns["encoder"] == 1 else resolve_mint)
        transforms = ([{"item": "mara", "patch": {"entities": stranger}}]
                      if mints else [])
        return {"events": [encoder_event(
            "A woman in a grey shawl is at the door.", source="world",
            transforms=transforms)]}

    def fake(role, step_key, system, payload, **kw):
        calls.append(step_key)
        if step_key == "director_prose":
            return {"prose": "A woman in a grey shawl is at the door."}
        if step_key == "director_specialist":
            return encoder(payload)
        return {}
    return fake


def test_the_interpret_refuses_a_double_it_mints(temp_db, monkeypatch, prose_director):
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input="Who is it?")
    ctx.director_interpret = None
    monkeypatch.setattr(director, "_agent_json", _cast_double_agents([]))

    out = director.director_interpret(ctx, nonce=0)

    # The identity join files the mint under the member's own key ("Mara").
    for key in ("state_assertions", "onset_state_assertions"):
        minted = (out.get(key) or {}).get("entities") or {}
        assert not [eid for eid in minted if eid.casefold() == "mara"], key
    assert [r["entity_id"].casefold() for r in out.get("cast_doubles_refused") or []] \
        == ["mara"]
    assert [w for w in ctx.warnings if "claims Mara's identity" in w], ctx.warnings


def test_the_resolve_refuses_a_double_the_interpret_carried(
        temp_db, monkeypatch, prose_director):
    """The interpret's mint reaches the resolve as an onset assertion (a beat
    stored before the interpret floor ran, or one a model wrote straight into
    the assertions): the resolve judges the MERGED diff, against the scene the
    beat opened on, never the onset preview that already holds the mint."""
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input="Who is it?")
    interp = _speech_interp()
    stranger = {"name": "a woman in a grey shawl", "kind": "woman",
                "aliases": ["the stranger at the door"]}
    interp["state_assertions"] = {"entities": {"mara": dict(stranger)}}
    interp["onset_state_assertions"] = {"entities": {"mara": dict(stranger)}}
    ctx.director_interpret = interp
    monkeypatch.setattr(director, "_agent_json",
                        _cast_double_agents([], interpret_mint=False))

    out = director.director_resolve(ctx, nonce=0)

    minted = (out.get("state_diff") or {}).get("entities") or {}
    assert not [eid for eid in minted if eid.casefold() == "mara"], minted
    assert [r["entity_id"].casefold() for r in out.get("cast_doubles_refused") or []] \
        == ["mara"]
