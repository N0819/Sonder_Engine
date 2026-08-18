"""Nobody speaks in display strings.

`known` gates every identity the engine will let a mind use, and the only
play-time path into it is `_names_heard_in`: a name learned when it is SPOKEN
in your hearing, of somebody standing in the room with you.

It required the roster's stored display string to appear verbatim. Names are
stored as `The Doctor`, `Cmdr. Vale`, `Jean-Luc Picard`; people say "Doctor",
"Vale", "Picard". So the ordinary way of addressing somebody taught nobody
anything.

Measured on chat 63: 552 dialogue lines, of which 95 carry an exact display
name and 120 carry a spoken form of one -- and "Doctor" appears in 33 lines
against a roster holding "The Doctor". The engine's own data shows the same
split from the other side: chat 22's recognition map holds `Data` and `Lt.
Commander Data`, `Deanna Troi` and `Counselor Troi`, as separate people who do
not know each other.

The honest denominator matters here and is recorded so nobody re-tunes this on
the wrong number: `_names_heard_in` landed 2026-08-04 in alpha 7.2, and since
then the whole database has offered it THREE lines carrying a cast name. It is
not a mechanism proven broken by disuse -- it is a mechanism two days old whose
matching rule was too strict, and the 166-turn history that predates it will
stay empty regardless, because nothing backfills.
"""

from __future__ import annotations

from persist import commit

SHRINE = ["Hinami", "Tamamo", "The Doctor"]
SCENE = {"positions": {"Hinami": "hall", "Tamamo": "hall",
                       "The Doctor": "hall"}}


def _heard(quote, hearer="Tamamo", roster=None):
    return commit._names_heard_in(quote, hearer, roster or SHRINE,
                                  SCENE, "hall")


def test_the_live_line_that_taught_nobody_anything():
    """THE REPRODUCTION. Chat 63 turn 165, the player's own words. She names
    him in the first three characters of the beat and he learned nothing.
    """
    assert _heard('Doctor. I\'m going to rest for today...') == ["The Doctor"]


def test_an_article_is_not_part_of_how_a_name_is_said():
    """`The Doctor` is addressed as "Doctor" and referred to as "the Doctor".
    Both are the same person and only one used to match.
    """
    assert _heard("Doctor, look at this") == ["The Doctor"]
    assert _heard("the Doctor said it was fine") == ["The Doctor"]
    assert _heard("The Doctor is here") == ["The Doctor"]


def test_a_surname_or_the_noun_under_a_title():
    """`Cmdr. Vale` is called Vale; `Jean-Luc Picard` is called Picard."""
    roster = ["Cmdr. Vale", "Jean-Luc Picard"]
    scene = {"positions": {"Cmdr. Vale": "bridge", "Jean-Luc Picard": "bridge"}}
    got = commit._names_heard_in("Vale, report", "Worf", roster, scene, "bridge")
    assert got == ["Cmdr. Vale"]
    got = commit._names_heard_in("Picard is on the bridge", "Worf", roster,
                                 scene, "bridge")
    assert got == ["Jean-Luc Picard"]


def test_a_form_two_people_share_identifies_neither():
    """Inventing an edge is worse than missing one: a wrong recognition cannot
    be told from a right one afterwards and nothing downstream can catch it.
    """
    roster = ["Jean-Luc Picard", "Robert Picard"]
    scene = {"positions": {"Jean-Luc Picard": "hall", "Robert Picard": "hall"}}
    assert commit._names_heard_in("Picard!", "Worf", roster, scene, "hall") == []
    # ...and the unambiguous full form still lands.
    assert commit._names_heard_in("Jean-Luc Picard!", "Worf", roster, scene,
                                  "hall") == ["Jean-Luc Picard"]


def test_a_name_that_is_also_an_ordinary_word_needs_its_capital():
    """The guard that keeps this from becoming noise, and the reason the word
    list is shared with `_scrub_unknown_identities` rather than rewritten.
    """
    roster = ["Data"]
    scene = {"positions": {"Data": "bridge"}}
    assert commit._names_heard_in("the sensor data is corrupted", "Worf",
                                  roster, scene, "bridge") == []
    assert commit._names_heard_in("Data, run the scan", "Worf", roster, scene,
                                  "bridge") == ["Data"]


def test_both_original_refusals_survive():
    """Widening WHAT counts as saying a name must not widen who it teaches.
    A name spoken of somebody absent teaches a name, not a face; and your own
    name teaches you nothing.
    """
    absent = {"positions": {"Hinami": "hall", "Tamamo": "hall"}}
    assert commit._names_heard_in("Doctor will know", "Tamamo", SHRINE,
                                  absent, "hall") == []
    elsewhere = {"positions": {"The Doctor": "upstairs", "Tamamo": "hall"}}
    assert commit._names_heard_in("Doctor?", "Tamamo", SHRINE, elsewhere,
                                  "hall") == []
    assert _heard("Tamamo, please", hearer="Tamamo") == []


def test_a_short_fragment_is_not_a_name():
    """Two-character forms match too much to be worth the edge they would
    write; the floor is deliberate rather than incidental.
    """
    forms = commit._address_forms(["Jo", "Xi Wu"])
    assert "Jo" not in forms.get("Jo", set())
    assert "Wu" not in forms.get("Xi Wu", set())
