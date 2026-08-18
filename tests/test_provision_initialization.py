"""Turn zero arrives whole, or no campaign appears at all.

`provision_story` was already atomic for the story, its cast, its lore and the
extension's own state. A playable campaign also needs the rules that make that
story mean anything -- Director context, narration context, per-era state,
opening documents -- and those were four writes AFTERWARDS.

The reference campaign showed the shape of the hazard: it provisioned the story
and then called `_install_rules`. If that second write failed, the story stayed
in the player's list, playable, carrying its campaign state and its `actor_only`
mode, and missing the one rule that made its sealed wing a sealed wing. Not a
race -- failure atomicity, and the only cure is the same transaction.

Data rather than a callback, which is what the report asked for and what keeps
the bootstrap serialisable, lintable, and free of arbitrary code running inside
a database transaction. Specification: `docs/design/DIRECTIVE_REMAINING_GAPS.md`
§3.
"""

from __future__ import annotations

import json

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _chat, _enable, _write_extension, ext_root, real_ext_root,
)

PACKAGE = {"version": 1, "chat": {"name": "Episode One"},
           "resources": {"persona": {"sheet": {"name": "Commander"}}}}


@pytest.fixture
def campaign(ext_root):
    _write_extension(ext_root, "directive", {
        "id": "directive", "version": "1.0.0", "ext_api": 1, "name": "Directive",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("directive")
    return extension_runtime._apis["directive"]


def _chats(db):
    return db.q("SELECT COUNT(*) c FROM chats", one=True)["c"]


class TestOneCallStartsACampaign:
    def test_every_bootstrap_value_is_present_when_it_returns(self, temp_db,
                                                               campaign):
        result = campaign.provision_story(
            PACKAGE,
            state={"mission": "survey"},
            frame_state={"objective": "locked"},
            player_authority="actor_only",
            director_context={"interpret": "Deck 4 is sealed.",
                              "resolve": "A sealed deck refuses entry."},
            narration_context="The ship is under tow.",
            documents={"missions/one": {"title": "Survey"}},
            package_id="episode-one", package_version="2.1.0")
        chat_id = result["chat_id"]

        assert campaign.state(chat_id).get() == {"mission": "survey"}
        assert campaign.frame_state(chat_id).get() == {"objective": "locked"}
        assert campaign.director_context(chat_id).text("interpret") \
            == "Deck 4 is sealed."
        assert campaign.narration_context(chat_id).text \
            == "The ship is under tow."
        assert campaign.documents(chat_id).get("missions/one") \
            == {"title": "Survey"}
        assert campaign.story_view(chat_id)["player_authority"]["mode"] \
            == "actor_only"
        assert campaign.provenance(chat_id)["package"] == "episode-one"

    def test_the_context_is_there_before_the_first_director_call(
            self, temp_db, campaign):
        """Turn zero is the beat a campaign's rules matter most, and it is the
        one they used to be installed after."""
        from tests.test_extensions import _StubCtx

        chat_id = campaign.provision_story(
            PACKAGE, director_context={"resolve": "A sealed deck refuses."},
        )["chat_id"]

        out = extension_runtime.dispatch_director_payload(
            _StubCtx(chat_id=chat_id), {}, phase="resolve")

        assert out["extension_context"][0]["text"] == "A sealed deck refuses."

    def test_provisioning_still_works_with_none_of_it(self, temp_db, campaign):
        """Every argument is optional; the old call is unchanged."""
        result = campaign.provision_story(PACKAGE, state={"mission": "survey"})

        assert campaign.state(result["chat_id"]).get() == {"mission": "survey"}
        assert campaign.director_context(result["chat_id"]).get() == {}


class TestNothingPartialSurvives:
    def test_a_bad_document_path_leaves_no_story(self, temp_db, campaign):
        before = _chats(temp_db)
        with pytest.raises(ExtensionError):
            campaign.provision_story(PACKAGE, documents={"../escape": {}})

        assert _chats(temp_db) == before

    def test_an_unknown_director_phase_leaves_no_story(self, temp_db,
                                                        campaign):
        before = _chats(temp_db)
        with pytest.raises(ExtensionError) as excinfo:
            campaign.provision_story(
                PACKAGE, director_context={"narrator": "wrong seam"})

        assert "narrator" in str(excinfo.value)
        assert _chats(temp_db) == before

    def test_an_invalid_authority_mode_leaves_no_story(self, temp_db,
                                                        campaign):
        before = _chats(temp_db)
        with pytest.raises(ExtensionError):
            campaign.provision_story(PACKAGE, player_authority="hard")

        assert _chats(temp_db) == before

    def test_an_unserialisable_value_is_named_actionably(self, temp_db,
                                                          campaign):
        for kwargs in ({"state": {"fn": lambda: None}},
                       {"frame_state": {"fn": lambda: None}},
                       {"documents": {"missions/one": {"fn": lambda: None}}}):
            with pytest.raises(ExtensionError) as excinfo:
                campaign.provision_story(PACKAGE, **kwargs)
            assert "serialisable" in str(excinfo.value).lower()

    def test_an_oversized_block_is_refused_before_anything_is_created(
            self, temp_db, campaign):
        before = _chats(temp_db)
        with pytest.raises(ExtensionError):
            campaign.provision_story(
                PACKAGE, director_context={"resolve": "x" * 8001})
        with pytest.raises(ExtensionError):
            campaign.provision_story(PACKAGE, narration_context="x" * 8001)

        assert _chats(temp_db) == before

    def test_validation_happens_before_the_archive_is_touched(self):
        """So a refusal is a refusal rather than a rollback doing work the
        caller could have been told about first -- and so the error names the
        field, which "campaign package refused" never would."""
        import inspect

        from extension_runtime.api import SonderExtensionAPI

        source = inspect.getsource(SonderExtensionAPI.provision_story)
        validate = source.index("DirectorBlock._phase(phase)")
        transaction = source.index("with transaction():")

        assert validate < transaction


class TestItSurvivesTheStoryPlumbing:
    def test_the_whole_bootstrap_rides_an_export(self, temp_db, campaign):
        import app

        chat_id = campaign.provision_story(
            PACKAGE, state={"mission": "survey"},
            director_context={"resolve": "A sealed deck refuses."},
            narration_context="Under tow.",
            documents={"missions/one": {"title": "Survey"}},
        )["chat_id"]

        world = json.loads(json.dumps(
            app._chat_archive_service.export_chat(chat_id)))["world"]

        assert world["ext:directive"] == {"mission": "survey"}
        assert world["ext:directive:director"]["resolve"]["text"]
        assert world["ext:directive:narration"]["text"] == "Under tow."
        assert any(k.startswith("ext:directive:doc:") for k in world)
