"""An AI-reinterpreted lorebook keeps every structural fact of its source.

The import recovers a book's tree from its titles -- title, `[›]` parent,
knowledge tag, range and locations, importance -- and keyed that structure by
the first 120 casefolded characters of each SOURCE entry's text. The AI
rewrite (the import dialog's default) then looked each REWRITTEN entry up by
the same key, exactly. `lore_reinterpret` asks the model to rewrite, merge
and split, so the better the rewrite the more was lost: every rephrased
opening landed with no title, no parent link and no knowledge tag -- and an
entry with no tag reaches no mind (`add_lore`: "Director-only"). Both halves
of a split entry lost it too, although `_structure_key`'s docstring says they
legitimately inherit it. And a source `constant` entry was rewritten and
stored unlocked (story_attire_import audit F6; the lane brief's F2).

The structure now travels with the SOURCE POSITION each rewritten entry came
from -- the same position when the batch came back one-for-one, otherwise the
source in its own batch it shares the most distinctive words with -- and a
locked entry is never sent to the rewrite at all.
"""

from __future__ import annotations

import json

from story import importers


SOURCES = [
    ("═══════[World]═══════", "", [], False),
    ("[«»] World History [«»]",
     "The world was remade after the witch's calamity four centuries ago.",
     ["world history"], False),
    ("[›] Great Calamity",
     "The Great Calamity was the witch's rampage that devoured half the "
     "continent.", ["calamity"], False),
    ("⚲────↓Kingdom Locations↓────⚲", "", [], False),
    ("[🏰] Dragon Kingdom of Lugunica [🏰]",
     "Lugunica is a kingdom bound to a dragon by an ancient covenant.",
     ["Lugunica"], False),
    ("[›] Lugunica Currency",
     "Lugunica mints holy gold coins, silver coins and copper coins.",
     ["currency"], False),
    ("═══════[Abilities]═══════", "", [], False),
    ("[⚖️]────↓Authority↓────[⚖️]", "", [], False),
    ("[›] Authority of Sloth",
     "The Authority of Sloth lets its bearer move unseen hands.",
     ["sloth"], True),
]

REWRITES = {
    "The world was remade": [{
        "keys": "world, remade", "category": "event",
        "content": "Four centuries ago, after the witch's calamity, the world "
                   "was remade."}],
    "The Great Calamity was": [{
        "keys": "great calamity", "category": "event",
        "content": "The witch's rampage, called the Great Calamity, devoured "
                   "half the continent."}],
    "Lugunica is a kingdom": [{
        "keys": "lugunica, covenant", "category": "location",
        "content": "An ancient covenant binds the kingdom of Lugunica to a "
                   "dragon."}],
    "Lugunica mints": [
        {"keys": "holy gold coin", "category": "mechanic",
         "content": "Holy gold coins are the highest currency Lugunica "
                    "mints."},
        {"keys": "silver coin, copper coin", "category": "mechanic",
         "content": "Silver and copper coins are the everyday currency "
                    "Lugunica mints."}],
}


def _book():
    return {"entries": {str(i): {"uid": i, "displayIndex": i, "comment": c,
                                 "content": body, "key": keys,
                                 "constant": constant}
                        for i, (c, body, keys, constant)
                        in enumerate(SOURCES)}}


def _import(temp_db, monkeypatch, rewrite):
    sent = []

    def fake(role, system, payload, **kwargs):
        batch = json.loads(payload)
        sent.extend(batch)
        return json.dumps({"entries": rewrite(batch)})

    monkeypatch.setattr(importers, "chat_complete", fake)
    lb, _n = importers.import_lorebook(_book(), name="tree", reinterpret=True)
    rows = temp_db.q("SELECT * FROM lore_entries WHERE lorebook_id=?", (lb,))
    return rows, sent


def _split_rewrite(batch):
    out = []
    for entry in batch:
        for prefix, rewrites in REWRITES.items():
            if entry["content"].startswith(prefix):
                out.extend(rewrites)
    return out


def test_a_rewrite_that_rephrases_and_splits_keeps_every_title(
        temp_db, monkeypatch):
    rows, _sent = _import(temp_db, monkeypatch, _split_rewrite)
    assert len(rows) == 6
    assert all(r["title"] for r in rows), [r["content"] for r in rows
                                           if not r["title"]]
    assert all(r["knowledge_tag"] for r in rows)


def test_both_halves_of_a_split_entry_are_local_knowledge(temp_db, monkeypatch):
    rows, _sent = _import(temp_db, monkeypatch, _split_rewrite)
    coins = [r for r in rows if "coins" in r["content"]]
    assert len(coins) == 2
    for row in coins:
        assert row["title"] == "Lugunica Currency"
        assert row["knowledge_range"] == "local"
        assert "Dragon Kingdom of Lugunica" in (row["knowledge_locations"]
                                                or "")


def test_the_parent_links_survive_the_rewrite(temp_db, monkeypatch):
    rows, _sent = _import(temp_db, monkeypatch, _split_rewrite)
    by_id = {r["id"]: r for r in rows}
    calamity = next(r for r in rows if r["title"] == "Great Calamity")
    parents = json.loads(calamity["relations"])["refines_entry_ids"]
    assert by_id[parents[0]]["title"] == "World History"


def test_a_constant_entry_is_never_rewritten_and_stays_locked(
        temp_db, monkeypatch):
    rows, sent = _import(temp_db, monkeypatch, _split_rewrite)
    assert not any("Sloth" in e["content"] for e in sent)
    sloth = next(r for r in rows if "Sloth" in r["content"])
    assert sloth["canon_locked"] == 1
    assert sloth["content"] == SOURCES[8][1]
    assert sloth["title"] == "Authority of Sloth"
    assert sloth["knowledge_tag"] == "esoteric"


def test_a_one_for_one_rewrite_is_matched_by_position(temp_db, monkeypatch):
    """A batch that comes back entry for entry carries each source's
    structure by position, even when the rewrite shares no opening and no
    keys with it."""
    def rename(batch):
        return [{"keys": "entry %d" % n, "category": "other",
                 "content": "Rewritten passage number %d." % n}
                for n, _e in enumerate(batch)]
    rows, _sent = _import(temp_db, monkeypatch, rename)
    titles = sorted(r["title"] for r in rows if not r["canon_locked"])
    assert titles == sorted(["World History", "Great Calamity",
                             "Dragon Kingdom of Lugunica",
                             "Lugunica Currency"])
