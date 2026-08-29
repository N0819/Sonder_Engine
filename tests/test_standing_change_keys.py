"""A standing percept's change key must hash the STATE it describes.

Measured on chat 95, a 16-turn story played 2026-08-28 with every stage of
every turn read against the others. One derived crowd stood in the same room
for the whole story, its band never leaving "a dozen or so", and its composer
ledger recorded `changed` SEVEN times. The subject half of its key was
constant (`content:a18283c042`) while the content half flipped
`6184c4ac7b -> 281ee78d66 -> 298fd44d7d -> 281ee78d66 -> b95bb7cb21 ->
1706af588a -> b95bb7cb21` at turns 2, 5, 8, 10, 11, 12 and 15 -- because the
content half hashed the composed SENTENCE, and that sentence is a
top-two-of-tally over a membership that walks its errands every beat: five
spellings of one unchanged fact ("a dozen or so captains and commanders",
"...commanders and lieutenant commanders", "...lieutenant commanders and
commanders").

`changed` is not cosmetic. `leads_the_beat` promotes every changed standing
percept into the beat half, `observations_from_render` projects a beat-marked
percept with `standing=False`, and `narration._render_observed_events` numbers
every non-standing entry into `current_events` -- which the narrator sheet
defines as obligation ("every entry in it happened and must reach the page").
Those seven flips are exactly the seven beats whose prose ends on the wide
shot ("...pulling transit watch", "...held their stations", "nobody had
stopped working" three times, including the story's last sentence). The
repetition tic is the narrator obeying.

The same class, a different field: the same story's scent key for one body
moved twice on a smell that never changed -- turn 7 when the body left the
room (level), and turn 9 when the player finally recognised it (label). The
authored scent string was re-declared as this beat's news each time.

The rule these pin: recomposing an unchanged fact is not a change, and
learning WHOSE a fact is is not a change to the fact.
"""

from __future__ import annotations

import time

from agents import composer


# The bridge crowd's own numbers, with the ranks left out: the fixture must
# not name a story. One subject, one band, two orders of the same tally.
_CROWD = "crowd:charter:8f21"
_BAND = "a dozen or so"


def _crowd_row(desc, state):
    return {"uid": _CROWD, "what": desc, "state": state}


class TestACrowdIsItsStateNotItsSentence:

    def test_a_crowd_whose_composed_description_reorders_is_not_a_change(self):
        state = (_BAND, "", "ordinary")
        first = composer.room_content_percepts(
            [_crowd_row("a dozen or so wardens and clerks", state)])[0]
        reordered = composer.room_content_percepts(
            [_crowd_row("a dozen or so clerks and wardens", state)])[0]

        assert first.dedupe_key == reordered.dedupe_key
        verdicts = composer.standing_verdicts(
            [reordered], prev_standing={first.dedupe_key})
        assert verdicts[reordered.dedupe_key] == "unchanged"
        # And therefore no sentence at all in a delta player view.
        assert composer.render_view(
            [reordered], mode="player",
            prev_standing={first.dedupe_key}).text == ""

    def test_a_crowd_that_thins_is_still_a_change(self):
        """The non-negotiable direction. A crowd going from a press to a
        handful is what the split key was built to be able to say, and a fix
        for the false positives that also silenced the true ones would be
        worse than the tic."""
        before = composer.room_content_percepts(
            [_crowd_row("a throng of wardens", ("a throng", "", "ordinary"))])[0]
        after = composer.room_content_percepts(
            [_crowd_row("a handful of wardens",
                        ("a handful", "", "ordinary"))])[0]

        assert before.dedupe_key != after.dedupe_key
        assert composer._subject_prefix(before.dedupe_key) == \
            composer._subject_prefix(after.dedupe_key)
        verdicts = composer.standing_verdicts(
            [after], prev_standing={before.dedupe_key})
        assert verdicts[after.dedupe_key] == "changed"
        assert composer.leads_the_beat(
            after, "changed", {before.dedupe_key}) is True

    def test_a_seam_that_publishes_no_state_keys_on_its_description(self):
        """Couriers and posted notices publish no state to key on, so the
        rendered description stays their identity-for-change. The fallback is
        the old behaviour exactly, which is what keeps this change to the one
        seam that has a state to publish."""
        waiting = composer.room_content_percepts(
            [{"uid": "courier:2", "what": "a courier waiting by the north door"}])[0]
        same = composer.room_content_percepts(
            [{"uid": "courier:2", "what": "a courier waiting by the north door"}])[0]
        moved = composer.room_content_percepts(
            [{"uid": "courier:2", "what": "a courier gone to the south door"}])[0]

        assert waiting.dedupe_key == same.dedupe_key
        assert waiting.dedupe_key != moved.dedupe_key

    def test_a_ledger_written_before_the_change_degrades_to_first_sight(self):
        """The migration, and the direction it must fail in. Every stored
        `composer_ledger` on disk holds the prose-hashed key; keeping its tag
        and moving only its content would leave every observer reading
        "subject known, content unknown" -- a false `changed` and one
        invented ambient event per crowd per chat on the first beat after the
        change. A new tag is a subject the old ledger never held, which
        `standing_verdicts` answers `first`, and `leads_the_beat` refuses a
        first-sight ambient."""
        desc = "a dozen or so wardens and clerks"
        stored = composer.standing_key("content", (_CROWD,), (desc,))
        now = composer.room_content_percepts(
            [_crowd_row(desc, (_BAND, "", "ordinary"))])[0]

        assert now.dedupe_key != stored
        verdicts = composer.standing_verdicts([now], prev_standing={stored})
        assert verdicts[now.dedupe_key] == "first"
        assert composer.leads_the_beat(now, "first", {stored}) is False


class TestTheSeamPublishesTheStateItComposesFrom:
    """`crowds_for_room` is where both species of crowd are built, so it is
    where the state a change is measured against is published."""

    def _story(self, temp_db):
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Watch", "", time.time()))
        scene = {
            "location": "Low Town",
            "rooms": {"square": {"name": "Square", "size": "large"},
                      "annex": {"name": "Annex", "size": "small"}},
            "positions": {},
        }
        bodies = {}
        for n in range(5):
            bodies["w%d" % n] = {"name": "W%d" % n, "place": "square",
                                 "available": True, "competence": {},
                                 "home_post": "warden"}
        for n in range(4):
            bodies["c%d" % n] = {"name": "C%d" % n, "place": "square",
                                 "available": True, "competence": {},
                                 "home_post": "clerk"}
        for n in range(3):
            bodies["p%d" % n] = {"name": "P%d" % n, "place": "square",
                                 "available": True, "competence": {},
                                 "home_post": "porter"}
        state = {"key": "guild", "upkeeps": {}, "priority": [],
                 "posts": {}, "bodies": bodies, "watch": {}, "figures": {}}
        temp_db.wset(cid, "charters", {"items": {"guild": {"state": state}}})
        return cid, scene, state

    def test_a_body_walking_its_errand_does_not_make_the_crowd_news(
            self, temp_db):
        """The measured case, in the engine's own vocabulary. The tally's top
        two reorder because one body left the room and another arrived; the
        band, the density and the mood are what they were. Chat 95 read
        `changed` seven times in sixteen turns on exactly this."""
        from agents.common import crowds_for_room

        cid, scene, state = self._story(temp_db)
        before = crowds_for_room(cid, scene, "square")[0]
        first = composer.room_content_percepts([before])[0]

        # One clerk walks out, one porter walks in: the membership count and
        # therefore the band are unchanged; the composed phrase is not.
        state["bodies"]["c0"]["place"] = "annex"
        state["bodies"]["p3"] = {"name": "P3", "place": "square",
                                 "available": True, "competence": {},
                                 "home_post": "porter"}
        temp_db.wset(cid, "charters", {"items": {"guild": {"state": state}}})
        after = crowds_for_room(cid, scene, "square")[0]
        second = composer.room_content_percepts([after])[0]

        assert after["what"] != before["what"], \
            "the fixture no longer reorders the composed phrase"
        assert second.dedupe_key == first.dedupe_key

    def test_an_authored_crowds_composition_is_state_because_a_write_moves_it(
            self, temp_db):
        """The two species part company here and the reason is not the
        species: an authored crowd's composition is a stored field, so it
        changes only when something writes it, and a write is an event. A
        derived crowd's is recomputed from the registry at every read."""
        from world import crowds as crowds_model
        from agents.common import crowds_for_room

        cid, scene, _state = self._story(temp_db)
        authored = crowds_model.new_crowd(cid, "square", band="a few dozen",
                                          composition="dockworkers",
                                          since_turn=1)
        temp_db.wset(cid, "crowds", [authored])
        rows = {bool(r.get("derived")): r for r in crowds_for_room(
            cid, scene, "square")}

        assert "dockworkers" in " ".join(str(v) for v in rows[False]["state"])
        assert "warden" not in " ".join(str(v) for v in rows[True]["state"])


class TestRecognitionIsNotAChangeToTheThingRecognised:

    def _source(self, label):
        return {"key": "body:5f2a", "label": label, "scent": "warm polymer",
                "level": "full", "attributed": True}

    def test_recognising_a_body_does_not_re_declare_its_smell(self):
        """Chat 95 turn 9: the player recognised a body they had been
        perceiving for nine beats, the label on its scent source went from a
        stranger descriptor to a name, the authored scent string was
        byte-identical -- and the key moved, so the smell was delivered again
        as this beat's news."""
        stranger = composer.scent_percepts(
            [self._source("the golden-skinned figure")])[0]
        known = composer.scent_percepts([self._source("the ship's officer")])[0]

        assert stranger.dedupe_key == known.dedupe_key
        # The label is not withdrawn -- it still says whose smell this is.
        assert known.source_label == "the ship's officer"
        assert composer.standing_verdicts(
            [known], prev_standing={stranger.dedupe_key})[
                known.dedupe_key] == "unchanged"

    def test_a_smell_that_changes_is_still_a_change(self):
        base = composer.scent_percepts([self._source("a figure")])[0]
        other = composer.scent_percepts(
            [{**self._source("a figure"), "scent": "scorched insulation"}])[0]
        assert base.dedupe_key != other.dedupe_key


class TestOneEntryIsOneDeliveryAtProjectionToo:
    """The sheet's rule ("never weld two entries' quotes into one quoted
    span") cannot fire against a weld made before the model saw it.

    Chat 95, turns 2, 6 and 11 -- three welds in sixteen turns, three of
    three with a merged entry as the direct antecedent. The projection had
    joined one speaker's two speech atoms into ONE numbered entry reading
    ``X says in a <manner> voice: "A." X says in a <manner> voice: "B."``,
    the model read one entry as one delivery, and the page carried `"A."
    "B."` with the second attribution gone.
    """

    def _speech(self, who, body, order):
        return composer.speech_percept(
            {"speaker": who, "text": body, "volume": "normal"},
            {"same_room": True}, "Observer",
            display=who, can_see=True, order_key=order,
            observer_id="player")

    def _project(self, percepts):
        rendered = composer.render_view(percepts, mode="character",
                                        full_render=True)
        return composer.observations_from_render("player", rendered)

    def _texts(self, obs):
        return [(o.get("observed") or {}).get("text") or "" for o in obs]

    def test_two_lines_from_one_mouth_stay_two_deliveries(self):
        texts = self._texts(self._project([
            self._speech("Mara", "We hold the line here.", 0),
            self._speech("Mara", "No one crosses.", 1),
        ]))
        welded = [t for t in texts
                  if "We hold the line here." in t and "No one crosses." in t]
        assert not welded, welded

    def test_the_cap_welds_one_mouth_before_it_welds_two(self):
        """Refusing the merge upstream spends the atom cap, and the cap is
        the one place a delivery boundary may still be lost. Measured over
        the 4,108 stored observer-beats in the bench corpus: 668 carry a
        same-mouth weld, and refusing it unconditionally would newly overflow
        the cap on 345 of them -- 333 of which hold no standing entry for the
        cap to spend instead. So the cap must reach for the same mouth's
        lines before it reaches for two mouths', or this fix would trade a
        dropped attribution for a misattributed line."""
        speakers = ["Mara"] * 9 + ["Vorne"]
        percepts = [self._speech(who, "Line %d." % n, n)
                    for n, who in enumerate(speakers)]
        texts = self._texts(self._project(percepts))

        assert len(texts) <= composer._MAX_OBSERVATION_ATOMS
        for text in texts:
            assert not ("Mara" in text and "Vorne" in text), text
