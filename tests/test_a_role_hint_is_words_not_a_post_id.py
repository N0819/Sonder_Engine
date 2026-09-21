"""What a stranger is TAKEN FOR is words, never a post id.

`background_presence_records` builds a presence's `role_hint` by joining the
raw watch-post keys, falling back to "member of <charter_key>" -- both of them
engine spellings. The hint reaches a perceived label
(`_unknown_actor_label(role=...)`), so snake_case walked into what a body sees
across a room.

Measured (Aldermill, fourth run, 2026-09-19): an ostler asked for an ale was
shown his own colleagues as

    "the salt-and-pepper stout inn_cook with heat rash along forearms"
    "the salt-and-pepper spry member of wheel_and_bushel"

Nobody perceives `inn_cook`. The charter already holds the readable forms --
`naming.titles.posts` gives "Miller" for `miller_journeyman`, and
`charter_crowd._role_noun` cleans an id to its words for exactly this reason
-- so this reads them rather than inventing a second vocabulary.

Same class as the crowd noun that rendered "a handful of journeymans": an id
is a key, and a key is not a thing anybody sees.
"""

from world.charter_runtime import _readable_role


def test_a_post_id_becomes_its_words():
    assert _readable_role({}, ["inn_cook"], "wheel_and_bushel") == "inn cook"


def test_an_authored_title_wins_over_the_id():
    naming = {"titles": {"posts": {"miller_journeyman": "Miller"}, "ranks": {}}}
    assert _readable_role(naming, ["miller_journeyman"], "aldermill_works") \
        == "Miller"


def test_several_posts_read_as_a_list():
    assert _readable_role({}, ["inn_cook", "tap_hand"], "x") == "inn cook, tap hand"


def test_the_fallback_names_the_house_in_words():
    assert _readable_role({}, [], "wheel_and_bushel") == "member of wheel and bushel"


def test_a_trailing_slot_marker_is_not_a_kind_of_person():
    """`_role_noun`'s own rule: ids carry disambiguators -- `patrol_a`,
    `tapster_2` -- and a trailing single letter or digit distinguishes a
    slot, never a kind of person."""
    assert _readable_role({}, ["tapster_2"], "x") == "tapster"
