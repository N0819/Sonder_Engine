"""The two composer-path fixes the full-corpus replay demanded.

The replay (design_notes/14) measured the composer strictly better than the
model on every information metric but one, and root-caused that one to the
engine's own repair passes:

1. `_strip_self_narration` was kept armed over composed views as a "free"
   tripwire. It splits on sentence punctuation, sentence punctuation occurs
   inside quoted speech, and composed quotes are entitled lines reproduced
   verbatim from `dialogue_log`. 167 of 382 fires dropped text containing a
   quote character; at least 16 cascaded into the invented-dialogue guard,
   which then failed to match the mangled quote and deleted the whole line.
   The composer lost 33 floor-era player same-room lines where the model
   lost 6 — its only recall regression, entirely self-inflicted.

2. 957 unearned-identity admissions reached the IR and were cleaned up
   after the fact by the output tripwire, and 69 more survived because the
   name belonged to a character not on the stage roster — so the tripwire
   had never heard of them either. Both channels are AUTHORED PROSE: room
   notes, appearance/overlay descriptions, ambient events, none of which
   was written for any particular mind.

The fix for the second makes the fix for the first safe: gate at admission,
where a subtraction costs nothing, instead of repairing a rendered view,
where it costs the reader a line.
"""

from __future__ import annotations

import json
import time

import pytest

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


# --- the quote-safe floor, as a unit -------------------------------------

def test_a_self_narrating_drop_that_would_take_a_quote_is_refused():
    """Chat 10, turn 29 in miniature: the stored composed player view was a
    147-char fragment ending mid-quote, because the sentence split landed
    inside a delivered 168-char line that happened to name the perceiver."""
    from agents.perception import _strip_self_narration_quote_safe

    view = ('Reya says: "You held the line, Reya. I saw it. '
            'Nobody else would have." The lantern gutters.')
    text, dropped, refused = _strip_self_narration_quote_safe(view, "Reya")

    assert text == view, "the delivered line must survive intact"
    assert not dropped
    assert refused, "and the refusal must be reported, not swallowed"


def test_prose_with_no_quote_in_it_is_still_stripped():
    """The floor is under delivered speech, not under the guard. A sentence
    carrying no quote carries no entitled line, so cutting it costs framing
    and nothing else — which is the guard doing its job."""
    from agents.perception import _strip_self_narration_quote_safe

    view = "Reya stands by the door. The lantern gutters."
    text, dropped, refused = _strip_self_narration_quote_safe(view, "Reya")

    assert "Reya stands" not in text
    assert "The lantern gutters." in text
    assert dropped and not refused


def test_a_possessive_apostrophe_is_not_a_delivered_line():
    """`_QUOTED_SPAN_RE`, not a quote character class. This prose is full of
    possessives, and refusing to cut every sentence containing an apostrophe
    would exempt most authored self-narration there is."""
    from agents.perception import _strip_self_narration_quote_safe

    text, dropped, refused = _strip_self_narration_quote_safe(
        "Reya's voice carries down the hall. Rope coils hang from the rafters.",
        "Reya")

    assert "Reya's voice" not in text
    assert dropped and not refused


# --- the admission gate, as a unit ---------------------------------------

def test_authored_prose_loses_a_name_the_observer_never_earned():
    from agents.perception import _composer_authored_prose

    text, notes = _composer_authored_prose(
        None, "perception_act",
        "Hinami's coat still hangs by the door.",
        "Reya", set(),
        [{"name": "Hinami", "appearance": "a fox-eared woman with six tails",
          "aliases": []}])

    assert "Hinami" not in text
    assert "fox-eared" in text or "six tails" in text
    assert notes


def test_a_name_the_observer_does_know_passes_through_untouched():
    """The gate is who COULD be leaked, not who must be hidden. Recognition
    decides, exactly as it does everywhere else."""
    from agents.perception import _composer_authored_prose

    text, notes = _composer_authored_prose(
        None, "perception_act",
        "Hinami's coat still hangs by the door.",
        "Reya", {"Hinami"},
        [{"name": "Hinami", "appearance": "a fox-eared woman",
          "aliases": []}])

    assert text == "Hinami's coat still hangs by the door."
    assert not notes


def test_authored_prose_stops_narrating_the_perceiver_at_themselves():
    """An establish-stage ambient event describing the perceiver's own voice
    — one of the 215 genuine Layer A admissions the replay found."""
    from agents.perception import _composer_authored_prose

    text, _notes = _composer_authored_prose(
        None, "perception_establish",
        "Reya's voice carries down the hall. Rope coils hang from the rafters.",
        "Reya", set(), [])

    assert "Reya's voice" not in text
    assert "Rope coils" in text


# --- the gate in the live stages -----------------------------------------

@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """See test_composer_pipeline: the guard moved down to the shared
    helper, because perception no longer imports a model seam at all."""
    import agents.common as common

    def _boom(*args, **kwargs):  # pragma: no cover - the assertion
        raise AssertionError("perception attempted a model call")

    monkeypatch.setattr(common, "_agent_json", _boom)


def _make_ctx(temp_db, *, room_notes="Rope coils hang from the rafters.",
              departed=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Gate", "", time.time()),
    )
    sheet = default_character_data("Reya")
    sheet["embodiment"]["visible"]["summary"] = (
        "a wiry courier with storm-grey eyes")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(sheet), "{}", time.time(), "char_reya"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    if departed:
        gone = default_character_data(departed)
        gone["embodiment"]["visible"]["summary"] = (
            "a fox-eared woman with six tails")
        gone_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (departed, json.dumps(gone), "{}", time.time(), "char_gone"),
        )
        # DORMANT, so `active_cast` — and therefore the stage roster and
        # every tripwire built from it — has never heard of her.
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)",
            (chat_id, gone_id, "dormant", "{}"),
        )
    temp_db.wset(chat_id, "scene", {
        "location": "Waystation", "time": "night",
        "rooms": {"hall": {"name": "the Long Hall", "notes": room_notes,
                           "adjacent": []}},
        "positions": {"The Stranger": "hall", "Reya": "hall"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=? AND cc.status='active'",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "hello", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Gate", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="hello", created=time.time()),
        cast=cast, input="hello",
    )
    ctx.director_interpret = {
        "sequence": [{"type": "action", "attempt": "raises the lantern",
                      "observable": "raises the lantern",
                      "visibility": "overt"}],
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": {"reactors": [char_id], "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx, char_id


def test_a_room_note_cannot_leak_an_off_roster_name(temp_db):
    """The dominant surviving leak channel in the replay: 69 floor-era views
    carrying a name out of `room_notes`, with zero warnings, because the
    named character was not on the stage roster the tripwire checks."""
    from agents.perception import perception_act

    ctx, char_id = _make_ctx(
        temp_db, room_notes="Hinami's coat still hangs by the door.",
        departed="Hinami")
    out = perception_act(ctx, "n0")

    for pid, view in out["views"].items():
        assert "Hinami" not in (view or ""), f"leaked to {pid}"


def test_the_gate_reports_the_admission_it_blocked(temp_db):
    """Subtracting silently would make this the kind of guard the audit
    history keeps finding: one that cannot be shown to have fired."""
    from agents.perception import perception_act

    ctx, _char_id = _make_ctx(
        temp_db, room_notes="Hinami's coat still hangs by the door.",
        departed="Hinami")
    perception_act(ctx, "n0")

    assert any("Hinami" in w and "no channel" in w for w in ctx.warnings)


def test_an_entitled_line_is_never_deleted_by_a_repair_pass(temp_db):
    """The blocking regression, end to end. The delivered line names the
    perceiver inside the quote — the shape that used to be cut mid-sentence
    and then deleted outright by the invented-dialogue cascade."""
    from agents.perception import perception_outcome

    ctx, char_id = _make_ctx(temp_db)
    ctx.director_resolve = {
        "resolved_event": "The stranger speaks.",
        "dialogue_log": [
            {"speaker": "The Stranger",
             "exact_quote": "You held the line, Reya. I saw it. "
                            "Nobody else would have.",
             "volume": "normal"},
        ],
        "state_diff": {},
    }
    out = perception_outcome(ctx, "n0")

    view = out["views"][str(char_id)]
    assert "Nobody else would have." in view, (
        "the tail of a delivered line was cut by a repair pass")


def test_the_invented_dialogue_guard_warns_without_deleting():
    """It removes whole lines, and on this path it has no legitimate work:
    every composed quote was built from `dialogue_log`. So a fire is a bug
    report, not a licence to take the reader's line away."""
    from agents.perception import _composer_tripwires

    class _Ctx:
        def __init__(self):
            self.warnings = []

    ctx = _Ctx()
    view = 'The Stranger says: "A line nobody logged."'
    out = _composer_tripwires(
        ctx, "perception_outcome", "player", "Reya", view,
        {}, [{"name": "Reya", "appearance": "", "aliases": []}],
        spoken_lines=[])

    assert out == view
    assert any("does not match the delivered-line ground truth" in w
               for w in ctx.warnings)


def test_the_identity_tripwire_still_repairs():
    """It substitutes a descriptor for a name outside quoted spans — it
    cannot delete a sentence and cannot touch a delivered line. And what it
    stops is a firewall breach, which must not ship on the strength of a
    warning nobody read."""
    from agents.perception import _composer_tripwires

    class _Ctx:
        def __init__(self):
            self.warnings = []

    ctx = _Ctx()
    out = _composer_tripwires(
        ctx, "perception_act", "1", "Reya",
        "Hinami crosses the floor.", {},
        [{"name": "Reya", "appearance": "", "aliases": []},
         {"name": "Hinami", "appearance": "a fox-eared woman with six tails",
          "aliases": []}])

    assert "Hinami" not in out
    assert any("unearned identity" in w for w in ctx.warnings)
