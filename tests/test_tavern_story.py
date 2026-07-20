"""A short 6-turn tavern story exercising the background-presence machinery
end to end (deterministically, no live LLM): NPCs popping into existence
through LOCATION (the tavern implies a barkeep at the opening) and through
PROMPT (the player waves over a serving girl), then reading as *real* people
-- reacting via the deterministic backstop, remembering across beats through
persisted dialogue turns, and accruing toward promotion -- without ever being
minted as full characters.

The whole story is driven through the real commit-side deterministic
functions (track_background_presences, pick_background_reactor) and the real
background_react stage with only its single LLM call stubbed. It doubles as
the regression test for the Step-1/Step-2 background-NPC work.
"""

from __future__ import annotations

import time

import agents.background as background
from commit import (
    track_background_presences,
    promotable_background_presences,
    prepare_memory_commit,
)
from pipeline_context import ChatData, PipelineContext, TurnData


class _Story:
    """Drives one persistent chat across turns against a temp_db."""

    def __init__(self, temp_db):
        self.db = temp_db
        self.cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Rusty Flagon", "A dockside tavern of ill repute.", time.time()),
        )
        self.last_payload = None

        def _canned_reaction(role, name, system, payload, **kw):
            self.last_payload = payload
            return {
                "reacts": True,
                "dialogue_log_entry": {
                    "speaker": "ignored", "exact_quote": '"Aye."',
                    "volume": "normal", "intended_target": None, "tone": "gruff",
                    "visibility": "overt", "conceal_from": [],
                },
                "action": "",
            }

        self._react = _canned_reaction

    def _ctx(self, idx, player_input, *, director_resolve=None, director_establish=None):
        return PipelineContext(
            chat=ChatData(id=self.cid, name="Rusty Flagon", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=idx + 1, chat_id=self.cid, idx=idx,
                          player_input=player_input, created=time.time()),
            cast=[], input=player_input,
            director_resolve=director_resolve, director_establish=director_establish,
        )

    def establish(self, director_establish):
        """Opening turn (idx 0): no background_react stage runs."""
        ctx = self._ctx(0, "", director_establish=director_establish)
        track_background_presences(ctx, nonce=0)
        return ctx

    def turn(self, idx, player_input, director_resolve, monkeypatch):
        """A normal turn: run the real gated backstop, then track."""
        monkeypatch.setattr(background, "_agent_json", self._react)
        ctx = self._ctx(idx, player_input, director_resolve=director_resolve)
        ctx["background_react"] = background.background_react(ctx, nonce=idx)
        track_background_presences(ctx, nonce=idx)
        return ctx

    def presences(self):
        return self.db.wget(self.cid, "background_presences", {})

    def promotable_names(self):
        return {r["name"] for r in promotable_background_presences(self.cid) if r["promotable"]}


def test_tavern_six_turn_story(temp_db, monkeypatch):
    s = _Story(temp_db)

    # --- Turn 0: LOCATION pop-in. The tavern implies a barkeep; the Director
    # establishes Doran at the opening. He exists, with a sketch, but has no
    # salience yet (no dialogue, not promotable).
    s.establish({
        "location": "The Rusty Flagon",
        "rooms": {"taproom": {"name": "The Taproom"}},
        "positions": {"Doran": "taproom"},
        "entities": {"barkeep": {
            "kind": "person", "name": "Doran",
            "description": "grizzled one-eyed barkeep of the Rusty Flagon",
        }},
    })
    doran = s.presences()["Doran"]
    assert doran["first_turn"] == 0
    assert doran["dialogue_turns"] == []
    assert "barkeep" in doran["sketch"]["role_hint"]
    assert doran["sketch"]["station_room"] == "taproom"
    assert "Doran" not in s.promotable_names()

    # --- Turn 1: the location-implied presence becomes salient (mentioned in
    # the resolved event) and the deterministic backstop voices him. That line
    # is bookkept as a real dialogue turn (Step 1).
    ctx1 = s.turn(1, "I take a stool at the bar and ask for whatever's on tap.", {
        "resolved_event": "Doran sizes up the newcomer and reaches for a tankard.",
        "dialogue_log": [],
    }, monkeypatch)
    assert ctx1["background_react"]["fired"] is True
    assert ctx1["background_react"]["name"] == "Doran"
    assert s.presences()["Doran"]["dialogue_turns"] == [1]
    # The backstop line is folded into the committed event record, not lost.
    import json
    event = json.loads(prepare_memory_commit(ctx1)["event_content"])
    assert any(d.get("source") == "background_react" and d["speaker"] == "Doran"
               for d in event["dialogue_log"])

    # --- Turn 2: player addresses Doran directly. He reacts again and crosses
    # the promotion threshold. The "hooded man" is mere scenery -- never a
    # structured entity, so he is never tracked (no NER over prose).
    s.turn(2, "Doran, pour another -- and tell me about the hooded man in the corner.", {
        "resolved_event": "Doran pours, eyeing the hooded figure by the hearth.",
        "dialogue_log": [],
    }, monkeypatch)
    assert s.presences()["Doran"]["dialogue_turns"] == [1, 2]
    assert "Doran" in s.promotable_names()
    assert not any("hooded" in n.lower() for n in s.presences())

    # --- Turn 3: PROMPT pop-in. The player waves over a serving girl; the
    # Director introduces AND voices Mira (structured entity + dialogue line),
    # so the gate does NOT spend a redundant backstop on her -- it stays with
    # the standing presence (Doran). Mira is tracked with a harvested sketch.
    ctx3 = s.turn(3, "I wave over a serving girl and ask what's good tonight.", {
        "resolved_event": "A serving girl threads over at your wave.",
        "state_diff": {
            "entities": {"g1": {"kind": "person", "name": "Mira",
                                "description": "harried young serving girl"}},
            "positions": {"Mira": "taproom"},
        },
        "dialogue_log": [{"speaker": "Mira",
                          "exact_quote": '"The lamb stew, if you\'re wise."',
                          "volume": "normal", "intended_target": None,
                          "tone": "brisk", "visibility": "overt", "conceal_from": []}],
    }, monkeypatch)
    assert ctx3["background_react"]["name"] == "Doran"      # Mira not double-voiced
    mira = s.presences()["Mira"]
    assert mira["first_turn"] == 3
    assert mira["dialogue_turns"] == [3]                    # from the Director's own line
    assert mira["sketch"]["role_hint"] == "harried young serving girl"
    assert mira["sketch"]["station_room"] == "taproom"

    # --- Turn 4: the prompt-born NPC gets her own backstop when addressed, and
    # the sketch harvested at turn 3 is replayed into her reaction payload
    # (Step 2 -- cheap individuation). The gate correctly prefers the addressed
    # presence (Mira) over the merely-standing one (Doran).
    ctx4 = s.turn(4, "Quietly, I ask Mira whether the hooded man came in alone.", {
        "resolved_event": "You lean in with the question.",
        "dialogue_log": [],
    }, monkeypatch)
    assert ctx4["background_react"]["name"] == "Mira"
    assert s.last_payload["entity"]["role_hint"] == "harried young serving girl"
    assert s.presences()["Mira"]["dialogue_turns"] == [3, 4]
    assert {"Doran", "Mira"} <= s.promotable_names()

    # --- Turn 5: continuity payoff. Doran, addressed again, reacts a third
    # backstop time; his dialogue history spans the whole scene -- exactly the
    # accrual that pre-Step-1 was invisible because backstop lines never
    # reached the bookkeeping.
    s.turn(5, "Doran -- you've seen the hooded man before, haven't you. Has he paid for a room?", {
        "resolved_event": "Doran's jaw tightens at the question.",
        "dialogue_log": [],
    }, monkeypatch)
    assert s.presences()["Doran"]["dialogue_turns"] == [1, 2, 3, 5]

    # --- Nothing was silently promoted below the boundary: neither NPC has a
    # character sheet or a chat_chars row. They remained cheap the whole story.
    for name in ("Doran", "Mira"):
        assert temp_db.q("SELECT id FROM characters WHERE name=?", (name,), one=True) is None
    assert temp_db.q(
        "SELECT cc.char_id FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=? AND ch.name IN ('Doran','Mira')", (s.cid,), one=True) is None
