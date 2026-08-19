"""One extension, composed: register, serve, persist, rewind, branch, die.

Sonder already tests the extension boundary part by part -- twelve
`test_extension*.py` files covering discovery, state homes, documents,
routes, assets, lifecycle and capability declaration. This file exists
because a per-part suite structurally cannot find a COMPOSITION defect, and
one was found in the field: `story_view`/`player_view` were tested for frame
correctness in `tests/test_story_view.py` while `frame_state`/`char_state`
were tested in `tests/test_extension_chat_lifecycle.py`. Every part was
correct. One DTO built from all four mixed two eras.

So the fixture here is deliberately ONE extension -- a generic external
consumer that knows nothing about this engine's internals -- carried through
the host's whole lifecycle: it gates on a capability NAME, serves a route
that composes five public reads, keeps state in all four durable homes, and
is then rewound, branched, exported, failed, disabled and re-enabled. The
assertions are made through `web.app` functions and
`extension_runtime.dispatch_route`, never against registry internals: a test
that read the registry would have passed on the mixed-frame engine too.

WHAT IS ALREADY PROVEN ELSEWHERE, and is therefore not repeated here:

* Frame coherence at route level, present/future inversion, and refusal of
  foreign/unknown frames on the api object -- `tests/test_extension_frame_view.py`,
  which is the fix's own test file and covers scenarios 1 and 2 in depth.
  What is added below is the refusal reaching a CALLER through the route,
  and one invariant stated over the whole DTO rather than field by field.
* Chat-global `ext:<id>` state riding a checkpoint and an export --
  `tests/test_extensions.py::TestStateRidesTheEngine`.
* Documents riding a checkpoint, an export and a branch --
  `tests/test_extension_documents.py::TestPersistenceRides`.
* A failed extension serving no assets, no UI and no stored context, and a
  disable taking every registration -- `tests/test_extensions.py`'s
  `TestAFailedExtensionIsInertEverywhere` and
  `TestDisableIsCompleteAndReEnableIsExactlyOnce`.
* `HOST_CAPABILITIES` being named, versioned and reachable --
  `tests/test_extensions.py::TestTheHostSaysWhatItOffers`.
* `on_error="fail"` propagating out of `run_commit_domains` --
  `tests/test_extension_seams.py::TestCommitDomains`.

The gaps those leave, which are what this file actually covers: the
frame-scoped and per-character homes were never carried through a checkpoint
restore or a branch AT ALL; nothing asserted that a branch REMAPS the frame
id embedded in an extension's `extf:` key; the strict commit domain was
never shown to roll back the ENGINE's writes beside its own; and no test
made an extension's own load decision depend on a capability name.
"""

from __future__ import annotations

import json
import time

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _character, _enable, _write_extension, ext_root,
)

EXT = "contract-fixture"


#: A generic external consumer. It imports nothing, knows no engine module,
#: and decides whether it can run by asking the host what it offers.
ENTRY = '''
REQUIRED = ("frame_coherent_reads", "frame_state", "char_state",
            "documents", "routes", "commit_domains", "stage_anchors")


def register(api):
    missing = [name for name in REQUIRED if name not in api.capabilities]
    if missing:
        raise RuntimeError(
            "host api %d offers no %s" % (api.api_version, ", ".join(missing)))

    def _bind(api, request):
        chat_id = request.chat_id
        if chat_id is None:
            raise ValueError("chat_id is required")
        raw = request.query.get("frame")
        if raw is None:
            return api.at_frame(chat_id)
        if raw == "present":
            return api.at_frame(chat_id, None)
        return api.at_frame(chat_id, int(raw))

    def projection(request):
        """One DTO out of five public reads -- the shape that mixed eras."""
        host = _bind(api, request)
        person_id = int(request.query["person_id"])
        return {
            "api_version": api.api_version,
            "frame_id": host.frame_id,
            "player": host.player_view(request.query.get("viewer", "player")),
            "frame_state": host.frame_state().get() or {},
            "char_state": host.char_state(person_id).get() or {},
            "state": api.state(request.chat_id).get() or {},
            "documents": sorted(
                meta["path"]
                for meta in api.documents(request.chat_id).list()),
        }

    def seed(request):
        """Write every durable home this extension owns, in one call."""
        host = _bind(api, request)
        body = request.body or {}
        api.state(request.chat_id).set_now(body["state"])
        host.frame_state().set_now(body["frame_state"])
        host.char_state(int(request.query["person_id"])).set_now(
            body["char_state"])
        api.documents(request.chat_id).put_now("ledger/current", body["doc"])
        api.narration_context(request.chat_id).set(body["block"])
        return {"seeded": True, "frame_id": host.frame_id}

    api.add_route("/projection", projection, methods=("GET",))
    api.add_route("/seed", seed, methods=("POST",))

    def tick(view):
        return {"ran": True}

    api.add_stage("tick", anchor="after:director_resolve", handler=tick)

    def ledger(view):
        """Runs inside the turn's transaction, and counts itself."""
        seen = api.settings.get() or {}
        seen["domain_runs"] = int(seen.get("domain_runs") or 0) + 1
        api.settings.set(seen)
        stored = dict(view.state.get() or {})
        stored["committed"] = True
        view.state.set(stored)
        view.frame_state.set({"mission": "advanced"})
        view.documents().put("ledger/committed", {"turn": view.turn_idx})
        return {"advanced": True}

    api.add_commit_domain("ledger", ledger)

    def strict(view):
        """`on_error="fail"`: this extension would rather lose the beat."""
        if (view.state.get() or {}).get("explode"):
            raise ValueError("the ledger disagrees with the beat")
        return {"checked": True}

    api.add_commit_domain("strict", strict, on_error="fail")
'''


def _install(root, entry=ENTRY):
    _write_extension(root, EXT, {
        "id": EXT, "version": "1.0.0", "ext_api": 1, "name": "Contract",
        "capabilities": {"python": "extension.py", "chat_state": True,
                         "ui": {"js": "ui/panel.js", "css": "ui/panel.css"}},
    }, {"extension.py": entry,
        "ui/panel.js": "Sonder.registerTab('contract');\n",
        "ui/panel.css": ".contract-panel { color: red; }\n"})


def _api():
    return extension_runtime._apis[EXT]


def _dispatch(method, path, **kwargs):
    return extension_runtime.dispatch_route(EXT, method, path, **kwargs)


def _projection(chat_id, person_id, frame=None, viewer="player"):
    query = {"chat_id": str(chat_id), "person_id": str(person_id),
             "viewer": viewer}
    if frame is not None:
        query["frame"] = frame
    return _dispatch("GET", "/projection", query=query)


SEED = {"state": {"campaign": "contract", "installed": True},
        "frame_state": {"mission": {"revision": 41}},
        "char_state": {"duty": "watch"},
        "doc": {"entries": ["one"]},
        "block": "The contract fixture is installed."}


@pytest.fixture
def story(temp_db, ext_root):
    """One installed extension, one story with two eras, everything seeded
    through the extension's own route rather than around it."""
    from web import app

    _install(ext_root)
    _enable(EXT)

    chat_id = _chat(temp_db, "Contract")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Sam", json.dumps({"name": "Sam"})))
    temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?",
               (persona_id, chat_id))
    char_id = _character(temp_db, chat_id, "Ilse", "uid-ilse")

    from core.db import wset, wset_for_frame
    wset(chat_id, "scene", {
        "location": "the yard", "time": "early",
        "rooms": {"yard": {"name": "The Yard"}},
        "positions": {"Sam": "yard", "Ilse": "yard"}, "entities": {}})
    temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 0, "look", time.time()))

    later = app.frames_create(chat_id, {"label": "Later", "ordinal": 10,
                                        "kind": "future"})
    wset_for_frame(chat_id, "scene", {
        "location": "the tower", "time": "late",
        "rooms": {"tower": {"name": "The Tower"}},
        "positions": {"Sam": "tower", "Ilse": "tower"}, "entities": {}},
        later["id"])
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (chat_id, 1, "climb", time.time(), later["id"]))

    _dispatch("POST", "/seed",
              query={"chat_id": str(chat_id), "person_id": str(char_id)},
              body=SEED)

    return {"chat_id": chat_id, "char_id": char_id, "frame": later["id"],
            "turn_id": turn_id}


# ------------------------------------------------------------ one projection


class TestOneProjectionOneEra:
    """Scenario 1 and 2, as COMPOSITION only.

    `tests/test_extension_frame_view.py` already pins every field of the
    projection against both eras, and `at_frame`'s refusals against the api
    object. Repeating that here would be a second copy. What it does not
    say is what a consumer actually depends on: that the DTO is
    self-consistent WHATEVER it holds -- an invariant one assertion can
    state over the whole object, and one that keeps holding when a field is
    added -- and that a refusal survives the trip out through a route,
    which is the only place an external caller ever meets it.
    """

    @staticmethod
    def _assert_coherent(dto):
        """The invariant a growing DTO cannot outgrow."""
        player_frame = (dto["player"]["frame"] or {}).get("id") \
            if dto["player"]["frame"] else None
        assert player_frame == dto["frame_id"], (
            "the player view and the bound reads disagree about the era: "
            f"{player_frame!r} vs {dto['frame_id']!r}")

    def test_the_latest_turns_era_answers_every_read(self, story):
        dto = _projection(story["chat_id"], story["char_id"])

        self._assert_coherent(dto)
        assert dto["frame_id"] == story["frame"]
        assert dto["player"]["location"]["room_id"] == "tower"
        assert dto["frame_state"] == {"mission": {"revision": 41}}
        assert dto["char_state"] == {"duty": "watch"}

    def test_selecting_the_present_moves_every_frame_scoped_read_together(
            self, story):
        """The inverse, asserted as a SET: the era-scoped fields all change
        and the chat-global ones all do not. A mixed result fails here
        whichever half moved."""
        latest = _projection(story["chat_id"], story["char_id"])
        present = _projection(story["chat_id"], story["char_id"],
                              frame="present")

        self._assert_coherent(present)
        assert present["frame_id"] is None
        assert present["player"]["location"]["room_id"] == "yard"
        assert present["frame_state"] == {}, \
            "the era-scoped mission never happened in the present"
        assert present["char_state"] == {}
        assert present["state"] == latest["state"] == SEED["state"]
        assert present["documents"] == latest["documents"] == \
            ["ledger/current"]

    def test_a_foreign_chats_frame_is_refused_through_the_route(self, temp_db,
                                                               story):
        """The refusal an external caller actually meets. An extension
        holding chat A must not be able to probe chat B's frame ids, and the
        route is where a hostile query string arrives."""
        from web import app

        other = _chat(temp_db, "Elsewhere")
        foreign = app.frames_create(other, {"label": "Theirs", "ordinal": 2})

        with pytest.raises(ExtensionError, match="no frame"):
            _projection(story["chat_id"], story["char_id"],
                        frame=str(foreign["id"]))

    def test_an_unknown_frame_is_refused_the_same_way(self, story):
        with pytest.raises(ExtensionError, match="no frame"):
            _projection(story["chat_id"], story["char_id"], frame="987654")


# --------------------------------------------------------------- checkpoints


class TestACheckpointRewindsEveryHome:
    """Scenario 3, and the gap the per-part suite left.

    Chat-global state and documents were each shown to ride a restore
    (`tests/test_extensions.py::TestStateRidesTheEngine`,
    `tests/test_extension_documents.py::TestPersistenceRides`). The
    frame-scoped and per-character homes were shown riding NOTHING -- both
    landed after those tests were written, both store somewhere else
    (`extf:<id><sep><frame>` rows and the `chat_char_frames` overlay), and
    an extension that rewound three of its four homes would be in a state no
    beat ever produced.
    """

    def _restore(self, story, later):
        from persist.checkpoints import ensure_checkpoint, restore_checkpoint

        ensure_checkpoint(story["chat_id"], 1)
        later()
        restore_checkpoint(story["chat_id"], 1)

    def test_all_four_homes_come_back_together(self, story):
        chat_id, char_id = story["chat_id"], story["char_id"]

        def advance():
            _dispatch("POST", "/seed",
                      query={"chat_id": str(chat_id),
                             "person_id": str(char_id)},
                      body={"state": {"campaign": "rewritten"},
                            "frame_state": {"mission": {"revision": 99}},
                            "char_state": {"duty": "relieved"},
                            "doc": {"entries": ["one", "two"]},
                            "block": "later"})
            _api().documents(chat_id).put_now("ledger/late", {"born": "after"})

        self._restore(story, advance)

        dto = _projection(chat_id, char_id)
        assert dto["frame_id"] == story["frame"]
        assert dto["state"] == SEED["state"]
        assert dto["frame_state"] == {"mission": {"revision": 41}}
        assert dto["char_state"] == {"duty": "watch"}
        assert dto["documents"] == ["ledger/current"], \
            "a document created after the checkpoint is gone, not orphaned"

    def test_the_present_era_is_rewound_too_and_stays_its_own(self, story):
        """The homes are per-era, so a restore has to put each era back to
        ITS own value -- not the latest era's over both."""
        chat_id, char_id = story["chat_id"], story["char_id"]
        present = _api().at_frame(chat_id, None)
        present.frame_state().set_now({"mission": {"revision": 1}})
        present.char_state(char_id).set_now({"duty": "asleep"})

        self._restore(story, lambda: present.frame_state().set_now(
            {"mission": {"revision": 500}}))

        assert _projection(chat_id, char_id, frame="present")["frame_state"] \
            == {"mission": {"revision": 1}}
        assert _projection(chat_id, char_id)["frame_state"] \
            == {"mission": {"revision": 41}}


# ------------------------------------------------------------ branch/archive


class TestBranchAndArchiveCarryTheWholeNamespace:
    """Scenario 4.

    The branch is the interesting half, and the untested one: a frame-scoped
    row's key literally embeds the SOURCE chat's frame id
    (`db._scoped_world_key`), so a branch that copied the world table
    faithfully would leave an extension's mission state addressed to a frame
    the branch does not have. `web/app.py`'s branch helper remaps it
    generically; `tests/test_extension_chat_lifecycle.py` asserts that the
    prefix makes extension state ELIGIBLE for that remap, which is a
    statement about a helper. Nothing asserted the remap landed.
    """

    def test_a_branch_carries_every_home_into_its_own_frame_ids(self, story):
        from persist.checkpoints import ensure_checkpoint
        from web import app

        chat_id, char_id = story["chat_id"], story["char_id"]
        ensure_checkpoint(chat_id, 1)
        ensure_checkpoint(chat_id, 2)

        branched = app.turn_branch(story["turn_id"])
        new_chat = branched["id"]

        new_char = _api().characters.get(new_chat, "Ilse")
        dto = _projection(new_chat, new_char.char_id)

        assert dto["frame_id"] not in (None, story["frame"]), \
            "the branch has its OWN frame, not a pointer to the source's"
        assert dto["frame_state"] == {"mission": {"revision": 41}}, \
            "the era-scoped home followed its era across the remap"
        assert dto["char_state"] == {"duty": "watch"}
        assert dto["state"] == SEED["state"]
        assert dto["documents"] == ["ledger/current"]

    def test_a_write_on_the_branch_does_not_reach_the_source(self, story):
        from persist.checkpoints import ensure_checkpoint
        from web import app

        chat_id, char_id = story["chat_id"], story["char_id"]
        ensure_checkpoint(chat_id, 1)
        ensure_checkpoint(chat_id, 2)
        branched = app.turn_branch(story["turn_id"])

        new_char = _api().characters.get(branched["id"], "Ilse")
        _dispatch("POST", "/seed",
                  query={"chat_id": str(branched["id"]),
                         "person_id": str(new_char.char_id)},
                  body={"state": {"campaign": "diverged"},
                        "frame_state": {"mission": {"revision": 900}},
                        "char_state": {"duty": "deserted"},
                        "doc": {"entries": []}, "block": "diverged"})

        assert _projection(chat_id, char_id)["frame_state"] == \
            {"mission": {"revision": 41}}
        assert _projection(chat_id, char_id)["char_state"] == {"duty": "watch"}

    def test_an_archive_round_trip_keeps_the_projection_coherent(self, story):
        from persist.checkpoints import ensure_checkpoint
        from web import app

        chat_id = story["chat_id"]
        ensure_checkpoint(chat_id, 1)

        imported = app.chat_import({"data": app.chat_export(chat_id)})
        new_char = _api().characters.get(imported["id"], "Ilse")
        dto = _projection(imported["id"], new_char.char_id)

        TestOneProjectionOneEra._assert_coherent(dto)
        assert dto["frame_id"] is not None, \
            "the imported story kept its era, not just its rows"
        assert dto["frame_state"] == {"mission": {"revision": 41}}
        assert dto["char_state"] == {"duty": "watch"}
        assert dto["state"] == SEED["state"]
        assert dto["documents"] == ["ledger/current"]


# ---------------------------------------------------------------- lifecycle


class TestAnInertExtensionIsInertEverywhere:
    """Scenario 5.

    `tests/test_extensions.py`'s `TestAFailedExtensionIsInertEverywhere` and
    `TestDisableIsCompleteAndReEnableIsExactlyOnce` already prove each
    surface goes quiet, and prove it by reading `registered_stages()` and
    the record's own hook lists. Both are worth having and neither is
    repeated. The composition they cannot make is this one: the SAME
    extension that a moment ago served a full projection out of four durable
    homes goes silent on every surface at once while its durable state is
    untouched -- which is what makes re-enabling a recovery rather than a
    reinstall.
    """

    def _assert_inert(self, story, *, reason):
        chat_id, char_id = story["chat_id"], story["char_id"]

        with pytest.raises(ExtensionError, match=reason):
            _projection(chat_id, char_id)
        with pytest.raises(ExtensionError, match=reason):
            extension_runtime.asset_path(EXT, "ui/panel.js")
        assert extension_runtime.ui_bundle() == ""
        assert extension_runtime.ui_styles() == ""
        assert extension_runtime.apply_plan_splices(
            [("director_resolve", "Resolve")]) == [("director_resolve",
                                                    "Resolve")]

        ctx = _StubCtx(chat_id=chat_id)
        payload = extension_runtime.dispatch_narration_payload(ctx, {"a": 1})
        assert payload.get("extension_context") is None, \
            "a stored block is DECLARATIVE -- there is nothing empty to " \
            "iterate, so the liveness check has to be made explicitly"

        results = {}
        extension_runtime.run_commit_domains(ctx, results)
        assert results == {}

    def test_a_disabled_extension_serves_nothing_anywhere(self, story):
        extension_runtime.disable_extension(EXT)
        self._assert_inert(story, reason="not enabled")

    def test_a_failed_extension_serves_nothing_anywhere_either(self, story,
                                                              ext_root):
        _install(ext_root, "def register(api):\n    raise ValueError('nope')\n")
        extension_runtime.reload()
        _enable(EXT)
        assert extension_runtime.failure_reason(EXT)

        self._assert_inert(story, reason="did not load")

    def test_the_durable_homes_survive_being_switched_off(self, story,
                                                          ext_root):
        """Disable is not uninstall. If it took the state with it, a host
        toggling an extension to diagnose something would destroy the
        campaign they were diagnosing."""
        chat_id, char_id = story["chat_id"], story["char_id"]
        extension_runtime.disable_extension(EXT)
        extension_runtime.reload()
        _enable(EXT)

        dto = _projection(chat_id, char_id)
        assert dto["state"] == SEED["state"]
        assert dto["frame_state"] == {"mission": {"revision": 41}}
        assert dto["char_state"] == {"duty": "watch"}
        assert dto["documents"] == ["ledger/current"]

    def test_re_enabling_registers_each_surface_exactly_once(self, story):
        """Counted through what each registration DOES, not through the
        registry that holds it -- a duplicate hook is only a defect because
        it runs twice.

        Routes are the one surface a count cannot reach: `_record_route`
        keys by `"<METHOD> <path>"`, so registering twice is idempotent by
        construction and a duplicate is unobservable from outside. The
        registry-level count for it is
        `test_extensions.py::test_re_enabling_registers_each_hook_exactly_once`.
        """
        chat_id = story["chat_id"]
        for _ in range(3):
            extension_runtime.disable_extension(EXT)
            extension_runtime.reload()
            _enable(EXT)
        extension_runtime.activate(refresh=True)

        plan = extension_runtime.apply_plan_splices(
            [("director_resolve", "Resolve"), ("narrator", "Narrator")])
        assert [key for key, _ in plan].count(f"ext:{EXT}:tick") == 1

        assert extension_runtime.ui_bundle().count(f'Sonder._begin("{EXT}")') \
            == 1

        blocks = extension_runtime.dispatch_narration_payload(
            _StubCtx(chat_id=chat_id), {})["extension_context"]
        assert [b["source"] for b in blocks] == [EXT]

        before = int((_api().settings.get() or {}).get("domain_runs") or 0)
        extension_runtime.run_commit_domains(
            _StubCtx(chat_id=chat_id, turn_id=1, idx=4), {})
        assert int(_api().settings.get()["domain_runs"]) == before + 1


# ------------------------------------------------------------- strict commit


class TestAStrictCommitDomainCostsTheWholeTurn:
    """Scenario 6.

    `tests/test_extension_seams.py::TestCommitDomains` proves `on_error="fail"`
    raises out of `run_commit_domains`. That is half the promise. The other
    half is the reason an extension would ever choose it: the raise has to
    reach through `commit_all`'s transaction and take the ENGINE's writes
    back with the extension's own, or "fail" buys a lost beat and a
    half-written world -- strictly worse than "warn".
    """

    @pytest.fixture
    def turn(self, story, monkeypatch):
        from persist import commit as commit_module
        from core.pipeline_context import ChatData, PipelineContext, TurnData

        monkeypatch.setattr(
            commit_module, "_prepare_turn_commit",
            lambda ctx: {"scene": {"scene": {}, "clock": None}, "mapping": {},
                         "memories": {}, "claims": {}})
        ctx = PipelineContext(
            chat=ChatData(id=story["chat_id"], name="Contract",
                          persona_id=None, lorebook_id=None, scenario="",
                          created=time.time()),
            turn=TurnData(id=story["turn_id"], chat_id=story["chat_id"],
                          idx=1, player_input="climb", created=time.time()),
            cast=[], input="climb")
        return commit_module, ctx

    def test_the_control_shows_both_halves_landing(self, story, turn):
        """Without this the rollback assertion could pass because nothing
        ever wrote."""
        from core.db import wget

        commit_module, ctx = turn
        commit_module.commit_all(ctx, nonce=0)

        assert wget(story["chat_id"], "pending") == [], "an engine write"
        assert _api().state(story["chat_id"]).get()["committed"] is True
        assert _api().documents(story["chat_id"]).get("ledger/committed") \
            == {"turn": 1}

    def test_a_strict_refusal_rolls_back_core_and_extension_alike(
            self, story, turn):
        from core.db import wget

        commit_module, ctx = turn
        _api().state(story["chat_id"]).set_now(dict(SEED["state"],
                                                    explode=True))

        with pytest.raises(RuntimeError, match="rolled back"):
            commit_module.commit_all(ctx, nonce=0)

        assert wget(story["chat_id"], "pending") is None, \
            "the engine's own domain wrote and was rolled back"
        assert _api().state(story["chat_id"]).get() == \
            dict(SEED["state"], explode=True), \
            "the extension's earlier domain wrote and was rolled back too"
        assert _api().documents(story["chat_id"]).get("ledger/committed") \
            is None
        assert _api().at_frame(story["chat_id"], story["frame"]) \
            .frame_state().get() == {"mission": {"revision": 41}}

    def test_the_failure_names_the_extension_that_asked_for_it(self, story,
                                                               turn):
        """A host reading a rolled-back turn must be able to tell an engine
        defect from an extension exercising its declared right to one.

        This composition is what found the defect. Every ENGINE domain is
        wrapped by `commit._commit_domain`, which prefixes the domain name
        and writes the turn's warning trail; the extension fan-out re-raised
        bare, so the host's entire account of a lost beat was `Commit failed
        and was rolled back: <whatever sentence the extension wrote>`. Unit
        coverage could not see it -- the raise was correct at the seam, and
        only the trip through `commit_all` shows what the host is left
        holding.
        """
        commit_module, ctx = turn
        _api().state(story["chat_id"]).set_now({"explode": True})

        with pytest.raises(RuntimeError) as excinfo:
            commit_module.commit_all(ctx, nonce=0)

        assert f"ext:{EXT}:strict" in str(excinfo.value)
        assert "the ledger disagrees with the beat" in str(excinfo.value)
        assert any(f"ext:{EXT}:strict" in note for note in ctx.warnings), \
            "the warning trail names it too, as it does for engine domains"


# ------------------------------------------------------------- capabilities


class TestTheFixtureGatesOnANameNotOnInternals:
    """Scenario 7.

    `tests/test_extensions.py::TestTheHostSaysWhatItOffers` pins the
    declaration -- the set is a frozenset, names the contract surface, and
    every name reaches a real method. What it cannot show is the point of
    declaring it: an extension deciding whether to load by reading the set,
    with no import of anything private, and a host that contains the refusal
    instead of crashing beside it.
    """

    def test_the_declared_surface_reaches_the_route(self, story):
        dto = _projection(story["chat_id"], story["char_id"])
        assert dto["api_version"] == extension_runtime.EXT_API_VERSION

    def test_an_extension_needing_an_unoffered_name_refuses_itself(
            self, temp_db, ext_root, monkeypatch):
        """The host is one capability short; the extension says so and does
        not load. It never had to look at a version number or probe for a
        method that might not exist."""
        from extension_runtime import api as api_module

        monkeypatch.setattr(
            api_module, "HOST_CAPABILITIES",
            frozenset(extension_runtime.HOST_CAPABILITIES
                      - {"frame_coherent_reads"}))
        _install(ext_root)
        _enable(EXT)

        reason = extension_runtime.failure_reason(EXT)
        assert "frame_coherent_reads" in reason
        with pytest.raises(ExtensionError, match="did not load"):
            _dispatch("GET", "/projection", query={"chat_id": "1",
                                                   "person_id": "1"})

    def test_the_rest_of_the_host_is_unharmed_by_that_refusal(
            self, temp_db, ext_root, monkeypatch):
        """The containment posture, at the one moment it is most likely to
        be forgotten: an extension refusing itself is an ordinary load
        failure, not a host error."""
        from extension_runtime import api as api_module
        from web import app

        monkeypatch.setattr(
            api_module, "HOST_CAPABILITIES",
            frozenset(extension_runtime.HOST_CAPABILITIES
                      - {"frame_coherent_reads"}))
        _install(ext_root)
        _write_extension(ext_root, "bystander", {
            "id": "bystander", "version": "1.0.0", "ext_api": 1,
            "capabilities": {"python": "extension.py"}},
            {"extension.py": "def register(api):\n"
                             "    api.add_route('/ok', lambda r: {'ok': True})\n"})
        _enable(EXT, "bystander")

        assert extension_runtime.dispatch_route(
            "bystander", "GET", "/ok") == {"ok": True}
        rows = {row["id"]: row for row in app.bootstrap()["extensions"]}
        assert rows[EXT]["enabled"] is True
        assert "frame_coherent_reads" in rows[EXT]["error"]
