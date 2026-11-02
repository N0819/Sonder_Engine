"""A backdrop is an empty room in every language a story is written in.

Rule 2 of `dressing/backdrops.py`: the one admitted free-text field,
`rooms[id].desc`, is "additionally people-stripped on the way out", because
the "no people" instruction alone is the half the module refuses to rely on.
The strip was English only (dressing audit F1): its person and body word
tables are English, its sentence splitter knew no `。`, so a Japanese room
description naming a body reached the image prompt whole --

    place_desc({'desc': '琥珀色の光とパノラマ窓。...ヒナミがカウンターに寄りかかっている。'})
    -> unchanged;   'ヒナミ' in compose_prompt(room_projection(sc, 'tf')) -> True

-- and a hidden or unperceived occupant named in a description could be
painted. The strip now splits sentences by script, drops a sentence that
names any BODY the scene holds (`scene_names_body`, whole-name matching in
every script), and reads the pronoun recogniser of every installed story
pack beside the English tables.
"""

from __future__ import annotations

from dressing import backdrops
from dressing.backdrops import (compose_prompt, compose_revision, place_desc,
                                room_projection, visual_signature)


def _scene(desc, *, body="ヒナミ", **extra):
    scene = {
        "rooms": {"lounge": {"name": "Lounge", "desc": desc}},
        "positions": {body: "lounge"},
        "entities": {body: {"name": body, "kind": "person"}},
    }
    scene.update(extra)
    return scene


# --- names and pronouns, in both scripts -----------------------------------

def test_a_japanese_sentence_naming_a_body_is_dropped():
    desc = "琥珀色の光とパノラマ窓。ヒナミがカウンターに寄りかかっている。"
    scene = _scene(desc)
    assert place_desc(scene["rooms"]["lounge"], scene) == "琥珀色の光とパノラマ窓。"
    prompt = compose_prompt(room_projection(scene, "lounge"))
    assert "ヒナミ" not in prompt
    assert "琥珀色の光" in prompt


def test_an_english_sentence_naming_a_body_is_dropped_too():
    """The English verb table never held "waits": a name is the class, a verb
    list is one instance of it."""
    desc = "Amber light and panoramic windows. Hinami waits at the counter."
    scene = _scene(desc, body="Hinami")
    assert place_desc(scene["rooms"]["lounge"], scene) == \
        "Amber light and panoramic windows."
    assert "Hinami" not in compose_prompt(room_projection(scene, "lounge"))


def test_a_japanese_given_name_is_a_spelling_of_the_body():
    """A body registered 佐藤ヒナミ is named by either of its script parts."""
    desc = "古い木の床。ヒナミが窓辺に立つ。"
    scene = _scene(desc, body="佐藤ヒナミ")
    assert place_desc(scene["rooms"]["lounge"], scene) == "古い木の床。"


def test_a_pack_pronoun_drops_its_sentence_and_a_lookalike_does_not():
    """彼女 stands for a person; 彼方 ("yonder") only shares a character."""
    scene = _scene("彼女がカウンターに寄りかかっている。地平線の彼方に山が見える。")
    assert place_desc(scene["rooms"]["lounge"], scene) == "地平線の彼方に山が見える。"


def test_a_thing_in_the_scene_is_not_a_body():
    """Only bodies are stripped: the scene's lamp is part of the picture."""
    scene = _scene("A brass lamp hangs low. Dark oak panelling.")
    scene["entities"]["lamp"] = {"name": "brass lamp", "kind": "fixture"}
    scene["positions"]["lamp"] = "lounge"
    assert place_desc(scene["rooms"]["lounge"], scene) == \
        "A brass lamp hangs low. Dark oak panelling."


def test_without_a_scene_the_strip_is_what_it_was_for_english():
    assert place_desc({"desc": "He leans on the bar. Dark oak panelling."}) \
        == "Dark oak panelling."


# --- quotation marks a description really uses ------------------------------

def test_curly_quotes_and_corner_brackets_are_dialogue():
    """`_setting_only`'s quote class repeated the ASCII quote where curly ones
    were meant (dressing audit F22)."""
    out = place_desc({"desc": "A cramped office. “Get out of my office!” "
                              "The window rattles."})
    assert "Get out" not in out
    assert "The window rattles." in out
    out = place_desc({"desc": "狭い事務所。「出て行け！」窓が鳴る。"})
    assert "出て行け" not in out
    assert "窓が鳴る。" in out


# --- a person who gives light is not named in the picture -------------------

def test_a_body_that_emits_light_is_not_a_light_source_by_name():
    """`_light_sources_in` called itself occupant-free and named whoever
    carried `light_source` (dressing audit F4)."""
    scene = _scene("A dim hall.", body="Elowen the Lightbearer")
    scene["entities"]["Elowen the Lightbearer"]["light_source"] = "dim"
    projection = room_projection(scene, "lounge")
    assert not any("Elowen" in str(s) for s in projection.get("light_sources") or [])
    assert "Elowen" not in compose_prompt(projection)


# --- the revision prompt never prints a Python dict -------------------------

def test_an_open_rooms_revision_names_no_dict():
    """`ground` meant the open-room brief's anchors AND a state key, so a
    revision printed `ground: {'n': [{'desc': ...}]}` (dressing audit F9)."""
    scene = {"rooms": {"hilltop": {
        "name": "Bare hilltop", "exposure": "open",
        "anchors": {"cairn": {"desc": "a tumbled stone cairn", "dir": "n",
                              "height": "waist", "footprint": "small"}}}},
        "day_phase": "evening", "time_of_day": "evening"}
    place = room_projection(scene, "hilltop")
    out = compose_revision(place, None, {})
    assert "{'" not in out and "[{" not in out
    assert "ground:" not in out


# --- the hour comes from the day cycle, in any language ---------------------

def test_the_time_bucket_reads_the_canonical_day_phase():
    """`time_bucket('夕方') -> ''`: the free-text label was read through an
    English table while `scene.day_phase` said "evening" (dressing audit
    F11)."""
    from dressing.backdrops import scene_time_bucket

    scene = _scene("古い木の床。", time_of_day="夕方", day_phase="evening")
    assert scene_time_bucket(scene) == "evening"
    assert room_projection(scene, "lounge")["time"] == "evening"
    later = dict(scene, day_phase="midday")
    assert visual_signature(scene, "lounge") != visual_signature(later, "lounge")


def test_the_label_still_answers_when_no_phase_is_kept():
    from dressing.backdrops import scene_time_bucket

    assert scene_time_bucket({"time_of_day": "Late autumn afternoon"}) == "day"
    assert scene_time_bucket({}) == ""


# --- a doorway is the room graph's, from either side ------------------------

def test_exits_are_the_effective_doorways_with_people_stripped():
    """`room_projection.exits` read `room["adjacent"]` alone, raw names and
    all (dressing audit F3): a doorway the neighbour declared was missing and
    a name with a person in it reached the prompt model."""
    scene = {"rooms": {
        "hall": {"name": "Hall", "adjacent": [
            {"to": "cellar", "barrier": "closed_door", "dir": "n",
             "name": "the door she locked behind her"}]},
        "yard": {"name": "Yard", "adjacent": [
            {"to": "hall", "barrier": "open", "dir": "w"}]},
        "cellar": {"name": "Cellar"}}}
    exits = room_projection(scene, "hall")["exits"]
    assert "she" not in repr(exits)
    assert {"barrier": "open", "dir": "e"} in exits
    assert "to" not in repr(exits)


def test_the_light_sources_reader_is_still_the_room_of_record():
    """Unchanged for a thing: a lantern on the table lights the picture."""
    scene = _scene("A dim hall.")
    scene["entities"]["lantern"] = {"name": "storm lantern", "kind": "object",
                                    "light_source": "dim"}
    scene["positions"]["lantern"] = "lounge"
    names = [s["name"] for s in backdrops._light_sources_in(scene, "lounge")]
    assert names == ["storm lantern"]


# --- a possessive names an owner, not someone standing there ----------------

def test_an_owners_name_in_a_possessive_keeps_its_sentence():
    """Measured on the owner's 156 live scenes (2026-11-01): of the 43
    sentences a bare name match newly dropped, 38 named nobody in the frame,
    and most of those were possessives -- "Tamamo's shrine", "the second to
    Hinami's room", "Dr. Crusher's office". A possessive says whose the place
    is; the sentences that put a person in the picture ("Hinami lies
    unconscious on the floor, bleeding.") name the person, not her room."""
    scene = _scene("A narrow wooden hallway. The second shoji opens to "
                   "Hinami's room. Hinami lies unconscious on the floor.",
                   body="Hinami")
    assert place_desc(scene["rooms"]["lounge"], scene) == (
        "A narrow wooden hallway. The second shoji opens to Hinami's room.")


def test_the_strips_body_candidates_are_the_body_predicates_ledgers():
    """`_scene_bodies` reads the body ledgers as candidates and lets
    `scene_names_body` decide; a ledger added there must be read here."""
    from world.spatial_identity import _BODY_LEDGERS

    assert backdrops._BODY_LEDGERS == _BODY_LEDGERS


# --- the name strip fires where the body is the subject -----------------------

KEPT = [
    # Real sentences from the owner's live scenes that the any-mention rule
    # dropped (2026-11-01): the body is named, nobody is in the frame.
    ("Tamamo", "The room smells of old paper, aged wood, incense, silk, "
               "and Tamamo herself."),
    ("Hinami", "Numerous wooden signs display unreadable Lugunican script "
               "that Hinami cannot decipher."),
    ("night clerk", "A narrow back office containing a small desk, a chair "
                    "and a cot where the night clerk had been resting."),
    ("VESPER", "Soundproof reinforced glass over Tethys; a VESPER sensor "
               "blind spot."),
    # The same class in Japanese, where a particle says what a name is doing:
    # の (whose), へ (towards), に (to).
    ("ヒナミ", "窓辺にはヒナミの古い本が積まれている。"),
    ("ヒナミ", "カウンターの奥にヒナミへの手紙がある。"),
]
DROPPED = [
    ("Hinami", "Hinami lies unconscious on the floor, bleeding."),
    ("Hinami", "At the counter, Hinami waits."),
    ("ヒナミ", "ヒナミがカウンターに寄りかかっている。"),
    ("ヒナミ", "奥の席ではヒナミも本を読んでいる。"),
    ("ヒナミ", "ヒナミさんは窓辺に立つ。"),
]


def test_a_body_is_stripped_where_it_is_the_subject_not_wherever_it_is_named():
    """Measured on 156 live scenes (2026-11-01): dropping every sentence that
    names a body dropped 19, and 15 of them put nobody in the frame. Limited
    to a body that is the SUBJECT -- the name opening its sentence or clause
    in a spaced script, a name marked by は/が/も in Japanese -- it drops the
    four that do ("Hinami lies unconscious on the floor, bleeding.") and one
    that does not."""
    for body, sentence in KEPT:
        scene = _scene(sentence, body=body)
        assert place_desc(scene["rooms"]["lounge"], scene) == sentence, sentence
    for body, sentence in DROPPED:
        scene = _scene(sentence + " Dark oak panelling.", body=body)
        assert place_desc(scene["rooms"]["lounge"], scene) == \
            "Dark oak panelling.", sentence
