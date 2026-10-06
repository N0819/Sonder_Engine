"""A character can hide an act from the player, by any name the beat knows
her by (Kirinoura, scratch chat 167 turn 3, 2026-10-05).

A character's `conceal_from` is resolved to the bodies the beat holds before
the firewall reader sees it (`director_floors.resolve_concealment_refs`), and
the bodies it knew were the cast's cards alone: every exclusion aimed at the
player was reported as naming "no body in this scene" -- four times a beat
while the surveyor stood one doorway off -- and any spelling of her but the
exact name had nothing to resolve against.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(temp_db, persona_aliases=(), cast_aliases=()):
    from story.character_schema import default_character_data, default_persona_data
    persona = default_persona_data("Mika Oda")
    persona["identity"]["aliases"] = list(persona_aliases)
    persona_id = temp_db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                            ("Mika Oda", json.dumps(persona), "{}"))
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
                         ("Hide", "", time.time(), persona_id))
    sheet = default_character_data("The Doctor")
    sheet["identity"]["aliases"] = list(cast_aliases)
    cast = [{"id": 58, "sheet": json.dumps(sheet), "cstate": "{}", "stance": "{}"}]
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Hide", persona_id=persona_id, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="", created=time.time()),
        cast=cast, input="")


def _concealed(conceal_from, targets=(), kind="action"):
    element = {"type": kind, "visibility": "concealed", "conceal_from": list(conceal_from),
               "targets": list(targets), "actor": "The Doctor"}
    element.update({"text": "Not a word."} if kind == "speech" else {"attempt": "runs a sweep"})
    return [element]


def test_the_player_is_a_body_a_character_can_hide_from(temp_db):
    from agents.director import resolve_concealment_refs
    from agents.director import _scene_match_forms
    by_id, by_name = _scene_match_forms(_ctx(temp_db, persona_aliases=["Oda"]))
    for spelling in ("Mika Oda", "Oda"):
        sequence = _concealed([spelling])
        notes = resolve_concealment_refs(sequence, by_id, by_name)
        assert not any("no body in this scene" in n for n in notes), (spelling, notes)
        assert sequence[0]["conceal_from"] == ["Mika Oda"], spelling


def test_an_alias_a_cast_member_answers_to_stays_the_cast_members(temp_db):
    from agents.director import _scene_match_forms
    _by_id, by_name = _scene_match_forms(_ctx(temp_db, persona_aliases=["Doc"],
                                              cast_aliases=["Doc"]))
    assert "doc" not in by_name["Mika Oda"]


def test_a_line_spoken_to_the_player_is_never_hidden_from_her(temp_db):
    """The fail-closed branch: an engine form that resolves to nobody hides
    the line from every body the beat knows except its addressees -- and a
    line whose element names no target is spoken to whoever its
    `interaction.addresses` says (review, 2026-10-05)."""
    from agents.director import resolve_concealment_refs
    from agents.director import _scene_match_forms
    by_id, by_name = _scene_match_forms(_ctx(temp_db))
    sequence = _concealed(["character:ghost"], kind="speech")
    resolve_concealment_refs(sequence, by_id, by_name, addressees=["Mika Oda"])
    assert "Mika Oda" not in sequence[0]["conceal_from"]
    sequence = _concealed(["character:ghost"], kind="speech")
    resolve_concealment_refs(sequence, by_id, by_name)
    assert "Mika Oda" in sequence[0]["conceal_from"]
    # ...but only a spoken line that names no addressee of its own: the
    # pocket picked mid-conversation stays hidden from its owner (review
    # round 2, 2026-10-05).
    sequence = _concealed(["character:ghost"])
    resolve_concealment_refs(sequence, by_id, by_name, addressees=["Mika Oda"])
    assert "Mika Oda" in sequence[0]["conceal_from"]


def test_a_form_two_bodies_answer_to_is_kept_from_both():
    """Review round 3 (2026-10-05): an alias two players share named nobody
    once dropped from both, and a line kept from it reached everyone it
    names. An exclusion is the conservative reading: it covers them all."""
    from agents.director import resolve_concealment_refs
    sequence = _concealed(["Doc"], kind="speech")
    resolve_concealment_refs(sequence, {}, {"Kiri Asano": ["kiri asano", "doc"],
                                            "Ren Aoki": ["ren aoki", "doc"]})
    assert sequence[0]["conceal_from"] == ["Kiri Asano", "Ren Aoki"]


def test_an_alias_a_card_lists_twice_is_still_its_own(temp_db):
    from agents.director import _scene_match_forms
    _by_id, by_name = _scene_match_forms(_ctx(temp_db, persona_aliases=["Ren", "ren"]))
    assert "ren" in by_name["Mika Oda"]


def test_siblings_who_share_a_surname_stay_two_bodies():
    """Review round 4 (2026-10-05): the floors compared SPELLING sets, so two
    players sharing the alias "Tosaka" were one person -- a line said to Rin
    and kept from Sakura was stripped as "concealed from its own addressee"
    and reached Sakura. They compare bodies now."""
    from agents.director import resolve_concealment_refs, strip_addressee_concealment
    by_name = {"Rin Tosaka": ["rin tosaka", "tosaka"],
               "Sakura Tosaka": ["sakura tosaka", "tosaka"]}

    notes = []

    def floors(conceal_from):
        sequence = _concealed(conceal_from, targets=["Rin Tosaka"], kind="speech")
        notes.extend(strip_addressee_concealment(sequence, {}, by_name))
        resolve_concealment_refs(sequence, {}, by_name)
        return sequence[0]

    assert floors(["Sakura Tosaka"])["conceal_from"] == ["Sakura Tosaka"]
    # ...and no warning that it reaches nobody: it reaches Rin (review
    # round 5, 2026-10-05).
    assert not any("reaches nobody" in n for n in notes), notes
    # The shared form names the one it is NOT said to.
    assert floors(["Tosaka"])["conceal_from"] == ["Sakura Tosaka"]
    # The fail-closed branch spares the addressee and nobody else.
    hidden = floors(["character:ghost"])["conceal_from"]
    assert "Sakura Tosaka" in hidden and "Rin Tosaka" not in hidden
    # A line kept only from the person it is said to is no secret at all.
    line = floors(["Rin Tosaka"])
    assert line["conceal_from"] == [] and line["visibility"] == "overt"


def test_an_act_kept_from_a_shared_form_stays_kept_from_its_target():
    """The pocket picked: an ACT keeps its own target in the exclusion."""
    from agents.director import resolve_concealment_refs
    by_name = {"Rin Tosaka": ["rin tosaka", "tosaka"],
               "Sakura Tosaka": ["sakura tosaka", "tosaka"]}
    sequence = _concealed(["Tosaka"], targets=["Rin Tosaka"])
    resolve_concealment_refs(sequence, {}, by_name)
    assert sequence[0]["conceal_from"] == ["Rin Tosaka", "Sakura Tosaka"]


def test_an_act_kept_from_its_target_by_a_broken_engine_form_stays_kept():
    """Review round 5 (2026-10-05): the fail-closed branch spared an ACT's
    own targets, so a theft concealed from its owner under a misspelled
    engine form was shown to the owner and hidden from the bystander."""
    from agents.director import resolve_concealment_refs
    by_name = {"The Doctor": ["the doctor"], "Tamamo": ["tamamo"], "Mika Oda": ["mika oda"]}
    sequence = [{"type": "action", "visibility": "concealed", "actor": "Mika Oda",
                 "attempt": "slips the screwdriver out of his coat pocket",
                 "targets": ["The Doctor"], "conceal_from": ["character:the_doctor"]}]
    resolve_concealment_refs(sequence, {}, by_name)
    hidden = sequence[0]["conceal_from"]
    assert "The Doctor" in hidden and "Tamamo" in hidden and "Mika Oda" not in hidden
