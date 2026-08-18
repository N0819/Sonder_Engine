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


def _deliver(temp_db, turn_id, views, observations=None, key="perception_outcome"):
    """Store one perception step the way the pipeline stores it."""
    step_id = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
        (turn_id, key, key, 3))
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
        (step_id, json.dumps({"views": views,
                              "observations": observations or {}}), time.time()))
    return step_id


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
