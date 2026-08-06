"""One entry, two revisions, both handed to the model.

Lore entries ACCRETE -- the engine appends narrative events to them as a story
goes on -- and `world.lore_cache` stores SNAPSHOTS rather than references. So
the same entry can sit in the cache twice at two different lengths, and the
merge that is supposed to collapse them could not.

Measured live on chat 59: ten cached entries, nine distinct ids, entry 2213
present twice at 1,572 and 1,442 characters. The shorter copy stops at
"...homes like this matter."; the longer one continues "Later, Hinami retired
upstairs to rest...". Both went into `relevant_lore`, so the mapping payload
handed the model the same room twice at two revisions, one of which did not
know a character had gone upstairs.

That is a contradiction served as retrieved lore, not merely a wasted slot
under the 12-entry cap.
"""

from __future__ import annotations

import agents.mapping as mapping


def _entry(entry_id, content, uid=None, keys="shrine"):
    return {"id": entry_id, "entry_uid": uid, "keys": keys,
            "content": content, "category": "layout"}


# THE PRODUCTION FUNCTION, not a copy of it. An earlier draft of this file
# reimplemented the merge here and passed against a reverted `mapping.py` --
# a test that proves an algorithm rather than a deployment, which is the same
# shape as grading on a boolean your own script computed.
_merge = mapping.merge_lore


def test_two_revisions_of_one_entry_collapse_to_one():
    """THE DEFECT. The fresh copy carries `entry_uid`; the fossil, written by
    an older cache path, does not. Keyed `entry_uid or fingerprint`, the first
    keys on its uid and the second falls through to the fingerprint -- and a
    uid and a fingerprint live in different namespaces, so they can never
    collide however similar the entries are.
    """
    fresh = _entry(2213, "The shrine's main hall. Later, Hinami went upstairs.",
                   uid="entry_3428e0a1")
    fossil = _entry(2213, "The shrine's main hall.", uid=None)

    merged = _merge([fresh], [fossil])

    assert len(merged) == 1
    assert merged[0]["content"].endswith("Hinami went upstairs.")


def test_the_fingerprint_cannot_rescue_it():
    """Worth pinning separately, because "add a fingerprint fallback" is the
    obvious wrong fix. The fingerprint hashes keys+content, which is exactly
    what differs between two revisions -- so it distinguishes them by
    construction rather than collapsing them.
    """
    fresh = _entry(2213, "Main hall. Later, Hinami went upstairs.", uid=None)
    fossil = _entry(2213, "Main hall.", uid=None)

    assert (mapping._lore_fingerprint(fresh)
            != mapping._lore_fingerprint(fossil))
    assert len(_merge([fresh], [fossil])) == 1


def test_the_surviving_copy_is_the_freshly_retrieved_one():
    """`hits` precede `cache` in the merge, so keeping the first occurrence
    keeps what retrieval just found and drops the fossil. Reversed, the cache
    would overwrite live results with older text on every turn.
    """
    fresh = _entry(2213, "current text", uid="entry_abc")
    fossil = _entry(2213, "superseded text", uid=None)

    assert _merge([fresh], [fossil])[0]["content"] == "current text"
    # ...and the same holds when only the fossil carries a uid.
    assert _merge([_entry(2213, "current text", uid=None)],
                  [_entry(2213, "superseded text", uid="entry_abc")]
                  )[0]["content"] == "current text"


def test_genuinely_different_entries_are_still_both_kept():
    """The control. Collapsing on `id` must not collapse the corpus -- two
    rows with different ids are two entries however alike their text.
    """
    merged = _merge([_entry(2213, "the main hall", uid="a")],
                    [_entry(2214, "the main hall", uid="b")])
    assert len(merged) == 2


def test_an_entry_with_no_id_still_dedupes_on_what_it_has():
    """A cached dict predating the `id` field falls through to `entry_uid`,
    then to the fingerprint. Losing that ladder would reintroduce duplicates
    for the oldest rows -- the very ones most likely to be fossils.
    """
    a = {"entry_uid": "entry_x", "keys": "k", "content": "same"}
    b = {"entry_uid": "entry_x", "keys": "k", "content": "same"}
    assert len(_merge([a], [b])) == 1

    c = {"keys": "k", "content": "identical text"}
    d = {"keys": "k", "content": "identical text"}
    assert len(_merge([c], [d])) == 1
