"""Reader prose in the character payload follows the story's language.

`_VERDICTS` is a pack table and `tools/build_japanese_pack.py` translates every
row's reader half, so a Japanese story receives Japanese verdicts -- except for
the one verdict the code writes itself. `unentered` is minted inline in
`_verdict`, in English, along with the two frontier-distance clauses and the
circling detail that ride on top of any verdict. A Japanese character was
therefore handed a Japanese verdict with an English sentence welded to it, and
one whole verdict in English only.

`unentered` is not a minor row. It is the fix for the measured failure in maze
arm A11 run 3: the shrine the character was in the maze to reach is a
cul-de-sac, he walked sixteen optimal moves to its doorway, read "closed", and
turned around. Chamber 0603 was never entered in any run of the arm.
"""

from __future__ import annotations

from language_runtime import language_scope, linguistic

from agents.character import _verdict


def _cul_de_sac():
    return {"visibly_no_way_through": True, "untried": True}


def test_the_unentered_verdict_is_readable_in_english():
    entry = _verdict(_cul_de_sac())
    assert entry["verdict"].startswith("unentered")
    assert "never been inside it" in entry["verdict"]


def test_the_unentered_verdict_is_readable_in_japanese():
    with language_scope("ja"):
        entry = _verdict(_cul_de_sac())
    assert not any(ch.isascii() and ch.isalpha() for ch in entry["verdict"]), \
        entry["verdict"]


def test_the_frontier_distance_clause_follows_the_verdict_it_rides_on():
    """The distance rides ANY verdict that has one, so it cannot be English
    while the verdict beside it is not."""
    with language_scope("ja"):
        near = _verdict(_cul_de_sac(), frontier_hops=1)
        far = _verdict(_cul_de_sac(), frontier_hops=9)
    assert "9" in far["verdict"]
    for entry in (near, far):
        assert not any(ch.isascii() and ch.isalpha()
                       for ch in entry["verdict"]), entry["verdict"]


def test_the_marker_keys_stay_canonical_in_every_pack():
    """The label is the half a translator changes; the marker key is protocol
    -- it is what the engine writes onto an exit, and `_APPEAL_ORDER` ranks on
    it. A pack that translated a key would sort every exit last, silently."""
    for language_id in ("en", "ja"):
        keys = {row[0] for row in
                linguistic("agents.character", "_VERDICTS", language_id)}
        assert "visibly_no_way_through" in keys, language_id
        assert "untried" in keys, language_id
