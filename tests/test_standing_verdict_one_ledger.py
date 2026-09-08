"""One observer, one standing ledger, one answer to "is this news" (B28).

THE DISAGREEMENT: `composer.render_view` diffs this observer's standing
percepts against their own previous ledger and suppresses a contact the
ledger already carried -- and `narration._sensory_channels_manifest`
re-derived the same standing contacts straight from the scene, with no
ledger to read, and shipped each one's full sensation sentence again. Two
representations of one fact, free to disagree, and after the first beat they
always did: measured chat 117, a hand that never left a belt was re-delivered
to the narrator on 40 of 70 beats under a template ending "continuous while
the contact holds".

The ledger is authoritative. `RenderedView.verdicts` carries what each
standing key WAS for this observer, `perception_outcome` ships it in the
per-observer `composer_ledger`, and the manifest stamps it onto the entry it
re-delivers. Nothing is dropped -- a standing fact the narrator must not
contradict is still a fact -- but an `unchanged` one now arrives saying so.

The join between the two is the composer's own dedupe key, minted by the
composer's own percept builders at both sites; a key spelled a second time in
the narrator would be the same defect one level down.
"""

from agents import composer, narration, perception
from agents.narration import _sensory_channels_manifest


PLAYER = "Hero"
GRIP = {"actor": "Sable", "actor_part": "hand", "target": PLAYER,
        "target_part": "wrist", "manner": "grip"}


def _scene():
    return {
        "rooms": {"yard": {"name": "Yard", "adjacent": [], "light": "lit"}},
        "positions": {PLAYER: "yard", "Sable": "yard"},
        "entities": {}, "contacts": [dict(GRIP)], "attire": {}, "overlays": {},
    }


def _manifest(scene, verdicts=None):
    return _sensory_channels_manifest(
        scene, PLAYER, "", [], set(), {}, "yard",
        standing_verdicts=verdicts)


def _grip_key(scene):
    """The composer's key for the standing grip, minted the way perception
    mints it -- the manifest must look the verdict up under this one."""
    percepts = composer.contact_percepts([(scene["contacts"][0], "a clause")])
    return percepts[0].dedupe_key


def test_render_view_hands_out_the_verdicts_it_judged():
    """The player tier already computed the verdict; before this it spent it
    inside the render and threw it away, so every other re-delivery had to
    guess. Character mode diffs against no ledger and carries none."""
    percepts = composer.contact_percepts([(dict(GRIP), "his hand on you")])
    key = percepts[0].dedupe_key

    first = composer.render_view(percepts, mode="player")
    assert first.verdicts.get(key) == "first"

    again = composer.render_view(percepts, mode="player",
                                 prev_standing=frozenset({key}))
    assert again.verdicts.get(key) == "unchanged"
    assert again.verdicts.get(key) in composer.STANDING_VERDICTS

    assert composer.render_view(percepts, mode="character").verdicts == {}


def test_manifest_marks_a_contact_the_ledger_already_carried():
    """The fact survives -- the narrator must not narrate the hand elsewhere
    -- and it arrives labelled `unchanged` instead of as this beat's news."""
    scene = _scene()
    key = _grip_key(scene)

    held = _manifest(scene, verdicts={key: "unchanged"})["touch"]
    assert held["status"] == "live"
    entries = [row for row in held["standing"] if "wrist" in row["clause"]]
    assert entries and entries[0]["verdict"] == "unchanged"

    fresh = _manifest(scene, verdicts={key: "first"})["touch"]
    entries = [row for row in fresh["standing"] if "wrist" in row["clause"]]
    assert entries and entries[0]["verdict"] == "first"


def test_no_ledger_answer_reads_as_not_computed_never_as_unchanged():
    """An absent verdict is a missing record, not a claim: a chat stored
    before the field existed, and every standing fact the composer files no
    key for (weather, light, a substance) ship with no verdict at all. The
    safe degradation is that the fact reads as news, which is what the
    manifest did for all of them before."""
    scene = _scene()
    touch = _manifest(scene)["touch"]
    assert touch["status"] == "live"
    assert all("verdict" not in row for row in touch["standing"])

    sight = _manifest(scene)["sight"]
    assert [row["clause"] for row in sight["standing"]] == ["light: lit"]
    assert all("verdict" not in row for row in sight["standing"])

    # A key from some other observer's ledger is not this observer's answer.
    stale = _manifest(scene, verdicts={"contact:someone-else": "unchanged"})
    assert all("verdict" not in row for row in stale["touch"]["standing"])


def test_the_lookup_key_is_the_composers_and_not_a_second_spelling():
    """Perception files the ledger under `composer.contact_percepts`' key.
    If the manifest ever mints its own, every verdict silently misses and the
    payload goes back to shipping standing contacts as news -- passing tests
    and a wrong page, which is how this class hides."""
    scene = _scene()
    verdicts = {_grip_key(scene): "unchanged"}
    entries = _manifest(scene, verdicts=verdicts)["touch"]["standing"]
    assert any(row.get("verdict") == "unchanged" for row in entries)


class _StubCtx:
    """All `_composer_finish_observer` needs from a context on this path:
    somewhere to put a tripwire warning."""

    def __init__(self):
        self.warnings = []


def _filed_ledger(verdicts):
    """The per-observer ledger entry perception actually files, built by the
    function that files it rather than by hand here."""
    ledger = {}
    perception._composer_finish_observer(
        _StubCtx(), "perception_outcome", "player", PLAYER,
        composer.RenderedView(text="", spans=[], standing_keys=set(),
                              described=set(), verdicts=dict(verdicts)),
        set(), {}, {}, {}, ledger)
    return ledger["player"]


def test_perception_files_the_verdicts_and_no_key_where_it_has_none():
    """The WRITING half of the join (B28). A record that exists is this
    observer's answer; a record that is ABSENT is "not computed" -- an empty
    `verdicts` dict would instead read as "this observer was judged and
    nothing was said", the reading that lets a settled fact ship as news.
    The absent half was asserted nowhere."""
    key = _grip_key(_scene())

    assert _filed_ledger({key: "unchanged"})["verdicts"] == {key: "unchanged"}

    # Character mode diffs against no ledger and computes nothing, and so
    # does a chat stored before the field existed: no key, not an empty one.
    assert "verdicts" not in _filed_ledger({})


def test_the_narrator_reads_the_ledger_perception_wrote():
    """The READING half against the writing half, in one place (B28).
    `perception_outcome` / `composer_ledger` / `player` / `verdicts` are
    string literals typed independently on the two sides, and nothing bound
    them: rename either side, or move the read to another step key, and the
    payload silently reverts to unverdicted entries with every test still
    green. Here the narrator's own read is handed the ledger perception
    built."""
    key = _grip_key(_scene())
    outcome = {"views": {}, "observations": {},
               "composer_ledger": {"player": _filed_ledger({key: "unchanged"})}}

    verdicts = narration._player_standing_verdicts(
        {"perception_outcome": outcome})
    assert verdicts == {key: "unchanged"}

    # ...and the whole way through: the manifest stamps what that read found.
    entries = _manifest(_scene(), verdicts=verdicts)["touch"]["standing"]
    assert any(row.get("verdict") == "unchanged" for row in entries)

    # No stored step, or one from before the field: no verdicts, and the
    # manifest degrades to "not computed" rather than to "unchanged".
    assert narration._player_standing_verdicts({}) == {}
    assert narration._player_standing_verdicts(
        {"perception_outcome": {"composer_ledger": {}}}) == {}
