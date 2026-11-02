"""Layer A writes no English, and no ASCII stop, into a Japanese view.

For `sensation`, `substance` and `ambient` percepts the Japanese renderer
prints `data["clause" | "text" | "desc"]` verbatim, so whatever Layer A
writes there IS the Japanese page; a label likewise. Three Layer-A sites wrote
English or an ASCII-only stop test there (audit agents_composer F9,
2026-11-01):

  (a) `ambient_percepts` appended `_en("sound_echo")` -- English always:
      「鐘の音が鳴り響く。, and the place gives it back」;
  (b) `room_content_percepts` and `chatter_percepts` tested `".!?"` and added
      "." -- 「群衆がざわめいている。.」;
  (c) the literal "someone" for a body the observer was not shown, which the
      Japanese adapter does not translate (it translates only "you").

The class rule: Layer A text goes through the ACTIVE pack (`_t`, the pack's
own stops). English stays byte-identical.
"""

import pytest

from agents import composer
from language_runtime import language_scope


def test_an_echo_is_said_in_the_storys_language():
    event = {"room": "nave", "detail": "鐘の音が鳴り響く。", "echo": True,
             "kind": "sound"}
    with language_scope("ja"):
        [p] = composer.ambient_percepts([event], "nave")
    desc = p.data["desc"]
    assert "place gives it back" not in desc and "。," not in desc, desc
    assert desc.startswith("鐘の音が鳴り響く"), desc
    # English is unchanged.
    with language_scope("en"):
        [en] = composer.ambient_percepts(
            [{"room": "nave", "detail": "A bell tolls.", "echo": True,
              "kind": "sound"}], "nave")
    assert en.data["desc"] == "A bell tolls, and the place gives it back"


@pytest.mark.parametrize("builder", ["room_content_percepts",
                                     "chatter_percepts"])
def test_a_japanese_line_keeps_its_own_stop(builder):
    entry = {"what": "群衆がざわめいている。", "uid": "crowd-1"}
    with language_scope("ja"):
        [p] = getattr(composer, builder)([entry])
    assert p.data["desc"] == "群衆がざわめいている。", p.data["desc"]
    with language_scope("ja"):
        [bare] = getattr(composer, builder)([{"what": "群衆がざわめいている",
                                              "uid": "crowd-1"}])
    assert bare.data["desc"] == "群衆がざわめいている。", bare.data["desc"]
    with language_scope("en"):
        [en] = getattr(composer, builder)([{"what": "a press of bodies",
                                            "uid": "crowd-1"}])
    assert en.data["desc"] == "a press of bodies."


def test_a_body_not_shown_is_someone_in_the_storys_language():
    with language_scope("ja"):
        parts = composer.body_part_percepts([("", {"kind": "尾"})])
        regions = composer.body_region_percepts([("", "肩", "長い傷跡")])
    for p in parts + regions:
        assert p.source_label != "someone", p
        assert not any("a" <= ch.casefold() <= "z" for ch in p.source_label), p
    with language_scope("en"):
        [en] = composer.body_region_percepts([("", "shoulder", "a scar")])
    assert en.source_label == "someone"


def test_a_pose_against_a_body_not_shown_names_no_english():
    """The observer's own pose, pinned beneath a body it was not shown."""
    scene = {"rooms": {"h": {"name": "広間", "light": "dark"}},
             "positions": {"Obs": "h", "Ghost": "h"},
             "poses": {"Obs": {"posture": "押さえつけられている",
                               "relative_to": "Ghost", "relation": "下に"},
                       # a pose of its own is what makes Ghost a BODY to
                       # `_names_a_body`; the observer was shown nobody
                       "Ghost": {"posture": "覆いかぶさっている"}}}
    with language_scope("ja"):
        [p] = composer.pose_percepts(scene, "Obs", [], {})
    assert "someone" not in str(p.data), p.data
    assert "誰か" in str(p.data.get("relative_to")), p.data
