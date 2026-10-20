"""An act that happened is seen; only the world refusing it un-sees it.

Chats 175-177 (the owner's play database, reviewed 2026-10-19): declared acts
that DID happen, whose state change landed, were withheld from every observer
as "unexecuted" -- tea poured six times over (175 t3-8), a seat taken (175
t4-5, 176 t2, 177 t16), a tail shaken dry (176 t1: Mellisande never saw it and
came to believe, as certain, that Hinami had apologised), soup ladled, spilt
and eaten (176 t4-6, 177 t16-18), an apron streaked (176 t8), a pot carried to
the table (177 t15). Replayed on the chats' own checkpoints, 54 acts were held
back (66 withheld views across the act and outcome passes), and the
receipt's reasons were three:

* a channel with no verifier read as the world refusing the act
  (`substance_ops`, a wardrobe `conditions` field, `following_ops`);
* the receipt compared the RAW request with the world the merge had
  legitimately normalized -- a fixture in a proximity list, a `null` that the
  merge reads as silence, a chair `support` the station's table overrules, a
  room as what a pose is turned toward, a set-down onto a thing that is not a
  fixture, a fixture whose name another room also uses;
* a write the world holds in a form its ledger cannot carry (a garment or the
  floor underfoot as a contact endpoint) sank the whole span.

Each test below states one rule and its other half: the Doctor stepping onto
a platform that is not there (`test_causal_completion_perception.py`) stays
unseen, and so does every act here whose referent the world does not hold
where the act happens.
"""
from copy import deepcopy

from world.causal_completion import execution_receipt
from world.causal_verification import LEDGER_LIMIT, verify_patch
from world.spatial import merge_scene_with_diff


def _cottage():
    """Chat 177's kitchen, cut down, with chat 175's quirk kept: a second room
    (the mill house) also has a fixture called `table`, so the name alone
    resolves to no room."""
    return {
        "rooms": {
            "kitchen": {"name": "Kitchen",
                        "adjacent": [{"to": "landing", "barrier": "open"}],
                        "anchors": {"table": {}, "chair_1": {}, "chair_2": {},
                                    "hearth": {}}},
            "landing": {"name": "Landing",
                        "adjacent": [{"to": "kitchen", "barrier": "open"},
                                     {"to": "spare_room", "barrier": "closed_door"}]},
            "spare_room": {"name": "Spare Room",
                           "adjacent": [{"to": "landing", "barrier": "closed_door"}]},
            "mill": {"name": "Mill House", "adjacent": [], "anchors": {"table": {}}},
        },
        "positions": {"Mellisande": "kitchen", "Hinami": "kitchen", "Miller": "mill",
                      "kettle": "kitchen", "cups": "kitchen", "pastry_board": "kitchen",
                      "spoon": "kitchen", "bowl": "kitchen", "plate": "kitchen"},
        "entities": {
            "kettle": {"name": "the kettle", "kind": "object", "portable": True},
            "cups": {"name": "two earthenware cups", "kind": "object",
                     "portable": True, "container": True},
            "pastry_board": {"name": "a board of pastries", "kind": "object",
                             "portable": True},
            "spoon": {"name": "a spoon", "kind": "object", "portable": True},
            "bowl": {"name": "a bowl of soup", "kind": "object",
                     "portable": True, "container": True},
            "plate": {"name": "a small plate with a warm scone", "kind": "object",
                      "portable": True, "aliases": ["plate", "scone"],
                      "scent": "warm scone and butter"},
        },
        "stations": {"Mellisande": {"at": "chair_1", "near": ["Hinami"]},
                     "Hinami": {"at": None, "near": ["Mellisande"]}},
        "attire": {"Mellisande": {"wearing": [
            "cream knit sweater", "flour-dusted cotton apron", "silver chain necklace"]},
                   "Hinami": {"wearing": []}},
        "contacts": [], "poses": {}, "substances": [],
    }


def _receipt(patch, before=None):
    before = before if before is not None else _cottage()
    after = merge_scene_with_diff(before, patch)
    return before, after, execution_receipt(before, after, {"patch": patch})


# ---------------------------------------------------------------------------
# A channel with no verifier is a limitation, never the world refusing the act
# ---------------------------------------------------------------------------

def test_tea_poured_into_the_cups_is_seen_and_tea_poured_into_nothing_is_not():
    """Chat 175 turns 3-8: `substance_ops` had no verifier, so every pour was
    held back while the tea stood in the cups. The ledger now vouches for it."""
    pour = {"op": "add", "source": "kettle", "source_part": "spout",
            "substance": "dark tea", "target": "cups", "placement": "contained",
            "amount": "two cups", "amount_band": "moderate"}
    _, after, receipt = _receipt({"substance_ops": [pour]})
    assert after["substances"], "premise: the merge pooled the tea in the cups"
    assert receipt["action_status"] == "applied"
    assert [row["status"] for row in receipt["effects"]] == ["applied"]
    # ...and matter with nowhere to go is still the world refusing it.
    _, _, refused = _receipt({"substance_ops": [
        dict(pour, target="a cup nobody set out")]})
    assert refused["action_status"] == "unresolved"


def test_soup_eaten_out_of_the_bowl_is_seen_and_a_bowl_never_filled_is_not():
    """Chat 177 turn 18: eating removes the bowl's pool by its id."""
    filled = merge_scene_with_diff(_cottage(), {"substance_ops": [{
        "op": "add", "source": "kettle", "substance": "soup", "target": "bowl",
        "placement": "contained"}]})
    pool_id = filled["substances"][0]["substance_id"]
    _, after, receipt = _receipt(
        {"substance_ops": [{"op": "remove", "substance_id": pool_id}]}, before=filled)
    assert not after["substances"]
    assert receipt["action_status"] == "applied"
    _, _, refused = _receipt({"substance_ops": [
        {"op": "remove", "substance_id": "substance:never-minted"}]}, before=filled)
    assert refused["action_status"] == "unresolved"


def test_a_channel_with_no_verifier_never_un_sees_the_act():
    """Chat 175 turn 2: "goes in through the cottage door, following
    Mellisande" -- the walk landed, the follow had no verifier, and the
    act was withheld. No verifier is a limitation: the receipt stays
    `pending` (nothing is claimed) and the act renders."""
    patch = {"positions": {"Hinami": "landing"},
             "following_ops": [{"op": "start", "follower": "Hinami", "target": "Mellisande"}]}
    _, _, receipt = _receipt(patch)
    assert receipt["status"] == "pending"
    assert receipt["action_status"] == "applied"


def test_an_apron_streak_is_seen_and_a_streak_that_never_landed_is_not():
    """Chat 176 turn 8: a wardrobe `conditions` field returned
    "needs a domain-specific verifier" and the wipe down the apron vanished."""
    def wardrobe(condition):
        return {"wearing": ["flour-dusted cotton apron"], "regions": {"torso": {
            "garments": [{"name": "flour-dusted cotton apron", "state": "worn",
                          "condition": condition}]}}}
    before = _cottage()
    before["attire"]["Mellisande"] = wardrobe("flour-dusted")
    after = deepcopy(before)
    streak = "flour-dusted, with a paler wiped streak down the front"
    after["attire"]["Mellisande"] = wardrobe(streak)
    patch = {"attire": {"Mellisande": {"conditions": {"flour-dusted cotton apron": streak}}}}
    assert execution_receipt(before, after, {"patch": patch})["action_status"] == "applied"
    assert [row["status"] for row in verify_patch(before, before, patch)] == ["unresolved"]
    # A wardrobe field with no verifier yet is the ledger's limit, not a refusal.
    coverage = {"attire": {"Mellisande": {"coverage": {"flour-dusted cotton apron": {"torso": ["chest"]}}}}}
    assert execution_receipt(before, before, {"patch": coverage})["action_status"] != "unresolved"


def test_weather_a_span_asks_for_is_the_commits_to_write():
    """Chat 176 turns 4, 7, 10: the scene merge never writes weather -- the
    commit does, from the beat's diff -- so a span's own world could not show
    the rain, and one word outside the vocabulary (`wind: moderate`) refused
    the whole record. The readable part is the commit's to receipt."""
    before = _cottage()
    before["weather"] = {"precipitation": "light rain"}
    _, _, receipt = _receipt({"weather": {"precipitation": "steady rain",
                                          "intensity": "moderate", "wind": "moderate"}},
                             before=before)
    assert receipt["action_status"] != "unresolved"
    assert receipt["effects"][0]["code"] == "pending_commit_domain"
    _, _, unreadable = _receipt({"weather": {"wind": "unreadable"}}, before=before)
    assert unreadable["action_status"] == "unresolved"


# ---------------------------------------------------------------------------
# The verifier judges what the merge made of the request
# ---------------------------------------------------------------------------

def test_a_fixture_another_room_shares_a_name_with_is_the_one_at_hand():
    """Chat 175: the kitchen and the mill house both had a `table`. The merge
    reads a contact's fixture against the room the other endpoint stands in;
    the receipt read the bare name, found two rooms, and refused the act --
    34 contact receipts across 15 acts, every seat and set-down at that table. The substance
    resolver had the same blind spot and threw the matter away."""
    lean = {"op": "add", "actor": "Mellisande", "actor_part": "forearms",
            "target": "table", "target_part": "edge", "manner": "rest",
            "relation": "surface", "motion": "settled"}
    _, after, receipt = _receipt({"contact_ops": [lean]})
    assert any(c.get("target") == "table" for c in after["contacts"])
    assert receipt["action_status"] == "applied"
    _, _, stepped_back = _receipt({"contact_ops": [
        {"op": "remove", "actor": "Mellisande", "target": "table"}]}, before=after)
    assert stepped_back["action_status"] != "unresolved"
    crumbs = {"op": "add", "source": "pastry_board", "substance": "pastry flakes",
              "target": "table", "placement": "surface", "target_part": "top"}
    _, after, receipt = _receipt({"substance_ops": [crumbs]})
    assert [s["target"] for s in after["substances"]] == ["table"]
    assert receipt["action_status"] == "applied"


def test_a_seat_at_the_table_is_judged_as_the_merge_keeps_it():
    """Chat 176 turn 2 / 177 turn 16: `near` holds bodies, so the merge drops
    the table from it -- and the receipt demanded the table back. A body
    named there that stands in another room is still a refusal."""
    patch = {"stations": {"Hinami": {"at": "chair_2", "near": ["Mellisande", "table"]}}}
    _, after, receipt = _receipt(patch)
    assert after["stations"]["Hinami"]["near"] == ["Mellisande"]
    assert receipt["action_status"] == "applied"
    _, _, refused = _receipt({"stations": {"Hinami": {
        "at": "chair_2", "near": ["Mellisande", "Miller"]}}})
    assert refused["action_status"] == "unresolved"


def test_a_null_field_in_a_redeclaration_is_silence_not_a_demand():
    """Chat 176 turn 7: "eats the last of the scone" re-declared the plate
    with `scent: null`; the merge keeps the standing smell (a schema default
    is silence) and the receipt demanded None."""
    patch = {"entities": {"plate": {"name": "an empty small plate",
                                    "description": "A small plate, now empty.",
                                    "aliases": ["plate", "empty plate"], "scent": None}}}
    before, after, receipt = _receipt(patch)
    assert after["entities"]["plate"]["scent"] == "warm scone and butter"
    assert receipt["action_status"] == "applied"
    assert verify_patch(before, before, patch)[0]["status"] == "unresolved"


def test_a_pose_relation_the_ledger_cannot_hold_is_not_a_refusal():
    """Chat 176 turn 8: seated on a chair with her forearms on the table, the
    station is AT the table and the merge empties the chair `support`.
    Chat 177 turns 19-20: a pose turned toward a ROOM (the spare room off
    the landing) has its relation retired -- a room is not a body or a
    fixture. Both are the ledger's limit; a pose turned toward a body in
    another room is still the world refusing it."""
    lean = {"op": "add", "actor": "Mellisande", "actor_part": "forearms",
            "target": "table", "target_part": "edge", "manner": "rest",
            "relation": "surface", "motion": "settled"}
    _, after, receipt = _receipt({"contact_ops": [lean], "poses": {"Mellisande": {
        "posture": "seated", "support": "chair_1", "relative_to": "table",
        "relation": "leaning over", "constraint": "",
        "detail": "leaning forward over the table"}}})
    assert after["poses"]["Mellisande"]["support"] == ""
    assert receipt["action_status"] == "applied"
    _, after, receipt = _receipt({"positions": {"Mellisande": "landing"}, "poses": {
        "Mellisande": {"posture": "standing", "support": "landing",
                       "relative_to": "spare_room", "relation": "at", "constraint": "",
                       "detail": "standing on the landing outside the second room door"}}})
    assert after["poses"]["Mellisande"]["relative_to"] == ""
    assert receipt["action_status"] == "applied"
    _, _, refused = _receipt({"poses": {"Mellisande": {
        "posture": "standing", "relative_to": "Miller", "relation": "facing"}}})
    assert refused["action_status"] == "unresolved"


def test_a_set_down_onto_a_thing_is_where_the_merge_puts_it():
    """Chat 177 turn 18: "sets the spoon down against the rim of the bowl".
    A thing set down on another THING is placed in that thing's room; the
    merge stations it only at a room fixture the thing IS, and the receipt
    demanded a fixture station the merge never writes."""
    before = _cottage()
    before["contained"] = {"spoon": {"in": "Mellisande", "mode": "held"}}
    before["contacts"] = [{"actor": "Mellisande", "actor_part": "hand", "target": "spoon",
                           "target_part": "handle", "manner": "hold",
                           "relation": "surface", "motion": "settled"}]
    patch = {"contact_ops": [
        {"op": "remove", "actor": "Mellisande", "target": "spoon"},
        {"op": "add", "actor": "spoon", "actor_part": "bowl", "target": "bowl",
         "target_part": "rim", "manner": "rest", "relation": "surface",
         "motion": "settled"}],
        "inventory_ops": [{"op": "transfer", "object_id": "spoon",
                           "from_id": "Mellisande", "to_id": "bowl"}]}
    _, after, receipt = _receipt(patch, before=before)
    assert not (after.get("contained") or {}).get("spoon")
    assert receipt["action_status"] == "applied"
    _, _, refused = _receipt({"inventory_ops": [{"op": "transfer", "object_id": "spoon",
                                                 "from_id": "Mellisande",
                                                 "to_id": "a dish nobody set out"}]},
                             before=before)
    assert refused["action_status"] == "unresolved"


# ---------------------------------------------------------------------------
# A write the world holds, in a form its ledger cannot carry
# ---------------------------------------------------------------------------

def test_a_garment_or_the_floor_underfoot_as_a_contact_endpoint_is_the_ledgers_limit():
    """Chat 175 turn 8 (a palm wiped on her own apron), 176 turn 11 (her
    necklace sliding on her collarbone), 177 turn 19 (her feet on the
    landing's floor): the contact ledger relates bodies, things and
    fixtures, so it drops a garment or a room as an endpoint. The world
    holds both right where the act happens; a rag nobody set out it does
    not hold at all, and that act stays refused."""
    wipe = {"op": "add", "actor": "Mellisande", "actor_part": "palm",
            "target": "flour-dusted cotton apron", "target_part": "front",
            "manner": "wipe", "relation": "surface", "motion": "moving"}
    _, _, receipt = _receipt({"contact_ops": [wipe]})
    assert receipt["action_status"] != "unresolved"
    assert [row["code"] for row in receipt["effects"]] == [LEDGER_LIMIT]
    slide = {"op": "add", "actor": "silver chain necklace", "actor_part": "chain",
             "target": "Mellisande", "target_part": "collarbone", "manner": "slide",
             "relation": "surface", "motion": "moving"}
    assert _receipt({"contact_ops": [slide]})[2]["action_status"] != "unresolved"
    climb = {"positions": {"Mellisande": "landing"}, "contact_ops": [
        {"op": "add", "actor": "Mellisande", "actor_part": "feet", "target": "landing",
         "target_part": "floor", "manner": "step", "relation": "surface",
         "motion": "settled"}]}
    assert _receipt(climb)[2]["action_status"] == "applied"
    _, _, refused = _receipt({"contact_ops": [dict(wipe, target="a rag nobody set out")]})
    assert refused["action_status"] == "unresolved"


def test_a_station_written_under_a_things_id_lands_on_the_thing():
    """Chat 177 turn 15, "carries the steaming pot to the kitchen table and
    sets it down on the folded cloth": the towel was positioned under its
    name, `the towel`, and the beat stationed it under its id. The subject
    fold kept the older record under the name and discarded the beat's own
    write, so the towel was never at the table. The fresh write wins, as it
    does for `positions` (`_dedup_duplicate_position_keys`)."""
    before = _cottage()
    before["entities"]["4a0a2b811bcc43e1"] = {"name": "the towel", "kind": "object",
                                              "portable": True}
    before["positions"]["the towel"] = "kitchen"
    before["stations"]["the towel"] = {"at": None, "near": ["Mellisande"]}
    before["stations"]["Mellisande"]["near"].append("the towel")
    _, after, receipt = _receipt(
        {"stations": {"4a0a2b811bcc43e1": {"at": "table", "near": []}}}, before=before)
    assert after["stations"]["the towel"]["at"] == "table"
    assert "4a0a2b811bcc43e1" not in after["stations"]
    assert receipt["action_status"] == "applied"


def test_a_body_stood_near_a_thing_by_its_id_stays_near_it():
    """The same beat stood Mellisande `near` the towel by its id. A station's
    `near` names beings, and the subject fold left it out, so the id failed
    the positions test and the link was dropped from both of them -- the
    receipt then held the act back for the near-link it had asked for."""
    before = _cottage()
    before["entities"]["4a0a2b811bcc43e1"] = {"name": "the towel", "kind": "object",
                                              "portable": True}
    before["positions"]["the towel"] = "kitchen"
    before["stations"]["the towel"] = {"at": None, "near": []}
    _, after, receipt = _receipt({"stations": {
        "Mellisande": {"at": "table", "near": ["Hinami", "4a0a2b811bcc43e1"]}}}, before=before)
    assert "the towel" in after["stations"]["Mellisande"]["near"]
    assert "Mellisande" in after["stations"]["the towel"]["near"]
    assert receipt["action_status"] == "applied"
