"""The vertical slice, end to end, over the shipped reference campaign.

`DIRECTIVE_GAP_REPORT.md` §5 defines "the gaps are closed" as ten steps ending
in a campaign that survives a checkpoint. Its §6 says the way to prove it is a
tiny reference campaign — one room change, two characters, one secret, one
gated objective, one forbidden invented player line. `extensions/campaign-demo`
is that campaign, and this file is the proof it runs.

The point is NOT that a demo works. It is that the five contracts compose:
provisioning creates a story the facade can read, the facade's viewer-filtered
mode is what the panel gets, the Director rules change with mission state, the
commit domain advances only on evidence the story actually produced, and the
authority rung the campaign asked for is the one the engine enforces. Each was
tested alone in its own file; nothing until now put them in one line.

Writing it found a real blocker on the first import, which is what a reference
build is for — see `test_an_extension_may_split_its_python_across_files`.
"""

from __future__ import annotations

import json

import pytest

import extension_runtime

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _enable, _write_extension, ext_root, real_ext_root,
)

EXT = "campaign-demo"


@pytest.fixture
def campaign(real_ext_root, temp_db):
    """The SHIPPED extension, not a stand-in.

    Over the real tree deliberately: a slice test against a fixture written in
    the test file proves the fixture works. What needs proving is that the
    thing in `extensions/` does.
    """
    _enable(EXT)
    api = extension_runtime._apis.get(EXT)
    assert api is not None, extension_runtime._registered[EXT].error
    return api


def _start(api):
    return extension_runtime.dispatch_route(EXT, "POST", "/start", body={})


def _commit(campaign_api, chat_id, player_view_text):
    """Run one beat's commit domains through the host's own entry point.

    `run_commit_domains` rather than reaching into the registry: a slice test
    that calls the callback directly proves the callback works and says nothing
    about whether the engine ever calls it, which is the exact failure the
    reasoning-trace defect was — both halves correct, never introduced.
    """
    from tests.test_extensions import _StubCtx

    ctx = _StubCtx(chat_id=chat_id, values={
        "perception_outcome": {"views": {"player": player_view_text}}})
    results = {}
    extension_runtime.run_commit_domains(ctx, results)
    assert not ctx.warnings, ctx.warnings
    return results


# ------------------------------------------------------------ the loader gap


def test_an_extension_may_split_its_python_across_files(campaign):
    """Found by building the reference campaign, and the same SHAPE as the
    ES-module blocker: nobody hits it until somebody builds something real.

    `campaign-demo` keeps its scenario data in `campaign.py` beside its entry.
    Before this, `_import_entry` loaded the entry as a lone module with its
    directory on no search path, so the import raised ModuleNotFoundError —
    and Directive is a module graph, so a Python port would have hit it on its
    first file.

    A package rather than a `sys.path` entry, which is why the import is
    relative: under a path entry every sibling is importable by its BARE name,
    so an extension shipping `db.py` would shadow the engine's for whatever
    imported next, and two extensions each shipping `helper.py` would get
    whichever loaded first.
    """
    import sys

    assert "sonder_ext_campaign_demo.campaign" in sys.modules


def test_disabling_forgets_every_submodule(campaign):
    """A disable that left a submodule behind would have the next enable run a
    stale copy of a file the host may have replaced in between — which is
    exactly what an update does."""
    import sys

    extension_runtime.disable_extension(EXT)

    assert not [n for n in sys.modules if n.startswith("sonder_ext_campaign_demo")]


# --------------------------------------------------------------- the slice


class TestTheSlice:
    def test_start_provisions_a_playable_story(self, campaign):
        result = _start(campaign)

        view = campaign.story_view(result["chat_id"])
        assert view["story"]["name"] == "The Sealed Wing"
        assert set(view["scene"]["rooms"]) == {"hall", "wing"}
        assert view["player"]["name"] == "The Visitor"
        assert sorted(m["name"] for m in view["cast"]) == ["Mireille", "Tobias"]

    def test_the_secret_is_kept_by_the_engine_and_not_by_the_campaign(
            self, campaign):
        """It lives in the caretaker's own `private_history`, so the ordinary
        boundaries hold it and this extension does nothing to help.

        A lorebook would have been the wrong home: lore is gated by knowledge
        TIER -- `common`/`scholarly`/`esoteric` -- which answers how obscure a
        fact is, not who holds it.
        """
        from story.character_schema import character_name_from_text
        from core.db import q

        chat_id = _start(campaign)["chat_id"]
        sheets = {
            character_name_from_text(row["sheet"]): json.loads(row["sheet"])
            for row in q("SELECT c.sheet FROM chat_chars cc "
                         "JOIN characters c ON c.id=cc.char_id "
                         "WHERE cc.chat_id=?", (chat_id,))
        }

        held = sheets["Mireille"]["knowledge"]["private_history"]
        assert any("behind the loose panel" in entry["content"] for entry in held)
        # `known_by` empty: hers alone until she says it out loud. That is the
        # engine's own field for the question, which is why the campaign has no
        # answer of its own to keep in sync.
        assert all(entry["known_by"] == [] for entry in held)
        assert sheets["Tobias"]["knowledge"]["private_history"] == []

    def test_both_reference_cards_author_a_drive(self, campaign):
        """`CLAUDE.md`'s worst silent failure, in a file people will copy.

        An empty `drive` reads as a complete card, never warns, and surfaces
        fifty beats later as a character who stops wanting things -- every
        motivation having been left in goals, which are built to be completed.
        A reference campaign shipping that would teach it.
        """
        from story.character_schema import character_name_from_text
        from core.db import q

        chat_id = _start(campaign)["chat_id"]
        for row in q("SELECT c.sheet FROM chat_chars cc "
                     "JOIN characters c ON c.id=cc.char_id "
                     "WHERE cc.chat_id=?", (chat_id,)):
            sheet = json.loads(row["sheet"])
            drive = sheet["psychology"]["drive"]
            who = character_name_from_text(row["sheet"])
            assert all(str(drive.get(k) or "").strip()
                       for k in ("essence", "expression", "taboo")), who
            assert sheet["psychology"]["values"], who

    def test_the_campaign_declares_the_authority_rung_it_needs(self, campaign):
        """The forbidden invented player line. Under `world_author` "I open the
        sealed door and step through" is simply true, and the campaign's whole
        premise is that it is not."""
        result = _start(campaign)

        assert (campaign.story_view(result["chat_id"])
                ["player_authority"]["mode"] == "actor_only")

    def test_a_declared_outcome_is_downgraded_under_that_rung(self, campaign):
        """The rung is not decoration: this is the engine acting on it."""
        from agents.common import apply_player_authority

        _start(campaign)
        beat = {
            "sequence": [{"type": "action", "attempt": "open the sealed door",
                          "targets": ["the door"], "commitment": "asserted",
                          "asserted_effects": [{"description": "it swings wide"}]}],
            "flow": {"authority_claims": [
                {"claim_id": "claim:0:0", "scope": "effect",
                 "subject_id": "the door", "predicate": "the door is open",
                 "source_text": "I open the sealed door and step through"}]},
        }

        records = apply_player_authority(beat, "actor_only", "The Visitor")

        assert [r["kind"] for r in records] == ["own_effect"]
        assert beat["flow"]["authority_claims"][0]["scope"] == "intent"
        assert beat["sequence"][0]["commitment"] == "contestable"
        # And the player's words are still there, verbatim.
        assert beat["sequence"][0]["attempt"] == "open the sealed door"

    def test_the_seal_rule_is_in_front_of_the_director_from_turn_zero(
            self, campaign):
        """Not appended to a verdict already reached. A rule installed after the
        Director had already decided the door opened would be a note about a
        beat the player has read."""
        from tests.test_extensions import _StubCtx

        chat_id = _start(campaign)["chat_id"]

        for phase in ("interpret", "resolve"):
            out = extension_runtime.dispatch_director_payload(
                _StubCtx(chat_id=chat_id), {}, phase=phase)
            assert out["extension_context"][0]["source"] == EXT
            assert "sealed" in out["extension_context"][0]["text"].casefold()

    def test_the_objective_stays_locked_until_the_fact_reaches_the_player(
            self, campaign):
        """Fair Discovery. A caretaker who KNOWS where the key is changes
        nothing; the objective turns on what reached the player's own view.

        Note what the campaign never does to check this: read a mind.
        """
        chat_id = _start(campaign)["chat_id"]

        _commit(campaign, chat_id, "The hall is quiet. Dust in the window light.")

        state = campaign.state(chat_id).get()
        assert state["objectives"][0]["status"] == "locked"
        assert state["discovered"] == []

    def test_the_objective_opens_when_it_does(self, campaign):
        chat_id = _start(campaign)["chat_id"]

        _commit(campaign, chat_id,
                '"The key\'s behind the panel," she says, not looking up.')

        state = campaign.state(chat_id).get()
        assert state["objectives"][0]["status"] == "available"
        assert state["discovered"] == ["know-where-the-key-is"]

    def test_opening_it_replaces_the_directors_rule_rather_than_adding_one(
            self, campaign):
        """An injector that only ever adds is one that tells the Director the
        wing is sealed for the rest of the story."""
        from tests.test_extensions import _StubCtx

        chat_id = _start(campaign)["chat_id"]
        _commit(campaign, chat_id, "she nods at the panel")

        out = extension_runtime.dispatch_director_payload(
            _StubCtx(chat_id=chat_id), {}, phase="resolve")
        blocks = out["extension_context"]

        assert len(blocks) == 1
        assert "opens to whoever holds it" in blocks[0]["text"]
        assert "no attempt opens that door" not in blocks[0]["text"].casefold()
        # And the interpret rule is gone entirely, rather than left standing.
        assert "extension_context" not in extension_runtime.dispatch_director_payload(
            _StubCtx(chat_id=chat_id), {}, phase="interpret")

    def test_a_result_that_breaks_the_seal_is_refused(self, campaign):
        """Contract three of the remaining-gaps report, demonstrated.

        The Director rule is model input and guides the decision; this is the
        deterministic half that refuses an answer which broke it. Without it a
        disregarded rule becomes canonical world state and the only remedy is a
        commit domain throwing the whole beat away.
        """
        chat_id = _start(campaign)["chat_id"]
        ctx = _StubCtx(chat_id=chat_id)

        violations, fatal = extension_runtime.validate_director_result(
            ctx, {"state_diff": {"positions": {"The Visitor": "wing"}}})

        assert fatal is False          # the demo warns rather than costing a turn
        assert [v["code"] for v in violations] == ["sealed-wing"]
        assert violations[0]["evidence"] == {"room": "wing",
                                             "bodies": ["The Visitor"]}

    def test_a_result_that_respects_the_seal_passes(self, campaign):
        chat_id = _start(campaign)["chat_id"]

        assert extension_runtime.validate_director_result(
            _StubCtx(chat_id=chat_id),
            {"state_diff": {"positions": {"The Visitor": "hall"}}}) == ([], False)

    def test_the_invariant_stands_down_once_the_wing_is_open(self, campaign):
        """A rule that kept firing after its own objective opened would make
        the wing unreachable forever -- the guard outliving its reason."""
        chat_id = _start(campaign)["chat_id"]
        _commit(campaign, chat_id, "she nods at the panel")

        assert extension_runtime.validate_director_result(
            _StubCtx(chat_id=chat_id),
            {"state_diff": {"positions": {"The Visitor": "wing"}}}) == ([], False)

    def test_the_campaign_starts_in_one_atomic_call(self, campaign):
        """Contract two. It used to provision and THEN install its rules; a
        failure in between left a playable story with no rule in it."""
        import inspect
        import sys

        source = inspect.getsource(
            sys.modules["sonder_ext_campaign_demo.extension"])
        start = source[source.index("def _start("):source.index("def _install_rules(")]

        assert "director_context=" in start
        assert "_install_rules" not in start

    def test_the_panel_reads_the_player_safe_projection(self, campaign):
        """`story_view` would answer more and is the right read for the
        campaign's RULES. It is the wrong read for a panel a player is looking
        at, and a demo that used it would be teaching the mistake."""
        import inspect

        import sys

        source = inspect.getsource(sys.modules["sonder_ext_campaign_demo.extension"])
        panel = source[source.index("def _campaign("):]

        assert "api.player_view(" in panel

    def test_the_panel_answers_before_anything_has_happened(self, campaign):
        chat_id = _start(campaign)["chat_id"]
        data = extension_runtime.dispatch_route(
            EXT, "GET", "/campaign", query={"chat_id": chat_id})

        assert data["campaign"] == "the-sealed-wing"
        assert data["authority"] == "actor_only"
        assert data["objectives"][0]["status"] == "locked"
        # No delivered view yet, so no view — omitted, never filled in.
        assert data["view"] is None

    def test_the_panel_refuses_a_story_that_is_not_ours(self, campaign,
                                                        temp_db):
        """A player who started a story by hand and later installed this must
        not see a campaign panel claiming their story is a campaign."""
        data = extension_runtime.dispatch_route(
            EXT, "GET", "/campaign", query={"chat_id": _chat(temp_db)})

        assert data["campaign"] is None

    def test_provenance_survives_and_names_the_package(self, campaign):
        chat_id = _start(campaign)["chat_id"]

        provenance = campaign.provenance(chat_id)

        assert provenance["extension"] == EXT
        assert provenance["package"] == "the-sealed-wing"
        assert provenance["version"] == "0.1.0"

    def test_the_whole_campaign_rides_an_export(self, campaign):
        """Step 10: refreshing, checkpointing or branching preserves a coherent
        campaign. `ext:<id>` lives in the `world` KV, so it travels with the
        story and needs no line in the archive schema."""
        from web import app

        chat_id = _start(campaign)["chat_id"]
        _commit(campaign, chat_id, "behind the panel")

        exported = json.loads(json.dumps(
            app._chat_archive_service.export_chat(chat_id)))

        assert exported["world"][f"ext:{EXT}"]["objectives"][0]["status"] \
            == "available"
        assert exported["world"][f"ext:{EXT}:director"]["resolve"]["text"]
        assert exported["world"]["player_authority"]["mode"] == "actor_only"
