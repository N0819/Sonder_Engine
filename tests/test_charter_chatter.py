"""The room's talk reaches an observer as ground plus at most one figure.

``docs/design/DESIGN_BACKGROUND_PRESENTATION.md`` Part A. The scale that set
every constant here was measured on twin_towns(40) over 180 windows (§0 of
the note): the observer's ROOM sees 4 acts median and 6 at p90 — not the
19-per-window whole-charter figure — and 95.2% of them are `ask`. So the hum
is a band, the fragment count is zero or one, and degradation INVERTS with
crowding: a crush is a din you cannot pick a voice out of.
"""

from __future__ import annotations

import copy
import time

from world import charter_chatter as chatter
from world import crowds


def _row(actor="b1", act="ask", other="b2", subject="b3", place="square",
         at=8.0, event=False, **extra):
    return {"actor": actor, "act": act, "other": other, "subject": subject,
            "place": place, "at_hours": at, "event": event, **extra}


# --- the hum -----------------------------------------------------------------

class TestTheHumIsVocabularyNotACount:
    """Thresholds are chosen once so the words keep their plain meanings,
    the way `crowds.BANDS` were — and they are set from the §0 measurement,
    not tuned."""

    def test_no_acts_and_no_crowd_is_silence(self):
        assert chatter.hum_rank(0) == 0
        assert chatter.hum_phrase(0) == ""

    def test_the_median_room_carries_scattered_talk(self):
        """4 acts is the measured median for the busiest single place."""
        assert chatter.hum_rank(4) == 1
        assert "scattered talk" in chatter.hum_phrase(1)

    def test_past_the_rooms_own_p90_it_becomes_a_steady_hum(self):
        """6 acts is the measured p90; one act is one speaker (`enact` is
        one choice per actor per window), and more conversations than anyone
        could follow is a hum."""
        assert chatter.hum_rank(chatter.STEADY_HUM_ACTS) == 2

    def test_a_throng_hums_even_in_a_window_that_landed_no_acts(self):
        """The acts sample the population; they do not exhaust it."""
        assert chatter.hum_rank(0, band_rank=4) == 2

    def test_a_dozen_or_so_never_reads_silent(self):
        assert chatter.hum_rank(0, band_rank=2) == 1

    def test_a_handful_produces_scattered_talk_however_busy(self):
        """No explicit cap needed: a handful of people cannot land six acts,
        because one act is one speaker."""
        assert chatter.hum_rank(5, band_rank=1) == 1

    def test_a_crush_is_a_din_whatever_was_said(self):
        assert chatter.hum_rank(0, density=crowds.CRUSH) == 3
        assert chatter.hum_rank(9, density=crowds.CRUSH) == 3

    def test_a_packed_room_hums(self):
        assert chatter.hum_rank(1, density=crowds.PACKED) == 2


# --- the fragment selector ---------------------------------------------------

class TestAtMostOneFragmentAndAttentionPicksIt:
    """Eligibility ordering from §A2b: entanglement with the beat first,
    then the kinds `_ACT_EVENTS` already deems relationship-changing, then a
    seeded low-rate draw for texture."""

    def test_talk_about_someone_present_outranks_everything(self):
        rows = [_row(actor="b1", subject="b9", subject_name="Someone Else"),
                _row(actor="b2", act="accuse", other="b3", subject="",
                     event=True),
                _row(actor="b4", subject="p", subject_name="Aldous")]
        picked = chatter.overheard_fragment(
            rows, notable={"Aldous"}, seed_material="s")
        assert picked["actor"] == "b4"

    def test_relationship_changing_acts_outrank_ordinary_talk(self):
        rows = [_row(actor="b1"), _row(actor="b2", act="tend", event=True),
                _row(actor="b3")]
        picked = chatter.overheard_fragment(rows, seed_material="s")
        assert picked["actor"] == "b2"

    def test_an_ordinary_act_surfaces_on_a_seeded_low_rate_draw(self):
        """Texture, not information — the rate is FRAGMENT_ODDS, declared a
        prediction awaiting play. Over 400 distinct seeds the gate should
        fire near 1-in-4, and never always or never."""
        rows = [_row(actor="b1"), _row(actor="b2")]
        fired = sum(
            1 for i in range(400)
            if chatter.overheard_fragment(
                rows, seed_material="seed-%d" % i) is not None)
        assert 0 < fired < 400
        assert abs(fired / 400 - 1 / chatter.FRAGMENT_ODDS) < 0.08

    def test_the_draw_replays_byte_identically(self):
        """Same seed material, same pick — checkpoint restore and branching
        depend on it."""
        rows = [_row(actor="b%d" % i) for i in range(9)]
        picks = {str(chatter.overheard_fragment(
            rows, notable={"x"}, seed_material="fixed",
            odds=1)) for _ in range(20)}
        assert len(picks) == 1

    def test_a_packed_room_admits_only_high_salience(self):
        """Degradation inverts with crowding: ordinary talk is lost to the
        press; the crowd talking about *you* still snags."""
        ordinary = [_row(actor="b1")]
        assert chatter.overheard_fragment(
            ordinary, density=crowds.PACKED, seed_material="s",
            odds=1) is None
        entangled = [_row(actor="b1", subject_name="Aldous")]
        assert chatter.overheard_fragment(
            entangled, notable={"Aldous"}, density=crowds.PACKED,
            seed_material="s") is not None

    def test_a_crush_yields_no_fragment_at_all(self):
        """The walla rule plus the engine's own physics: a `membrane` you
        cannot see across is a press you cannot pick one voice out of."""
        rows = [_row(actor="b1", subject_name="Aldous", event=True)]
        assert chatter.overheard_fragment(
            rows, notable={"Aldous"}, density=crowds.CRUSH,
            seed_material="s") is None

    def test_the_same_act_keeps_the_same_key(self):
        """Dedupe on the act's identity — composer `dedupe_key` discipline —
        so a fragment re-selected while its window stands reads as unchanged
        furniture, never a fresh overhearing."""
        assert chatter.fragment_key(_row()) == chatter.fragment_key(_row())
        assert chatter.fragment_key(_row()) != chatter.fragment_key(
            _row(other="b9"))


# --- attribution -------------------------------------------------------------

class TestAttributionFollowsRecognition:
    """§A2c: a name only where recognition licenses it, and the asymmetry
    that makes rumour work — the SUBJECT was said aloud."""

    BODIES = {"b1": {"key": "b1", "name": "Marn", "place": "square"},
              "b2": {"key": "b2", "name": "Etta", "place": "square"}}
    POSTS = {"warden": {"place": "square"}}
    WATCH = {"warden": "b1"}

    def test_an_unmet_body_is_not_named(self):
        label, recognized = chatter.participant_label(
            "b2", place="square", bodies=self.BODIES, watch=self.WATCH,
            posts=self.POSTS)
        assert (label, recognized) == ("", False)

    def test_a_met_body_is_named(self):
        """A live presence record means the story has already met this
        person individually — the same floor background presences use."""
        label, recognized = chatter.participant_label(
            "b2", place="square", bodies=self.BODIES, watch=self.WATCH,
            posts=self.POSTS, known_bodies=frozenset({"b2"}))
        assert recognized and "Etta" in label

    def test_a_post_visible_in_the_room_is_a_role_noun(self):
        """Engine vocabulary by construction: posts are authored per
        charter, so the noun is genre-correct without this module knowing
        any genre."""
        label, recognized = chatter.participant_label(
            "b1", place="square", bodies=self.BODIES, watch=self.WATCH,
            posts=self.POSTS)
        assert recognized and label == "the warden"

    def test_the_post_does_not_name_a_body_in_another_room(self):
        label, _ = chatter.participant_label(
            "b1", place="annex", bodies=self.BODIES, watch=self.WATCH,
            posts=self.POSTS)
        assert label == ""

    def test_the_subject_is_named_even_when_unmet(self):
        """Overhearing a stranger's name is how a name first reaches you —
        the name was said aloud, so it is inside the budget by construction."""
        assert chatter.subject_label("b2", bodies=self.BODIES) == "Etta"

    def test_a_news_subject_is_not_a_person(self):
        assert chatter.subject_label(
            "news:incident:door@8.0", bodies=self.BODIES) == ""

    def test_a_figure_is_named_as_the_scene_knows_them(self):
        label, recognized = chatter.participant_label(
            "Aldous", place="square", figures={"Aldous": {}})
        assert (label, recognized) == ("Aldous", True)

    def test_the_phrase_is_composed_from_the_triple_never_the_template(self):
        """The substrate's `line` is `{actor} asked {other} about {subject}`
        and putting a literal line in a payload gets it restated (the
        chat-78 lesson). The clause is composed from labels; the skeleton's
        own wording must not appear."""
        phrase = chatter.fragment_phrase(
            {"speaker_label": "", "act": "ask", "other_label": "the warden",
             "subject_label": "Etta"})
        assert "asking the warden about Etta" in phrase
        assert "someone" in phrase
        assert "asked" not in phrase

    def test_an_act_kind_the_map_never_met_still_surfaces_as_talk(self):
        """A fiction may grow an affordance; overhearing it costs nothing."""
        phrase = chatter.fragment_phrase(
            {"speaker_label": "", "act": "haggle", "other_label": "",
             "subject_label": ""})
        assert "talking with" in phrase


# --- the substrate deposit ---------------------------------------------------

class TestTheSubstrateDepositsTheTriple:
    """`after_charter["acts"]` dies at every `normalize_charter` (each step
    head and each save rebuilds the state from a fixed key set), so the note's
    plan to filter "a list the registry already holds" read a list every
    persistence boundary deleted. `window_acts` is that list made durable."""

    def _run(self, hours=48.0, seed=3, folk=40):
        import sys
        import pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        from charter_worlds import twin_towns
        from world.charter import normalize_charter, run, seed_roster
        ch = normalize_charter(copy.deepcopy(twin_towns(folk)))
        ch["roster"] = seed_roster(ch["bodies"])
        return run(ch, hours=hours, window=4.0, seed=seed)

    def test_an_ask_records_its_subject_structurally(self):
        """The line names its subject only inside prose; parsing it back out
        would be a second spelling of `_afford_ask` that drifts."""
        ch, _ = self._run()
        asks = [a for a in ch["acts"] if a["act"] == "ask"]
        assert asks
        for act in asks:
            assert act["line"] == "%s asked %s about %s" % (
                act["actor"], act["other"], act["subject"])

    def test_the_deposit_is_room_stamped_and_survives_normalization(self):
        from world.charter import normalize_charter
        ch, _ = self._run()
        rows = ch["window_acts"]
        assert rows
        for row in rows:
            assert row["place"] == ch["bodies"][row["actor"]]["place"]
        assert normalize_charter(ch)["window_acts"] == rows

    def test_the_template_line_is_deliberately_not_deposited(self):
        """What a bystander takes in is who-spoke-to-whom-about-whom, never a
        sentence — and a literal string in a payload gets restated."""
        ch, _ = self._run()
        assert all("line" not in row for row in ch["window_acts"])

    def test_the_deposit_survives_the_registry_split(self):
        """§1.99d stores people once at registry level and institutions name
        their members; the room's talk is the institution's record, so it
        must ride the institution side of the split and come back whole."""
        from world.charter_runtime import _stored_shape, normalize_registry
        ch, _ = self._run(hours=8.0)
        registry = normalize_registry({"items": {"twin": {"state": ch}}})
        stored = _stored_shape(registry)
        back = normalize_registry(stored)
        assert (back["items"]["twin"]["state"]["window_acts"]
                == ch["window_acts"])
        assert ch["window_acts"]

    def test_the_deposit_replays_byte_identically(self):
        one, _ = self._run(seed=7)
        two, _ = self._run(seed=7)
        assert one["window_acts"] == two["window_acts"]

    def test_an_actor_who_left_the_charter_leaves_no_talk_behind(self):
        """The same filter `marks` and `experiences` apply, at the boundary
        that counts: `normalize_charter` runs at the head of every step."""
        rows = chatter.normalize_window_acts(
            [_row(actor="ghost"), _row(actor="b1")],
            {"b1": {"name": "Marn"}})
        assert [r["actor"] for r in rows] == ["b1"]

    def test_ordinary_talk_is_not_a_witnessable_event(self):
        """The refused symmetric move (§A3): adding speech kinds to
        `WITNESSABLE` would deposit, at the measured median of 19
        acts/window against ~5 co-present bodies, on the order of a hundred
        claims per window into heads whose caps and decay would churn on
        noise. Onscreen bystanders learn through the rendered fragment;
        offscreen participants already learn through `hear`."""
        from world.charter_news import WITNESSABLE
        assert not {"ask", "tell", "greet"} & set(WITNESSABLE)


# --- the perception seam -----------------------------------------------------

class TestTheRoomsTalkReachesAnObserver:
    """Delivered exactly where the crowd view is (`crowds_for_room`'s twin),
    so admission is decided at the seam that already decides what a
    bystander takes in, and `observations_from_render` makes character
    receipt legitimate with no second representation."""

    def _story(self, temp_db, *, acting_body="b2", subject="Aldous"):
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Chatter", "", time.time()))
        scene = {
            "location": "Low Town",
            "rooms": {"square": {"name": "Square", "size": "large"},
                      "office": {"name": "Back Office", "size": "small"}},
            "positions": {"Aldous": "square"},
        }
        state = {
            "key": "guild",
            "upkeeps": {}, "priority": [],
            "posts": {"warden": {"place": "square", "serves": [],
                                 "requires": {}}},
            "bodies": {
                "b1": {"name": "Marn", "place": "square", "available": True,
                       "competence": {}},
                "b2": {"name": "Etta", "place": "square", "available": True,
                       "competence": {}},
                "b3": {"name": "Vane", "place": "annex", "available": True,
                       "competence": {}},
            },
            "watch": {"warden": "b1"},
            "figures": {"Aldous": {"place": "square"}},
            "window_acts": [
                {"actor": acting_body, "act": "ask", "other": "b1",
                 "subject": subject, "place": "square", "at_hours": 8.0,
                 "event": False}],
        }
        temp_db.wset(cid, "charters", {"items": {"guild": {"state": state}}})
        return cid, scene

    def test_an_observer_hears_the_hum_and_the_one_fragment(self, temp_db):
        from agents.common import chatter_for_room
        cid, scene = self._story(temp_db)
        entries = chatter_for_room(cid, scene, "square")
        kinds = [e["kind"] for e in entries]
        assert kinds == ["hum", "fragment"]
        assert "scattered talk" in entries[0]["what"]

    def test_talk_about_the_present_figure_is_the_fragment_that_snags(
            self, temp_db):
        """Dramatic irony: the one fragment worth hearing is the crowd
        talking about *you* — and the subject's name was said aloud."""
        from agents.common import chatter_for_room
        cid, scene = self._story(temp_db)
        fragment = chatter_for_room(cid, scene, "square")[1]
        assert fragment["subject_label"] == "Aldous"
        assert fragment["act"] == "ask"

    def test_an_unmet_speaker_is_anonymous(self, temp_db):
        from agents.common import chatter_for_room
        cid, scene = self._story(temp_db)
        fragment = chatter_for_room(cid, scene, "square")[1]
        assert fragment["speaker_label"] == ""
        assert "someone" in fragment["what"]

    def test_a_speaker_at_a_visible_post_is_its_role_noun(self, temp_db):
        from agents.common import chatter_for_room
        cid, scene = self._story(temp_db, acting_body="b1")
        fragment = chatter_for_room(cid, scene, "square")[1]
        assert fragment["speaker_label"] == "the warden"

    def test_no_body_key_and_no_template_line_crosses(self, temp_db):
        """The triple, not the sentence — and never the substrate's keys."""
        from agents.common import chatter_for_room
        cid, scene = self._story(temp_db)
        fragment = chatter_for_room(cid, scene, "square")[1]
        assert "b1" not in fragment["what"]
        assert "b2" not in fragment["what"]
        assert "asked" not in fragment["what"]

    def test_a_back_office_hears_none_of_it(self, temp_db):
        """Room-scoped like every sibling seam: a scene-wide feed would hand
        someone behind a closed door the square's talk."""
        from agents.common import chatter_for_room
        cid, scene = self._story(temp_db)
        assert chatter_for_room(cid, scene, "office") == []

    def test_the_murmur_replays_byte_identically(self, temp_db):
        from agents.common import chatter_for_room
        cid, scene = self._story(temp_db)
        assert (chatter_for_room(cid, scene, "square")
                == chatter_for_room(cid, scene, "square"))

    def test_the_fragment_rides_hearing_and_keeps_one_dedupe_key(
            self, temp_db):
        """Delivery is a percept in the same IR as everything else; the act
        identity keys it, so the same act re-selected next beat is standing
        furniture, not a fresh overhearing."""
        from agents import composer
        from agents.common import chatter_for_room
        cid, scene = self._story(temp_db)
        entries = chatter_for_room(cid, scene, "square")
        percepts = composer.chatter_percepts(entries)
        assert [p.channel for p in percepts] == ["hearing", "hearing"]
        again = composer.chatter_percepts(
            chatter_for_room(cid, scene, "square"))
        assert [p.dedupe_key for p in percepts] == \
            [p.dedupe_key for p in again]

    def test_receipt_is_re_derived_from_the_render(self, temp_db):
        """The re-derivation property (§A3.2): a character in the room
        receives the fragment through the same door the player did, as an
        observation whose text is byte-for-byte part of the rendered view."""
        from agents import composer
        from agents.common import chatter_for_room
        cid, scene = self._story(temp_db)
        percepts = composer.chatter_percepts(
            chatter_for_room(cid, scene, "square"))
        rendered = composer.render_view(percepts, mode="character",
                                        full_render=True)
        assert "overheard" in rendered.text
        obs = composer.observations_from_render("player", rendered)
        assert any("overheard" in str(o) for o in obs)


class TestTheDerivedCrowdFeedsTheHumAndTheInversion:
    """The band floor and the density inversion read BOTH crowd species.

    §A2a grades the hum "against the crowd band already present" and §A2d
    keys fragment suppression to density — and after Part B a derived
    charter crowd IS a crowd standing in the room. The common case is the
    authored ledger being empty (the Director never raised a crowd), so
    reading it alone left a derived throng with no hum floor and a derived
    crush still admitting ordinary fragments: degradation failed to invert
    for the exact species the design is about. Found in review of the
    Part A/B merge; the fix folds `charter_crowds_for_room`'s rows into the
    same two maxima, on the fetch `chatter_for_room` already shares.
    """

    def _charter_only_story(self, temp_db, *, count, room_size, acts=(),
                            figures=None, positions=None):
        """A story whose ONLY crowd is the derived one: the authored crowds
        ledger stays empty, `count` unpresented bodies stand at the yard."""
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Derived", "", time.time()))
        scene = {
            "location": "Low Town",
            "rooms": {"yard": {"name": "Yard", "size": room_size}},
            "positions": dict(positions or {}),
        }
        state = {
            "key": "guild",
            "upkeeps": {}, "priority": [], "posts": {}, "watch": {},
            "bodies": {
                "b%d" % i: {"name": "Hand %d" % i, "place": "yard",
                            "available": True, "competence": {}}
                for i in range(count)},
            "figures": dict(figures or {}),
            "window_acts": list(acts),
        }
        temp_db.wset(cid, "charters", {"items": {"guild": {"state": state}}})
        return cid, scene

    def test_a_derived_crowd_floors_the_hum_in_a_window_with_no_acts(
            self, temp_db):
        """25 unpresented bodies band as "a few dozen" — the acts sample the
        population, they do not exhaust it, so the room hums even though the
        last window landed nothing. Before the fix this rendered silence."""
        from agents.common import chatter_for_room
        cid, scene = self._charter_only_story(
            temp_db, count=25, room_size="vast")
        entries = chatter_for_room(cid, scene, "yard")
        assert [e["kind"] for e in entries] == ["hum"]
        assert entries[0]["band"] == "a steady hum"

    def test_a_packed_derived_crowd_admits_no_ordinary_fragment(
            self, temp_db):
        """12 bodies in a small yard is PACKED (band rank 2 == room rank 2):
        ordinary talk is lost to the press whatever the seeded draw says.
        Before the fix the derived press never suppressed anything."""
        from agents.common import chatter_for_room
        ordinary = [{"actor": "b0", "act": "ask", "other": "b1",
                     "subject": "b2", "place": "yard", "at_hours": 8.0,
                     "event": False}]
        cid, scene = self._charter_only_story(
            temp_db, count=12, room_size="small", acts=ordinary)
        entries = chatter_for_room(cid, scene, "yard")
        assert [e["kind"] for e in entries] == ["hum"]

    def test_a_packed_derived_crowd_still_lets_talk_about_you_snag(
            self, temp_db):
        """The inversion lowers intelligibility, not entanglement: the crowd
        talking about someone the scene places in the room still crosses."""
        from agents.common import chatter_for_room
        entangled = [{"actor": "b0", "act": "ask", "other": "b1",
                      "subject": "Aldous", "place": "yard", "at_hours": 8.0,
                      "event": False}]
        cid, scene = self._charter_only_story(
            temp_db, count=12, room_size="small", acts=entangled,
            figures={"Aldous": {"place": "yard"}},
            positions={"Aldous": "yard"})
        kinds = [e["kind"] for e in chatter_for_room(cid, scene, "yard")]
        assert kinds == ["hum", "fragment"]

    def test_a_derived_crush_is_a_din_and_zero_fragments(self, temp_db):
        """12 bodies in a tiny yard is CRUSH (band rank 2 - room rank 1 = 1):
        the same physics that makes the press a membrane you cannot see
        across makes it one you cannot pick a voice out of — even a voice
        saying your name."""
        from agents.common import chatter_for_room
        entangled = [{"actor": "b0", "act": "ask", "other": "b1",
                      "subject": "Aldous", "place": "yard", "at_hours": 8.0,
                      "event": False}]
        cid, scene = self._charter_only_story(
            temp_db, count=12, room_size="tiny", acts=entangled,
            figures={"Aldous": {"place": "yard"}},
            positions={"Aldous": "yard"})
        entries = chatter_for_room(cid, scene, "yard")
        assert [e["kind"] for e in entries] == ["hum"]
        assert entries[0]["band"] == "a din nothing carries over"
