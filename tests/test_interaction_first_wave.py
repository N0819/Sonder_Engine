"""The simultaneous first wave: what it fixed, and why it is no longer default.

THE WAVE. The interaction loop's early exits end the BEAT, and the commonest of
them is `_requires_director_resolution`. When this was written it fired on any
declared act with a target — a hug returned, a hand on a shoulder, a glance
answered. Since the addressed character is deliberately queued first, the usual
shape was: the addressed character touches somebody, the loop breaks, and every
other reactor is never called. Measured across the stored corpus: **153 of 196
beats with two or more reactors left at least one reactor never called at all**,
106 of those on that one exit. Live in chat 38 t140 — the Doctor stood six feet
from the embrace, was a reactor, had a pass-1 view of it, and never ran.

A character who never ran has no appraisal, so no `goal_impacts`, so no drive
strain from a beat aimed at them; no psychology commit; no memory of having
chosen to stay quiet — and the narrator, seeing nothing, renders the absence as
a deliberate silence nobody chose.

WHY IT IS NO LONGER THE DEFAULT. The wave's own argument is that everyone in the
initial queue is answering the SAME already-fixed thing and none of them has
seen another's response, so making them take turns claims something false. That
is right about a beat aimed at the ROOM and wrong about one aimed at a person,
which is most of them: the others are bystanders to an exchange that has not
finished, and deciding blind they answer a question that is already answered.
Live, chat 59 t161 — the player asked the Doctor a direct question, he was
correctly ranked first and answered, and Tamamo in the same blind instant said
"Doctor?", prompting a man who had just spoken. The narrator's own fidelity
check caught it as dialogue rendered out of order.

The stranding it was introduced for is now fixed where it was caused: that exit
is gated on `commitment: "contestable"` (see `test_conversation_continues.py`),
and `_defer_to_focus` plus the queue-not-empty guard cover the rest.

So the default is 1 and `initial_parallel_reactors` is the knob. The tests below
still exercise the wave at 2 and 3, because raising it must keep working — a
duel, a crowd turning at a noise, any beat where nobody was addressed.
"""

from __future__ import annotations

import json

import agents.loops as loops
from story.character_schema import default_character_data


class _Chat:
    id = 1


class _Turn:
    idx = 5
    frame_id = None


class _Ctx:
    def __init__(self, reactors, tom_triggers=(), addressed=(), cast=None,
                 sequence=()):
        self.chat = _Chat()
        self.turn = _Turn()
        self.cast = [
            {"id": cid, "sheet": json.dumps(default_character_data(f"Char{cid}")),
             "state": "{}", "active": 1, "stance": "{}"}
            for cid in (cast if cast is not None else reactors)
        ]
        self.director_interpret = {
            "flow": {
                "reactors": list(reactors),
                "addressed_to": list(addressed),
                "tom_triggers": list(tom_triggers),
                "dialogue_mode": True,
            },
            "sequence": [dict(e) for e in sequence],
        }
        self.perception_act = {"views": {}}
        self.reaction_results = {}
        self.reaction_loop = {}
        self.character_results = {}
        self.warnings = []
        self._extra = {}

    def get(self, key, default=None):
        return getattr(self, key, default) or default


def _install(monkeypatch, calls_log, *, wave=2, physical=(), asks_player=(),
             silent=(), max_calls=6, max_rounds=4, seen_views=None):
    monkeypatch.setattr(loops, "dialogue_config", lambda cid: {
        "max_micro_rounds": max_rounds,
        "max_character_calls": max_calls,
        "initial_parallel_reactors": wave,
        "stop_on_question_to_player": True,
        "allow_npc_to_npc_dialogue": True,
        "silence_ends_exchange": True,
    })
    monkeypatch.setattr(loops, "get_scene", lambda *a, **kw: {})
    monkeypatch.setattr(loops, "normalize_character_refs",
                        lambda refs, cast: [int(r) for r in refs
                                            if isinstance(r, int) or str(r).isdigit()])
    monkeypatch.setattr(loops, "_drop_non_awake", lambda ctx, ids: ids)
    # Same reason as the line above, for the sibling gate: this stand-in's
    # `get_scene` returns {}, so every reactor would read as a body the scene
    # places nowhere. Presence narrowing has its own suite
    # (tests/test_reactors_are_narrowed_to_presence.py).
    monkeypatch.setattr(loops, "_drop_absent", lambda ctx, ids: ids)
    monkeypatch.setattr(loops, "_merge_character_results", lambda prev, new: new)
    monkeypatch.setattr(loops, "_requires_director_resolution",
                        lambda r: r["cid"] in physical)
    monkeypatch.setattr(loops, "_asks_player",
                        lambda r, chat, cast: r["cid"] in asks_player)
    monkeypatch.setattr(loops, "_sequence_has_content",
                        lambda r: r["cid"] not in silent)
    # Each speaker's line becomes visible to everyone else -- which is exactly
    # what must NOT have happened yet while their wave-mates were deciding.
    monkeypatch.setattr(
        loops, "deterministic_micro_perception",
        lambda ctx, actor_id, actor_result, scene: (
            {other["id"]: [f"{actor_id} spoke"]
             for other in ctx.cast if other["id"] != actor_id},
            {other["id"] for other in ctx.cast if other["id"] != actor_id},
        ))
    monkeypatch.setattr(loops, "_append_micro_view",
                        lambda existing, additions: (existing or "") + "|".join(additions))
    monkeypatch.setattr(loops, "_next_speaker_candidates",
                        lambda ctx, sid, perceived, spoke: [])
    # These fixtures are about WAVE mechanics, so the untargeted shuffle is
    # pinned to identity here and exercised on its own below. Otherwise every
    # assertion about who ran would be asserting the jitter.
    monkeypatch.setattr(loops, "_untargeted_order",
                        lambda ctx, ids, nonce: list(ids))

    def fake_character_step(ctx, cid, nonce):
        calls_log.append(cid)
        if seen_views is not None:
            seen_views[cid] = ctx._extra.get("interaction_views", {}).get(cid, "")
        return {"cid": cid, "sequence": [{"type": "speech", "line": f"{cid} speaks"}]}

    monkeypatch.setattr(loops, "character_step", fake_character_step)


class TestTheLiveFailure:
    def test_a_bystander_is_not_stranded_by_somebody_elses_embrace(self, monkeypatch):
        """Chat 38 t140: Tamamo (addressed, queued first) returns the hug — an
        act with a target — and the Doctor, a reactor with a pass-1 view of it,
        used to be dropped."""
        calls = []
        _install(monkeypatch, calls, wave=2, physical={41})
        ctx = _Ctx(reactors=[41, 35], addressed=[41])

        out = loops.interaction_loop(ctx, nonce=0)

        assert calls == [41, 35], (
            "the second reactor never ran "
            f"(calls={calls}, stop={out.get('stop_reason')!r})")
        assert out["stop_reason"] == "physical resolution required"

    def test_the_exit_still_fires_once_the_wave_is_done(self, monkeypatch):
        """The wave defers the exit; it does not delete it. A third reactor
        beyond the wave is still not called on a beat needing resolution."""
        calls = []
        _install(monkeypatch, calls, wave=2, physical={41})
        ctx = _Ctx(reactors=[41, 35, 40], addressed=[41])

        out = loops.interaction_loop(ctx, nonce=0)

        # All three run now, not two: the exit waits for everybody the beat
        # summoned, which is the general rule the wave was approximating.
        assert calls == [41, 35, 40]
        assert out["stop_reason"] == "physical resolution required"

    def test_a_question_to_the_player_also_waits_for_the_wave(self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=2, asks_player={41})
        ctx = _Ctx(reactors=[41, 35], addressed=[41])

        out = loops.interaction_loop(ctx, nonce=0)

        assert calls == [41, 35]
        assert out["stop_reason"] == "awaiting player response"


class TestTheWaveIsBlind:
    def test_no_member_sees_another_member_while_deciding(self, monkeypatch):
        """This is the whole claim. They are answering the player, not each
        other, and delivering one's line into another's view mid-wave would
        make the second a reply to something they had not heard when they
        started."""
        calls, seen = [], {}
        _install(monkeypatch, calls, wave=3, seen_views=seen)
        ctx = _Ctx(reactors=[1, 2, 3])

        loops.interaction_loop(ctx, nonce=0)

        assert calls == [1, 2, 3]
        assert seen == {1: "", 2: "", 3: ""}, (
            "a wave member was shown a wave-mate's line before declaring")

    def test_the_wave_becomes_visible_once_it_is_over(self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=2)
        ctx = _Ctx(reactors=[1, 2])

        loops.interaction_loop(ctx, nonce=0)

        views = ctx._extra["interaction_views"]
        assert "2 spoke" in views[1] and "1 spoke" in views[2]

    def test_after_the_wave_speakers_are_serial_again(self, monkeypatch):
        """A character replying to another character IS responding to
        something they just heard, and ordering is the whole content of it."""
        calls, seen = [], {}
        _install(monkeypatch, calls, wave=2, seen_views=seen)
        monkeypatch.setattr(
            loops, "_next_speaker_candidates",
            lambda ctx, sid, perceived, spoke: [3] if 3 not in spoke else [])
        ctx = _Ctx(reactors=[1, 2], cast=[1, 2, 3])

        loops.interaction_loop(ctx, nonce=0)

        assert calls == [1, 2, 3]
        assert seen[3], "the serial speaker should hear what the wave said"


class TestTheWaveIsBounded:
    def test_it_never_exceeds_the_configured_size(self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=2)
        ctx = _Ctx(reactors=[1, 2, 3, 4])

        loops.interaction_loop(ctx, nonce=0)

        assert calls[:2] == [1, 2]

    def test_a_size_of_one_is_the_old_serial_behaviour(self, monkeypatch):
        """Every existing loop test omits the key and therefore gets 1 — the
        change has to be opt-in from config, not baked into the loop."""
        calls = []
        _install(monkeypatch, calls, wave=1, physical={1})
        ctx = _Ctx(reactors=[1, 2])

        out = loops.interaction_loop(ctx, nonce=0)

        # A wave of one is now the DEFAULT, and the beat still gives every
        # initial reactor its call before the exit stands.
        assert calls == [1, 2]
        assert out["stop_reason"] == "physical resolution required"

    def test_the_call_budget_still_wins(self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=4, max_calls=2)
        ctx = _Ctx(reactors=[1, 2, 3, 4])

        loops.interaction_loop(ctx, nonce=0)

        assert calls == [1, 2]

    def test_the_round_budget_still_wins(self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=4, max_rounds=2)
        ctx = _Ctx(reactors=[1, 2, 3, 4])

        loops.interaction_loop(ctx, nonce=0)

        assert calls == [1, 2]

    def test_every_wave_member_gets_a_round_of_its_own(self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=2)
        ctx = _Ctx(reactors=[1, 2])

        out = loops.interaction_loop(ctx, nonce=0)

        assert [r["speaker_id"] for r in out["rounds"]] == [1, 2]
        assert [r["round"] for r in out["rounds"]] == [0, 1]
        assert out["calls"] == 2


class TestSilenceIsAPropertyOfTheWave:
    def test_one_quiet_character_beside_a_talkative_one_is_not_a_lull(
            self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=2, silent={2})
        monkeypatch.setattr(
            loops, "_next_speaker_candidates",
            lambda ctx, sid, perceived, spoke: [3] if 3 not in spoke else [])
        ctx = _Ctx(reactors=[1, 2], cast=[1, 2, 3])

        out = loops.interaction_loop(ctx, nonce=0)

        assert 3 in calls, f"beat ended on a lull that did not happen: {out}"

    def test_a_wave_where_nobody_spoke_does_end_it(self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=2, silent={1, 2})
        monkeypatch.setattr(
            loops, "_next_speaker_candidates",
            lambda ctx, sid, perceived, spoke: [3] if 3 not in spoke else [])
        ctx = _Ctx(reactors=[1, 2], cast=[1, 2, 3])

        out = loops.interaction_loop(ctx, nonce=0)

        assert calls == [1, 2]
        assert out["stop_reason"] == "natural silence"


def test_the_beat_opens_with_one_character_so_causality_can_build():
    """Reversed deliberately. The wave opened with two on the argument that
    everyone is responding to the same fixed thing and so could not have seen
    each other -- true of a beat aimed at the room, false of one aimed at a
    person, which is most of them. Addressed to somebody else, the others are
    bystanders to an exchange that has not finished, and deciding blind they
    answer a question that is already answered.

    Live, chat 59 t161: the player asked the Doctor a direct question, he was
    correctly ranked first and answered, and Tamamo in the same blind instant
    said "Doctor?" -- prompting a man who had just spoken. The narrator's own
    fidelity check caught it as dialogue rendered out of order.

    The knob stays, for a beat where the room really does react as a room."""
    from story.scene import DEFAULT_INTERACTION_CONFIG

    assert DEFAULT_INTERACTION_CONFIG["initial_parallel_reactors"] == 1

class TestTheAskerStepsOutOfTheWave:
    """The wave's justification is that its members are answering the same
    thing, unseen by each other. That holds when everyone is reacting to the
    PLAYER. It fails when one member is answering another: the answer is FOR
    the asker, and the question already exists from last beat.

    Live, chat 59 t146. The Doctor owed Tamamo an answer and was correctly
    queued first — but she was in the same blind instant, so her round was
    written deaf. Her present evidence was "dim light... gravel... Hinami
    stands perfectly still", with his answer nowhere in it, and she selected
    "rephrase the dimensional question freshly to the Doctor". On the page: an
    answer, then the question it had just answered, then (given a second round)
    the answer restated back to the person who gave it.
    """

    def _install_debt(self, monkeypatch, ower, asker_name, asker_id):
        import agents.loops as loops_mod

        def fake_note(chat_id, name, idx, frame, *a, **kw):
            if name == ower:
                return {"awaiting_your_answer": {
                    "from": asker_name, "asked": "How does it fold dimensions?",
                    "turns_ago": 1}}
            return {}

        monkeypatch.setattr(loops_mod, "_unanswered_question_note", fake_note)
        monkeypatch.setattr(
            loops_mod, "normalize_character_refs",
            lambda refs, cast: [asker_id if r == asker_name else int(r)
                                for r in refs
                                if r == asker_name or str(r).isdigit()])

    def test_the_asker_is_not_in_the_same_blind_wave(self, monkeypatch):
        calls, seen = [], {}
        _install(monkeypatch, calls, wave=2, seen_views=seen)
        self._install_debt(monkeypatch, "Char35", "Char41", 41)
        ctx = _Ctx(reactors=[35, 41])

        loops.interaction_loop(ctx, nonce=0)

        assert calls[0] == 35, "the one who owes an answer still speaks first"
        assert calls[1] == 41, "the asker still speaks, just after"
        assert seen[41], "the asker must have heard the answer before replying"

    def test_the_answerer_is_still_blind_to_nothing_in_particular(self, monkeypatch):
        calls, seen = [], {}
        _install(monkeypatch, calls, wave=2, seen_views=seen)
        self._install_debt(monkeypatch, "Char35", "Char41", 41)
        ctx = _Ctx(reactors=[35, 41])

        loops.interaction_loop(ctx, nonce=0)

        assert seen[35] == "", "nobody spoke before the answerer"

    def test_nobody_loses_a_turn(self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=2)
        self._install_debt(monkeypatch, "Char35", "Char41", 41)
        ctx = _Ctx(reactors=[35, 41])

        loops.interaction_loop(ctx, nonce=0)

        assert sorted(calls) == [35, 41]

    def test_with_no_debt_the_wave_is_unchanged(self, monkeypatch):
        """The split is for the answering case only; an ordinary beat where
        everyone is reacting to the player keeps the simultaneous wave."""
        calls, seen = [], {}
        _install(monkeypatch, calls, wave=2, seen_views=seen)
        ctx = _Ctx(reactors=[35, 41])

        loops.interaction_loop(ctx, nonce=0)

        assert calls == [35, 41]
        assert seen == {35: "", 41: ""}, "both still declare blind"

    def test_mutual_debt_does_not_stall_the_beat(self, monkeypatch):
        """If each owes the other, deferring both would empty the wave.
        Somebody has to go first; the queue order already decided who."""
        import agents.loops as loops_mod

        calls = []
        _install(monkeypatch, calls, wave=2)
        monkeypatch.setattr(
            loops_mod, "_unanswered_question_note",
            lambda chat_id, name, idx, frame, *a, **kw: {
                "awaiting_your_answer": {
                    "from": "Char41" if name == "Char35" else "Char35",
                    "asked": "?", "turns_ago": 1}})
        monkeypatch.setattr(
            loops_mod, "normalize_character_refs",
            lambda refs, cast: [{"Char35": 35, "Char41": 41}.get(r, r)
                                for r in refs
                                if r in ("Char35", "Char41") or isinstance(r, int)])
        ctx = _Ctx(reactors=[35, 41])

        loops.interaction_loop(ctx, nonce=0)

        assert calls, "the beat must not stall with nobody speaking"


class TestOrderIsCausality:
    """Whoever runs first decides in a room where nothing has happened yet, and
    everyone after them answers a room that has. So the beat says who goes
    first, in two places: who was spoken to, and who was acted upon."""

    def test_the_person_spoken_to_opens_the_beat(self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=1)
        ctx = _Ctx([7, 3], addressed=[3])

        loops.interaction_loop(ctx, nonce=0)

        assert calls[0] == 3

    def test_the_person_acted_upon_opens_it_when_nobody_was_spoken_to(
            self, monkeypatch):
        calls = []
        _install(monkeypatch, calls, wave=1)
        ctx = _Ctx([7, 3], sequence=[
            {"type": "action", "attempt": "sets a hand on their shoulder",
             "targets": [3]},
        ])

        loops.interaction_loop(ctx, nonce=0)

        assert calls[0] == 3

    def test_speech_outranks_action(self, monkeypatch):
        """An action's `targets` is a looser field than an address -- the
        deterministic binder fills it from whoever the act plausibly lands on,
        and a live beat had "sits back down at the table" targeting both people
        in the room. Treating that as an address would make the ranking say
        nothing."""
        calls = []
        _install(monkeypatch, calls, wave=1)
        ctx = _Ctx([7, 3], addressed=[7], sequence=[
            {"type": "action", "attempt": "sits back down at the table",
             "targets": [3, 7]},
        ])

        loops.interaction_loop(ctx, nonce=0)

        assert calls[0] == 7

    def test_an_act_landing_on_everyone_leaves_the_prior_order_alone(
            self, monkeypatch):
        """Stable sort, so a target list that names the whole room ranks them
        all together and cast-registration order still decides."""
        calls = []
        _install(monkeypatch, calls, wave=1)
        ctx = _Ctx([7, 3], sequence=[
            {"type": "action", "attempt": "sits back down", "targets": [7, 3]},
        ])

        loops.interaction_loop(ctx, nonce=0)

        assert calls == [7, 3]

    def test_everyone_after_the_first_sees_what_the_first_did(
            self, monkeypatch):
        """The whole point of opening with one. The second character decides in
        a room where the first has already spoken."""
        calls, seen = [], {}
        _install(monkeypatch, calls, wave=1, seen_views=seen)
        ctx = _Ctx([7, 3], addressed=[7])

        loops.interaction_loop(ctx, nonce=0)

        assert calls[0] == 7
        assert "7 spoke" in (seen.get(3) or "")
        assert "3 spoke" not in (seen.get(7) or "")


class TestWhoOpensAnUntargetedBeat:
    """Cast-REGISTRATION order was deciding when the beat named nobody, which
    is not a fact about the fiction: the same character opened every untargeted
    beat for the life of a story, whatever anybody wanted."""

    def _cast_ctx(self, urgencies):
        ctx = _Ctx(list(urgencies))
        for row in ctx.cast:
            row["state"] = json.dumps({"active_state": {"wants": [
                {"want": "say the thing", "urgency": urgencies[row["id"]]},
            ]}})
        return ctx

    def test_standing_pressure_reads_the_top_want(self):
        ctx = self._cast_ctx({1: 0.2, 2: 0.9})

        assert loops._standing_pressure(ctx, 2) == 0.9
        assert loops._standing_pressure(ctx, 1) == 0.2

    def test_a_character_with_no_committed_state_has_no_pressure(self):
        """Missing state is 0, not an error -- a mind that has never been
        committed has no standing wants, which is the true answer."""
        ctx = _Ctx([1, 2])

        assert loops._standing_pressure(ctx, 1) == 0.0

    def test_the_urgent_want_usually_opens_the_beat(self):
        """Usually, not always: it is a lull, nobody was addressed, and a pure
        ranking would be as fixed as registration order was."""
        ctx = self._cast_ctx({1: 0.05, 2: 0.95})
        firsts = [loops._untargeted_order(ctx, [1, 2], nonce)[0]
                  for nonce in range(40)]

        assert firsts.count(2) > firsts.count(1)

    def test_equal_pressure_still_varies_beat_to_beat(self):
        """The jitter is what stops one character owning every lull."""
        ctx = self._cast_ctx({1: 0.5, 2: 0.5})
        firsts = {loops._untargeted_order(ctx, [1, 2], nonce)[0]
                  for nonce in range(40)}

        assert firsts == {1, 2}

    def test_the_same_beat_orders_the_same_way_twice(self):
        """Seeded, so a rerun from a stage replays identically."""
        ctx = self._cast_ctx({1: 0.4, 2: 0.6})

        assert (loops._untargeted_order(ctx, [1, 2], 7)
                == loops._untargeted_order(ctx, [1, 2], 7))

    def test_it_never_drops_or_invents_a_reactor(self):
        ctx = self._cast_ctx({1: 0.1, 2: 0.9, 3: 0.5})

        for nonce in range(20):
            assert sorted(loops._untargeted_order(ctx, [1, 2, 3], nonce)) \
                == [1, 2, 3]


class TestTheIsolatedException:
    """Two people in separate rooms, out of sight and out of earshot, are not
    taking turns in any sense a reader could detect. That is the one case where
    the wave's original argument -- mutually blind by construction -- is
    literally true, and it is what offscreen simulation will need.

    Written, tested, and SWITCHED OFF: every reactor in a beat today is
    somebody the player can hear, so this branch would never fire on a real
    story, and shipping it live would mean its first run was its first
    exercise.
    """

    _SCENE = {
        "positions": {"A": "hall", "B": "cellar", "C": "hall"},
        "rooms": {"hall": {"name": "Hall", "adjacent": []},
                  "cellar": {"name": "Cellar", "adjacent": []}},
        "entities": {},
    }

    def test_two_sealed_rooms_are_isolated(self):
        assert loops._perceptually_isolated(self._SCENE, "A", "B")

    def test_the_same_room_is_never_isolated(self):
        assert not loops._perceptually_isolated(self._SCENE, "A", "C")

    def test_an_unresolvable_room_fails_closed(self):
        """A wrong yes puts two characters in one instant while one could hear
        the other; a wrong no costs a sequential call nobody needed."""
        assert not loops._perceptually_isolated(self._SCENE, "A", "Nobody")
        assert not loops._perceptually_isolated({}, "A", "B")

    def test_disabled_the_wave_is_just_the_first_reactor(self):
        ctx = _Ctx([1, 2])
        assert loops._isolated_wave(ctx, self._SCENE, [1, 2], False) == [1]

    def test_enabled_it_admits_only_the_unreachable(self, monkeypatch):
        ctx = _Ctx([1, 2, 3])
        monkeypatch.setattr(loops, "character_name",
                            lambda sheet: {"Char1": "A", "Char2": "B",
                                           "Char3": "C"}[sheet["identity"]["name"]])

        wave = loops._isolated_wave(ctx, self._SCENE, [1, 2, 3], True)

        assert wave == [1, 2]   # C is in the hall with A and waits its turn

    def test_it_is_off_by_default(self):
        from story.scene import DEFAULT_INTERACTION_CONFIG

        assert DEFAULT_INTERACTION_CONFIG["parallel_isolated_reactors"] is False
