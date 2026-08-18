"""An extension may refuse a Director result, and buy one repair.

`api.director_context` puts a campaign rule in front of the decision, and that
is model input: it can guide a result and cannot guarantee one. A commit domain
can refuse the transaction afterwards, but its only move is to lose the beat --
a turn thrown away where a corrected turn was possible, with the explanation
arriving after the whole pipeline has been paid for.

This is the seam between them. A validator judges the MERGED result, after
every deterministic floor this engine owns has run, and either accepts it or
returns a structured violation that buys exactly one re-resolution. The
corrected answer goes back through every floor and every validator again.

Specification and acceptance tests: `docs/design/DIRECTIVE_REMAINING_GAPS.md`
§1.
"""

from __future__ import annotations

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _enable, _write_extension, ext_root, real_ext_root,
)

RESULT = {"resolved_event": "The door opens and she steps through.",
          "state_diff": {"positions": {"Hinami": "deck_4"}}}


@pytest.fixture
def campaign(ext_root):
    _write_extension(ext_root, "campaign", {
        "id": "campaign", "version": "1.0.0", "ext_api": 1, "name": "Campaign",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("campaign")
    return extension_runtime._apis["campaign"]


def _second(ext_root, ext_id="alpha"):
    _write_extension(ext_root, ext_id, {
        "id": ext_id, "version": "1.0.0", "ext_api": 1, "name": ext_id.title(),
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    return ext_id


def _run(chat_id, result=None):
    return extension_runtime.validate_director_result(
        _StubCtx(chat_id=chat_id), result if result is not None else RESULT)


# ------------------------------------------------------------- the contract


class TestTheValidator:
    def test_a_clean_result_produces_no_violation(self, temp_db, campaign):
        campaign.on_director_result(lambda result, info: None)

        assert _run(_chat(temp_db)) == ([], False)

    def test_a_violation_is_structured_and_attributed(self, temp_db, campaign):
        @campaign.on_director_result
        def sealed(result, info):
            if "deck_4" in result.positions.values():
                return info.api.correction(
                    "sealed-location",
                    "Deck 4 remains sealed; no committed movement may enter it.",
                    evidence={"room_id": "deck_4"})
            return None

        violations, fatal = _run(_chat(temp_db))

        assert fatal is False
        assert violations == [{
            "extension": "campaign", "validator": "sealed",
            "code": "sealed-location",
            "message": "Deck 4 remains sealed; no committed movement may enter it.",
            "evidence": {"room_id": "deck_4"},
        }]

    def test_it_judges_the_merged_result(self, temp_db, campaign):
        """Not a prose-author fragment and not one specialist's channel: what
        a validator is shown is what would actually be committed."""
        seen = {}
        campaign.on_director_result(
            lambda result, info: seen.update(
                event=result.resolved_event, positions=result.positions))

        _run(_chat(temp_db))

        assert seen["positions"] == {"Hinami": "deck_4"}
        assert seen["event"].startswith("The door opens")

    def test_a_validator_cannot_mutate_the_result(self, temp_db, campaign):
        """A validator that could edit the result directly would be a second
        author of objective causality, and the Director would never learn its
        answer had been changed underneath it."""
        def meddle(result, info):
            result.resolve["resolved_event"] = "Something else entirely."
            result.positions["Hinami"] = "somewhere_else"
            return None

        campaign.on_director_result(meddle)
        result = {"resolved_event": "The door opens.",
                  "state_diff": {"positions": {"Hinami": "deck_4"}}}
        _run(_chat(temp_db), result)

        assert result["resolved_event"] == "The door opens."
        assert result["state_diff"]["positions"] == {"Hinami": "deck_4"}

    def test_a_validator_gets_no_model_handle(self, temp_db, campaign):
        """Deterministic code. A campaign invariant that needs a model call to
        evaluate is not an invariant, and paying for one inside the beat's wall
        clock to decide whether the beat may finish is the cost this avoids."""
        from extension_runtime.api import DirectorResult

        assert not hasattr(DirectorResult, "llm_json")
        assert not hasattr(DirectorResult, "llm_text")

    def test_ordering_is_stable_across_extensions(self, temp_db, campaign,
                                                   ext_root):
        """Two extensions disagreeing about one beat must produce the same
        notes in the same order on every run, including a reroll."""
        _second(ext_root, "alpha")
        _enable("campaign", "alpha")
        for ext_id in ("campaign", "alpha"):
            api = extension_runtime._apis[ext_id]
            api.on_director_result(
                lambda result, info, _e=ext_id: info.api.correction(
                    f"{_e}-rule", f"{_e} refuses"))

        violations, _ = _run(_chat(temp_db))

        assert [v["extension"] for v in violations] == ["alpha", "campaign"]

    def test_several_violations_from_one_validator_all_travel(self, temp_db,
                                                               campaign):
        campaign.on_director_result(lambda result, info: [
            info.api.correction("one", "first"),
            info.api.correction("two", "second"),
        ])

        violations, _ = _run(_chat(temp_db))

        assert [v["code"] for v in violations] == ["one", "two"]

    def test_disabling_the_extension_removes_its_validator(self, temp_db,
                                                            campaign):
        campaign.on_director_result(
            lambda result, info: info.api.correction("x", "refused"))
        extension_runtime.disable_extension("campaign")

        assert _run(_chat(temp_db)) == ([], False)


class TestFailurePolicy:
    def test_a_warning_validator_that_raises_costs_nothing(self, temp_db,
                                                            campaign):
        def broken(result, info):
            raise RuntimeError("campaign planner exploded")

        campaign.on_director_result(broken)
        ctx = _StubCtx(chat_id=_chat(temp_db))

        violations, fatal = extension_runtime.validate_director_result(
            ctx, RESULT)

        assert (violations, fatal) == ([], False)
        assert any("result validator" in w for w in ctx.warnings)

    def test_a_failing_validator_that_raises_has_not_approved_the_beat(
            self, temp_db, campaign):
        """An extension whose rule cannot even be evaluated has not said yes."""
        def broken(result, info):
            raise RuntimeError("cannot read mission state")

        campaign.on_director_result(broken, on_error="fail")

        violations, fatal = _run(_chat(temp_db))

        assert fatal is True
        assert violations[0]["code"] == "validator-error"

    def test_the_policy_is_refused_rather_than_guessed(self, temp_db,
                                                        campaign):
        with pytest.raises(ExtensionError):
            campaign.on_director_result(lambda r, i: None, on_error="maybe")


class TestTheCorrectionValue:
    def test_an_oversized_message_is_refused_rather_than_truncated(
            self, temp_db, campaign):
        with pytest.raises(ExtensionError) as excinfo:
            campaign.correction("x", "m" * 601)

        assert "600" in str(excinfo.value)

    def test_unserialisable_evidence_is_refused(self, temp_db, campaign):
        """It ends up in a model payload and on the durable turn. Evidence that
        survives neither is a violation nobody can read afterwards."""
        with pytest.raises(ExtensionError):
            campaign.correction("x", "m", evidence={"fn": lambda: None})

    def test_evidence_is_optional_and_absent_when_not_given(self, temp_db,
                                                             campaign):
        assert "evidence" not in campaign.correction("x", "m").as_dict()


# --------------------------------------------------------------- the wiring


class TestTheWiring:
    def test_the_resolve_validates_last_of_all(self):
        """After every deterministic floor, so a validator judges what would
        actually be committed."""
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)
        backstop = source.index('_orchestration_scope_backstop(ctx, out, "resolve")')
        validate = source.index("_validate_campaign_result(ctx, out)")

        assert validate > backstop

    def test_a_refusal_re_enters_the_whole_stage(self):
        """Not a patch applied in place. Re-entering is what makes the
        corrected result trustworthy: every floor runs again over it, in order,
        and the validators run again over that."""
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)

        assert "out = director_resolve(ctx, nonce, _corrections=_violations)" \
            in source

    def test_the_correction_is_bounded_to_one_attempt(self):
        """`_corrections` is the recursion guard and the bound in one: the
        second pass carries the violations, and never validates again."""
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)

        assert "if _corrections is None:" in source

    def test_the_violations_ride_the_channel_the_retries_already_use(self):
        """So the Director reads a campaign violation the way it reads a
        player-authority one -- attributed, specific, about this beat."""
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)

        assert '"correction_notes": _campaign_correction_note(_corrections)' \
            in source

    def test_only_a_fail_policy_can_end_the_beat(self):
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)
        raise_at = source.index("raise CampaignInvariantError")
        guard = source.rindex("if _again_fatal:", 0, raise_at)

        assert guard < raise_at

    def test_the_seam_is_total_apart_from_a_declared_failure(self):
        """An unreachable or broken registry leaves the beat exactly as the
        engine resolved it."""
        import agents.director as director

        assert director._validate_campaign_result(None, RESULT) == ([], False)

    def test_a_reroll_uses_the_same_contract(self):
        """A reroll re-runs this stage, so the validation is the stage's and
        needs no second registration -- which is the property to pin, because a
        contract that applied only to a first attempt would be one a player
        could reroll their way past."""
        import inspect

        import agents.director as director

        assert "_validate_campaign_result" in inspect.getsource(
            director.director_resolve)
