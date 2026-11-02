"""A room write answers with the record the next read reads, list for list.

The World Browser writes a room's exits, anchors and parts as WHOLE lists,
and since the 2026-11-01 audit (`frontend_settings_world` F2) it writes one
only after reading the room again and finding the list it edited from
unchanged (`static/js/world_browser.js`, `wbPatchRoomList`; the attire
editor asks the same of the ledger). The card it edits from is very often
the one a previous write's ANSWER drew (`ctx.replaceCard(fresh)`), so the
check is only a check if the answer of `PATCH /rooms/{id}` and a following
`GET /rooms/{id}` say the same thing, byte for byte, about every list --
the same keys in the same order. If they ever disagree, every second edit
on the card is refused as "changed since the card was drawn" when nothing
changed at all. This pins that contract on the real routes.
"""

from __future__ import annotations

import json

from test_world_routes import client, story  # noqa: F401  (fixtures)


def _lists(slice_):
    record = slice_["record"]
    return {name: json.dumps(record[key])
            for name, key in (("exits", "adjacent"), ("anchors", "anchors"),
                              ("parts", "parts"))}


def test_each_list_write_answers_what_the_next_read_reads(client, story):  # noqa: F811
    cid = story["chat_id"]
    url = f"/api/chats/{cid}/rooms/kitchen"
    first = client.get(url).json()

    # An exit added with a bearing, the standing ones sent back as the card
    # sends them (`asExit`: to, barrier, dir).
    exits = [{"to": e["to"], "barrier": e.get("barrier") or "", "dir": e.get("dir") or ""}
             for e in first["record"]["adjacent"]]
    exits.append({"to": "garden", "barrier": "closed_door", "dir": "s"})
    answer = client.patch(url, json={"exits": exits})
    assert answer.status_code == 200, answer.text
    assert _lists(answer.json()) == _lists(client.get(url).json())

    # The anchor map, with every geometry word, a wall place and a pinned cell.
    answer = client.patch(url, json={"anchors": {
        "hearth": {"desc": "the hearth", "dir": "w", "height": "waist",
                   "footprint": "small", "offset": 0.5},
        "oak_table": {"desc": "the oak table", "cell": [2, 2]}}})
    assert answer.status_code == 200, answer.text
    assert _lists(answer.json()) == _lists(client.get(url).json())

    # An L's parts under a measured box.
    answer = client.patch(url, json={"extent": {"w": 8, "d": 6}, "shape": "l",
                                     "parts": [{"w": 8, "d": 3, "at": "nw"},
                                               {"w": 3, "d": 6, "at": "nw"}]})
    assert answer.status_code == 200, answer.text
    assert _lists(answer.json()) == _lists(client.get(url).json())

    # The card is redrawn from the doorways route's answer too (a door's
    # description, material, width), which mints the passage record.
    answer = client.patch(f"/api/chats/{cid}/doorways/kitchen/hallway",
                          json={"desc": "a stone arch", "width": 2})
    assert answer.status_code == 200, answer.text
    assert _lists(answer.json()["slice"]) == _lists(client.get(url).json())


def test_an_attire_write_is_read_back_as_the_index_hands_it_over(client, story):  # noqa: F811
    """The attire editor draws a body from the index (`body_rows`) and checks
    it against `GET /attire` before it writes: the two must hand over the
    same entry for the same body."""
    cid = story["chat_id"]
    entry = {"wearing": ["apron"], "state": [],
             "regions": {"torso": {"garments": [{"name": "apron", "state": "loosened",
                                                 "condition": "floury"}],
                                   "beneath": ""}}}
    assert client.put(f"/api/chats/{cid}/attire", json={"Alice": entry}).status_code == 200
    index = client.get(f"/api/chats/{cid}/rooms").json()
    drawn = next(b for b in index["bodies"] if b["name"] == "Alice")["attire"]
    ledger = client.get(f"/api/chats/{cid}/attire").json()
    assert json.dumps(drawn) == json.dumps(ledger["Alice"])
