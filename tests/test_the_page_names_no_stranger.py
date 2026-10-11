"""THE PAGE NAMES NO STRANGER, IN THE DIRECTOR'S OWN WORDS EITHER.

Saltmarsh Crossing (scratch chat 170, 2026-10-11), turns 4 and 5. The player
turned to "the red-faced man at the windlass"; the interpret bound him to the
charter figure he is, and wrote her conduct in the engine's vocabulary --
"looks up toward North Quay, then back at Cortonold Gorleridge". Three
narrator fields carried those words to the page as written: `player_declared`
(its onsets and targets), the player's own acts in `current_events`, and
`spatial_frame.turned`. The page said "Cortonold Gorleridge stood where he had
stood" and "Goddricey took up the mooring line"; nobody had said either name
to her, and her own view called the two men "the middle-aged raw-boned ferry
hand" and "the old square-shouldered ferry hand".
"""

import json
import time

from agents import composer, narration
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import persona_name
from story.scene import persona_of

#: The player of a chat with no persona, as every stage names her.
PLAYER = persona_name(persona_of({"persona_id": None}))
HAND = "Cortonold Gorleridge"
LABEL = "the middle-aged raw-boned ferry hand"


def _act(observable, *, look=None):
    return {"type": "action", "event_id": "turn:3:player:0:action",
            "commitment": "asserted", "visibility": "overt",
            "attempt": observable, "observable": observable, "onset": observable,
            "targets": [HAND], **({"look": look} if look else {})}


def _ctx(temp_db, *, known=None, label=LABEL):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Ferry", "", time.time()))
    scene = {
        "rooms": {"chain_ferry": {"name": "The Chain Ferry", "light": "lit"}},
        "entities": {HAND: {"name": HAND, "kind": "person",
                            "appearance": "raw-boned, iron-grey at the temples"}},
        "positions": {PLAYER: "chain_ferry", HAND: "chain_ferry"},
    }
    temp_db.wset(chat_id, "scene", scene)
    if known:
        temp_db.wset(chat_id, "known", known)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Ferry", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=3,
                      player_input="", created=time.time()),
        cast=[], input="")
    ctx["_player_room"] = "chain_ferry"
    ctx._extra["outcome_scene"] = scene
    view = f"The deck rocks underfoot. {label[0].upper() + label[1:]} leans on the windlass."
    ctx["perception_outcome"] = {
        "views": {"player": view},
        "observations": {"player": [{
            "observation_id": "current:player:0", "channel": "sight",
            "phase": "state", "actor": "", "kind": "action",
            "observed": {"text": view}, "standing": True}]},
        "company": {"player": [{"name": HAND, "label": label, "full": True}]},
    }
    ctx["director_interpret"] = {"sequence": [
        _act(f"looks up toward the quay, then back at {HAND}", look=HAND)]}
    return ctx


def _payload(ctx, monkeypatch):
    seen = {}

    def generate(payload, view, *args, **kwargs):
        seen["payload"] = payload
        return {"prose": "<p>Quiet.</p>", "new_specifics": []}, [], []

    monkeypatch.setattr(narration, "_generate_narration", generate)
    narration.narrator(ctx, "test")
    return seen["payload"]


def test_the_players_own_conduct_calls_a_stranger_what_her_view_does(
        temp_db, monkeypatch):
    payload = _payload(_ctx(temp_db), monkeypatch)
    text = json.dumps(payload)
    for part in ("Cortonold", "Gorleridge"):
        assert part not in text, part
    act = next(e for e in payload["current_events"]
               if e.get("source") == "reconciled_player_action")
    assert act["text"].endswith(f"back at {LABEL}")
    declared = payload["player_declared"]["sequence"][0]
    assert declared["targets"] == [LABEL]
    assert declared["onset"].endswith(f"back at {LABEL}")
    assert payload["spatial_frame"]["turned"]["look"] == LABEL


def test_a_body_she_knows_by_name_keeps_it(temp_db, monkeypatch):
    payload = _payload(_ctx(temp_db, known={PLAYER: [HAND]}, label=HAND),
                       monkeypatch)
    act = next(e for e in payload["current_events"]
               if e.get("source") == "reconciled_player_action")
    assert act["text"].endswith(f"back at {HAND}")
    assert payload["player_declared"]["sequence"][0]["targets"] == [HAND]


def test_a_given_name_alone_is_the_same_body(temp_db, monkeypatch):
    ctx = _ctx(temp_db)
    ctx["director_interpret"] = {"sequence": [
        _act("waits while Cortonold takes up the mooring line")]}
    payload = _payload(ctx, monkeypatch)
    assert "Cortonold" not in json.dumps(payload)
    assert payload["player_declared"]["sequence"][0]["onset"] == (
        f"waits while {LABEL} takes up the mooring line")


def test_the_second_seat_reads_its_own_floor(temp_db, monkeypatch):
    ctx = _ctx(temp_db)
    ctx.extra_players = [{"persona_id": 4, "name": "Companion", "input": ""}]
    stage = ctx["perception_outcome"]
    stage["views"]["extra:4"] = "The deck rocks underfoot."
    stage["observations"]["extra:4"] = []
    stage["company"]["extra:4"] = [{"name": HAND, "label": "the ferry hand",
                                    "full": True}]
    ctx["director_interpret"]["other_players"] = {"4": {"sequence": [
        _act(f"nods to {HAND}")]}}
    captures = []

    def generate(payload, view, *args, **kwargs):
        captures.append(payload)
        return {"prose": "<p>Quiet.</p>", "new_specifics": []}, [], []

    monkeypatch.setattr(narration, "_generate_narration", generate)
    narration.narrator_extra(ctx, "test")
    declared = captures[-1]["player_declared"]["sequence"][0]
    assert declared["onset"] == "nods to the ferry hand"
    assert declared["targets"] == ["the ferry hand"]


def test_a_stranger_with_no_label_is_the_unfamiliar_person(temp_db):
    ctx = _ctx(temp_db)
    scrub = narration._page_identity_scrub(
        ctx, PLAYER, ctx._extra["outcome_scene"], {}, lambda name: None)
    assert scrub(f"looks for {HAND}") == (
        f"looks for {composer._unfamiliar_person()}")


def test_a_disguise_that_hides_who_he_is_makes_an_acquaintance_a_stranger(
        temp_db):
    ctx = _ctx(temp_db)

    def present(name):
        return "the hooded pilgrim" if name == HAND else name

    scrub = narration._page_identity_scrub(
        ctx, PLAYER, ctx._extra["outcome_scene"], {PLAYER: [HAND]},
        present, present=present)
    assert scrub(f"steps toward {HAND}") == "steps toward the hooded pilgrim"
    # Known and undisguised, the same body keeps its name.
    scrub = narration._page_identity_scrub(
        ctx, PLAYER, ctx._extra["outcome_scene"], {PLAYER: [HAND]},
        lambda name: name, present=lambda name: name)
    assert scrub(f"steps toward {HAND}") == f"steps toward {HAND}"


def test_a_spoken_line_is_never_touched(temp_db):
    ctx = _ctx(temp_db)
    scrub = narration._page_identity_scrub(
        ctx, PLAYER, ctx._extra["outcome_scene"], {}, lambda name: LABEL)
    assert scrub(f'calls out "{HAND}!" to the deck') == (
        f'calls out "{HAND}!" to the deck')
