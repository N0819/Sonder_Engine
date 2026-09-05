"""Authority expires with its request, and a total grant means every kind.

Two measured defects, one rule each (`story/mandates.py`, module note).

* PE14, the flat run, 2026-09-05: the player granted `arrival` for a
  courier on turn 11 and withdrew the idea in words on turn 16 -- "I don't
  want the courier at all any more". The room cleared the package and said
  so; `mandate_831d8f2fa3` was still active, because a grant is state and a
  retraction in words is not.
* F11/F15, chat 114, 2026-09-04: "I'll give you full authority." was
  written down as the list of kinds that existed on turn 5, and
  `director_note` -- added later -- was refused under it until the player
  happened to say the word again.
"""

import pytest

from story import mandates


@pytest.fixture()
def chat(temp_db):
    from core import db
    return db.qi("INSERT INTO chats(name,created) VALUES('t',0)")


def _grant(chat, **kw):
    kw.setdefault("text", "plan me a courier")
    kw.setdefault("capabilities", ["arrival"])
    return mandates.grant_mandate(chat, None, **kw)


# -- the total grant ---------------------------------------------------------

def test_a_total_grant_authorises_a_kind_invented_after_it_was_written():
    """The rule, stated without a database: `permits` resolves the total
    grant against the capability being asked for, so a kind the vocabulary
    learns tomorrow is covered by a grant written today."""
    row = {"capabilities": [mandates.TOTAL_CAPABILITY]}
    assert mandates.permits(row, "director_note")
    assert mandates.permits(row, "a_kind_nobody_has_built_yet")


def test_a_total_grant_covers_a_package_that_needs_a_later_kind(chat):
    """F11/F15, end to end through the check that actually refused."""
    _grant(chat, text="I'll give you full authority.",
           capabilities=[mandates.TOTAL_CAPABILITY])
    cov = mandates.coverage(chat, None, ["director_note", "plan_rooms"])
    assert cov["ok"] and not cov["missing"]
    assert cov["cited"], "the grant that covered it is named"


def test_an_enumerated_grant_is_still_a_snapshot(chat):
    """The complement, so the fix is not read as "grants cover everything":
    a grant that listed its kinds still covers exactly those."""
    _grant(chat, text="plan rooms for me", capabilities=["plan_rooms"])
    cov = mandates.coverage(chat, None, ["plan_rooms", "director_note"])
    assert cov["missing"] == ["director_note"]


def test_the_total_grant_reaches_the_limits_readers_too(chat):
    """Every reader of a row's capabilities goes through `permits`, so
    there is no second answer to the same question."""
    _grant(chat, text="full authority, four fills an hour",
           capabilities=[mandates.TOTAL_CAPABILITY],
           limits={"fills_per_hour": 3})
    assert mandates.fill_limit(chat, None) == 3


# -- the grant that lapses with its request ----------------------------------

def test_a_grant_does_not_authorise_an_operation_after_its_request_closes(chat):
    """PE14. The ask ends; the licence ends with it."""
    row = _grant(chat, request={"uid": "req_courier",
                                "text": "bring a courier at dusk"})
    assert mandates.coverage(chat, None, ["arrival"])["ok"]

    mandates.close_request(chat, None, "req_courier")

    cov = mandates.coverage(chat, None, ["arrival"])
    assert not cov["ok"] and cov["missing"] == ["arrival"]
    lapsed = [m for m in mandates._load(chat, None) if m["uid"] == row["uid"]]
    assert lapsed[0]["status"] == "expired"
    assert lapsed[0]["lapsed_reason"] == "request_closed", (
        "a grant that disappears without a reason is one the player has to "
        "be told about twice")


def test_a_grant_scoped_to_a_package_lapses_when_the_package_is_retired(chat):
    """The half that needs nobody to remember: the work the grant licensed
    is over, so the licence is."""
    from story.plot_packages import new_package, retire_package

    pkg = new_package(chat, title="The courier", premise="someone comes")
    _grant(chat, request={"uid": pkg["uid"], "text": "the courier plan"})
    assert mandates.coverage(chat, None, ["arrival"])["ok"]

    retire_package(chat, pkg["uid"], note="the player withdrew it")
    assert not mandates.coverage(chat, None, ["arrival"])["ok"]


def test_a_grant_naming_no_request_still_stands(chat):
    """Every grant before this one was standing, and stays standing."""
    _grant(chat)
    mandates.close_request(chat, None, "req_courier")
    assert mandates.coverage(chat, None, ["arrival"])["ok"]


def test_renewal_is_an_explicit_act_and_a_new_row(chat):
    """A licence that came back to life in place would leave no record that
    anyone asked for it twice."""
    row = _grant(chat, request={"uid": "req_courier"})
    mandates.close_request(chat, None, "req_courier")

    renewed = mandates.renew_mandate(chat, None, row["uid"],
                                     request={"uid": "req_courier_again"})
    assert renewed["uid"] != row["uid"]
    assert renewed["renewed_from"] == row["uid"]
    assert renewed["capabilities"] == row["capabilities"]
    assert mandates.coverage(chat, None, ["arrival"])["ok"]

    old = [m for m in mandates._load(chat, None) if m["uid"] == row["uid"]][0]
    assert old["status"] == "expired", "the lapsed grant stays lapsed"


def test_the_request_survives_every_save(chat):
    """`_save` normalizes every row on every write, so a field the
    normalizer does not carry is a field that silently disappears."""
    _grant(chat, request={"uid": "req_courier", "text": "a courier at dusk"})
    _grant(chat, text="and a summons", capabilities=["summons"])
    stored = [m for m in mandates._load(chat, None)
              if m["request"] and m["request"]["uid"] == "req_courier"]
    assert stored and stored[0]["request"]["text"] == "a courier at dusk"


def test_an_ask_the_engine_holds_no_row_for_ends_only_when_closed(chat):
    """A licence must not lapse on a guess: the sweep resolves the two kinds
    of ask the engine actually holds, and nothing else."""
    row = _grant(chat, request={"uid": "something_only_we_said"})
    assert row["request"]["kind"] == "other"
    assert mandates.active_mandates(chat, None)
