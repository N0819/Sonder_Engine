"""The correction path, driven through the real Director resolution.

`tests/test_director_result_validation.py` proves the component contracts --
registration, correction values, ordering, read-only access, policy. Directive's
author read those and asked, correctly, for something they cannot give: they
assert on `inspect.getsource` that the pipeline calls the seam, which is a claim
about the source text and not about the orchestration
(`docs/design/DIRECTIVE_HARDENING_REPORT.md` §2).

So this file drives `director_resolve` itself with controlled model responses
and observes the retry boundary from outside. What only a pipeline test can
prove:

  * validation runs AFTER every engine-owned floor, on the settled result;
  * the violation reaches the SECOND Director request, attributed;
  * the whole resolution reruns rather than the first result being patched;
  * exactly one correction attempt, ever;
  * a surviving violation under `fail` ends the beat before commit.
"""

from __future__ import annotations

import json
import time

import pytest

import extension_runtime
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

from tests.conftest import fanout_resolve_agent
from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _enable, _write_extension, ext_root, real_ext_root,
)

SEALED = "deck_4"


def _ctx(temp_db):
    """A story with an open room and a sealed one, and a declared move."""
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Campaign", "", time.time()))
    sheet = default_character_data("Reyes")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reyes", json.dumps(sheet), "{}", time.time(), "char_reyes"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "Deck 3", "time": "night",
        "rooms": {
            "corridor": {"name": "Corridor", "adjacent": [
                {"to": SEALED, "barrier": "open", "distance": "near"}]},
            SEALED: {"name": "Deck 4", "adjacent": [
                {"to": "corridor", "barrier": "open", "distance": "near"}]},
        },
        "positions": {"The Stranger": "corridor", "Reyes": "corridor"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "look around", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Campaign", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="look around", created=time.time()),
        cast=cast, input="look around")
    # NO declared movement. The first Director answer invents the move into the
    # sealed room, which is the case a campaign invariant exists for -- and the
    # only case a correction can actually fix. Writing this fixture the obvious
    # way (declaring the move) made every attempt fail the invariant, because
    # the movement backstop honours a passable declared move and re-created the
    # violation after the validator had refused it. That is correct engine
    # behaviour and worth knowing: a validator cannot talk the Director out of
    # something the PLAYER declared, only out of something it invented.
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None, "movement": None,
        "flow": {"reactors": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    return ctx


def _responses(monkeypatch, outputs):
    """Serve one whole-beat resolve per Director call, in order.

    Records every `director_resolve` payload so a test can count the calls and
    read what the second request was actually told.
    """
    import agents.director as director

    seen = []
    served = {"n": 0}

    def fake(role, step_key, system, payload, **kw):
        if step_key == "director_resolve":
            index = min(served["n"], len(outputs) - 1)
            served["n"] += 1
            seen.append(payload)
            return fanout_resolve_agent(outputs[index])(
                role, step_key, system, payload, **kw)
        # Specialists answer from whichever whole-beat output is current.
        current = outputs[min(max(served["n"] - 1, 0), len(outputs) - 1)]
        return fanout_resolve_agent(current)(role, step_key, system, payload,
                                             **kw)

    monkeypatch.setattr(director, "_agent_json", fake)
    return seen


ENTERS = {"resolved_event": "She steps through onto Deck 4.",
          "state_diff": {"positions": {"The Stranger": SEALED}}}
STAYS = {"resolved_event": "The hatch does not give. She stays in the corridor.",
         "state_diff": {"positions": {}}}


@pytest.fixture
def campaign(ext_root):
    _write_extension(ext_root, "campaign", {
        "id": "campaign", "version": "1.0.0", "ext_api": 1, "name": "Campaign",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("campaign")
    return extension_runtime._apis["campaign"]


def _seal(api, *, policy="warn", seen=None):
    """Refuse any result that puts a body on the sealed deck."""
    def validator(result, info):
        if seen is not None:
            seen.append(dict(result.positions))
        if SEALED in (result.positions or {}).values():
            return info.api.correction(
                "sealed-location",
                "Deck 4 remains sealed; no committed movement may enter it.",
                evidence={"room_id": SEALED})
        return None

    api.on_director_result(validator, on_error=policy)


class TestSuccessfulCorrection:
    def test_the_corrected_result_is_the_one_returned(self, temp_db,
                                                      monkeypatch, campaign):
        _seal(campaign)
        ctx = _ctx(temp_db)
        seen = _responses(monkeypatch, [ENTERS, STAYS])

        out = director_resolve(ctx)

        assert len(seen) == 2, "exactly one correction attempt"
        assert SEALED not in (out["state_diff"].get("positions") or {}).values()
        assert "does not give" in out["resolved_event"]

    def test_the_second_request_carries_the_attributed_violation(
            self, temp_db, monkeypatch, campaign):
        """The violation must reach the MODEL, not just the log -- otherwise the
        second attempt is a reroll with no idea what was wrong with the first."""
        _seal(campaign)
        ctx = _ctx(temp_db)
        seen = _responses(monkeypatch, [ENTERS, STAYS])

        director_resolve(ctx)

        second = seen[1]
        violations = second.get("campaign_violations") or []
        assert [v["code"] for v in violations] == ["sealed-location"]
        assert violations[0]["extension"] == "campaign"
        assert violations[0]["evidence"] == {"room_id": SEALED}
        note = second.get("correction_notes") or ""
        assert "sealed-location" in note and "campaign" in note
        assert "Deck 4 remains sealed" in note

    def test_the_first_request_carried_no_violation(self, temp_db, monkeypatch,
                                                    campaign):
        _seal(campaign)
        ctx = _ctx(temp_db)
        seen = _responses(monkeypatch, [ENTERS, STAYS])

        director_resolve(ctx)

        assert "campaign_violations" not in seen[0]

    def test_the_validator_judged_the_settled_result_both_times(
            self, temp_db, monkeypatch, campaign):
        """Not a prose-author draft: what it saw is what the merged diff said
        after every floor, and it saw the corrected one too."""
        judged = []
        _seal(campaign, seen=judged)
        ctx = _ctx(temp_db)
        _responses(monkeypatch, [ENTERS, STAYS])

        director_resolve(ctx)

        assert len(judged) == 2
        assert judged[0].get("The Stranger") == SEALED
        assert judged[1].get("The Stranger") != SEALED

    def test_a_valid_first_result_costs_no_second_call(self, temp_db,
                                                       monkeypatch, campaign):
        _seal(campaign)
        ctx = _ctx(temp_db)
        seen = _responses(monkeypatch, [STAYS])

        director_resolve(ctx)

        assert len(seen) == 1


class TestFailClosed:
    def test_a_surviving_violation_under_fail_ends_the_beat(
            self, temp_db, monkeypatch, campaign):
        from agents.director import CampaignInvariantError

        _seal(campaign, policy="fail")
        ctx = _ctx(temp_db)
        seen = _responses(monkeypatch, [ENTERS, ENTERS])

        with pytest.raises(CampaignInvariantError) as excinfo:
            director_resolve(ctx)

        assert len(seen) == 2, "the retry stays bounded even when it fails"
        assert "campaign" in str(excinfo.value)
        assert "sealed-location" in str(excinfo.value)

    def test_it_raises_before_anything_is_committed(self, temp_db, monkeypatch,
                                                    campaign):
        """The stage raising IS the no-partial-state guarantee: commit runs
        after this stage, so a beat that dies here never opened a transaction.
        Pinned by observing the scene is untouched."""
        from agents.director import CampaignInvariantError
        from scene import get_scene

        _seal(campaign, policy="fail")
        ctx = _ctx(temp_db)
        _responses(monkeypatch, [ENTERS, ENTERS])
        before = json.dumps(get_scene(ctx.chat.id)["positions"], sort_keys=True)

        with pytest.raises(CampaignInvariantError):
            director_resolve(ctx)

        assert json.dumps(get_scene(ctx.chat.id)["positions"],
                          sort_keys=True) == before

    def test_the_same_survival_under_warn_keeps_the_beat(self, temp_db,
                                                         monkeypatch, campaign):
        """`warn` is the default for the reason every seam here has one: a
        broken extension must not cost a turn. The violation is still recorded
        on the step where the next reader will find it."""
        _seal(campaign, policy="warn")
        ctx = _ctx(temp_db)
        seen = _responses(monkeypatch, [ENTERS, ENTERS])

        out = director_resolve(ctx)

        assert len(seen) == 2
        assert [v["code"] for v in out["campaign_violations"]] \
            == ["sealed-location"]
        assert any("survived correction" in w for w in ctx.warnings)


class TestOrderingAcrossExtensions:
    def test_two_extensions_appear_in_deterministic_order(
            self, temp_db, monkeypatch, campaign, ext_root):
        """Two campaigns disagreeing about one beat must produce the same
        correction note every run, including a reroll."""
        _write_extension(ext_root, "alpha", {
            "id": "alpha", "version": "1.0.0", "ext_api": 1, "name": "Alpha",
            "capabilities": {"python": "extension.py", "chat_state": True},
        }, {"extension.py": "def register(api):\n    pass\n"})
        _enable("campaign", "alpha")
        for ext_id in ("campaign", "alpha"):
            api = extension_runtime._apis[ext_id]
            api.on_director_result(
                lambda result, info, _e=ext_id: info.api.correction(
                    f"{_e}-rule", f"{_e} refuses this"))
        ctx = _ctx(temp_db)
        seen = _responses(monkeypatch, [ENTERS, STAYS])

        director_resolve(ctx)

        codes = [v["code"] for v in seen[1]["campaign_violations"]]
        assert codes == ["alpha-rule", "campaign-rule"]
        note = seen[1]["correction_notes"]
        assert note.index("alpha-rule") < note.index("campaign-rule")


def director_resolve(ctx):
    import agents.director as director

    return director.director_resolve(ctx, nonce=0)
