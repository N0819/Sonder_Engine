"""An extension adds a channel of its own to the Director's record of a beat,
gated by its own question to the decision model (owner, 2026-09-28:
"Extensions api should be adjusted to add channels gated by their own jev
question").

The causal Director let an extension add a sixth specialist; that fan-out went
on 2026-09-27 and the call has raised since. A channel is what the one encoder
can carry: the decision model asks the extension's question beside the
engine's, the encoder holds the channel only when it is granted, and what it
writes is collected for the extension -- never split to an engine owner, never
dropped as a channel nobody owns, and never read by an engine domain.
"""

from __future__ import annotations

import pytest

import agents.director as director
import agents.director_prose as director_prose
import extension_runtime
from extension_runtime import CommitView, ExtensionError
from llm import decisions, prompts
from tests.director_fakes import _make_ctx, encoder_event, prose_resolve_agent
from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _enable, _write_extension, ext_root,
)

QUESTS = "ext:campaign:quests"
QUESTION = ("Does the passage advance, complete or abandon something the "
            "party set out to do?")
INSTRUCTIONS = ("One entry per step the passage takes toward a quest: "
                "{\"quest\": <quest id>, \"step\": <what was done>}.")


@pytest.fixture
def campaign(temp_db, ext_root):
    """One enabled extension whose python entry registers nothing, so each
    test declares the channel it is about."""
    _write_extension(ext_root, "campaign", {
        "id": "campaign", "version": "1.0.0", "ext_api": 1, "name": "Campaign",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("campaign")
    return extension_runtime._apis["campaign"]


def _quests(api, **kwargs):
    return api.add_director_channel("quests", question=QUESTION,
                                    instructions=INSTRUCTIONS,
                                    list_shaped=True, **kwargs)


def _resolve(temp_db, monkeypatch, seen, *transforms,
             prose="Mara hands the ledger to the clerk."):
    """A resolve beat whose encoder writes `transforms`; `seen` collects
    every model call with its system sheet."""
    ctx = _make_ctx(temp_db, interp={"sequence": []})
    fake = prose_resolve_agent(
        {"resolved_event": prose},
        per_step={"director_specialist": {"events": [encoder_event(
            prose, source="character:mara", transforms=list(transforms))],
            "missing_tools": [], "missing_referents": [], "notes": []}})

    def recording(role, step_key, system, payload, **kw):
        seen.append({"step_key": step_key, "system": system, "payload": payload})
        return fake(role, step_key, system, payload, **kw)

    monkeypatch.setattr(director, "_agent_json", recording)
    return ctx, director.director_resolve(ctx, nonce=0)


def _encoder_call(seen):
    [call] = [c for c in seen if c["step_key"] == "director_specialist"]
    return call


# --------------------------------------------------------------- registering


class TestRegistration:
    def test_a_channel_is_named_for_its_extension_and_kept_at_resolve(
            self, campaign):
        assert _quests(campaign) == QUESTS
        [spec] = extension_runtime.director_channels("resolve")
        assert spec["channel"] == QUESTS
        assert spec["question"] == QUESTION and spec["list_shaped"] is True
        # The finished beat by default: the declared attempt is not where a
        # record of what HAPPENED belongs.
        assert extension_runtime.director_channels("interpret") == []

    def test_declaring_it_twice_is_one_channel(self, campaign):
        _quests(campaign)
        _quests(campaign, stages=("interpret", "resolve"))
        [spec] = extension_runtime.director_channels()
        assert spec["stages"] == ("interpret", "resolve")

    @pytest.mark.parametrize("change", [
        {"name": "Bad Name"},
        {"question": ""},
        {"instructions": "  "},
        {"stages": ()},
        {"stages": ("narrate",)},
        {"record": "not a function"},
    ])
    def test_a_channel_that_could_never_work_is_refused_by_name(
            self, campaign, change):
        args = {"name": "quests", "question": QUESTION,
                "instructions": INSTRUCTIONS, **change}
        name = args.pop("name")
        with pytest.raises(ExtensionError) as caught:
            campaign.add_director_channel(name, **args)
        assert "campaign" in str(caught.value), str(caught.value)
        assert extension_runtime.director_channels() == []

    def test_a_disabled_extension_keeps_no_channel(self, campaign):
        _quests(campaign)
        extension_runtime.disable_extension("campaign")
        assert extension_runtime.director_channels() == []

    def test_the_host_names_the_capability(self, campaign):
        assert "director_channels" in campaign.capabilities

    def test_the_withdrawn_specialist_call_points_at_the_channel(self, campaign):
        with pytest.raises(ExtensionError) as caught:
            campaign.add_director_specialist("morale", channels=["ops"],
                                             prompt="judge morale")
        assert "add_director_channel" in str(caught.value)


# --------------------------------------------------------------------- a beat


class TestTheBeat:
    def test_the_decision_model_is_asked_the_extensions_own_question(
            self, temp_db, campaign, prose_director, monkeypatch):
        _quests(campaign)
        _resolve(temp_db, monkeypatch, [])
        assert any((battery["questions"].get(QUESTS) or {}).get("instructions")
                   == QUESTION for battery in prose_director), prose_director

    def test_granted_the_encoder_holds_it_and_writes_it_for_the_extension(
            self, temp_db, campaign, prose_director, monkeypatch):
        _quests(campaign)
        seen = []
        ctx, out = _resolve(temp_db, monkeypatch, seen, {
            "item": "Mara",
            "patch": {QUESTS: [{"quest": "ledger", "step": "handed over"}]}})
        call = _encoder_call(seen)
        assert INSTRUCTIONS in call["system"]
        assert QUESTS in call["payload"]["granted_tools"]
        assert out["orchestration"]["extension_channels"] == {
            QUESTS: [{"quest": "ledger", "step": "handed over"}]}
        # Collected for its extension, so not "a channel no owner holds".
        assert not any(QUESTS in w for w in ctx.warnings), ctx.warnings

    def test_refused_the_encoder_never_hears_of_it(
            self, temp_db, campaign, prose_director, monkeypatch):
        _quests(campaign)
        grant_all = decisions.OVERRIDE

        def refuse_the_extension(state, questions):
            answers = grant_all(state, questions)
            answers[QUESTS] = {"type": "noul", "noul": 0.01}
            return answers

        monkeypatch.setattr(decisions, "OVERRIDE", refuse_the_extension)
        seen = []
        _resolve(temp_db, monkeypatch, seen)
        call = _encoder_call(seen)
        assert INSTRUCTIONS not in call["system"]
        assert QUESTS not in call["payload"]["granted_tools"]

    def test_a_decision_model_that_cannot_answer_grants_it(
            self, temp_db, campaign, prose_director, monkeypatch):
        """Fail open with the engine's own channels: a longer sheet, never a
        lost change."""
        _quests(campaign)

        def unreachable(state, questions):
            raise decisions.DecisionError("no decision model")

        monkeypatch.setattr(decisions, "OVERRIDE", unreachable)
        seen = []
        _resolve(temp_db, monkeypatch, seen)
        assert INSTRUCTIONS in _encoder_call(seen)["system"]

    def test_a_granted_channels_record_reaches_the_encoder(
            self, temp_db, campaign, prose_director, monkeypatch):
        _quests(campaign, record=lambda chat_id: {"open": ["ledger"]})
        seen = []
        _resolve(temp_db, monkeypatch, seen)
        assert _encoder_call(seen)["payload"]["extension_records"] == {
            QUESTS: {"open": ["ledger"]}}

    def test_a_record_reader_that_raises_costs_the_record_not_the_beat(
            self, temp_db, campaign, prose_director, monkeypatch):
        def broken(chat_id):
            raise KeyError("ledger")

        _quests(campaign, record=broken)
        seen = []
        ctx, out = _resolve(temp_db, monkeypatch, seen)
        assert out["resolved_event"]
        assert "extension_records" not in _encoder_call(seen)["payload"]
        assert any("extension record unavailable" in w and QUESTS in w
                   for w in ctx.warnings), ctx.warnings

    def test_a_channel_nobody_registered_is_still_dropped_out_loud(
            self, temp_db, campaign, prose_director, monkeypatch):
        ctx, out = _resolve(temp_db, monkeypatch, [], {
            "item": "Mara", "patch": {"ext:campaign:morale": {"crew": "low"}}})
        assert "extension_channels" not in out["orchestration"]
        assert any("ext:campaign:morale" in w and "no channel owner" in w
                   for w in ctx.warnings), ctx.warnings


# ------------------------------------------------------------------- folding


def _specs(channel=QUESTS, *, list_shaped=True, stages=("resolve",)):
    return {channel: {"channel": channel, "list_shaped": list_shaped,
                      "stages": stages}}


MORALE = "ext:campaign:morale"


def test_list_entries_concatenate_in_event_order():
    """One entry written bare, without its list, is a list of one."""
    transforms = {2: [{"item": "b", "patch": {QUESTS: [{"n": 2}, {"n": 3}]}}],
                  1: [{"item": "a", "patch": {QUESTS: {"n": 1}}}]}
    assert director_prose.extension_channel_values(
        transforms, _specs(), "resolve") == {QUESTS: [{"n": 1}, {"n": 2}, {"n": 3}]}


def test_objects_merge_a_later_event_winning():
    transforms = {1: [{"item": "a", "patch": {MORALE: {"crew": "low", "captain": "steady"}}}],
                  2: [{"item": "b", "patch": {MORALE: {"crew": "breaking"}}}]}
    assert director_prose.extension_channel_values(
        transforms, _specs(MORALE, list_shaped=False), "resolve") == {
            MORALE: {"crew": "breaking", "captain": "steady"}}


def test_the_other_shape_is_dropped_out_loud():
    warnings = []
    transforms = {1: [{"item": "a", "patch": {MORALE: ["low"]}}]}
    assert director_prose.extension_channel_values(
        transforms, _specs(MORALE, list_shaped=False), "resolve",
        warn=warnings.append) == {}
    assert any(MORALE in w and "dropped" in w for w in warnings), warnings


def test_a_stage_the_channel_is_not_kept_at_drops_it_out_loud():
    warnings = []
    transforms = {1: [{"item": "a", "patch": {QUESTS: [{"n": 1}]}}]}
    assert director_prose.extension_channel_values(
        transforms, _specs(), "interpret", warn=warnings.append) == {}
    assert any("keeps at resolve only" in w for w in warnings), warnings


# --------------------------------------------------------------------- sheet


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_sheet_carries_its_header_and_the_instructions_verbatim(language):
    plain = prompts.unified_specialist_prompt(["attire"], language, [])
    sheet = prompts.unified_specialist_prompt(
        ["attire"], language, [], extensions=[(QUESTS, INSTRUCTIONS, True)])
    header = prompts.prose_contract_text(
        "encoder_extensions", language).strip().splitlines()[0]
    assert header in sheet and header not in plain
    assert f"`{QUESTS}` `(list)`\n{INSTRUCTIONS}" in sheet
    # Granted by name alone, a channel with no entry reaches no sheet.
    assert prompts.unified_specialist_prompt(
        ["attire", QUESTS], language, []) == plain


# ----------------------------------------------------------------- reading


def test_a_commit_domain_reads_its_own_channel_and_no_one_elses(campaign):
    ctx = _StubCtx(values={"director_resolve": {"orchestration": {
        "extension_channels": {QUESTS: [{"n": 1}],
                               "ext:rival:quests": [{"n": 9}]}}}})
    view = CommitView(campaign, ctx)
    assert view.channel("quests") == [{"n": 1}]
    assert view.channel("morale") is None
