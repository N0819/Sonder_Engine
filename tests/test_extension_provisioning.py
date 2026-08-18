"""Campaign provisioning: a whole playable story in one act, or none of it.

A campaign is not a settings blob. Starting one means a story, a persona, a
cast with stable ids, rooms and positions, a scene, a clock, authored lore on
both sides of the firewall and the campaign's own state, all agreeing from the
first turn. There was no supported extension operation for creating that.

There is now, and it is deliberately NOT a new scenario format. It is the chat
archive -- the thing `chat_archive.py` already exports, validates and remaps,
because a branch and a restore have to get exactly this list right, and a
second importer would be a second copy of the bugs the first one already had.

What the archive alone cannot do is seed the extension's own state in the same
breath, and a story that exists with no campaign state attached is the partial
provisioning the contract exists to forbid. That is the seam these tests are
mostly about.
"""

from __future__ import annotations

import json

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _chat, _enable, _write_extension, ext_root, real_ext_root,
)


@pytest.fixture
def campaign(ext_root):
    _write_extension(ext_root, "directive", {
        "id": "directive", "version": "1.0.0", "ext_api": 1, "name": "Directive",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("directive")
    return extension_runtime._apis["directive"]


def _package(name="Episode One"):
    """The smallest archive the importer accepts, with a scene in it."""
    return {
        "version": 1,
        "chat": {"name": name, "scenario": "A ship under tow."},
        "world": {"scene": {
            "location": "the bridge",
            "time": "0400",
            "rooms": {"bridge": {"name": "Bridge"}},
            "positions": {},
            "entities": {},
        }},
        "resources": {"persona": {"sheet": {"name": "Commander"}}},
    }


class TestProvisioning:
    def test_a_package_becomes_a_playable_story(self, temp_db, campaign):
        result = campaign.provision_story(_package())

        view = campaign.story_view(result["chat_id"])
        assert view["story"]["name"] == "Episode One"
        assert view["scene"]["location"] == "the bridge"
        assert view["player"]["name"] == "Commander"

    def test_campaign_state_is_seeded_in_the_same_act(self, temp_db, campaign):
        """The half an archive cannot do. A story that exists with no campaign
        state attached is exactly the partial provisioning this forbids."""
        result = campaign.provision_story(
            _package(), state={"mission": "survey", "objectives": []})

        assert campaign.state(result["chat_id"]).get() == {
            "mission": "survey", "objectives": []}

    def test_provenance_records_the_extension_and_the_package_version(
            self, temp_db, campaign):
        """Six months later this is the difference between a reproducible
        campaign and a save file nobody can place."""
        result = campaign.provision_story(
            _package(), package_id="episode-one", package_version="2.1.0")

        provenance = campaign.provenance(result["chat_id"])
        assert provenance["extension"] == "directive"
        assert provenance["package"] == "episode-one"
        assert provenance["version"] == "2.1.0"
        assert provenance["at"] > 0

    def test_a_story_this_extension_did_not_provision_has_no_provenance(
            self, temp_db, campaign):
        """A story a player started by hand and later installed you into is a
        different situation from a campaign of yours, and must not read as one."""
        assert campaign.provenance(_chat(temp_db)) is None

    def test_a_refused_package_leaves_nothing_behind(self, temp_db, campaign):
        """Everything or nothing. A half-created story is worse than a refusal:
        it looks playable."""
        from db import q

        before = q("SELECT COUNT(*) c FROM chats", one=True)["c"]
        with pytest.raises(ExtensionError):
            campaign.provision_story({"world": {}})          # no `chat` object

        assert q("SELECT COUNT(*) c FROM chats", one=True)["c"] == before

    def test_a_failure_after_the_import_rolls_the_story_back_too(
            self, temp_db, campaign):
        """The seam that made this a method rather than a documentation note.

        Importing and then seeding in two transactions would leave a story with
        no campaign state whenever the second one failed -- and the story would
        still be in the chat list, looking finished.
        """
        from db import q

        before = q("SELECT COUNT(*) c FROM chats", one=True)["c"]

        class Unserialisable:
            pass

        with pytest.raises(Exception):
            campaign.provision_story(_package(), state=Unserialisable())

        assert q("SELECT COUNT(*) c FROM chats", one=True)["c"] == before

    def test_a_non_dict_package_is_refused_by_name(self, temp_db, campaign):
        with pytest.raises(ExtensionError) as excinfo:
            campaign.provision_story("episode-one.json")

        assert "archive dict" in str(excinfo.value)

    def test_the_refusal_carries_the_engines_own_validation_message(
            self, temp_db, campaign):
        """An extension author debugging a package needs to know WHICH field
        the engine refused, not that something went wrong."""
        with pytest.raises(ExtensionError) as excinfo:
            campaign.provision_story({"version": 1, "world": {}})

        assert "chat" in str(excinfo.value).lower()

    def test_two_campaigns_do_not_share_a_story(self, temp_db, campaign):
        first = campaign.provision_story(_package("One"), state={"n": 1})
        second = campaign.provision_story(_package("Two"), state={"n": 2})

        assert first["chat_id"] != second["chat_id"]
        assert campaign.state(first["chat_id"]).get()["n"] == 1
        assert campaign.state(second["chat_id"]).get()["n"] == 2

    def test_the_provisioned_story_reads_back_through_the_facade(
            self, temp_db, campaign):
        """The report's own acceptance shape: import and readback tested
        together, against the same public schemas."""
        result = campaign.provision_story(_package(), state={"mission": "survey"})
        chat_id = result["chat_id"]

        assert campaign.story_view(chat_id)["schema"] == result["schema"]
        assert campaign.viewers(chat_id)[0]["name"] == "Commander"
        assert campaign.player_view(chat_id, "player")["viewer"]["id"] == "player"

    def test_campaign_state_rides_an_export_of_the_story_it_seeded(
            self, temp_db, campaign):
        """`ext:<id>:*` lives in the `world` KV, so it travels with the story
        through export, branch and clone with no line of its own. Worth pinning
        rather than assuming: a campaign whose state did not survive a branch
        would be discovered by a player, mid-story."""
        import app

        result = campaign.provision_story(_package(), state={"mission": "survey"})
        exported = app._chat_archive_service.export_chat(result["chat_id"])
        world = json.loads(json.dumps(exported))["world"]

        assert world["ext:directive"] == {"mission": "survey"}
