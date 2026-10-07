"""A post is its people's between watches -- in the Writers' Room's view too.

`inspect_charters` showed each post's `held_by`, which is the WATCH: who is
standing it this hour. Asked to file who keeps the inn, the Room answered
"the world has not yet said which of them stands behind that bar" -- while
the inn's keeper, `home_post: keeper`, off watch and resting, stood in his
own taproom (scratch story 165, 2026-10-07). The same rule as the presence
records (`background_presence_records`): a keeper between watches is still
the keeper.
"""

from story.room_tools import POST_MEMBERS_SHOWN, _charter_post_rows


def _inn(hands):
    bodies = {"keeper:0001": {"name": "Fetoard Hollelwick", "home_post": "keeper"}}
    for n in range(1, hands + 1):
        bodies["house_hand:%04d" % n] = {"name": "Hand %d" % n,
                                         "home_post": "house_hand"}
    return {"key": "inn", "bodies": bodies,
            "posts": {"keeper": {"place": "inn_common"},
                      "house_hand": {"place": "inn_common"}},
            "watch": {"house_hand": "house_hand:0001"}}


def test_an_off_watch_keeper_is_still_the_keepers():
    rows = {row["key"]: row for row in _charter_post_rows(_inn(2))}
    keeper = rows["keeper"]
    assert keeper["held_by"] == "", "nobody is standing it this hour"
    assert keeper["members"] == [{"body": "keeper:0001",
                                  "name": "Fetoard Hollelwick"}]
    assert "members_withheld" not in keeper


def test_a_crowded_post_counts_what_it_does_not_list():
    rows = {row["key"]: row for row in _charter_post_rows(
        _inn(POST_MEMBERS_SHOWN + 3))}
    hands = rows["house_hand"]
    assert len(hands["members"]) == POST_MEMBERS_SHOWN
    assert hands["members_withheld"] == 3
    assert "section='bodies'" in hands["members_ask"]
