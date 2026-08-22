"""Superseded prose has to say it is superseded.

A turn is a chain of steps, and a step is marked stale BEFORE it is recomputed
so that an interrupted rerun leaves an accurate breadcrumb instead of
downstream content that goes on looking fresh. That is deliberate and it works.
What did not work was telling anybody.

`chat_get` collapsed per-step staleness to one boolean per turn, so the host UI
could only dim -- a dim says something is off and cannot say what. `guest_state`
omitted the field entirely and `guest.html` set `className = "turn"`
unconditionally, so an invited guest got no signal at all, not even the dim:
prose written before an upstream step was re-run reached them looking exactly
like current prose.

Found in the field, on chat 56 turn idx 11 of a real engine database -- the only
turn in 1,727 with any stale steps. Its narration quotes a character saying
"left hand" while the active interaction_loop, re-run 76 minutes later, has them
say "right hand". Both halves are internally consistent; the contradiction lives
only across the seam, and the seam was invisible.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest

STATIC = Path(__file__).resolve().parents[1] / "static"


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    guest._join_attempts.clear()
    guest._login_attempts.clear()
    with TestClient(app_module.app) as c:
        r = c.post("/api/auth/setup",
                   json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield c
    guest.reset_host_account()
    guest._join_attempts.clear()
    guest._login_attempts.clear()


def _chat(db, name="Run!"):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "", time.time()))


def _turn(db, chat_id, idx, player_input=""):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, player_input, time.time()))


def _step(db, turn_id, key, label, ordn, stale=0, content=None):
    """One step of a turn, with its active variant."""
    sid = db.qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,?)",
        (turn_id, key, label, ordn, stale))
    db.qi("INSERT INTO variants(step_id,content,created,active) "
          "VALUES(?,?,?,1)",
          (sid, json.dumps(content if content is not None else {}),
           time.time()))
    return sid


def _interrupted_turn(db, chat_id, idx=0):
    """The shape a rerun that stopped partway through actually leaves.

    Ords 0-3 were reached and un-staled themselves as they succeeded; ords 4-8
    were marked before the run began and never recomputed. This is chat 56 turn
    11, reproduced -- and the same shape a single-step reroll produces.
    """
    tid = _turn(db, chat_id, idx, "Which lever?!")
    plan = [("director_interpret", "Director · interpret", 0, 0),
            ("mapping_quick", "Mapping · cached recall", 1, 0),
            ("perception_act", "Perception · pass 1", 2, 0),
            ("interaction_loop", "Characters · interaction loop", 3, 0),
            ("director_resolve", "Director · resolve", 4, 1),
            ("background_react", "Background · presence", 5, 1),
            ("perception_outcome", "Perception · pass 2", 6, 1),
            ("narrator", "Narrator · render", 7, 1),
            ("commit", "Mapping & memory · commit", 8, 1)]
    for key, label, ordn, stale in plan:
        _step(db, tid, key, label, ordn, stale,
              {"prose": "the brass lever by your left hand"}
              if key == "narrator" else {})
    return tid


def _turns_of(client, chat_id):
    r = client.get(f"/api/chats/{chat_id}")
    assert r.status_code == 200, r.text
    return r.json()["turns"]


# --------------------------------------------------------------------------
# The host payload
# --------------------------------------------------------------------------

def test_a_turn_with_nothing_stale_does_not_claim_to_be_stale(client, temp_db):
    """The degenerate case, which is almost every turn in a real database --
    exactly one turn in 1,727 had any stale steps. A serializer that reports
    staleness on a clean turn would put a warning under the entire transcript.
    """
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid, 0)
    _step(temp_db, tid, "narrator", "Narrator · render", 0, 0, {"prose": "ok"})

    turn = _turns_of(client, cid)[0]
    assert turn["stale"] is False
    assert turn["stale_from"] is None
    assert turn["prose_stale"] is False


def test_stale_from_names_the_earliest_stale_step(client, temp_db):
    """A reader needs to know WHICH step was re-run underneath the prose. The
    payload carried only a boolean, so the UI could dim and nothing more --
    and a dim tells a reader something is off without telling them what.
    """
    cid = _chat(temp_db)
    _interrupted_turn(temp_db, cid)

    turn = _turns_of(client, cid)[0]
    assert turn["stale"] is True
    assert turn["stale_from"] == {"ord": 4, "key": "director_resolve",
                                  "label": "Director · resolve"}


def test_the_earliest_stale_step_is_the_lowest_ord_not_the_first_row(
        client, temp_db):
    """TAKING rows[0] IS CORRECT ONLY WHILE THE ORDER BY HOLDS. Row order is a
    property of the query, not of the data, and a later edit to that query --
    or an index the planner chooses differently -- would silently start naming
    whichever stale step happened to come back first.

    Here the rows are inserted so that the lowest `ord` is NOT the lowest row
    id, which is what first-row indexing would return.
    """
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid, 0)
    # Inserted out of plan order on purpose: commit (ord 8) gets the smaller
    # rowid, director_resolve (ord 4) the larger.
    _step(temp_db, tid, "commit", "Mapping & memory · commit", 8, 1)
    _step(temp_db, tid, "director_resolve", "Director · resolve", 4, 1)
    _step(temp_db, tid, "narrator", "Narrator · render", 7, 1, {"prose": "x"})

    turn = _turns_of(client, cid)[0]
    assert turn["stale_from"]["ord"] == 4
    assert turn["stale_from"]["key"] == "director_resolve"


def test_prose_stale_is_true_only_when_the_narrator_itself_went_stale(
        client, temp_db):
    """Two different sentences hang off this. A turn whose narrator is stale
    shows prose that was actually superseded; a turn stale only DOWNSTREAM of
    the narrator shows prose that still stands, with later bookkeeping
    unfinished. Collapsing them would tell a reader their text is wrong when it
    is not, which is the fastest way to get the warning ignored.
    """
    cid = _chat(temp_db)
    tid = _turn(temp_db, cid, 0)
    _step(temp_db, tid, "narrator", "Narrator · render", 7, 0, {"prose": "ok"})
    _step(temp_db, tid, "commit", "Mapping & memory · commit", 8, 1)

    turn = _turns_of(client, cid)[0]
    assert turn["stale"] is True
    assert turn["stale_from"]["key"] == "commit"
    assert turn["prose_stale"] is False


def test_two_stale_turns_in_one_chat_each_get_their_own_answer(
        client, temp_db):
    """The bucketing path. One query now serves the whole chat, so every turn
    reads its answer out of a shared dict -- and a bucketing bug would show up
    only here, as one turn wearing another's `stale_from`. It cannot be caught
    in the field: exactly one turn in the entire engine has stale steps, so
    this configuration does not occur there.
    """
    cid = _chat(temp_db)
    _interrupted_turn(temp_db, cid, idx=0)

    tid2 = _turn(temp_db, cid, 1)
    _step(temp_db, tid2, "narrator", "Narrator · render", 7, 1, {"prose": "y"})
    _step(temp_db, tid2, "commit", "Mapping & memory · commit", 8, 1)

    tid3 = _turn(temp_db, cid, 2)
    _step(temp_db, tid3, "narrator", "Narrator · render", 7, 0, {"prose": "z"})

    first, second, third = _turns_of(client, cid)
    # The interrupted turn's stale tail runs ords 4-8, and the narrator is ord
    # 7 -- so its prose IS superseded. That is the field case: the reader of
    # chat 56 turn 11 is looking at text written before the re-run.
    assert first["stale_from"]["key"] == "director_resolve"
    assert first["prose_stale"] is True
    assert second["stale_from"]["key"] == "narrator"
    assert second["prose_stale"] is True
    assert third["stale"] is False and third["stale_from"] is None


def test_the_whole_chat_costs_one_stale_query_not_one_per_turn(
        client, temp_db, monkeypatch):
    """This replaced a per-turn `SELECT COUNT(*) ... WHERE turn_id=?`, so the
    widened payload is CHEAPER than the boolean it replaced. A later refactor
    that moved the query back inside the loop would restore the N+1 while every
    other test here still passed.
    """
    cid = _chat(temp_db)
    for idx in range(6):
        _interrupted_turn(temp_db, cid, idx=idx)

    seen = []
    real_q = app_module.q

    def counting_q(sql, *args, **kwargs):
        if "FROM steps" in sql and "stale" in sql:
            seen.append(sql)
        return real_q(sql, *args, **kwargs)

    monkeypatch.setattr(app_module, "q", counting_q)
    turns = _turns_of(client, cid)

    assert len(turns) == 6
    assert len(seen) == 1, f"{len(seen)} stale queries for 6 turns: {seen}"


# --------------------------------------------------------------------------
# The guest payload -- which used to carry none of this
# --------------------------------------------------------------------------

def _guest_client(client, temp_db, chat_id):
    """A joined guest, in a browser of its own with no host cookie."""
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Guest Persona", "{}", "{}"))
    temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status) "
               "VALUES(?,?,'active')", (chat_id, persona_id))
    invite = client.post(f"/api/chats/{chat_id}/guest_invites",
                         json={"persona_id": persona_id}).json()
    gc = TestClient(app_module.app)
    r = gc.post("/api/join", json={"code": invite["code"]})
    assert r.status_code == 200, r.text
    return gc, persona_id


def test_a_guest_is_told_when_the_prose_was_superseded(client, temp_db):
    """THE GUEST GOT NOTHING AT ALL -- not the field, and so not even the dim
    the host page draws from it. Superseded prose reached an invited reader
    looking exactly like current prose, which is the worst of the three
    surfaces because a guest cannot open the pipeline view to find out.
    """
    cid = _chat(temp_db)
    gc, pid = _guest_client(client, temp_db, cid)
    tid = _interrupted_turn(temp_db, cid)
    # What a guest reads is their own per-persona render.
    _step(temp_db, tid, "narrator_extra", "Narrator · per player", 9, 1,
          {str(pid): {"prose": "the brass lever by your left hand"}})

    turn = gc.get("/api/guest/state").json()["turns"][0]
    assert turn["stale"] is True
    assert turn["stale_from"]["key"] == "director_resolve"
    assert turn["prose_stale"] is True


def test_a_guest_reading_a_stale_narrator_extra_is_warned_about_it(
        client, temp_db):
    """THE TWO HANDLERS DIVERGE ON PURPOSE, and this pins the reason so a
    later reader does not "fix the inconsistency" and silently break it.

    The prose a guest reads comes from `narrator_extra`, which is its own step
    key -- not content written by the `narrator` step. Keying the guest's
    warning on `narrator` alone would key it on a step that does not produce
    what the guest is looking at. So `guest_state` takes the union of the two,
    and on a turn whose only stale step is `narrator_extra` it says the prose
    is superseded while `chat_get`, correctly, does not.
    """
    cid = _chat(temp_db)
    gc, pid = _guest_client(client, temp_db, cid)
    tid = _turn(temp_db, cid, 0)
    _step(temp_db, tid, "narrator", "Narrator · render", 7, 0, {"prose": "ok"})
    _step(temp_db, tid, "narrator_extra", "Narrator · per player", 8, 1,
          {str(pid): {"prose": "superseded"}})

    guest_turn = gc.get("/api/guest/state").json()["turns"][0]
    assert guest_turn["prose_stale"] is True

    host_turn = _turns_of(client, cid)[0]
    assert host_turn["stale"] is True
    assert host_turn["prose_stale"] is False


def test_a_guest_on_a_clean_turn_is_not_warned(client, temp_db):
    """The control for the guest lane. A warning on every turn is the same as
    no warning at all.
    """
    cid = _chat(temp_db)
    gc, pid = _guest_client(client, temp_db, cid)
    tid = _turn(temp_db, cid, 0)
    _step(temp_db, tid, "narrator_extra", "Narrator · per player", 8, 0,
          {str(pid): {"prose": "current"}})

    turn = gc.get("/api/guest/state").json()["turns"][0]
    assert turn["stale"] is False
    assert turn["stale_from"] is None
    assert turn["prose_stale"] is False


# --------------------------------------------------------------------------
# The two renderers. Server-side alone is inert.
# --------------------------------------------------------------------------

def test_the_guest_page_marks_a_stale_turn_and_says_why():
    """`guest.html` loads no application JS -- only an inline script -- so the
    fix is two-part and the server half is inert without this one. It used to
    set `className = "turn"` unconditionally, so the shared stylesheet's
    `.turn.stale .prose` rule could never match.
    """
    html = (STATIC / "guest.html").read_text(encoding="utf-8")
    assert 't.stale ? "ui-guest-turn turn stale" : "ui-guest-turn turn"' in html
    assert "t.stale_from" in html
    assert "t.prose_stale" in html
    assert "Superseded" in html and "Partly out of date" in html


def test_the_host_page_writes_a_sentence_and_not_only_a_dim():
    """The dim already existed. What it could not do was name the step, which
    is the only part a reader can act on.
    """
    chat_js = (STATIC / "js" / "chat.js").read_text(encoding="utf-8")
    assert "t.stale_from" in chat_js
    assert "stale-note" in chat_js
    assert "Superseded" in chat_js and "Partly out of date" in chat_js


def test_the_dim_the_notes_sit_under_still_exists():
    """Both notes are written on the assumption that the prose above them is
    already dimmed by the shared stylesheet -- guest.html links it too. If that
    rule were dropped the notes would still render and the visual signal they
    explain would be gone.
    """
    legacy_css = (STATIC / "styles.css").read_text(encoding="utf-8")
    guest_css = (STATIC / "css" / "ui" / "guest.css").read_text(encoding="utf-8")
    assert ".turn.stale .prose" in legacy_css
    assert ".stale-note" in legacy_css
    assert ".ui-guest-turn.stale .ui-guest-turn__prose" in guest_css
    assert ".ui-guest-turn__stale" in guest_css
    assert '/static/css/ui/guest.css' in (
        STATIC / "guest.html").read_text(encoding="utf-8")
