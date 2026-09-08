"""A delivered detail that is still true and has gone unsaid (review D7).

THE DEFECT: the player tier suppresses a standing fact this observer already
holds -- correctly; a room does not re-introduce its own furniture every beat
-- and the narrator's `past_narration` reaches `narrator_history_turns` turns
back. Between the two, a detail delivered once and never rendered again falls
out of everything the narrator can see and stays out for the rest of the
story. Measured on the descent copy (chat 117): a body co-present in the
player's standing ledger from beat 19 to beat 102, and 41 of 123 beats
carrying at least one fact first delivered twelve or more beats earlier.

The ledger was a bare set of keys, which answers "have I been told this" and
nothing else. `perception._standing_meta` gives each key the two numbers and
the sentence that make "still true, not said for N beats" sayable, and
`narration._player_long_established` hands the ones older than the page's own
memory to the narrator as REFERENCE.

Firewall: every entry is this observer's own previously rendered sentence,
read back under this observer's own ledger key. Nothing is derived from the
scene here, so nothing can be admitted that was not already delivered.
"""

import json

from agents import composer, narration, perception


PLAYER = "Hero"
GRIP = {"actor": "Sable", "actor_part": "hand", "target": PLAYER,
        "target_part": "wrist", "manner": "grip"}


def _percepts(clause="his hand on your wrist", manner="grip"):
    return composer.contact_percepts([({**GRIP, "manner": manner}, clause)])


class _StubCtx(dict):
    """All the two sides need from a context: warnings, and a turn index."""

    class _Turn:
        def __init__(self, idx):
            self.idx = idx

        def __getitem__(self, key):
            return getattr(self, key)

    def __init__(self, idx=0, **kw):
        super().__init__(**kw)
        self.warnings = []
        self.turn = self._Turn(idx)


def _filed(ctx, rendered, prev_meta, pid="player", track=True,
           known=None, roster=(), views=None):
    """The per-observer ledger entry perception actually files, built by the
    function that files it rather than by hand here."""
    ledger = {}
    perception._composer_finish_observer(
        ctx, "perception_outcome", pid, PLAYER, rendered, known or {},
        list(roster), views if views is not None else {}, {},
        ledger, prev_meta=prev_meta, track_standing_meta=track)
    return ledger[pid]


def test_a_suppressed_fact_keeps_the_beat_it_was_last_said_on():
    """The whole mechanism in one place: rendered at beat 3, suppressed at
    beat 9 because the observer already holds it, and the record still says
    when it was last put into words and what those words were."""
    percepts = _percepts()
    key = percepts[0].dedupe_key

    shown = composer.render_view(percepts, mode="player")
    assert shown.text.strip()
    meta = perception._standing_meta({}, shown, 3, shown.text)
    assert meta[key]["first_turn"] == 3
    assert meta[key]["last_rendered_turn"] == 3
    assert meta[key]["sentence"] == shown.text.strip()

    quiet = composer.render_view(percepts, mode="player",
                                 prev_standing=frozenset(shown.standing_keys))
    assert quiet.text == "", "the tier suppresses a fact already delivered"
    later = perception._standing_meta(meta, quiet, 9, quiet.text)
    assert later[key]["last_rendered_turn"] == 3
    assert later[key]["first_turn"] == 3
    assert later[key]["sentence"] == meta[key]["sentence"]


def test_a_fact_that_changed_takes_its_old_sentence_with_it():
    """`composer.standing_key` hashes subject and CONTENT separately, so a
    changed fact mints a different key. The record follows the key, which is
    what stops a stale sentence outliving its own subject."""
    shown = composer.render_view(_percepts(), mode="player")
    meta = perception._standing_meta({}, shown, 3, shown.text)

    moved = _percepts(clause="his hand on your shoulder", manner="rest")
    changed = composer.render_view(moved, mode="player")
    after = perception._standing_meta(meta, changed, 4, changed.text)

    assert list(after) == [moved[0].dedupe_key]
    assert list(meta) != list(after)


def test_a_key_that_never_reached_a_sentence_has_nothing_to_refer_back_to():
    """A standing key filed by a view that rendered no sentence for it (a
    voice key, a percept the tier dropped) is a fact with no delivered
    wording, and an entry for it would be a reference to nothing."""
    key = _percepts()[0].dedupe_key
    bare = composer.RenderedView(text="", spans=[], standing_keys={key},
                                 described=set())
    assert perception._standing_meta({}, bare, 5, "") == {}


def test_perception_files_the_record_only_for_a_seat_that_reads_it():
    """The player tier is the only view that suppresses what it already
    delivered, so it is the only one where "not said for N beats" is a real
    state -- and the narrator is its only reader. Absent, never empty,
    everywhere else: a chat stored before the field has no record, not an
    empty one."""
    ctx = _StubCtx(idx=7)
    shown = composer.render_view(_percepts(), mode="player")

    filed = _filed(ctx, shown, {})
    assert set(filed["standing_meta"]) == set(shown.standing_keys)

    assert "standing_meta" not in _filed(ctx, shown, {}, pid="Sable",
                                        track=False)


def test_the_narrator_reads_what_perception_wrote_and_only_past_its_window():
    """The two halves against each other (the B28 join, one field over):
    `perception_outcome` / `composer_ledger` / `player` / `standing_meta` are
    string literals typed independently on the two sides. And the threshold
    is the narrator's OWN window -- a fact last rendered inside
    `past_narration` is already on the page the model reads, so only one
    older than that is invisible."""
    percepts = _percepts()
    shown = composer.render_view(percepts, mode="player")
    quiet = composer.render_view(percepts, mode="player",
                                 prev_standing=frozenset(shown.standing_keys))

    at_three = _filed(_StubCtx(idx=3), shown, {})
    at_twenty = _filed(_StubCtx(idx=20), quiet, at_three["standing_meta"])
    ctx = _StubCtx(idx=20, perception_outcome={
        "composer_ledger": {"player": at_twenty}})

    inside = narration._player_long_established(ctx, 20, 30)
    assert inside == [], "still inside the page the narrator can read"

    outside = narration._player_long_established(ctx, 20, 12)
    assert [row["detail"] for row in outside] == [shown.text.strip()]
    assert outside[0]["unmentioned_for"] == 17

    # Another seat's ledger is not this seat's answer, and a chat stored
    # before the field reads as no record rather than as a silent detail.
    assert narration._player_long_established(
        ctx, 20, 12, pid="extra:2") == []
    assert narration._player_long_established(_StubCtx(idx=20), 20, 12) == []


#: A body this observer has no channel to the identity of, carrying the
#: appearance the unknown-actor descriptor is built from. The contact itself
#: is unchanged, so every clause below files under one dedupe key.
STRANGER = [{"name": "Sable", "appearance": "a tall figure in a grey coat",
             "aliases": []}]


def test_a_sentence_the_identity_tripwire_repaired_is_not_what_gets_filed():
    """THE RECORD IS BUILT FROM THE DELIVERED VIEW, not from `rendered`.

    `rendered.spans` is the composition BEFORE `_composer_tripwires` runs. A
    composer defect that put an unearned name into the player's view is
    repaired there -- the view says "the tall figure", and the warning says
    Layer A admitted a fact with no channel -- but this record outlives the
    beat, so filing the pre-repair wording would hand the scrubbed name back
    to the narrator dozens of beats later, under a key the observer really
    does hold. The contract is that when a tripwire fires, nothing crosses.
    """
    ctx = _StubCtx(idx=4)
    rendered = composer.render_view(
        _percepts(clause="Sable's hand closes on your wrist"), mode="player")
    assert "Sable" in rendered.text, "the composer defect this stands in for"

    views = {}
    filed = _filed(ctx, rendered, {}, known={PLAYER: []}, roster=STRANGER,
                   views=views)
    assert any("unearned identity" in w for w in ctx.warnings)
    assert "Sable" not in (views["player"] or "")

    meta = filed["standing_meta"]
    assert "Sable" not in json.dumps(meta)
    # Nothing older to fall back on, so the key files nothing at all rather
    # than filing the repaired half of a sentence.
    assert meta == {}

    later = _StubCtx(idx=40, perception_outcome={
        "composer_ledger": {"player": filed}})
    assert narration._player_long_established(later, 40, 12) == []


def test_a_repaired_beat_leaves_the_older_delivered_wording_standing():
    """The same key, once it HAS been delivered cleanly: the tripwire beat
    files no new sentence, so the entry keeps the wording this observer was
    actually given and the beat it was given on. The detail stays sayable;
    only the repaired text is refused."""
    clean = composer.render_view(
        _percepts(clause="a gloved hand closes on your wrist"), mode="player")
    key = sorted(clean.standing_keys)[0]
    first = _filed(_StubCtx(idx=2), clean, {})

    # The same contact, so the same key -- but this beat's composition names
    # an identity the observer has no channel to.
    leaky = composer.render_view(
        _percepts(clause="Sable's gloved hand closes on your wrist"),
        mode="player")
    ctx = _StubCtx(idx=9)
    filed = _filed(ctx, leaky, first["standing_meta"], known={PLAYER: []},
                   roster=STRANGER)
    assert any("unearned identity" in w for w in ctx.warnings)

    entry = filed["standing_meta"][key]
    assert "Sable" not in entry["sentence"]
    assert entry["sentence"] == first["standing_meta"][key]["sentence"]
    assert entry["last_rendered_turn"] == 2, "a repaired beat is no delivery"

    at_twenty = _StubCtx(idx=20, perception_outcome={
        "composer_ledger": {"player": filed}})
    rows = narration._player_long_established(at_twenty, 20, 12)
    assert [row["detail"] for row in rows] == [clean.text.strip()]
    assert "Sable" not in json.dumps(rows)


def test_the_narrator_is_told_how_long_the_detail_has_been_standing():
    """`first_turn` has a reader: the two numbers are different facts about
    one detail. Something planted in the opening beat and unsaid for twelve
    beats is furniture the story has lived with; something introduced twelve
    beats ago and unsaid since is a loose end."""
    percepts = _percepts()
    shown = composer.render_view(percepts, mode="player")
    quiet = composer.render_view(percepts, mode="player",
                                 prev_standing=frozenset(shown.standing_keys))
    at_two = _filed(_StubCtx(idx=2), shown, {})
    at_thirty = _filed(_StubCtx(idx=30), quiet, at_two["standing_meta"])
    ctx = _StubCtx(idx=30, perception_outcome={
        "composer_ledger": {"player": at_thirty}})

    row = narration._player_long_established(ctx, 30, 12)[0]
    assert row["unmentioned_for"] == 28
    assert row["established_for"] == 28

    # A record stored before either number existed still says something true
    # rather than nothing.
    ctx["perception_outcome"]["composer_ledger"]["player"] = {
        "standing_meta": {"k": {"sentence": "The lamp still burns.",
                                "last_rendered_turn": 4}}}
    row = narration._player_long_established(ctx, 30, 12)[0]
    assert row["unmentioned_for"] == row["established_for"] == 26
