"""An act that names a body the observer cannot see loses THAT clause only,
in a Japanese story as in an English one.

`_act_surface_admission` cuts the span of an act's observable that names a
body outside the observer's own sight, and keeps the actor's own conduct --
"a floor subtracts what the rule states and no more". Its clause split knew
only ASCII `, ; :` and dashes with spaces round them, so a Japanese
observable (clauses joined by 、, no spaces) was ONE span, and naming one
unseen body cut the whole act -- the actor's visible conduct with it
(agents_common audit F7: `('', ['イヴォ'])`).
"""

from __future__ import annotations

from language_runtime import language_scope

from agents.common import _act_surface_admission


def test_a_japanese_act_keeps_the_clauses_that_name_nobody_unseen():
    with language_scope("ja"):
        kept, cut = _act_surface_admission(
            "グラスを持ち上げ、イヴォの素顔を眺め、ゆっくりと一口飲む",
            actor="ヴェリン", observer="ミラ",
            forms_by_body={"イヴォ": ["イヴォ"]}, perceived=set(), who="ミラ")
    assert (kept, cut) == ("グラスを持ち上げ、ゆっくりと一口飲む", ["イヴォ"])


def test_the_english_act_is_cut_as_before():
    kept, cut = _act_surface_admission(
        "lifts his glass, looks over Ivo's uncovered face, takes a slow sip",
        actor="Verrin", observer="Mira", forms_by_body={"Ivo": ["Ivo"]},
        perceived=set(), who="Mira")
    assert (kept, cut) == ("lifts his glass, takes a slow sip", ["Ivo"])
