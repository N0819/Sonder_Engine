"""On screen, a charter body is played by a model and the Director resolves
what it did (owner's rule, 2026-09-14).

Off screen the charter is pure code. In the player's aperture the only voice
a charter body had ran AFTER resolve, so a creature's act was narrated and
never resolved, and the scene the hands wrote to did not hold the body at
all (scratch play 2026-09-14, chat 4 turns 9-11).
"""
import time
import types

from agents import background
from agents.common import lay_charter_figures
from agents.director import _take_declaration
from persist.commit import beat_reactions
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import save_registry

SC = {
    "rooms": {"yard": {"name": "Farmyard", "adjacent": [
                  {"to": "scullery", "barrier": "open_door"}]},
              "scullery": {"name": "Scullery", "adjacent": [
                  {"to": "yard", "barrier": "open_door"}]}},
    "positions": {"Iris Vale": "scullery"},
    "entities": {},
}


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Well", "", time.time()))


def _well_thing():
    charter = normalize_charter({
        "key": "well",
        "upkeeps": {"hunger": {"place": "well_house", "level": 0.7,
                               "floor": 0.3, "drift_per_hour": 0.01,
                               "service_per_hour": 0.0}},
        "posts": {"hunt": {"place": "yard", "serves": ["hunger"],
                           "requires": {"hunt": 1}}},
        "bodies": {"thing_0": {"place": "yard", "name": "Well Thing",
                               "competence": {"hunt": 1}}},
        "priority": ["hunger"],
        "creature": {"prey": ["figure"], "senses": {"hearing": True},
                     "look": "a long pale jointed thing", "noun": "thing",
                     "voice": {"moving": {"level": "faint",
                                          "sound": "a wet dragging"}}},
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


class _Chat(dict):
    """The chat row as the stages hold it: a mapping with attribute access."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


def _ctx(cid):
    chat = _Chat(id=cid, persona_id=None, persona="{}", name="Well")
    turn = types.SimpleNamespace(id=7, idx=3, frame_id=None)
    return types.SimpleNamespace(chat=chat, turn=turn, cast=[],
                                 extra_players=[], warnings=[],
                                 add_warning=lambda m: None)


class TestTheResolveSceneHoldsTheBody:
    def test_a_charter_body_in_the_aperture_is_laid_onto_the_copy(self, temp_db):
        cid = _chat(temp_db)
        save_registry(cid, {"well": _well_thing()})
        sc = {k: (dict(v) if isinstance(v, dict) else v) for k, v in SC.items()}
        rows = lay_charter_figures(_ctx(cid), sc, ["scullery", "yard"])
        assert [r["name"] for r in rows] == ["Well Thing"]
        assert rows[0]["room"] == "yard"
        assert sc["positions"]["Well Thing"] == "yard"
        assert SC["positions"] == {"Iris Vale": "scullery"}

    def test_a_body_the_scene_already_stands_is_left_alone(self, temp_db):
        cid = _chat(temp_db)
        save_registry(cid, {"well": _well_thing()})
        sc = {**SC, "positions": {"Iris Vale": "scullery",
                                  "Well Thing": "scullery"}}
        lay_charter_figures(_ctx(cid), sc, ["scullery", "yard"])
        assert sc["positions"]["Well Thing"] == "scullery"


class TestTheDeclaredBeatIsWhatTheVoiceHears:
    INTERP = {
        "ledgers": [
            {"object_name": "Iris Vale", "event": "You're not one of ours,",
             "categories": ["speech"], "volume": "normal",
             "targets": ["Well Thing"], "visibility": "overt"},
            {"object_name": "Iris Vale", "observable": "steps back twice",
             "categories": ["positions"]},
        ],
        "flow": {"addressed_to_refs": []},
    }
    DECLS = [{"name": "Abel Trask", "sequence": [
        {"type": "speech", "text": "Get in here!", "volume": "shout"},
        {"type": "action", "attempt": "strains up", "observable": "strains up"}]}]

    def test_lines_and_observables_take_the_resolved_shape(self):
        beat = background._provisional_beat(None, self.INTERP, self.DECLS,
                                            "Iris Vale")
        assert [d["speaker"] for d in beat["dialogue_log"]] == [
            "Iris Vale", "Abel Trask"]
        assert beat["dialogue_log"][0]["exact_quote"] == \
            '"You\'re not one of ours,"'
        assert beat["dialogue_log"][0]["intended_target"] == "Well Thing"
        assert beat["dialogue_log"][1]["volume"] == "shout"
        assert beat["resolved_event"] == \
            "Iris Vale steps back twice Abel Trask strains up"
        assert beat["public_evidence"] == [] and beat["state_diff"] == {}


class TestTheVoiceComesBackAsADeclaration:
    def _run(self, monkeypatch, temp_db, answers):
        cid = _chat(temp_db)
        save_registry(cid, {"well": _well_thing()})
        sc = {**SC, "positions": {"Iris Vale": "yard", "Well Thing": "yard"}}
        seen = []

        def fake_react(ctx, dr, name, present_others, roster, sc_, rec, nonce,
                       player_addressed=False):
            seen.append((name, player_addressed, dr["resolved_event"]))
            return answers.get(name)

        monkeypatch.setattr(background, "_react_one", fake_react)
        monkeypatch.setattr(background, "_player_room",
                            lambda ctx, sc_: "yard")
        ctx = _ctx(cid)
        interp = dict(TestTheDeclaredBeatIsWhatTheVoiceHears.INTERP)
        rows = [{"name": "Well Thing", "room": "yard"}]
        return seen, background.declare_charter_figures(
            ctx, interp, sc, rows, [], 0)

    def test_an_act_and_a_line_become_a_sequence_with_phase_ids(
            self, monkeypatch, temp_db):
        seen, out = self._run(monkeypatch, temp_db, {"Well Thing": {
            "name": "Well Thing", "room": "yard",
            "action": "drags itself a pace closer",
            "dialogue_log_entry": None, "charter_act": None,
            "charter_offers": []}})
        assert len(seen) == 1
        assert seen[0][:2] == ("Well Thing", True)
        assert seen[0][2].endswith("steps back twice")
        assert len(out) == 1
        decl = out[0]
        assert decl["char_id"] is None and decl["is_figure"] is True
        assert [e["type"] for e in decl["sequence"]] == ["action"]
        assert decl["sequence"][0]["event_id"] == "turn:7:figure:0:0:action"
        assert decl["sequence"][0]["attempt"] == "drags itself a pace closer"

    def test_a_creatures_act_is_heard_at_its_own_voice_rung(
            self, monkeypatch, temp_db):
        _seen, out = self._run(monkeypatch, temp_db, {"Well Thing": {
            "name": "Well Thing", "room": "yard",
            "action": "drags itself a pace closer", "activity": "moving",
            "dialogue_log_entry": None, "charter_act": None,
            "charter_offers": []}})
        assert out[0]["sensory_events"] == [{
            "kind": "sound", "room": "yard", "level": "faint",
            "source": "Well Thing", "detail": "a wet dragging"}]

    def test_an_activity_the_voice_lacks_makes_no_sound(
            self, monkeypatch, temp_db):
        _seen, out = self._run(monkeypatch, temp_db, {"Well Thing": {
            "name": "Well Thing", "room": "yard", "action": "waits",
            "activity": "idle", "dialogue_log_entry": None,
            "charter_act": None, "charter_offers": []}})
        assert out[0]["sensory_events"] == []

    def test_a_silent_body_declares_nothing(self, monkeypatch, temp_db):
        _seen, out = self._run(monkeypatch, temp_db, {"Well Thing": None})
        assert out == []


class TestTheDeclarationIsFiledLikeACharacters:
    def test_take_declaration_fills_the_three_tables(self):
        decls, speech, acts = [], {}, {}
        _take_declaration(decls, speech, acts, {
            "char_id": None, "name": "Well Thing", "sequence": [
                {"type": "action", "attempt": "drags closer",
                 "event_id": "turn:7:figure:0:0:action"},
                {"type": "speech", "text": "hsss", "volume": "whisper"}]})
        assert decls[0]["name"] == "Well Thing" and decls[0]["char_id"] is None
        assert decls[0]["speech"] == "hsss"
        assert acts["Well Thing"][0]["attempt"] == "drags closer"
        assert speech["Well Thing"][0]["volume"] == "whisper"


class TestTheCommitReadsBothVoices:
    def test_figure_declarations_join_the_reactions(self):
        ctx = {"background_react": {"fired": True, "reactions": [
                   {"name": "Mara", "action": "nods", "dialogue_log_entry": None}]},
               "director_resolve": {"charter_declarations": [
                   {"name": "Well Thing", "action": "drags closer",
                    "dialogue_log_entry": None, "room": "yard",
                    "charter_act": None, "charter_offers": []},
                   {"name": "Mute", "action": "", "dialogue_log_entry": None}]}}
        br = beat_reactions(ctx)
        assert [r["name"] for r in br["reactions"]] == ["Mara", "Well Thing"]
        assert ctx["background_react"]["reactions"][0]["name"] == "Mara"
        assert len(ctx["background_react"]["reactions"]) == 1

    def test_no_figures_leaves_the_stage_result_as_it_was(self):
        br = {"fired": False, "reactions": []}
        assert beat_reactions({"background_react": br,
                               "director_resolve": {}}) == br


class TestEvidenceFindsAnActorByItsDisplayName:
    def test_a_role_prefixed_display_name_is_placed(self, temp_db):
        """Chat 5 turn 21: the sawyer spoke as "Apprentice Barrowbrookdale"
        and the evidence pass placed him nowhere, because the display map
        deals a name on subscription and the lookup used `.get`."""
        from world.charter_runtime import (_scene_placing_charter_actors,
                                           identity_index, save_registry)
        cid = _chat(temp_db)
        charter = _well_thing()
        charter["creature"] = None
        save_registry(cid, {"well": charter})
        from world.charter_runtime import registry_for
        registry = registry_for(cid)
        shown = identity_index(registry).display("well")["thing_0"]
        assert shown
        scene = {"rooms": {"yard": {"name": "Yard"}}, "positions": {},
                 "entities": {}}
        placed = _scene_placing_charter_actors(
            registry, scene, [{"actor": shown, "kind": "speech"}])
        assert placed["positions"] == {shown: "yard"}
        assert scene["positions"] == {}


class TestTheCapAsksTheCreature:
    def test_a_creature_outranks_a_stranger_in_another_room(self, monkeypatch, temp_db):
        cid = _chat(temp_db)
        save_registry(cid, {"well": _well_thing()})
        sc = {**SC, "positions": {"Iris Vale": "scullery", "Well Thing": "yard"}}
        asked = []
        monkeypatch.setattr(background, "_react_one",
                            lambda ctx, dr, name, *a, **k: asked.append(name) or None)
        monkeypatch.setattr(background, "_player_room", lambda ctx, sc_: "scullery")
        rows = [{"name": "Aaron", "room": "scullery"}, {"name": "Abel", "room": "scullery"},
                {"name": "Ada", "room": "scullery"},
                {"name": "Well Thing", "room": "yard", "creature": {"hunts": ["figure"]}}]
        background.declare_charter_figures(_ctx(cid), dict(
            TestTheDeclaredBeatIsWhatTheVoiceHears.INTERP), sc, rows, [], 0)
        assert "Well Thing" in asked and len(asked) == background.CHARTER_VOICES_PER_BEAT
