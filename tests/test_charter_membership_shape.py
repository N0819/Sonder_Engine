"""An institution described only as its own org chart, and the warning that
says so.

MEASURED CASE (chat 95, charter `starfleet_crew`, generated from a brief
asking for a thousand people on three shifts): 24 bodies across 7 posts,
`home_post` non-empty for all 24, and rank a strict function of post -- 7
posts, 7 distinct (post, rank) pairs, so 3 of the naming law's 6 rungs were
carried by nobody and 2 of them were unreachable by construction. The root of
the chain of command (`reports_to: ""`) held three bodies. What the player
read, faithfully composed from that membership by code that was correct at
every step, was "a dozen or so captains and commanders pulling transit watch".

`registry_warnings` is the surface this repo already built for a consequence
rule that would otherwise fail silently. It refuses no charter and rewrites
nothing: an institution of nothing but post-holders is legal, and small ones
are legitimately shaped that way. What it may not do is arrive unremarked.
"""

from __future__ import annotations

from world.charter_runtime import registry_warnings


def _institution(posts, bodies, *, ranks=None):
    """One charter in the engine's own vocabulary -- no domain nouns, because
    the rule is about the SHAPE of a membership and not about any trade."""
    return {"guild": {
        "key": "guild",
        "upkeeps": {"the_work_continues": {"place": "hall"}},
        "posts": posts,
        "bodies": bodies,
        "naming": {"titles": {"ranks": dict(ranks or {})}},
    }}


def _posts(*keys, reports_to=None):
    return {key: {"place": "hall", "serves": ["the_work_continues"],
                  "reports_to": (reports_to or {}).get(key, "")}
            for key in keys}


def _staff(post, rank, count, start=1):
    return {f"{post}:{index:04d}": {"name": f"{post} {index}",
                                    "home_post": post, "rank": rank}
            for index in range(start, start + count)}


def test_an_institution_whose_every_member_holds_a_post_is_named():
    """Chat 95's shape, reduced to the tell: no body outside a post, rank a
    function of post, and more bodies than posts -- an org chart replicated
    into a population rather than a population organised by one."""
    bodies = {}
    for post, rank in (("first", "high"), ("second", "middle"),
                       ("third", "low")):
        bodies.update(_staff(post, rank, 3))
    warnings = registry_warnings(_institution(
        _posts("first", "second", "third"), bodies))
    assert any("no rank-and-file" in warning for warning in warnings), warnings


def test_members_who_hold_no_post_answer_the_question():
    """The complement, and the only thing that has to change for the warning
    to stop: somebody in the institution who is not one of its offices."""
    bodies = {}
    for post, rank in (("first", "high"), ("second", "middle"),
                       ("third", "low")):
        bodies.update(_staff(post, rank, 3))
    bodies.update({f"hand:{i:04d}": {"name": f"hand {i}", "home_post": "",
                                     "rank": "low"} for i in range(1, 8)})
    warnings = registry_warnings(_institution(
        _posts("first", "second", "third"), bodies))
    assert not any("no rank-and-file" in warning for warning in warnings), \
        warnings


def test_an_institution_no_larger_than_its_own_offices_is_left_alone():
    """One body per post is a small institution, not a defective one. The
    tell is REPLICATION -- more bodies than posts, and every one of them a
    post-holder."""
    bodies = {}
    for post, rank in (("first", "high"), ("second", "middle"),
                       ("third", "low")):
        bodies.update(_staff(post, rank, 1))
    warnings = registry_warnings(_institution(
        _posts("first", "second", "third"), bodies))
    assert not any("no rank-and-file" in warning for warning in warnings), \
        warnings


def test_a_rank_the_naming_law_defines_and_nobody_carries_is_named():
    """Two of chat 95's six rungs were carried by zero bodies and unreachable
    by construction, because rank was only ever acquired by being minted into
    a post and no post carried them. Visible on the day of generation."""
    bodies = _staff("first", "high", 1)
    warnings = registry_warnings(_institution(
        _posts("first"), bodies,
        ranks={"high": "High", "middle": "Middle", "low": "Low"}))
    assert any("'middle'" in warning and "carried by no body" in warning
               for warning in warnings), warnings
    assert not any("'high'" in warning and "carried by no body" in warning
                   for warning in warnings), warnings


def test_a_chain_of_command_with_more_than_one_top_is_named():
    """docs/UNBUILT.md 1.84b's half, from `reports_to` alone: a post nobody
    reports to is an address, and one word resolving to two minds is the same
    defect as two bodies sharing a display name. Chat 95: three bodies on the
    root post."""
    warnings = registry_warnings(_institution(
        _posts("first", "second", reports_to={"second": "first"}),
        {**_staff("first", "high", 3), **_staff("second", "middle", 1)}))
    assert any("root of the chain of command" in warning
               for warning in warnings), warnings


def test_co_equal_posts_are_not_a_chain_and_are_not_flagged():
    """`reports_to` empty on every post means no hierarchy was authored at
    all, not that every post is a top. Cardinality is only readable where a
    chain exists."""
    warnings = registry_warnings(_institution(
        _posts("first", "second"),
        {**_staff("first", "high", 3), **_staff("second", "middle", 3)}))
    assert not any("root of the chain of command" in warning
                   for warning in warnings), warnings


def test_the_two_fixture_institutions_stay_quiet():
    """Tune-against, not a claim about them: SHIP and ABBEY are authored, hold
    no `home_post` and no rank ladder, and must not start emitting membership
    warnings the day this check lands."""
    from tests.charter_fixtures import ABBEY, SHIP

    for fixture in (SHIP, ABBEY):
        warnings = registry_warnings({fixture["key"]: fixture})
        assert not any("no rank-and-file" in warning
                       or "carried by no body" in warning
                       or "root of the chain of command" in warning
                       for warning in warnings), warnings
