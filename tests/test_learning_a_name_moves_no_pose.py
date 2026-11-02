"""Learning a name moves nobody: a pose's ledger key is the arrangement, not
this observer's word for its referents.

`pose_percepts` keyed a pose on its RENDERED fields, and `support` /
`relative_to` are rendered through the observer's display map -- so Xan
leaning against "the woman in grey" and Xan leaning against "Yul" were two
different arrangements the moment the observer learned her name. Nothing
moved, and the player view led with `The tall man is leaning against Yul.`
as a numbered change the narrator must write (audit agents_composer F7,
2026-11-01; the 1.70 class's second half -- `scent_percepts` stopped hashing
"a fact about this observer's recognition of the source" long ago, the pose
key had not). The key now hashes what the referents ARE; what this observer
calls them is the sentence's business.
"""

from agents.composer import pose_percepts, render_view, standing_verdicts


def _scene(poses):
    return {
        "rooms": {"h": {"name": "Hall", "light": "bright"}},
        "positions": {"Obs": "h", "Xan": "h", "Yul": "h"},
        "poses": poses,
    }


BODIES = [{"name": "Xan"}, {"name": "Yul"}]
STRANGER = {"Xan": "the tall man", "Yul": "the woman in grey"}
NAMED = {"Xan": "the tall man", "Yul": "Yul"}


def _verdict(poses, before, after, subject):
    sc = _scene(poses)
    held = pose_percepts(sc, "Obs", BODIES, before)
    now = pose_percepts(sc, "Obs", BODIES, after)
    prev = frozenset(p.dedupe_key for p in held)
    [p] = [q for q in now if q.source_label == after.get(subject, "you")]
    return standing_verdicts(now, prev)[p.dedupe_key], now, prev


def test_another_bodys_pose_is_unchanged_when_its_referent_gets_a_name():
    verdict, now, prev = _verdict(
        {"Xan": {"posture": "leaning", "relative_to": "Yul",
                 "relation": "against"}}, STRANGER, NAMED, "Xan")
    assert verdict == "unchanged", verdict
    # ...and the player view does not lead the beat with it.
    view = render_view(now, mode="player", prev_standing=prev)
    assert "leaning" not in view.text, view.text


def test_your_own_pose_is_unchanged_when_its_referent_gets_a_name():
    verdict, _now, _prev = _verdict(
        {"Obs": {"posture": "sitting", "relative_to": "Yul",
                 "relation": "beside"}}, STRANGER, NAMED, "Obs")
    assert verdict == "unchanged", verdict


def test_a_pose_that_moved_is_still_a_change():
    sc = _scene({"Xan": {"posture": "leaning", "relative_to": "Yul",
                         "relation": "against"}})
    held = pose_percepts(sc, "Obs", BODIES, STRANGER)
    moved = pose_percepts(_scene({"Xan": {"posture": "kneeling",
                                          "relative_to": "Yul",
                                          "relation": "beside"}}),
                          "Obs", BODIES, NAMED)
    prev = frozenset(p.dedupe_key for p in held)
    assert set(standing_verdicts(moved, prev).values()) == {"changed"}
