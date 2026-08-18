"""The read-only story facade, and the player-safe projection of it.

Two reads with different jobs. `story_view` is canonical -- what is true --
and exists so a campaign layer, an authoring tool or a panel can derive its
own answers without importing an engine module or opening the database. That
is not a firewall breach: the firewall constrains what reaches a fictional
MIND, and none of those readers is one.

`player_view` is the boundary. Its correctness property is not "returns the
right fields" but "cannot return a fact this person does not have", and the
way it earns that is by NOT deciding: every section is something the engine
already delivered to that viewer. The tests below are mostly about that --
about what is absent, and about the projection having no opinion of its own.
"""

from __future__ import annotations

import json
import time

import pytest

import story_view
from story_view import STORY_VIEW_SCHEMA, player_view, viewers

from tests.test_extensions import _character, _chat, _turn


@pytest.fixture
def story(temp_db):
    """A chat with a scene, a turn, a cast and one delivered perception step."""
    from db import wset

    chat_id = _chat(temp_db, "Facade")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Sam", json.dumps({"name": "Sam"})))
    temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?", (persona_id, chat_id))
    char_id = _character(temp_db, chat_id, "Ilse", "uid-ilse", state=json.dumps(
        {"relationships": {"Sam": {"trust": 0.4}}}))
    wset(chat_id, "scene", {
        "location": "the observatory",
        "time": "late",
        "rooms": {"dome": {"name": "The Dome"}, "vault": {"name": "The Vault"}},
        "positions": {"Sam": "dome", "Ilse": "vault"},
        "entities": {},
    })
    turn_id = _turn(temp_db, chat_id, idx=4)
    return {"chat_id": chat_id, "char_id": char_id, "persona_id": persona_id,
            "turn_id": turn_id}


def _deliver(temp_db, turn_id, views, observations=None, company=None,
             key="perception_outcome"):
    """Store one perception step the way the pipeline stores it."""
    content = {"views": views, "observations": observations or {}}
    if company is not None:
        content["company"] = company
    step_id = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
        (turn_id, key, key, 3))
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
        (step_id, json.dumps(content), time.time()))
    return step_id


def _author_public(temp_db, char_id, *, appearance=None, history=None,
                   name=None):
    """Edit the card's genuinely public surfaces, and only those."""
    row = temp_db.q("SELECT sheet FROM characters WHERE id=?", (char_id,),
                    one=True)
    sheet = json.loads(row["sheet"])
    if appearance is not None:
        sheet.setdefault("embodiment", {}).setdefault(
            "visible", {})["summary"] = appearance
    if history is not None:
        sheet.setdefault("knowledge", {})["public_history"] = history
    if name is not None:
        sheet.setdefault("identity", {})["name"] = name
    temp_db.qi("UPDATE characters SET sheet=? WHERE id=?",
               (json.dumps(sheet), char_id))
    return sheet


# --------------------------------------------------------------- canonical


class TestStoryView:
    def test_it_answers_the_questions_a_campaign_layer_asks(self, temp_db, story):
        view = story_view.story_view(story["chat_id"])

        assert view["schema"] == STORY_VIEW_SCHEMA
        assert view["story"]["chat_id"] == story["chat_id"]
        assert view["turn"]["idx"] == 4
        assert view["scene"]["location"] == "the observatory"
        assert view["scene"]["positions"] == {"Sam": "dome", "Ilse": "vault"}
        assert view["player"]["name"] == "Sam"
        assert view["clock"] is not None

    def test_the_cast_carries_stable_ids(self, temp_db, story):
        """A UI selection keyed on a display name breaks the first time
        somebody is renamed -- and in this engine the STORY renames people, not
        only the author: a stranger becomes a name the moment they are known."""
        view = story_view.story_view(story["chat_id"])

        assert view["cast"] == [
            {"char_id": story["char_id"], "status": "active", "name": "Ilse"}]

    def test_it_returns_plain_serialisable_values(self, temp_db, story):
        """A caller handed the engine's own objects inherits every future
        change to them, which is the thing a facade exists to prevent."""
        view = story_view.story_view(story["chat_id"])

        assert json.loads(json.dumps(view))["schema"] == STORY_VIEW_SCHEMA

    def test_mutating_the_result_cannot_reach_the_story(self, temp_db, story):
        from scene import get_scene

        view = story_view.story_view(story["chat_id"])
        view["scene"]["positions"]["Sam"] = "vault"

        assert get_scene(story["chat_id"])["positions"]["Sam"] == "dome"

    def test_it_carries_the_player_authority_mode(self, temp_db, story):
        """Which rung the story is on changes what a declaration MEANS, so a
        campaign that adjudicates player intent has to be able to read it."""
        from scene import set_player_authority

        set_player_authority(story["chat_id"], "actor_only", turn_idx=4)
        view = story_view.story_view(story["chat_id"])

        assert view["player_authority"]["mode"] == "actor_only"

    def test_events_are_bounded_and_oldest_first(self, temp_db, story):
        for n in range(5):
            temp_db.qi(
                "INSERT INTO world_events(event_id,chat_id,occurred_at,kind,"
                "payload,committed) VALUES(?,?,?,?,?,?)",
                (f"e{n}", story["chat_id"], float(n), "move", "{}", time.time()))

        view = story_view.story_view(story["chat_id"], events=3)

        assert [e["event_id"] for e in view["events"]] == ["e2", "e3", "e4"]

    def test_an_absurd_event_limit_is_capped_rather_than_obeyed(self, temp_db,
                                                                story):
        """This is a per-render read from a UI; an unbounded history turns a
        panel refresh into a scan of the whole story."""
        view = story_view.story_view(story["chat_id"], events=10 ** 9)

        assert view["events"] == []

    def test_an_unknown_chat_is_refused_rather_than_answered_emptily(
            self, temp_db):
        with pytest.raises(ValueError):
            story_view.story_view(999999)


# ------------------------------------------------------------ the boundary


class TestPlayerView:
    def test_it_returns_what_the_engine_delivered_to_that_viewer(self, temp_db,
                                                                 story):
        _deliver(temp_db, story["turn_id"],
                 {"player": "The dome is dark.", str(story["char_id"]):
                  "The vault door is shut."},
                 {"player": [{"kind": "environment"}]})

        view = player_view(story["chat_id"], "player")

        assert view["perception"]["view"] == "The dome is dark."
        assert view["perception"]["observations"] == [{"kind": "environment"}]
        assert view["perception"]["stage"] == "perception_outcome"

    def test_two_viewers_receive_different_knowledge(self, temp_db, story):
        """The report's acceptance test, and the whole reason this is not a
        filter written in the campaign layer."""
        _deliver(temp_db, story["turn_id"],
                 {"player": "The dome is dark.",
                  str(story["char_id"]): "The vault door is shut."})

        assert (player_view(story["chat_id"], "player")["perception"]["view"]
                != player_view(story["chat_id"], str(story["char_id"]))
                ["perception"]["view"])

    def test_a_secret_in_one_view_is_absent_from_the_other(self, temp_db,
                                                            story):
        _deliver(temp_db, story["turn_id"],
                 {str(story["char_id"]): "The vault holds the second key.",
                  "player": "The dome is dark."})

        rendered = json.dumps(player_view(story["chat_id"], "player"))

        assert "second key" not in rendered

    def test_a_viewer_with_no_delivered_view_has_no_perception_key(
            self, temp_db, story):
        """Absent means ABSENT. An empty string or a placeholder would be a
        claim that the engine looked and found nothing, which is a different
        fact from never having been asked."""
        view = player_view(story["chat_id"], "player")

        assert "perception" not in view

    def test_it_never_falls_back_to_another_viewers_view(self, temp_db, story):
        """The cheapest possible leak, and the one a 'sensible default' makes."""
        _deliver(temp_db, story["turn_id"],
                 {str(story["char_id"]): "The vault holds the second key."})

        view = player_view(story["chat_id"], "player")

        assert "perception" not in view

    def test_the_outcome_view_wins_over_the_act_view(self, temp_db, story):
        """`perception_act` is mid-beat and a later stage may have corrected
        it; showing it is showing something the story no longer says."""
        _deliver(temp_db, story["turn_id"], {"player": "Mid-beat."},
                 key="perception_act")
        _deliver(temp_db, story["turn_id"], {"player": "Settled."},
                 key="perception_outcome")

        assert player_view(story["chat_id"])["perception"]["view"] == "Settled."

    def test_a_body_knows_where_it_is(self, temp_db, story):
        view = player_view(story["chat_id"], "player")

        assert view["location"] == {"room_id": "dome", "name": "The Dome"}

    def test_the_identity_ledger_is_the_authority_on_who_can_be_named(
            self, temp_db, story):
        """Not the cast list. A body a viewer can SEE but cannot name is in
        their observations under whatever label the composer gave it, and is
        deliberately not resolved to a name here."""
        from db import wset

        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})

        assert player_view(story["chat_id"], "player")["knows"] == ["Ilse"]
        assert "knows" not in player_view(
            story["chat_id"], str(story["char_id"]))

    def test_a_character_receives_their_own_relationships_and_memories(
            self, temp_db, story):
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
            "provenance,content,gist) VALUES(?,?,?,?,?,?,?,?)",
            (story["chat_id"], story["char_id"], 3, "episodic", "episode",
             "witnessed", "The vault door shut.", "the door shut"))

        view = player_view(story["chat_id"], str(story["char_id"]))

        assert view["relationships"] == {"Sam": {"trust": 0.4}}
        assert view["memories"][0]["gist"] == "the door shut"

    def test_a_memory_carries_the_engines_own_epistemic_vocabulary(
            self, temp_db, story):
        """`what_i_experienced` / `what_i_was_told` / `what_i_concluded` --
        the labels the character's own context already uses. Inventing a
        second provenance vocabulary here would give the same fact two names."""
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
            "provenance,content,gist) VALUES(?,?,?,?,?,?,?,?)",
            (story["chat_id"], story["char_id"], 3, "inference", "inference",
             "inferred", "She is lying.", "she is lying"))

        view = player_view(story["chat_id"], str(story["char_id"]))

        assert view["memories"][0]["epistemic_origin"] == "what_i_concluded"

    def test_one_minds_memories_cannot_reach_another(self, temp_db, story):
        other_id = _character(temp_db, story["chat_id"], "Ruth", "uid-ruth")
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
            "provenance,content,gist) VALUES(?,?,?,?,?,?,?,?)",
            (story["chat_id"], other_id, 3, "episodic", "episode",
             "witnessed", "Ruth saw the combination.", "the combination"))

        view = player_view(story["chat_id"], str(story["char_id"]))

        assert "memories" not in view

    def test_the_player_receives_no_character_psychology(self, temp_db, story):
        """The player is not a mind this engine simulates, and a projection
        that handed them relationship scores would be handing them the
        machinery rather than the story."""
        view = player_view(story["chat_id"], "player")

        assert "relationships" not in view
        assert "memories" not in view

    def test_an_unknown_viewer_is_refused_rather_than_guessed(self, temp_db,
                                                              story):
        with pytest.raises(ValueError):
            player_view(story["chat_id"], "Ilse")

    def test_viewers_lists_the_ids_that_are_accepted(self, temp_db, story):
        """A caller must never have to guess the spelling of the thing it is
        about to ask for -- perception keys the player `"player"` and a
        character by numeric id, which is not discoverable by inspection."""
        listed = viewers(story["chat_id"])

        assert listed == [
            {"id": "player", "name": "Sam", "kind": "player"},
            {"id": str(story["char_id"]), "name": "Ilse", "kind": "character"},
        ]
        for entry in listed:
            assert player_view(story["chat_id"], entry["id"])["viewer"] == entry


class TestPeople:
    """`player_view["people"]` -- the structured roster, still deciding
    nothing. Its two admissions are the identity ledger and the perception
    stage's own delivered-company record; every test here is about one of
    those being the ONLY authority, because the failure this projection
    invites is a UI-friendly join that quietly re-implements disclosure."""

    def test_a_known_person_carries_a_stable_id_and_public_facts(
            self, temp_db, story):
        """The Directive report's core acceptance test: a crew UI can key on
        `id` and render host-owned public facts without joining canonical
        cast data to known-name strings."""
        from db import wset

        _author_public(temp_db, story["char_id"],
                       appearance="a silver-haired astronomer in a long coat",
                       history="Keeper of the observatory for thirty years.")
        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})

        view = player_view(story["chat_id"], "player")

        person, = view["people"]
        assert person["id"] == str(story["char_id"])
        assert person["kind"] == "character"
        assert person["display_name"] == "Ilse"
        assert person["identity_status"] == "recognized"
        assert person["facts"] == {
            "appearance": "a silver-haired astronomer in a long coat",
            "public_history": "Keeper of the observatory for thirty years.",
        }
        assert person["fact_sources"] == {
            "appearance": "authored_public",
            "public_history": "authored_public",
        }

    def test_a_rename_changes_display_name_and_never_id(self, temp_db, story):
        """A UI keyed on a display name breaks the first time somebody is
        renamed, and in this engine the STORY renames people. The id must
        not be derived from the label."""
        from db import wset

        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})
        before, = player_view(story["chat_id"], "player")["people"]

        _author_public(temp_db, story["char_id"], name="Countess Ilse")
        wset(story["chat_id"], "known", {"Sam": ["Countess Ilse"]})
        after, = player_view(story["chat_id"], "player")["people"]

        assert before["display_name"] == "Ilse"
        assert after["display_name"] == "Countess Ilse"
        assert after["id"] == before["id"] == str(story["char_id"])

    def test_a_stranger_appears_under_a_label_and_leaks_no_canonical_name(
            self, temp_db, story):
        """The label is the composer's, the key is opaque, and the canonical
        name and canonical id appear NOWHERE in the serialised view -- a
        stranger entry that carried either would hand a joining UI the
        identity the viewer has not earned."""
        ruth_id = _character(temp_db, story["chat_id"], "Ruth", "uid-ruth")
        _deliver(temp_db, story["turn_id"], {"player": "Someone is here."},
                 company={"player": [
                     {"key": "ab12cd34ef", "name": "Ruth",
                      "label": "the grey-eyed courier", "recognized": False}]})

        view = player_view(story["chat_id"], "player")

        person, = view["people"]
        assert person == {"id": person["id"], "kind": "presence",
                          "display_name": "the grey-eyed courier",
                          "identity_status": "observed",
                          "last_observed_turn": 4}
        assert person["id"].startswith("body:")
        # Not the composer's own ledger key either: that key is a canonical-
        # name hash shared by every viewer, i.e. a correlation handle.
        assert person["id"] != "body:ab12cd34ef"
        assert "Ruth" not in json.dumps(view)
        assert str(ruth_id) not in [p["id"] for p in view["people"]]

    def test_a_person_neither_known_nor_delivered_is_absent(self, temp_db,
                                                            story):
        """Absent means absent: this projection has no opinion of its own
        about who exists. A cast member the viewer never met and never saw
        would only appear here through a deduction, which is the one thing
        the facade is forbidden to make."""
        _character(temp_db, story["chat_id"], "Ruth", "uid-ruth")

        view = player_view(story["chat_id"], "player")

        assert "people" not in view

    def test_the_composers_verdict_outranks_the_ledger_on_a_disguised_body(
            self, temp_db, story):
        """`recognized` is the delivery record's verdict, never re-derived
        from the identity ledger -- a disguise that conceals identity makes a
        well-known name a stranger, and a ledger re-check here would undo the
        disguise. The two entries of a disguised acquaintance deliberately do
        not join."""
        from db import wset

        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})
        _deliver(temp_db, story["turn_id"], {"player": "A veiled figure."},
                 company={"player": [
                     {"key": "dd11", "name": "Ilse",
                      "label": "the veiled figure", "recognized": False}]})

        view = player_view(story["chat_id"], "player")

        by_status = {p["identity_status"]: p for p in view["people"]}
        assert by_status["recognized"]["id"] == str(story["char_id"])
        assert "last_observed_turn" not in by_status["recognized"]
        assert by_status["observed"]["id"].startswith("body:")
        assert by_status["observed"]["id"] != by_status["recognized"]["id"]
        assert by_status["observed"]["display_name"] == "the veiled figure"

    def test_a_recognised_body_delivered_this_beat_dates_the_entry(
            self, temp_db, story):
        from db import wset

        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})
        _deliver(temp_db, story["turn_id"], {"player": "Ilse is here."},
                 company={"player": [
                     {"key": "ee22", "name": "Ilse", "label": "Ilse",
                      "recognized": True}]})

        person, = player_view(story["chat_id"], "player")["people"]

        assert person["id"] == str(story["char_id"])
        assert person["last_observed_turn"] == 4

    def test_missing_public_fields_stay_absent(self, temp_db, story):
        """No `facts: {}`, no `facts: null`: a UI cannot tell an empty claim
        from a missing one, and an empty dict invites a renderer to fill the
        gap with a default of its own."""
        from db import wset

        _author_public(temp_db, story["char_id"], appearance="", history="")
        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})

        person, = player_view(story["chat_id"], "player")["people"]

        assert "facts" not in person
        assert "fact_sources" not in person

    def test_two_viewers_receive_different_projections_of_one_person(
            self, temp_db, story):
        """The report's acceptance test: what each viewer gets for the same
        human being is that viewer's own disclosure state, not a shared
        directory row."""
        from db import wset

        ruth_id = _character(temp_db, story["chat_id"], "Ruth", "uid-ruth")
        wset(story["chat_id"], "known", {"Sam": ["Ruth"]})
        _deliver(temp_db, story["turn_id"], {str(story["char_id"]): "Someone."},
                 company={str(story["char_id"]): [
                     {"key": "ff33", "name": "Ruth",
                      "label": "the grey-eyed courier", "recognized": False}]})

        sam_person, = player_view(story["chat_id"], "player")["people"]
        ilse_person, = player_view(
            story["chat_id"], str(story["char_id"]))["people"]

        assert sam_person["id"] == str(ruth_id)
        assert sam_person["display_name"] == "Ruth"
        assert "facts" in sam_person
        assert ilse_person["id"].startswith("body:")
        assert ilse_person["id"] != str(ruth_id)
        assert ilse_person["display_name"] == "the grey-eyed courier"
        assert "facts" not in ilse_person

    def test_no_private_field_survives_serialisation(self, temp_db, story):
        """Psychology, private history, goals, another mind's memories: the
        projection must not merely rename these, it must have no path to them
        at all, and the only way to prove that is to look at every byte it
        produces."""
        from db import wset

        row = temp_db.q("SELECT sheet FROM characters WHERE id=?",
                        (story["char_id"],), one=True)
        sheet = json.loads(row["sheet"])
        sheet["psychology"]["self_model"]["summary"] = "SECRET-SELF"
        sheet["knowledge"]["private_history"] = [
            {"summary": "SECRET-HEIR", "known_to": []}]
        sheet["initial_state"]["goals"] = [{"text": "SECRET-GOAL"}]
        temp_db.qi("UPDATE characters SET sheet=? WHERE id=?",
                   (json.dumps(sheet), story["char_id"]))
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
            "provenance,content,gist) VALUES(?,?,?,?,?,?,?,?)",
            (story["chat_id"], story["char_id"], 3, "episodic", "episode",
             "witnessed", "SECRET-MEMORY", "SECRET-MEMORY"))
        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})

        rendered = json.dumps(player_view(story["chat_id"], "player"))

        for secret in ("SECRET-SELF", "SECRET-HEIR", "SECRET-GOAL",
                       "SECRET-MEMORY"):
            assert secret not in rendered
        assert "trust" not in rendered   # Ilse's relationship state

    def test_a_known_name_with_no_stable_id_is_omitted(self, temp_db, story):
        """A ledger name that resolves to no cast member or persona has no id
        a UI could key on, and inventing one here would be this module
        holding an identity scheme of its own -- the exact thing it exists
        not to do."""
        from db import wset

        wset(story["chat_id"], "known", {"Sam": ["The Fishmonger"]})

        assert "people" not in player_view(story["chat_id"], "player")

    def test_the_ledger_roster_survives_a_beat_with_no_company_record(
            self, temp_db, story):
        """Stories older than the delivery record still get their recognised
        roster -- and get NO observed entries, rather than entries guessed
        from the scene."""
        from db import wset

        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})
        _deliver(temp_db, story["turn_id"], {"player": "The dome is dark."})

        people = player_view(story["chat_id"], "player")["people"]

        assert [p["identity_status"] for p in people] == ["recognized"]

    def test_the_viewer_is_not_listed_among_their_own_people(self, temp_db,
                                                             story):
        from db import wset

        wset(story["chat_id"], "known", {"Ilse": ["Ilse", "Sam"]})

        people = player_view(story["chat_id"],
                             str(story["char_id"]))["people"]

        assert [p["id"] for p in people] == ["player"]


class TestImmutableIdentity:
    """Names are labels, not identities: they collide and they change while
    the person stays the same. The Directive hardening report
    (docs/design/DIRECTIVE_HARDENING_REPORT.md §1) named the three story
    cases the old name-keyed join broke -- a shared name, a recurring
    stranger, a rename -- and every test here is one of its acceptance
    tests. The projection now keys every stage on immutable identity and
    hands an unrecognising viewer only a viewer-scoped opaque derivative
    of it."""

    def test_two_people_sharing_a_name_are_distinct_entries(
            self, temp_db, story):
        """A dict keyed by name collapses two same-named people into one
        entry, or hangs one person's public facts on the other's id -- the
        exact failure the report opens with. Each bearer of a granted name
        is their own person, on their own immutable id, with their own
        facts."""
        from db import wset

        twin_id = _character(temp_db, story["chat_id"], "Ilse", "uid-ilse-2")
        _author_public(temp_db, story["char_id"],
                       appearance="a silver-haired astronomer")
        _author_public(temp_db, twin_id,
                       appearance="a scarred deckhand with silver hair")
        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})

        people = player_view(story["chat_id"], "player")["people"]

        by_id = {p["id"]: p for p in people}
        assert set(by_id) == {str(story["char_id"]), str(twin_id)}
        assert by_id[str(story["char_id"])]["facts"]["appearance"] \
            == "a silver-haired astronomer"
        assert by_id[str(twin_id)]["facts"]["appearance"] \
            == "a scarred deckhand with silver hair"

    def test_a_transporter_duplicate_stays_separately_trackable(
            self, temp_db, story):
        """The report's hard case: at the moment of duplication the two
        people share canonical name, appearance and history -- every label
        is identical, so only the immutable id can tell them apart, and it
        must."""
        from db import wset

        twin_id = _character(temp_db, story["chat_id"], "Ilse", "uid-ilse-2")
        for cid in (story["char_id"], twin_id):
            _author_public(temp_db, cid,
                           appearance="a silver-haired astronomer",
                           history="Keeper of the observatory.")
        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})

        people = player_view(story["chat_id"], "player")["people"]

        assert len(people) == 2
        assert {p["id"] for p in people} == {str(story["char_id"]),
                                             str(twin_id)}
        assert all(p["display_name"] == "Ilse" for p in people)
        assert people[0]["facts"] == people[1]["facts"]

    def test_a_shared_name_delivered_this_beat_dates_nobody(
            self, temp_db, story):
        """A recognised body arrives from the delivery record under a name
        two people bear; the projection cannot affirm WHICH body it was, and
        a date it cannot attribute is a guess. Absent means absent, applied
        to a field: both people appear, neither is dated."""
        from db import wset

        _character(temp_db, story["chat_id"], "Ilse", "uid-ilse-2")
        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})
        _deliver(temp_db, story["turn_id"], {"player": "Ilse is here."},
                 company={"player": [
                     {"key": "aa00", "name": "Ilse", "label": "Ilse",
                      "recognized": True}]})

        people = player_view(story["chat_id"], "player")["people"]

        assert len(people) == 2
        assert all("last_observed_turn" not in p for p in people)

    def test_a_recurring_stranger_keeps_one_id_across_encounters(
            self, temp_db, story):
        """'The same injured stranger from Engineering' is a property of the
        PERSON, not an accident of this beat's label. Two separated
        encounters -- different turns, different composer labels -- must
        surface the same opaque id, or a crew UI tracks one continuing
        person as two."""
        _character(temp_db, story["chat_id"], "Ruth", "uid-ruth")
        _deliver(temp_db, story["turn_id"], {"player": "Someone limps past."},
                 company={"player": [
                     {"key": "ab12cd34ef", "name": "Ruth",
                      "label": "the injured stranger", "recognized": False}]})
        first, = player_view(story["chat_id"], "player")["people"]

        later_turn = _turn(temp_db, story["chat_id"], idx=9)
        _deliver(temp_db, later_turn, {"player": "The stranger returns."},
                 company={"player": [
                     {"key": "ab12cd34ef", "name": "Ruth",
                      "label": "the limping figure", "recognized": False}]})
        second, = player_view(story["chat_id"], "player")["people"]

        assert first["display_name"] == "the injured stranger"
        assert second["display_name"] == "the limping figure"
        assert second["id"] == first["id"]
        assert second["last_observed_turn"] == 9

    def test_the_opaque_id_survives_a_canonical_rename(self, temp_db, story):
        """Under the old scheme the id was a hash of the canonical name, so
        renaming the person split them into two unrelated panel entries.
        The id now rides the card's immutable uid: the name moves, the
        person does not."""
        ruth_id = _character(temp_db, story["chat_id"], "Ruth", "uid-ruth")
        _deliver(temp_db, story["turn_id"], {"player": "Someone limps past."},
                 company={"player": [
                     {"key": "ab12cd34ef", "name": "Ruth",
                      "label": "the injured stranger", "recognized": False}]})
        first, = player_view(story["chat_id"], "player")["people"]

        _author_public(temp_db, ruth_id, name="Ruthanna")
        later_turn = _turn(temp_db, story["chat_id"], idx=9)
        _deliver(temp_db, later_turn, {"player": "The stranger returns."},
                 company={"player": [
                     {"key": "99ffee0011", "name": "Ruthanna",
                      "label": "the injured stranger", "recognized": False}]})
        second, = player_view(story["chat_id"], "player")["people"]

        assert second["id"] == first["id"]

    def test_an_adopted_alias_changes_display_name_and_never_id(
            self, temp_db, story):
        """An identity reveal mid-story: the viewer's word for the person
        changes, the person does not. `display_name` is a mutable projection
        hung off the id, so campaign state keyed on the id survives the
        reveal untouched."""
        from db import wset

        wset(story["chat_id"], "known", {"Sam": ["Ilse"]})
        before, = player_view(story["chat_id"], "player")["people"]

        _author_public(temp_db, story["char_id"], name="Selene Var")
        wset(story["chat_id"], "known", {"Sam": ["Selene Var"]})
        after, = player_view(story["chat_id"], "player")["people"]

        assert before["display_name"] == "Ilse"
        assert after["display_name"] == "Selene Var"
        assert after["id"] == before["id"] == str(story["char_id"])

    def test_the_opaque_id_is_no_cross_viewer_correlation_key(
            self, temp_db, story):
        """The composer's `key` is a canonical-name hash, identical in every
        viewer's record -- serialise two projections of one stranger and
        they join on it. The viewer-scoped id must not: two viewers who both
        see the same unnamed body get ids that share nothing, so nobody
        holding both projections can prove they watched the same person."""
        _character(temp_db, story["chat_id"], "Ruth", "uid-ruth")
        record = {"key": "ab12cd34ef", "name": "Ruth",
                  "label": "the grey-eyed courier", "recognized": False}
        _deliver(temp_db, story["turn_id"],
                 {"player": "Someone.", str(story["char_id"]): "Someone."},
                 company={"player": [dict(record)],
                          str(story["char_id"]): [dict(record)]})

        sam_person, = player_view(story["chat_id"], "player")["people"]
        ilse_person, = player_view(
            story["chat_id"], str(story["char_id"]))["people"]

        assert sam_person["id"] != ilse_person["id"]
        assert sam_person["id"] != "body:ab12cd34ef"
        assert ilse_person["id"] != "body:ab12cd34ef"

    def test_continuity_costs_no_identity_material_at_all(self, temp_db,
                                                          story):
        """The whole point of a viewer-scoped derivative: continuity without
        disclosure. Serialise the projection and assert the absence of every
        identity the id is derived from -- canonical name, canonical row id,
        the card's uid, the composer's shared ledger key, and the story's
        secret namespace itself. Any one of them surviving would let a
        caller join this projection against canonical data it has not
        earned."""
        from db import wget

        ruth_id = _character(temp_db, story["chat_id"], "Ruth", "uid-ruth")
        row = temp_db.q("SELECT sheet FROM characters WHERE id=?", (ruth_id,),
                        one=True)
        uid = json.loads(row["sheet"])["identity"]["uid"]
        _deliver(temp_db, story["turn_id"], {"player": "Someone limps past."},
                 company={"player": [
                     {"key": "ab12cd34ef", "name": "Ruth",
                      "label": "the injured stranger", "recognized": False}]})

        rendered = json.dumps(player_view(story["chat_id"], "player"))
        namespace = wget(story["chat_id"], "presence_id_namespace")

        assert "people" in json.loads(rendered)
        # The row id would ride as a JSON string, so the quoted token is the
        # precise thing to look for -- a bare small integer is everywhere.
        for material in ("Ruth", f'"{ruth_id}"', uid, "ab12cd34ef", namespace):
            assert material and material not in rendered

    def test_one_viewers_recognition_leaks_nothing_to_the_other(
            self, temp_db, story):
        """The report's two-viewer acceptance test, proved at the byte
        level: Sam knows Ruth and gets her id and name; Ilse only saw a body
        and gets a projection carrying no canonical name, no canonical id,
        no uid -- nothing that would let her panel be joined to Sam's."""
        from db import wset

        ruth_id = _character(temp_db, story["chat_id"], "Ruth", "uid-ruth")
        row = temp_db.q("SELECT sheet FROM characters WHERE id=?", (ruth_id,),
                        one=True)
        uid = json.loads(row["sheet"])["identity"]["uid"]
        wset(story["chat_id"], "known", {"Sam": ["Ruth"]})
        _deliver(temp_db, story["turn_id"], {str(story["char_id"]): "Someone."},
                 company={str(story["char_id"]): [
                     {"key": "ab12cd34ef", "name": "Ruth",
                      "label": "the grey-eyed courier", "recognized": False}]})

        sam_person, = player_view(story["chat_id"], "player")["people"]
        ilse_rendered = json.dumps(
            player_view(story["chat_id"], str(story["char_id"])))

        assert sam_person["id"] == str(ruth_id)
        for material in ("Ruth", f'"{ruth_id}"', uid):
            assert material not in ilse_rendered
        assert f'"{sam_person["id"]}"' not in ilse_rendered


class TestTheExtensionSurface:
    def test_the_api_exposes_all_three_reads(self):
        from extension_runtime.api import SonderExtensionAPI

        for name in ("story_view", "player_view", "viewers"):
            assert callable(getattr(SonderExtensionAPI, name))

    def test_the_facade_needs_no_agent_import_to_answer(self, temp_db, story):
        """A panel refresh must not drag the pipeline in. `story_view.py` is
        reached from HTTP routes, and an import of `agents.*` there would pull
        the whole runtime into a read that wants four tables."""
        import inspect

        source = inspect.getsource(story_view)

        assert "import agents" not in source
        assert "from agents" not in source
