"""An errand carries the word it was sent with, and the word reaches the
person it was for.

Scratch play 2026-09-14, chat 9: the social hand's errand moved a footman
toward the card room and carried nothing, so nothing he could say on arrival
was the message he was sent with, and the brewer the Room had planted had no
mind to receive it anyway. Now the walker holds the message as a claim its
voice may bring up; `deliver_errands` files it into the addressee's mind when
the two stand together, across charters; the feed says whom the word is for.
"""

import copy
import time

from world.charter import normalize_charter
from world.charter_ops import apply_charter_ops
from world.charter_runtime import deliver_errands


def _registry():
    assembly = normalize_charter({
        "key": "assembly",
        "posts": {"footman": {"place": "landing", "serves": []}},
        "bodies": {"footman:0001": {"name": "Lianw Brabw", "place": "landing",
                                    "berth": "landing", "available": True,
                                    "home_post": "footman"}},
    })
    crown = normalize_charter({
        "key": "crown",
        "posts": {"guest": {"place": "card_room", "serves": []}},
        "bodies": {"josiah_crane:1": {"name": "Josiah Crane", "place": "card_room",
                                      "berth": "card_room", "available": True,
                                      "home_post": "guest"}},
    })
    return {"version": 1, "items": {"assembly": {"state": assembly},
                                    "crown": {"state": crown}}}


MESSAGE = "A lady from Harrow Court asks a word with you in the supper room."


def test_the_walker_holds_the_word_from_dispatch():
    registry = _registry()
    rows = apply_charter_ops(registry, [
        {"op": "errand", "body": "Lianw Brabw", "to": "card_room",
         "purpose": "deliver a message", "message": MESSAGE,
         "addressee": "Josiah Crane", "sender": "the companion"}],
        by="director", turn_idx=7)
    assert rows[0]["result"]["carries"] == MESSAGE
    state = registry["items"]["assembly"]["state"]
    body = state["bodies"]["footman:0001"]
    assert body["errand"]["addressee"] == "Josiah Crane"
    held = state["minds"]["footman:0001"]
    claim = held[body["errand"]["claim_key"]]
    assert claim["public_evidence"]["exact_quote"] == MESSAGE
    assert claim["about"] == "the companion" and claim["provenance"] == "carried_word"


def test_the_word_is_delivered_where_the_two_stand_together():
    registry = _registry()
    apply_charter_ops(registry, [
        {"op": "errand", "body": "Lianw Brabw", "to": "card_room",
         "message": MESSAGE, "addressee": "Josiah Crane", "sender": "the companion"}],
        by="director", turn_idx=7)
    assert deliver_errands(registry) == []          # still on the landing
    body = registry["items"]["assembly"]["state"]["bodies"]["footman:0001"]
    body["place"] = "card_room"; body.pop("walk", None)   # arrived
    delivered = deliver_errands(registry)
    assert [(d["to"], d["message"]) for d in delivered] == [("josiah_crane:1", MESSAGE)]
    crane = registry["items"]["crown"]["state"]["minds"]["josiah_crane:1"]
    claim = next(iter(crane.values()))
    assert claim["public_evidence"]["exact_quote"] == MESSAGE
    assert claim["heard_from"] == "Lianw Brabw"
    assert body["errand"]["delivered_at"] is not None
    assert deliver_errands(registry) == []          # once


def test_the_feed_says_whom_the_word_is_for(temp_db):
    from world.charter_runtime import charter_moves_since, save_registry
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Wendover", "", time.time()))
    registry = _registry()
    apply_charter_ops(registry, [
        {"op": "errand", "body": "Lianw Brabw", "to": "card_room",
         "message": MESSAGE, "addressee": "Josiah Crane", "sender": "the companion"}],
        by="director", turn_idx=7)
    registry["items"]["assembly"]["state"]["bodies"]["footman:0001"]["place"] = "card_room"
    save_registry(cid, registry)
    fed = charter_moves_since(cid, {"card_room"}, {"places": {"Lianw Brabw": "landing"}, "acts": []})
    assert any("came into card_room from landing with word for Josiah Crane" in line
               for line in fed["lines"]), fed["lines"]
