"""Regression tests for identity masking in perception_outcome.

Deterministic dialogue/action injection must not reveal a source's real
name to a perceiver who has never been introduced to them -- it should
fall back to an appearance description or a generic unknown-actor label,
exactly like the existing action-onset masking in perception_act does for
NPCs observing the player.
"""

import json
import time

from agents.perception import _repaired_observations

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

def _make_chat_and_cast(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    def add_character(name):
        sheet = default_character_data(name)
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(), f"char_{name.lower()}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"),
        )
        return char_id

    mara_id = add_character("Mara")
    elden_id = add_character("Elden")

    temp_db.wset(
        chat_id,
        "scene",
        {
            "location": "Blackthorn Lighthouse",
            "time": "night",
            "rooms": {
                "keeper_room": {
                    "name": "Keeper's Room",
                    "adjacent": [
                        {"to": "lamp_room", "barrier": "open", "distance": "near"},
                        {"to": "cellar", "barrier": "closed_door", "distance": "near"},
                    ],
                },
                "lamp_room": {"name": "Lamp Room", "adjacent": []},
                "cellar": {"name": "Cellar", "adjacent": []},
            },
            "positions": {"Mara": "lamp_room", "Elden": "cellar"},
            "entities": {},
            "attire": {},
            "overlays": {},
        },
    )

    # The player has met Mara but has never encountered Elden, who is
    # hiding in the cellar.
    temp_db.wset(chat_id, "known", {"The Stranger": ["Mara"]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "listen", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="listen",
                      created=time.time()),
        cast=cast,
        input="listen",
    )
    ctx["_player_room"] = "keeper_room"
    return ctx, mara_id, elden_id

def test_unrecognized_speaker_name_is_masked_in_player_view(temp_db, monkeypatch):
    import agents.perception as perception

    ctx, mara_id, elden_id = _make_chat_and_cast(temp_db)

    ctx.director_resolve = {
        "resolved_event": "Voices carry through the lighthouse.",
        "dialogue_log": [
            {"speaker": "Mara", "exact_quote": '"Mind the steps."',
             "volume": "normal", "intended_target": None, "tone": ""},
            {"speaker": "Elden", "exact_quote": '"Please, help me."',
             "volume": "shout", "intended_target": None, "tone": ""},
        ],
    }
    ctx.director_interpret = {}

    result = perception.perception_outcome(ctx, nonce=0)
    player_view = result["views"]["player"]

    assert "Mind the steps" in player_view
    assert "Mara" in player_view, "recognized speaker should be named"

    assert "Elden" not in player_view, (
        "unrecognized speaker's real name leaked into the player's view"
    )
    assert "Please, help me" in player_view, (
        "the (unattributed) quote should still be delivered"
    )


class TestObservationsCarryTheViewsRepairs:
    """`observations_from_render` projects from the view BEFORE the tripwires
    repair it, so the two diverge exactly when a repair fires. Measured over
    104 turns in eight stories: 102 byte-identical, and both divergences the
    same class -- the observer named in the THIRD PERSON inside its own view,
    which the self-narration tripwire drops from the view and the observations
    kept. That was survivable while observations were secondary; it stopped
    being survivable when `current_events` began sourcing from them.
    """

    ROSTER = [{"name": "Hinami"}, {"name": "The Doctor"}]

    VIEW = "You are in Moonlit shoreline. You are walking toward the ferry port."

    def _obs(self, *texts):
        return [{"observation_id": f"current:player:{i}", "channel": "sight",
                 "observed": {"text": t}} for i, t in enumerate(texts)]

    def test_self_narration_is_dropped_the_way_the_view_drops_it(self):
        out = _repaired_observations(
            self._obs("Hinami and The Doctor have begun walking inland "
                      "toward the ferry port.",
                      "You are walking toward the ferry port."),
            self.VIEW, "Hinami", {"Hinami": ["The Doctor"]}, self.ROSTER)
        texts = [o["observed"]["text"] for o in out]
        assert not any("Hinami and The Doctor have begun" in t for t in texts)
        assert any("You are walking" in t for t in texts)

    def test_a_delivered_line_is_never_dropped(self):
        """The self-narration strip is quote-safe and REFUSES a drop that
        would take a quote, so nothing an enforceable dialogue check will
        demand can be lost here. A bare containment filter would carry no
        such guarantee."""
        spoken = ('Hinami and The Doctor stop, and The Doctor says: '
                  '"We should go."')
        out = _repaired_observations(
            self._obs(spoken), "The shore is quiet. " + spoken, "Hinami",
            {"Hinami": ["The Doctor"]}, self.ROSTER)
        assert len(out) == 1
        assert '"We should go."' in out[0]["observed"]["text"]

    def test_untouched_observations_pass_through_unchanged(self):
        obs = self._obs("The Doctor kneels on the shore.")
        out = _repaired_observations(
            obs, "The Doctor kneels on the shore.", "Hinami",
            {"Hinami": ["The Doctor"]}, self.ROSTER)
        assert [o["observed"]["text"] for o in out] == [
            "The Doctor kneels on the shore."]
        # Every other field survives the repair.
        assert out[0]["observation_id"] == "current:player:0"
        assert out[0]["channel"] == "sight"

    def test_junk_and_empties_are_dropped(self):
        assert _repaired_observations([], self.VIEW, "Hinami", {},
                                      self.ROSTER) == []
        assert _repaired_observations(
            ["junk", {"observed": {"text": "   "}}], self.VIEW, "Hinami", {},
            self.ROSTER) == []
        # An empty repaired view means the tripwires removed everything.
        assert _repaired_observations(
            self._obs("Anything at all."), "", "Hinami", {},
            self.ROSTER) == []
