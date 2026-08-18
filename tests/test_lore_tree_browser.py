"""The lorebook tree a story's workspace browses, and the orphans that broke it.

A live database showed every chat holding lorebooks the browser could not
display: `TARDIS`, `Shelter Elevator`, `Kansai Region`, `Japan` — chat-owned
books with `parent_id` NULL and no `chat_lorebooks` row. The workspace built
its tree from the chat payload's `lorebooks`, which is `chat_lorebook_ids()`:
the RETRIEVAL graph, resolved outward from canon plus attachments through
parents, children and links. Nothing reaches a book that hangs off nothing, so
those books were absent from the tree, and a story whose canon had no children
opened as one lonely book.

Two distinct properties, and both need defending:

* the browser asks about OWNERSHIP, which cannot orphan anything, while
  retrieval scoping stays exactly as strict as it was, and
* the generator's apply path stops MAKING orphans -- `commit.py` already
  refuses to ("never an unreachable orphan"); this path did not.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest
from story import importers
from mind.memory import chat_lorebook_ids


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        response = c.post(
            "/api/auth/setup",
            json={"username": "host", "password": "pw12345"},
        )
        assert response.status_code == 200, response.text
        yield c
    guest.reset_host_account()


def _book(db, name, chat_id=None, parent_id=None, book_type="general"):
    return db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,parent_id) VALUES(?,?,?,?)",
        (name, chat_id, book_type, parent_id),
    )


@pytest.fixture
def story(temp_db):
    """A chat shaped like the live data: a proper tree plus two orphans."""
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("The Doctor", "", time.time()),
    )
    canon = _book(temp_db, "The Doctor — canon", chat_id=cid)
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, cid))

    world = _book(temp_db, "Crossover Universe", cid, canon, "world")
    ship = _book(temp_db, "USS Enterprise-D", cid, world, "location")

    # An attached library book, reachable the other way.
    library = _book(temp_db, "SCP Foundation", None, None, "world")
    attached = _book(temp_db, "SCP Foundation (chat copy)", cid, None, "world")
    temp_db.qi(
        "INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) VALUES(?,?,1)",
        (cid, attached),
    )

    # The orphans: chat-owned, no parent, never attached.
    tardis = _book(temp_db, "TARDIS", cid, None, "vehicle")
    japan = _book(temp_db, "Japan", cid, None, "general")

    return {
        "chat_id": cid, "canon": canon, "world": world, "ship": ship,
        "library": library, "attached": attached,
        "tardis": tardis, "japan": japan,
    }


class TestTheBugItself:
    def test_retrieval_cannot_reach_the_orphans(self, temp_db, story):
        # This is the pre-existing behaviour the browser was built on, and the
        # reason the tree came back short. Pinned so the next reader sees that
        # the two questions genuinely differ.
        reachable = set(chat_lorebook_ids(story["chat_id"], enabled_only=False))

        assert story["canon"] in reachable
        assert story["ship"] in reachable
        assert story["attached"] in reachable
        assert story["tardis"] not in reachable
        assert story["japan"] not in reachable


class TestOwnedLorebooksRoute:
    def test_it_returns_the_whole_tree_including_orphans(self, client, story):
        response = client.get(f"/api/chats/{story['chat_id']}/lorebooks")

        assert response.status_code == 200, response.text
        ids = {b["id"] for b in response.json()["lorebooks"]}
        assert ids == {
            story["canon"], story["world"], story["ship"],
            story["attached"], story["tardis"], story["japan"],
        }

    def test_a_library_book_that_is_not_attached_stays_out(self, client, story):
        ids = {
            b["id"]
            for b in client.get(
                f"/api/chats/{story['chat_id']}/lorebooks"
            ).json()["lorebooks"]
        }
        assert story["library"] not in ids

    def test_it_flags_which_books_retrieval_can_actually_reach(
        self, client, story,
    ):
        books = {
            b["id"]: b
            for b in client.get(
                f"/api/chats/{story['chat_id']}/lorebooks"
            ).json()["lorebooks"]
        }

        # Visible in the browser is not the same as usable in play, and the
        # payload says which is which instead of leaving it to be guessed.
        assert books[story["ship"]]["retrievable"] is True
        assert books[story["attached"]]["retrievable"] is True
        assert books[story["tardis"]]["retrievable"] is False
        assert books[story["japan"]]["retrievable"] is False

    def test_it_marks_canon_and_attachment(self, client, story):
        books = {
            b["id"]: b
            for b in client.get(
                f"/api/chats/{story['chat_id']}/lorebooks"
            ).json()["lorebooks"]
        }

        assert books[story["canon"]]["canon"] is True
        assert books[story["world"]]["canon"] is False
        assert books[story["attached"]]["attached"] is True
        assert books[story["tardis"]]["attached"] is False

    def test_it_carries_the_fields_the_tree_draws(self, client, story, temp_db):
        temp_db.qi(
            "INSERT INTO lore_entries(lorebook_id,keys,content) VALUES(?,?,?)",
            (story["ship"], "bridge", "The bridge is on deck 1."),
        )

        books = {
            b["id"]: b
            for b in client.get(
                f"/api/chats/{story['chat_id']}/lorebooks"
            ).json()["lorebooks"]
        }
        ship = books[story["ship"]]

        assert ship["entry_count"] == 1
        assert ship["parent_id"] == story["world"]
        assert ship["book_type"] == "location"
        assert ship["chat_id"] == story["chat_id"]
        assert books[story["canon"]]["entry_count"] == 0

    def test_a_chat_with_only_a_canon_book_returns_just_it(self, client, temp_db):
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Bare", "", time.time()),
        )
        canon = _book(temp_db, "Bare — canon", chat_id=cid)
        temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, cid))

        books = client.get(f"/api/chats/{cid}/lorebooks").json()["lorebooks"]
        assert [b["id"] for b in books] == [canon]

    def test_a_chat_with_no_canon_still_lists_what_it_owns(
        self, client, temp_db,
    ):
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Hmmm", "", time.time()),
        )
        root = _book(temp_db, "USS Enterprise D (chat copy)", cid, None, "vehicle")
        kid = _book(temp_db, "Saucer Section (chat copy)", cid, root, "location")

        ids = {b["id"] for b in client.get(
            f"/api/chats/{cid}/lorebooks"
        ).json()["lorebooks"]}
        assert ids == {root, kid}

    def test_a_missing_chat_is_a_404(self, client):
        assert client.get("/api/chats/999999/lorebooks").status_code == 404

    def test_it_does_not_leak_another_chats_books(self, client, story, temp_db):
        other = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Elsewhere", "", time.time()),
        )
        intruder = _book(temp_db, "Not Yours", other, None, "general")

        ids = {b["id"] for b in client.get(
            f"/api/chats/{story['chat_id']}/lorebooks"
        ).json()["lorebooks"]}
        assert intruder not in ids


class TestRetrievalScopingIsUnchanged:
    """The fix must not widen what the pipeline may read. Making an orphan
    visible in an editor is a UI question; making it retrievable would put
    lore into play that was not in play before."""

    def test_listing_a_chats_books_does_not_make_orphans_retrievable(
        self, client, story,
    ):
        client.get(f"/api/chats/{story['chat_id']}/lorebooks")

        reachable = set(chat_lorebook_ids(story["chat_id"], enabled_only=False))
        assert story["tardis"] not in reachable
        assert story["japan"] not in reachable

    def test_reparenting_an_orphan_is_what_connects_it(self, client, story):
        # The tree's existing drag-to-parent, which is now reachable for these
        # books because they finally appear in it.
        response = client.post(
            f"/api/lorebooks/{story['tardis']}/move",
            json={"parent_id": story["canon"]},
        )
        assert response.status_code == 200, response.text

        reachable = set(chat_lorebook_ids(story["chat_id"], enabled_only=False))
        assert story["tardis"] in reachable

        books = {
            b["id"]: b
            for b in client.get(
                f"/api/chats/{story['chat_id']}/lorebooks"
            ).json()["lorebooks"]
        }
        assert books[story["tardis"]]["retrievable"] is True


class TestApplyPlanStopsMakingOrphans:
    def test_a_book_with_no_parent_lands_under_the_targeted_book(
        self, temp_db, story,
    ):
        result = importers.apply_lorebook_plan(
            {
                "book_ops": [{
                    "op": "create", "temp_id": "t1", "name": "Gallifrey",
                    "book_type": "world",
                }],
                "entry_ops": [], "link_ops": [],
            },
            chat_id=story["chat_id"],
            root_id=story["canon"],
        )

        assert result["books_created"] == 1
        created = temp_db.q(
            "SELECT * FROM lorebooks WHERE name='Gallifrey'", one=True,
        )
        assert created["parent_id"] == story["canon"]
        # The whole point: it is reachable the moment it exists.
        assert created["id"] in set(
            chat_lorebook_ids(story["chat_id"], enabled_only=False)
        )

    def test_an_unresolvable_string_parent_lands_there_too(self, temp_db, story):
        importers.apply_lorebook_plan(
            {
                "book_ops": [{
                    "op": "create", "temp_id": "t1", "name": "Nowhere",
                    "parent_id": "no_such_temp_id",
                }],
                "entry_ops": [], "link_ops": [],
            },
            chat_id=story["chat_id"],
            root_id=story["canon"],
        )

        created = temp_db.q(
            "SELECT * FROM lorebooks WHERE name='Nowhere'", one=True,
        )
        assert created["parent_id"] == story["canon"]

    def test_a_parent_id_naming_a_book_that_does_not_exist_is_refused(
        self, temp_db, story,
    ):
        importers.apply_lorebook_plan(
            {
                "book_ops": [{
                    "op": "create", "temp_id": "t1", "name": "Hallucinated",
                    "parent_id": 999999,
                }],
                "entry_ops": [], "link_ops": [],
            },
            chat_id=story["chat_id"],
            root_id=story["canon"],
        )

        created = temp_db.q(
            "SELECT * FROM lorebooks WHERE name='Hallucinated'", one=True,
        )
        assert created["parent_id"] == story["canon"]

    def test_a_real_parent_is_honored(self, temp_db, story):
        importers.apply_lorebook_plan(
            {
                "book_ops": [{
                    "op": "create", "temp_id": "t1", "name": "Deck 10",
                    "parent_id": story["ship"],
                }],
                "entry_ops": [], "link_ops": [],
            },
            chat_id=story["chat_id"],
            root_id=story["canon"],
        )

        created = temp_db.q(
            "SELECT * FROM lorebooks WHERE name='Deck 10'", one=True,
        )
        assert created["parent_id"] == story["ship"]

    def test_a_temp_id_chain_is_still_honored(self, temp_db, story):
        importers.apply_lorebook_plan(
            {
                "book_ops": [
                    {"op": "create", "temp_id": "a", "name": "Region"},
                    {"op": "create", "temp_id": "b", "name": "City",
                     "parent_id": "a"},
                ],
                "entry_ops": [], "link_ops": [],
            },
            chat_id=story["chat_id"],
            root_id=story["canon"],
        )

        region = temp_db.q("SELECT * FROM lorebooks WHERE name='Region'", one=True)
        city = temp_db.q("SELECT * FROM lorebooks WHERE name='City'", one=True)
        assert region["parent_id"] == story["canon"]
        assert city["parent_id"] == region["id"]

    def test_falls_back_to_canon_when_no_root_is_given(self, temp_db, story):
        importers.apply_lorebook_plan(
            {
                "book_ops": [{"op": "create", "temp_id": "t1", "name": "Drifting"}],
                "entry_ops": [], "link_ops": [],
            },
            chat_id=story["chat_id"],
        )

        created = temp_db.q(
            "SELECT * FROM lorebooks WHERE name='Drifting'", one=True,
        )
        assert created["parent_id"] == story["canon"]

    def test_a_library_book_may_still_be_a_root(self, temp_db):
        importers.apply_lorebook_plan(
            {
                "book_ops": [{"op": "create", "temp_id": "t1", "name": "Free Book"}],
                "entry_ops": [], "link_ops": [],
            },
        )

        created = temp_db.q(
            "SELECT * FROM lorebooks WHERE name='Free Book'", one=True,
        )
        # Nothing to hang from and nothing that needs it to: a library root is
        # legitimate, unlike a chat-owned book reachable from nothing.
        assert created["parent_id"] is None
        assert created["chat_id"] is None

    def test_an_entry_with_an_unresolvable_book_is_filed_not_dropped(
        self, temp_db, story,
    ):
        result = importers.apply_lorebook_plan(
            {
                "book_ops": [],
                "entry_ops": [{
                    "op": "create", "book_id": "no_such_temp_id",
                    "keys": "salvage", "content": "A fact worth keeping.",
                }],
                "link_ops": [],
            },
            chat_id=story["chat_id"],
            root_id=story["canon"],
        )

        assert result["entries_created"] == 1
        entry = temp_db.q(
            "SELECT * FROM lore_entries WHERE keys='salvage'", one=True,
        )
        assert entry["lorebook_id"] == story["canon"]


class TestApplyRouteWiring:
    def test_the_route_roots_new_books_under_the_book_it_was_called_for(
        self, client, story,
    ):
        response = client.post(
            f"/api/lorebooks/{story['world']}/apply_plan",
            json={"plan": {
                "book_ops": [{"op": "create", "temp_id": "t1",
                              "name": "Sector 001"}],
                "entry_ops": [], "link_ops": [],
            }},
        )

        assert response.status_code == 200, response.text
        books = {
            b["name"]: b
            for b in client.get(
                f"/api/chats/{story['chat_id']}/lorebooks"
            ).json()["lorebooks"]
        }
        # Under the book the user was looking at, not floating at the root.
        assert books["Sector 001"]["parent_id"] == story["world"]
        assert books["Sector 001"]["retrievable"] is True
