"""W3/W4 background-character fixes (Enterprise-D audit, findings.md).

W3: a background presence the director's flow.addressed_to names (preserved
as flow.addressed_to_refs before int coercion) is FORCED to react this beat
in pick_background_reactors -- bypassing the <=1 cap and the normal priority
order -- so a directly-addressed NPC always answers with its own line instead
of being displaced by a merely-standing presence.

W4: promotion is no longer UI-only. promote_background_character factors the
confirm-route body into a reusable helper, and auto_promote_background_characters
is a commit-side sweep that autonomously promotes a presence crossing the
auto-threshold (promotable + dialogue_turns >= 3 + present/addressed this
beat), gated behind setting('auto_promote') which defaults ON.

Driven through the real deterministic commit-side functions with only the
LLM boundary (draft_promoted_character) stubbed, in the style of
tests/test_tavern_story.py.
"""

from __future__ import annotations

import json
import time

import importers
from commit import (
    auto_promote_background_characters,
    pick_background_reactor,
    pick_background_reactors,
    promote_background_character,
)
from pipeline_context import ChatData, PipelineContext, TurnData
from schemas import validate_llm_output


def _make_chat(db, name="Enterprise-D"):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        (name, "The bridge, mid-crisis.", time.time()),
    )


def _ctx(cid, idx, player_input, *, addressed_refs=None, background_react=None):
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Enterprise-D", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=idx + 1, chat_id=cid, idx=idx,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input,
    )
    if addressed_refs is not None:
        ctx["director_interpret"] = {"flow": {"addressed_to_refs": addressed_refs}}
    if background_react is not None:
        ctx["background_react"] = background_react
    return ctx


def _presence(first_turn, last_turn, dialogue_turns=(), mention_turns=(),
              role_hint="", station_room=""):
    rec = {
        "first_turn": first_turn, "last_turn": last_turn,
        "dialogue_turns": list(dialogue_turns),
        "mention_turns": list(mention_turns),
    }
    if role_hint or station_room:
        rec["sketch"] = {"role_hint": role_hint, "station_room": station_room}
    return rec


# ---- W3: flow-addressed presences are forced reactors ----

class TestFlowAddressedForcedReactor:
    def test_addressed_ref_qualifies_presence_with_no_other_salience(self, temp_db):
        """An address by role ('the counselor') never mentions the tracked
        name in the raw text -- only flow.addressed_to carries it. Previously
        the presence did not even qualify; now it must answer."""
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "background_presences", {
            "Counselor Troi": _presence(1, 1, role_hint="ship's counselor"),
        })
        ctx = _ctx(cid, 7, "I turn to the counselor. \"What do you sense?\"",
                   addressed_refs=["Troi"])
        dr = {"resolved_event": "The question hangs on the bridge.",
              "dialogue_log": []}

        assert pick_background_reactor(ctx, dr) == "Counselor Troi"

    def test_addressed_presence_displaces_higher_standing_candidate(self, temp_db):
        """At cap=1 the flow-addressed presence wins over a presence with a
        long dialogue history that is also mentioned in the resolved event."""
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "background_presences", {
            "Vorne": _presence(1, 6, dialogue_turns=[1, 2, 3, 4, 5, 6]),
            "Counselor Troi": _presence(1, 1),
        })
        ctx = _ctx(cid, 7, "I look to the counselor for her read.",
                   addressed_refs=["Troi"])
        dr = {"resolved_event": "Vorne shifts at the tribunal bench.",
              "dialogue_log": []}

        assert pick_background_reactors(ctx, dr, cap=1) == ["Counselor Troi"]

    def test_multiple_addressed_presences_bypass_the_cap(self, temp_db):
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "background_presences", {
            "Counselor Troi": _presence(1, 1),
            "Worf": _presence(1, 1),
            "Doran": _presence(1, 6, dialogue_turns=[1, 2, 3]),
        })
        ctx = _ctx(cid, 7, "Both of you -- report.",
                   addressed_refs=["Troi", "Worf"])
        dr = {"resolved_event": "The order lands.", "dialogue_log": []}

        picks = pick_background_reactors(ctx, dr, cap=1)
        assert set(picks) == {"Counselor Troi", "Worf"}

    def test_registered_or_already_voiced_addressee_is_not_forced(self, temp_db):
        """A presence the director already voiced in this beat's dialogue_log
        needs no backstop, forced or not."""
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "background_presences", {
            "Counselor Troi": _presence(1, 1),
        })
        ctx = _ctx(cid, 7, "Counselor?", addressed_refs=["Troi"])
        dr = {"resolved_event": "Troi answers at once.",
              "dialogue_log": [{"speaker": "Counselor Troi",
                                "exact_quote": '"Grief. Enormous grief."',
                                "volume": "normal", "visibility": "overt",
                                "conceal_from": []}]}

        assert pick_background_reactors(ctx, dr, cap=1) == []

    def test_int_like_refs_are_ignored(self, temp_db):
        """Numeric refs are registered-character ids -- never matched against
        presence names."""
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "background_presences", {"7": _presence(1, 1)})
        ctx = _ctx(cid, 3, "A quiet beat.", addressed_refs=["7", 7])
        dr = {"resolved_event": "Nothing stirs.", "dialogue_log": []}

        assert pick_background_reactors(ctx, dr, cap=1) == []

    def test_schema_preserves_raw_addressed_refs(self, temp_db):
        raw = {"kind": "dialogue", "flow": {"addressed_to": ["Troi", 3]}}
        out, _warnings = validate_llm_output("director_interpret", raw)
        assert out["flow"]["addressed_to"] == [3]
        assert out["flow"]["addressed_to_refs"] == ["Troi", 3]


# ---- W4: reusable promotion helper + autonomous commit-side sweep ----

_SHEET = {"identity": {"name": "Data"}}


def _stub_draft(monkeypatch, name="Data", seeds=("Analyzed the Kelvan core log.",)):
    calls = []

    def fake_draft(cid, presence_name):
        calls.append((cid, presence_name))
        return {"sheet": {"identity": {"name": name}},
                "memory_seeds": list(seeds), "evidence_turns": [4]}

    monkeypatch.setattr(importers, "draft_promoted_character", fake_draft)
    return calls


class TestPromoteBackgroundCharacter:
    def test_attaches_character_and_seeds_scene_known_memory(self, temp_db, monkeypatch):
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "scene", {
            "location": "Bridge", "rooms": {"bridge": {"name": "Bridge"}},
            "positions": {"The Stranger": "bridge"},
        })
        temp_db.wset(cid, "background_presences", {
            "Data": _presence(1, 4, dialogue_turns=[1, 2, 4]),
        })
        _stub_draft(monkeypatch)

        char_id = promote_background_character(cid, "Data")

        row = temp_db.q("SELECT * FROM characters WHERE id=?", (char_id,), one=True)
        assert row["name"] == "Data"
        assert json.loads(row["source"]) == {"format": "promoted", "chat_id": cid}
        cc = temp_db.q(
            "SELECT status FROM chat_chars WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)
        assert cc["status"] == "active"
        # Seeded at the player's position, mid-scene.
        assert temp_db.wget(cid, "scene")["positions"]["Data"] == "bridge"
        # Mutual recognition with the player.
        known = temp_db.wget(cid, "known", {})
        assert "The Stranger" in known["Data"]
        assert "Data" in known["The Stranger"]
        # Starter memory seeded from the draft.
        mem = temp_db.q(
            "SELECT content FROM memories WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)
        assert mem["content"] == "Analyzed the Kelvan core log."
        # No longer a tracked background presence.
        assert "Data" not in temp_db.wget(cid, "background_presences", {})

    def test_reviewed_sheet_skips_the_draft_llm_call(self, temp_db, monkeypatch):
        cid = _make_chat(temp_db)
        calls = _stub_draft(monkeypatch)
        char_id = promote_background_character(cid, "Data", sheet=dict(_SHEET),
                                               memory_seeds=[])
        assert calls == []
        assert temp_db.q("SELECT name FROM characters WHERE id=?",
                         (char_id,), one=True)["name"] == "Data"


class TestAutoPromoteSweep:
    def _seed(self, db, cid, dialogue_turns, last_turn):
        db.wset(cid, "background_presences", {
            "Data": _presence(1, last_turn, dialogue_turns=dialogue_turns),
        })

    def test_promotes_qualifying_presence_active_this_beat(self, temp_db, monkeypatch):
        cid = _make_chat(temp_db)
        self._seed(temp_db, cid, [1, 2, 4], last_turn=5)
        _stub_draft(monkeypatch)

        result = auto_promote_background_characters(_ctx(cid, 5, "Data, report."))

        assert [p["name"] for p in result["promoted"]] == ["Data"]
        assert temp_db.q("SELECT id FROM characters WHERE name='Data'", one=True)
        assert "Data" not in temp_db.wget(cid, "background_presences", {})

    def test_gated_off_by_the_auto_promote_setting(self, temp_db, monkeypatch):
        cid = _make_chat(temp_db)
        self._seed(temp_db, cid, [1, 2, 4], last_turn=5)
        _stub_draft(monkeypatch)
        temp_db.set_setting("auto_promote", "0")

        result = auto_promote_background_characters(_ctx(cid, 5, "Data, report."))

        assert result == {"promoted": []}
        assert temp_db.q("SELECT id FROM characters WHERE name='Data'", one=True) is None

    def test_below_dialogue_threshold_stays_tracked(self, temp_db, monkeypatch):
        """Promotable per the UI badge (2 dialogue turns) but below the
        autonomous threshold (3) -- the sweep leaves her alone."""
        cid = _make_chat(temp_db)
        self._seed(temp_db, cid, [1, 2], last_turn=5)
        _stub_draft(monkeypatch)

        result = auto_promote_background_characters(_ctx(cid, 5, "Data, report."))

        assert result == {"promoted": []}
        assert "Data" in temp_db.wget(cid, "background_presences", {})

    def test_not_present_this_beat_is_not_promoted(self, temp_db, monkeypatch):
        cid = _make_chat(temp_db)
        self._seed(temp_db, cid, [1, 2, 4], last_turn=4)  # untouched this turn
        _stub_draft(monkeypatch)

        result = auto_promote_background_characters(_ctx(cid, 9, "A quiet beat."))

        assert result == {"promoted": []}

    def test_flow_address_counts_as_present_this_beat(self, temp_db, monkeypatch):
        cid = _make_chat(temp_db)
        self._seed(temp_db, cid, [1, 2, 4], last_turn=4)
        _stub_draft(monkeypatch)

        ctx = _ctx(cid, 9, "I turn to the android.", addressed_refs=["Data"])
        result = auto_promote_background_characters(ctx)

        assert [p["name"] for p in result["promoted"]] == ["Data"]

    def test_at_most_one_promotion_per_beat(self, temp_db, monkeypatch):
        """Two qualifiers in the same beat: only the most-voiced is promoted;
        the other stays tracked for a later beat."""
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "background_presences", {
            "Data": _presence(1, 5, dialogue_turns=[1, 2, 4, 5]),
            "Worf": _presence(1, 5, dialogue_turns=[2, 3, 5]),
        })
        _stub_draft(monkeypatch)

        result = auto_promote_background_characters(_ctx(cid, 5, "Report, both of you."))

        assert [p["name"] for p in result["promoted"]] == ["Data"]
        remaining = temp_db.wget(cid, "background_presences", {})
        assert "Worf" in remaining and "Data" not in remaining
