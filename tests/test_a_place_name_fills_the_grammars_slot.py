"""A place code mints is named in the frame the Room's grammar opened.

A structure grammar's name may be a frame with a `{name}` slot. Until
2026-10-08 nothing filled one: `mint_frontier` handed chat 165's frames out
as written -- the axis "the mainland" minted a stub called "the {name}
Sheds", because every frame opened on "the" -- and the rooms the closure
splits off a dwelling took ordinals ("the Back Row 2" .. "5"). Code now
deals a word from the story's own naming lanes into a frame the Room opened
for a kind the place was CHOSEN to be, and only there; a sibling's name
is dealt on the owner's ruling of 2026-10-08 (`DEAL_SIBLING_NAMES`). Review
2026-10-08: a name in kana re-keyed its room to '' (H1), a dealt word could
repeat a resident's (M1), a kind drawn at random was dealt into a name
(M2), a frame matched inside a word (M3), and a purpose's articles and
prepositions asked for a kind (N1)
(`docs/design/DESIGN_CHARTER_PLACES.md` § 5). Hand-made grammars and laws;
the words are illustrations.
"""

from __future__ import annotations

import time

import pytest

from world import place_names
from world.charter_generate import close_plan
from world.charter_identity import (NAME_PREFIX_FLOOR, NAME_SIMILARITY_FLOOR,
                                    identity_reservation, jaro_winkler,
                                    reconstructs_a_reserved_name)
from world.place_names import (deal_place_name, pattern_filler,
                               standing_fillers)
from world.spatial import normalize_room_id
from world.structure import (apply_frontier_mutations, mint_frontier,
                             plant_structure, prepare_frontier_expansion)


#: Chat 165's structure grammar, verbatim from its `world` row.
BRACKWATER = {"key": "brackwater", "max_planned": 40, "grammar": [
    {"kind": "row", "names": ["the {name} Row", "the {name} Houses"],
     "purposes": ["a row of stilt houses on piles, homes opening onto the walk"]},
    {"kind": "shed", "names": ["the {name} Sheds", "the {name} Shed"],
     "purposes": ["a trade shed standing on the walk or the mud"]},
    {"kind": "walk", "names": ["the {name} Walk", "the {name} Way"],
     "purposes": ["a plank walk on piles"]},
    {"kind": "stage", "names": ["the {name} Stage", "the {name} Float"],
     "purposes": ["a trestle stage or float over the water"]},
]}

#: A grammar whose axes can ask for one rule by a word of their own.
FEN = {"key": "fen", "max_planned": 40, "grammar": [
    {"kind": "walk", "names": ["the {name} Walk"], "purposes": ["a plank walk"]},
    {"kind": "stage", "names": ["the {name} Stage"], "purposes": ["a float"]}]}

LANE = {"given_parts": {"starts": ["Ba", "Do", "Ke", "Mo", "Ri"],
                        "ends": ["n", "rk", "lt", "ss", "dd"]},
        "family_parts": {"starts": ["Sal", "Fen", "Hol", "Wic", "Mar"],
                         "middles": ["a", "e", ""],
                         "ends": ["more", "den", "croft", "stead", "wick"]}}

#: A kana law broad enough that a town of thirty named from it leaves words
#: no resident carries (the town's people are refused, review M1).
KANA = {"given_parts": {"starts": ["カ", "サ", "タ", "ミ"],
                        "ends": ["ナ", "ミ", "ロ", "ト"]},
        "family_parts": {"starts": ["ナカ", "ヤマ", "タニ", "イシ", "オオ",
                                    "キタ", "ミナ", "フジ"],
                         "middles": ["", "ノ"],
                         "ends": ["ダ", "モト", "ガワ", "ハラ", "サキ", "ムラ",
                                  "ジマ", "オカ"]}}

MINATO = {"key": "minato", "max_planned": 40, "grammar": [
    {"kind": "道", "names": ["{name}通り"], "purposes": ["板張りの道"]},
    {"kind": "長屋", "names": ["{name}長屋"], "purposes": ["杭の上の長屋"]}]}


def _filler(name, grammar=BRACKWATER):
    found = place_names.instance_of(grammar["grammar"], name)
    return found[1] if found else None


# ---------------------------------------------------------------------------
# The frontier
# ---------------------------------------------------------------------------

def test_a_frame_is_never_a_stubs_name_as_written():
    for axis in ("the mainland", "the fish lanes", "up-river"):
        uid, spec = mint_frontier(BRACKWATER, "causeway", axis, "165:brackwater")
        assert "{" not in spec["name"] and "name" not in uid.split("_"), spec
    uid, spec = mint_frontier(BRACKWATER, "causeway", "the mainland",
                              "165:brackwater", lanes=[LANE])
    # The planner named what lies that way, and its word stands.
    assert (uid, spec["name"]) == ("the_mainland", "The Mainland")


def test_a_later_stretch_is_named_in_the_frame_of_the_rule_its_axis_asked_for():
    first, spec = mint_frontier(FEN, "quay", "far walk", "1:fen")
    assert (first, spec["name"]) == ("far_walk", "Far Walk")
    plain, plain_spec = mint_frontier(FEN, "far_walk", "far walk", "1:fen",
                                      [first])
    assert (plain, plain_spec["name"]) == ("far_walk_2", "Far Walk 2")
    uid, spec = mint_frontier(FEN, "far_walk", "far walk", "1:fen",
                              [first], lanes=[LANE])
    assert pattern_filler("the {name} Walk", spec["name"])
    # A dealt name renames the room and never re-keys it.
    assert uid == "far_walk_2"
    assert spec["purpose"] == plain_spec["purpose"]
    again = mint_frontier(FEN, "far_walk", "far walk", "1:fen",
                          [first], lanes=[LANE])
    assert again == (uid, spec)


def test_a_bare_bearing_is_named_only_where_its_axis_asked_for_the_rule():
    roads = {"key": "fen", "max_planned": 40, "grammar": [
        {"kind": "north road", "names": ["the {name} Road"],
         "purposes": ["the way out of the fen"]},
        {"kind": "walk", "names": ["the {name} Walk"],
         "purposes": ["a plank walk"]}]}
    uid, spec = mint_frontier(roads, "gate", "north", "1:fen", lanes=[LANE])
    assert uid == "north"
    assert pattern_filler("the {name} Road", spec["name"])
    # A bearing a PURPOSE mentions is not a kind the axis asked for: the
    # purpose is prose, and the bearing keeps its label.
    prose = {"key": "fen", "max_planned": 40, "grammar": [
        {"kind": "road", "names": ["the {name} Road"],
         "purposes": ["the north road out of the fen"]},
        {"kind": "walk", "names": ["the {name} Walk"],
         "purposes": ["a plank walk"]}]}
    uid, spec = mint_frontier(prose, "gate", "north", "1:fen", lanes=[LANE])
    assert (uid, spec["name"]) == ("north", "North")
    # Chat 165's grammar says nothing of the north: the rule is a draw, and
    # the bearing keeps its label.
    uid, spec = mint_frontier(BRACKWATER, "causeway", "north",
                              "165:brackwater", lanes=[LANE])
    assert (uid, spec["name"]) == ("north", "North")


def test_a_purposes_prose_never_asks_for_a_kind():
    """Review N1: the ask read every word of a rule, purposes included, so
    on chat 165's own grammar "the far end of the walk" drew the row rule
    by "the", "of" and "walk" (its purpose: "a row of stilt houses ...
    onto the walk") and its second stretch was dealt "the Holawick Row".
    A kind is named by the rule's `kind` and the words its frames do not
    all share; the draw, and so the purpose, does not move."""
    for axis in ("the far end of the walk", "the walk out of town",
                 "the end of the line", "out over the reeds"):
        first, _spec = mint_frontier(BRACKWATER, "causeway", axis,
                                     "165:brackwater", ["causeway"])
        plain = mint_frontier(BRACKWATER, first, axis, "165:brackwater",
                              ["causeway", first])
        uid, spec = mint_frontier(BRACKWATER, first, axis, "165:brackwater",
                                  ["causeway", first], lanes=[LANE])
        assert (uid, spec) == plain, axis
        assert spec["name"] == f"{_spec['name']} 2", axis
    # The words a rule's frames do not all share name its kind: "houses"
    # asks for the row, and the draw agrees.
    first, spec = mint_frontier(BRACKWATER, "causeway", "the fish houses",
                                "165:brackwater", ["causeway"])
    uid, spec = mint_frontier(BRACKWATER, first, "the fish houses",
                              "165:brackwater", ["causeway", first],
                              lanes=[LANE])
    assert uid == "the_fish_houses_2"
    assert (pattern_filler("the {name} Row", spec["name"])
            or pattern_filler("the {name} Houses", spec["name"]))
    # An article only one rule's frame opens on is that frame's scaffolding,
    # not the rule's kind: a one-frame rule is named by its `kind` alone.
    partial = {"key": "row", "max_planned": 40, "grammar": [
        {"kind": "row", "names": ["the {name} Row"], "purposes": ["homes"]},
        {"kind": "lane", "names": ["{name} Lane"], "purposes": ["a lane"]}]}
    uid, spec = mint_frontier(partial, "the_mainland", "the mainland", "1:row",
                              ["the_mainland"], lanes=[LANE])
    assert (uid, spec["name"]) == ("the_mainland_2", "The Mainland 2")


def test_a_kind_drawn_at_random_never_names_a_stretch():
    """Chat 165's "the mainland" shares only its article with the grammar,
    so its rule is a draw (review M2: the mainland ran The Mainland -> "the
    Fennasted Way" -> "the Hollaholm Row"); and two rules that tie are a
    draw too. Either way the ordinal stays."""
    uid, spec = mint_frontier(BRACKWATER, "the_mainland", "the mainland",
                              "165:brackwater", ["the_mainland"], lanes=[LANE])
    assert (uid, spec["name"]) == ("the_mainland_2", "The Mainland 2")
    tied = {"key": "fen", "max_planned": 40, "grammar": [
        {"kind": "row", "names": ["the {name} Row"],
         "purposes": ["houses along the walk"]},
        {"kind": "walk", "names": ["the {name} Walk"], "purposes": ["a walk"]}]}
    uid, spec = mint_frontier(tied, "far_walk", "far walk", "1:fen",
                              ["far_walk"], lanes=[LANE])
    assert (uid, spec["name"]) == ("far_walk_2", "Far Walk 2")


def test_an_article_every_grammar_name_shares_draws_no_name():
    literal = {"key": "row", "max_planned": 40, "grammar": [
        {"kind": "row", "names": ["the Back Row", "the Fish Row"],
         "purposes": ["homes"]},
        {"kind": "walk", "names": ["the Long Walk"], "purposes": ["a walk"]}]}
    uid, spec = mint_frontier(literal, "quay", "the mainland", "1:row")
    assert (uid, spec["name"]) == ("the_mainland", "The Mainland")


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

def test_a_frame_holds_whole_words():
    for pattern, name in (("the {name} Row", "the Sparrow"),
                          ("the {name} Row", "the Barrow"),
                          ("the {name} Row", "Theatre Row"),
                          ("the {name} Shed", "the Woodshed"),
                          ("the {name} Way", "the Causeway")):
        assert pattern_filler(pattern, name) is None, (pattern, name)
    assert pattern_filler("the {name} Row", "the Back Row") == "Back"
    assert pattern_filler("the {name} Row", "THE  back   ROW") == "back"
    # A frame that writes its slot against its text is filled against it.
    assert pattern_filler("{name}長屋", "北長屋") == "北"
    assert pattern_filler("{name}ton", "Fenton") == "Fen"
    # Chat 165's own rooms: "the Causeway" is no "Cause" Way.
    assert standing_fillers(BRACKWATER["grammar"], [
        "the Causeway", "the Back Row", "the Fish Lanes"]) == ["Back"]


# ---------------------------------------------------------------------------
# The closure's siblings
# ---------------------------------------------------------------------------

def _row_plan(house_name, grammar, *, workplace=False, naming=LANE):
    upkeep_place = "house" if workplace else "yard"
    return {
        "name": "Row",
        "structure": {"key": "row", "max_planned": 20, "grammar": grammar},
        "rooms": {
            "lane": {"name": "the Lane", "purpose": "a lane",
                     "adjacent": [{"to": "house"}, {"to": "yard"}]},
            "house": {"name": house_name, "purpose": "homes",
                      "adjacent": [{"to": "lane"}]},
            "yard": {"name": "the Yard", "purpose": "labour",
                     "adjacent": [{"to": "lane"}]},
        },
        "charters": [{
            "key": "yard", "naming": naming,
            "upkeeps": {"stack": {"place": upkeep_place, "floor": 0.3,
                                  "fails_untended": "days",
                                  "one_body_restores_in": "hours"}},
            "posts": {"hand": {"place": upkeep_place, "serves": ["stack"],
                               "requires": {"labour": 1}}},
            "populations": [{"post": "hand", "count": 30,
                             "competence": {"labour": 1}, "berth": "house"}],
        }],
    }


ROWS = [{"kind": "row", "names": ["the {name} Row"], "purposes": ["homes"]}]


def _sibling_names(town, berth="house"):
    return [town["rooms"][uid]["name"]
            for uid in town["closure"]["berths_split"][berth]["rooms"]]


def test_a_sibling_is_named_in_its_parents_frame_on_the_owners_ruling(monkeypatch):
    """The owner ruled on 2026-10-08 that a split dwelling's siblings are
    dealt proper names, over keeping the numbers: each is held apart from
    every resident of the town, as any dealt word is (review M1)."""
    assert place_names.DEAL_SIBLING_NAMES is True
    town = close_plan(_row_plan("the Back Row", ROWS))
    names = _sibling_names(town)
    fillers = [pattern_filler("the {name} Row", name) for name in names]
    assert all(fillers) and "Back" not in fillers
    assert len(set(fillers)) == len(fillers)
    residents = {word for charter in town["charters"].values()
                 for body in charter["bodies"].values()
                 for word in body["name"].split()}
    assert len(residents) > len(names)
    assert not any(jaro_winkler(filler, word) >= NAME_SIMILARITY_FLOOR
                   for filler in fillers for word in residents)
    # The same plan closes to the same names: a reroll renames nobody.
    assert _sibling_names(close_plan(_row_plan("the Back Row", ROWS))) == names
    # Off, the ordinals the closure always gave.
    monkeypatch.setattr(place_names, "DEAL_SIBLING_NAMES", False)
    assert _sibling_names(close_plan(_row_plan("the Back Row", ROWS))) == [
        "the Back Row 2", "the Back Row 3", "the Back Row 4"]


def test_a_dealt_sibling_name_is_held_apart_from_every_resident(monkeypatch):
    """Review M1, at the closure: whichever word the dealer would reach for
    first, a town whose people carry it -- exactly or misheard -- gets
    another, and no sibling's word reads as anybody's who lives there."""
    town = close_plan(_row_plan("the Back Row", ROWS))
    first = pattern_filler("the {name} Row", _sibling_names(town)[0])
    misheard = first + "e"
    assert jaro_winkler(first, misheard) >= NAME_SIMILARITY_FLOOR
    from world import charter_generate
    real = charter_generate.materialize_body_names

    def one_of_them_is_called_so(ckey, bodies, naming, reservation=None):
        named = real(ckey, bodies, naming, reservation)
        body = named[sorted(named)[0]]
        body["name"] = f"Ada {misheard}"
        return named

    monkeypatch.setattr(charter_generate, "materialize_body_names",
                        one_of_them_is_called_so)
    town = close_plan(_row_plan("the Back Row", ROWS))
    assert any(body["name"] == f"Ada {misheard}"
               for charter in town["charters"].values()
               for body in charter["bodies"].values())
    # A law this thin can run out for one of them, and that one keeps its
    # ordinal; none is dealt the resident's word or one that reads as it.
    fillers = [filler for filler in (pattern_filler("the {name} Row", name)
                                     for name in _sibling_names(town))
               if filler]
    assert fillers and first not in fillers
    assert not any(jaro_winkler(filler, misheard) >= NAME_SIMILARITY_FLOOR
                   for filler in fillers)


def test_the_plan_specification_says_what_a_frame_is_only_on_the_owners_word(
        monkeypatch):
    """Review N6: the sentence was live in every location pass with no
    switch, and said the slot was filled where the engine knew the kind --
    false both ways under the defaults it shipped with. Off, the
    specification is the one every pass read before 2026-10-08, and both of
    its readers see the same one."""
    from world import charter_generate
    assert charter_generate.PLAN_EXPLAINS_FRAMES is False
    spec = charter_generate.plan_specification()
    assert spec is charter_generate._PLAN_SYSTEM and "{name}" not in spec
    sent = []
    monkeypatch.setattr(charter_generate, "_json_call",
                        lambda system, payload, **kw: sent.append(system) or {})
    charter_generate.propose_town("lore")
    monkeypatch.setattr(charter_generate, "PLAN_EXPLAINS_FRAMES", True)
    spec = charter_generate.plan_specification()
    assert spec.startswith(charter_generate._PLAN_SYSTEM)
    said = " ".join(spec.split())
    assert "{name}" in spec and "whose label names the kind" in said
    # The bare bearing a frontier is first named by is one of the places the
    # slot is filled, and the Room is told so (review B2).
    assert "a frontier named only by its bearing" in said
    charter_generate.propose_town("lore")
    assert sent == [charter_generate._PLAN_SYSTEM, spec]


def test_where_no_frame_was_opened_the_ordinal_stays():
    assert _sibling_names(close_plan(_row_plan("the House", ROWS))) == [
        "the House 2", "the House 3", "the House 4"]
    # A boarding house whose name ends in the frame's word is no row.
    assert _sibling_names(close_plan(_row_plan("the Sparrow", ROWS))) == [
        "the Sparrow 2", "the Sparrow 3", "the Sparrow 4"]
    # An annex has no kind, so no frame is its own, whatever its workplace
    # is called.
    annexed = close_plan(_row_plan("the Back Row", ROWS, workplace=True))
    split = annexed["closure"]["berths_split"]["house"]
    assert split["mode"] == "annexes"
    assert annexed["rooms"][split["rooms"][0]]["name"] == "the Back Row 2"


# ---------------------------------------------------------------------------
# What a dealt word is held apart from
# ---------------------------------------------------------------------------

def _first(pattern="the {name} Row", **kwargs):
    return pattern_filler(pattern, deal_place_name(
        pattern, scope="row", key="house_2", lanes=[LANE], **kwargs))


def test_a_dealt_place_word_never_names_a_person_the_story_has():
    first = _first()
    reservation = identity_reservation([f"Ada {first}"])
    refused = _first(reservation=reservation)
    assert refused and refused != first
    assert not reconstructs_a_reserved_name(refused, reservation)
    assert jaro_winkler(refused, first) < NAME_SIMILARITY_FLOOR
    # Nor one that reads as a place word already standing.
    echoed = _first(standing=[first])
    assert jaro_winkler(echoed, first) < NAME_SIMILARITY_FLOOR


def test_a_dealt_place_word_never_reads_as_a_residents_name():
    """Review M1: "the Marlaburn Row" was dealt to the room the Marleyburns
    sleep in -- not the same word, the same word misheard."""
    first = _first()
    misheard = first[:-1] + ("a" if first[-1] != "a" else "e")
    assert NAME_SIMILARITY_FLOOR <= jaro_winkler(first, misheard) < 1.0
    for residents in ([first], [misheard]):
        word = _first(residents=residents)
        assert word and word != first
        assert jaro_winkler(word, residents[0]) < NAME_SIMILARITY_FLOOR


def test_a_dealt_place_word_never_opens_like_one_standing():
    """Review L6: "the Drayelburn Row" and "the Drayamere Row" side by side
    are below the similarity floor and still one row misheard."""
    first = _first()
    opener = first[:NAME_PREFIX_FLOOR] + "qqqqq"
    assert jaro_winkler(first, opener) < NAME_SIMILARITY_FLOOR
    word = _first(standing=[opener])
    assert word and word[:NAME_PREFIX_FLOOR] != first[:NAME_PREFIX_FLOOR]


def test_a_name_in_any_script_is_compared_by_its_own_letters():
    """Review H1: every kana name folds to the empty room id, so the closure
    held every candidate taken and a frontier stub was re-keyed to ''."""
    pattern = "{name}長屋"
    dealt = deal_place_name(pattern, scope="minato", key="nagaya_2",
                            lanes=[KANA], taken=["北長屋", "nagaya"])
    assert dealt and pattern_filler(pattern, dealt) and dealt != "北長屋"
    again = deal_place_name(pattern, scope="minato", key="nagaya_2",
                            lanes=[KANA], taken=["北長屋", "nagaya", dealt])
    assert again and again != dealt
    # The frontier: a later stretch is named and keeps its key.
    first, spec = mint_frontier(MINATO, "hatoba", "長屋", "1:minato", ["hatoba"])
    assert (first, spec["name"]) == ("planned_room", "長屋")
    uid, spec = mint_frontier(MINATO, first, "長屋", "1:minato",
                              ["hatoba", first], lanes=[KANA])
    assert uid == "planned_room_2"
    assert pattern_filler(pattern, spec["name"])
    # The closure.
    grammar = [{"kind": "長屋", "names": [pattern, "{name} Nagaya"],
                "purposes": ["長屋"]}]
    names = _sibling_names(close_plan(_row_plan("北長屋", grammar, naming=KANA)))
    assert all(pattern_filler(pattern, name) for name in names)
    assert len(set(names)) == len(names) and "北長屋 2" not in names
    # A frame whose Latin words the room fold keeps folds every kana name
    # it makes to those words alone ("タニダ Nagaya" and "ヤマモト Nagaya"
    # are both `nagaya`), and two rooms that fold alike are one room to the
    # engine: no fold is ever dealt to a second room.
    town = close_plan(_row_plan("Kita Nagaya", grammar, naming=KANA))
    owners = {}
    for uid, room in town["rooms"].items():
        for fold in {uid, normalize_room_id(room["name"])} - {""}:
            owners.setdefault(fold, set()).add(uid)
    assert all(len(rooms) == 1 for rooms in owners.values()), owners


def test_jaro_winkler_is_the_published_measure_at_the_ruled_floor():
    assert NAME_SIMILARITY_FLOOR == 0.88
    assert round(jaro_winkler("MARTHA", "MARHTA"), 3) == 0.961
    assert round(jaro_winkler("DWAYNE", "DUANE"), 2) == 0.84
    assert round(jaro_winkler("DIXON", "DICKSONX"), 3) == 0.813
    assert jaro_winkler("", "Saltwick") == 0.0


# ---------------------------------------------------------------------------
# The frontier, end to end through the commit's own reader
# ---------------------------------------------------------------------------

@pytest.fixture()
def chat(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("A story", "", time.time()))


def _walk_out(temp_db, cid, structure, holder, axis, law):
    """Plant `holder` with one frontier axis under `law`, stand in it, and
    mint the first stretch; returns the scene standing in that stretch."""
    from story.naming import set_authored_naming_profile

    plant_structure(cid, structure, {holder: {
        "name": holder, "purpose": "", "adjacent": [], "frontier": [axis]}})
    set_authored_naming_profile(cid, law)
    scene = {"rooms": {holder: {"name": holder, "adjacent": []}},
             "positions": {"Player": holder}}
    scene, mutations = prepare_frontier_expansion(cid, scene)
    with temp_db.transaction():
        apply_frontier_mutations(cid, None, mutations)
    first = next(m["room_uid"] for m in mutations if m["room_uid"] != holder)
    scene["positions"] = {"Player": first}
    return scene, first


def _next_stretch(cid, scene, first):
    import copy
    _scene, mutations = prepare_frontier_expansion(cid, copy.deepcopy(scene))
    return next(m for m in mutations if m["room_uid"] != first)


@pytest.mark.parametrize("employed", [True, False],
                         ids=["an_institutions_body", "an_unemployed_person"])
def test_the_frontier_holds_a_dealt_word_apart_from_the_towns_people(
        chat, temp_db, employed):
    """Review M1: the frontier mint was passed no residents, so chat 165's
    mainland would mint "the Holensted Walk" with a Holensted asleep in the
    Back Row. The town's people are the charter registry's, wherever it
    keeps them: an institution's own bodies -- every resident of chats
    164-166 is one -- and the people nobody employs (review N4: the test
    pinned only the second, which holds none of them)."""
    scene, first = _walk_out(temp_db, chat, FEN, "quay", "far walk", LANE)
    unscreened = _next_stretch(chat, scene, first)
    word = pattern_filler("the {name} Walk", unscreened["name"])
    assert word and unscreened["room_uid"] == "far_walk_2"
    body = {"name": f"Ada {word}"}
    if employed:
        registry = {"items": {"yard": {"state": {
            "key": "yard", "bodies": {"hand_1": body}}}}}
    else:
        registry = {"items": {}, "people": {"yard/ada": {"bodies": body}}}
    temp_db.wset(chat, "charters", registry)
    from world.charter_runtime import registry_for
    stored = registry_for(chat, None)
    assert bool((stored["items"].get("yard") or {}).get("state", {})
                .get("bodies")) is employed
    assert bool(stored["people"]) is not employed
    screened = _next_stretch(chat, scene, first)
    other = pattern_filler("the {name} Walk", screened["name"])
    assert other and other != word
    assert jaro_winkler(other, word) < NAME_SIMILARITY_FLOOR
    assert screened["room_uid"] == "far_walk_2"


def test_a_stretch_named_in_kana_keeps_its_room_key(chat, temp_db):
    """Review H1, end to end: the registry gained a row keyed '' and the
    holder recorded its axis as spent into it."""
    scene, first = _walk_out(temp_db, chat, MINATO, "hatoba", "長屋", KANA)
    assert first == "planned_room"
    _scene, mutations = prepare_frontier_expansion(chat, scene)
    uids = [m["room_uid"] for m in mutations]
    assert "" not in uids and "planned_room_2" in uids
    stretch = next(m for m in mutations if m["room_uid"] == "planned_room_2")
    assert pattern_filler("{name}長屋", stretch["name"])
    holder = next(m for m in mutations if m["room_uid"] == first)
    assert holder["payload"]["planned"]["frontier_standing"] == {
        "長屋": "planned_room_2"}
    assert "" not in _scene["rooms"]
