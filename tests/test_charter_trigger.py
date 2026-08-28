"""Rules that fire off a change, and the four bounds that stop them.

``docs/guides/RESEARCH.md`` §1.7.6 item 5 -- the last of the five taken from
Comme il Faut, and the one whose whole risk is that a cascade does not stop.
So most of this file is a bound: the propagation depth, the refractory, the
per-window yield, and the cap on the persisted frame. Every one of them is
stated as a number in `world/charter_trigger.py` and every one of them has to
be a test here or it is a comment.

The other half is the firewall. A trigger is not a mind: it is handed
objective change and a body index, it produces objective consequence, and who
LEARNS of that consequence is `charter_news.witness`'s separate question.
`test_the_pass_is_not_given_a_head_to_read` is the structural half of that and
MUST NOT BE DELETED -- it is the only assertion that would survive a future
reader deciding the pass would be "simpler" with the charter in hand.
"""

from __future__ import annotations

import copy
import inspect
import json
import pathlib

import pytest

from world.charter_model import EXPERIENCE_CAP
from world.charter import (
    DEFAULT_TRIGGERS, PENDING_CHANGE_CAP, TRIGGER_DEPTH, TRIGGER_EMITTABLE,
    TRIGGER_MEMORY_CAP, TRIGGER_YIELD_CAP, changes_from, fire_triggers,
    normalize_charter, normalize_triggers, run, seed_needs, seed_roster, step,
    trigger_view, trigger_warnings)

from charter_fixtures import SHIP


def _yard(*, drift=0.05, folk=("ilse", "raul", "mira", "tomas")):
    """One granary nobody can hold, and four people standing in the yard.

    The smallest institution in which blame can LAND on somebody (the post is
    filled, so `attribute_blame` has a body to attach to) and somebody else is
    standing there to round on them. `charter_fixtures.SHIP` cannot do the
    second half: its bodies sit one to a post place, so the blamed engineer is
    alone in the engine room and there is nobody to open a quarrel with.
    """
    charter = normalize_charter({
        "key": "yard",
        "upkeeps": {"granary": {"place": "yard", "level": 0.9, "floor": 0.4,
                                "drift_per_hour": drift,
                                "service_per_hour": 0.02}},
        "posts": {"keeper": {"place": "yard", "serves": ["granary"]}},
        "bodies": {key: {"place": "yard"} for key in folk},
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _ready(spec):
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    return charter


def _change(**fields):
    row = {"kind": "blame_landed", "at_hours": 0.0, "place": "yard",
           "actor": "", "subject": "ilse", "about": "", "depth": 0}
    row.update(fields)
    return row


BODIES = {key: {"place": "yard", "available": True}
          for key in ("ilse", "raul", "mira", "tomas")}


def _only(*rules):
    """An authored rule set with every default switched off.

    `normalize_triggers` merges authored rows OVER `DEFAULT_TRIGGERS` by id,
    which is the feature -- and it means a unit test that hands in one rule is
    actually running two. The first draft of this file measured `quarrel`
    openings the shipped default had made and attributed them to the rule
    under test. Writing the default's id back with an empty `then` is the
    author's own disable path, so the arm exercises exactly what it says.
    """
    return [{"id": rule["id"], "on": rule["on"], "then": []}
            for rule in DEFAULT_TRIGGERS] + list(rules)


# --------------------------------------------------------------- the bounds

class TestTheLayerCostsNothingWhenNothingHappened:
    """`charter_run`'s first invariant, extended to the consequence layer:
    storage and work grow with INCIDENT, never with time."""

    def test_a_quiet_week_still_emits_nothing_with_the_default_rules_loaded(
            self):
        """The incident rule, in the register of
        `tests/test_charter_run.py`'s
        `test_a_week_of_a_working_ship_emits_zero_events`. A rule set is
        loaded on every charter now, including a healthy one."""
        charter = _ready(SHIP)
        assert normalize_triggers(charter["triggers"])

        after, events = run(charter, hours=168.0, window=4.0)

        assert events == []
        assert after["fired"] == []

    def test_a_quiet_window_leaves_the_change_frame_empty(self):
        """This is what makes the pass FREE rather than merely cheap: with an
        empty frame `fire_triggers` returns on one falsy test, so a healthy
        institution never pays for the layer at all."""
        after, _ = run(_ready(SHIP), hours=24.0, window=4.0)

        assert after["pending_changes"] == []

    def test_the_change_frame_does_not_grow_with_time(self):
        """2,400 simulated hours on a charter that cannot hold its granary.

        The frame is PERSISTED state and unbounded persisted state is how this
        package gets hurt -- 169 rows for five things happening, 1,134
        acquaintance rows in two years. Both caps are enforced in
        `charter_model.normalize_charter`, which runs at the head of every
        `step`, so this holds however the writer behaves.
        """
        after, _ = run(_yard(), hours=2_400.0, window=4.0, seed=7)

        assert len(after["pending_changes"]) <= PENDING_CHANGE_CAP
        assert len(after["trigger_last"]) <= TRIGGER_MEMORY_CAP

    def test_a_self_feeding_rule_fires_twice_and_stops(self):
        """The cascade bound, and the test that would catch a `depth` field
        that stopped being carried.

        Measured 2026-08-27 over 2,000 simulated hours of SHIP with
        `on: event:harm_done -> emit harm_done` and one authored `harm_done`
        seeded into the frame: the rule produces exactly `TRIGGER_DEPTH`
        consequences at every setting tried (1, 2, 3 and 4), which is what
        says this bound is the only thing stopping it. Without it the rule
        runs until `TRIGGER_YIELD_CAP` catches it, every window, forever.
        """
        charter = _ready(SHIP)
        charter["triggers"] = [{
            "id": "harm_begets_harm", "on": "event:harm_done",
            "then": [{"op": "emit", "kind": "harm_done",
                      "actor": "actor", "subject": "subject"}]}]
        charter["pending_changes"] = [_change(
            kind="event:harm_done", place="engine_room",
            actor="chief", subject="ramos")]

        _, events = run(charter, hours=2_000.0, window=4.0, seed=5)

        produced = [e for e in events
                    if e.get("trigger") == "harm_begets_harm"]
        assert len(produced) == TRIGGER_DEPTH

    def test_a_rule_cannot_fire_again_for_the_same_pair_inside_its_refractory(
            self):
        """The same change re-offered every window yields one consequence per
        refractory horizon, not one per window.

        Driven against `fire_triggers` directly rather than through a run,
        because the point is the arithmetic: at a 168-hour refractory and a
        4-hour window that is 1 in 42, and a run that happened to produce the
        change only once would pass whatever the store did.
        """
        rules = _only({"id": "quarrel_again", "on": "blame_landed",
                       "refractory_hours": 168.0,
                       "then": [{"op": "open_practice", "kind": "quarrel",
                                 "a": "nearby", "b": "subject"}]})
        memory, opened_total = {}, 0
        for window in range(84):
            at = 4.0 * (window + 1)
            _, opened, _, memory, _, _ = fire_triggers(
                [_change(at_hours=at)], BODIES, at, seed=3, rules=rules,
                last_fired=memory)
            opened_total += len(opened)

        assert opened_total == 2

    def test_the_yield_cap_binds_on_a_rulebase_that_has_gone_wrong(self):
        """A rule with no refractory, offered more changes than the cap.

        Measured with the shipped defaults the per-window yield is 0 on a
        healthy simulated year of `big_town(40)` and never above 2 on
        `twin_towns(240)` in famine, so this cap never binds in play. It is
        here for the rulebase that has gone wrong, and this is that rulebase.
        """
        # `on: act:greet` rather than `blame_landed`: since 2026-08-27 a mark
        # in `charter_mark.BODY_MARKS` may only be set from a change a body in
        # the room could have perceived (`perceivable_change`), and this test
        # is about the CAP rather than about which changes are legal.
        rules = _only({"id": "always", "on": "act:greet",
                       "then": [{"op": "set_mark", "mark": "accused",
                                 "on": "subject", "by": "actor"}]})
        changes = [_change(kind="act:greet", at_hours=1.0, subject=key,
                           actor="raul")
                   for key in BODIES] * 8

        _, _, onsets, _, fired, _ = fire_triggers(
            changes, BODIES, 1.0, seed=3, rules=rules)

        assert sum(len(rows) for rows in onsets.values()) == TRIGGER_YIELD_CAP
        assert len(fired) == TRIGGER_YIELD_CAP

    def test_a_runaway_rulebase_cannot_flood_the_autobiographies(self):
        """The yield cap is the ONLY thing holding
        `_record_coarse_experiences`.

        Its `stood_through` loop writes one UNFOLDED row per (event x body
        present), so a trigger-emitted event multiplies by the size of the
        room. That makes a bad rulebase blow `EXPERIENCE_CAP` (4,000) before
        it blows the event log -- the quieter and worse of the two failures,
        because an event log that grows is visible and a body that quietly
        loses the first three years of its life is not. So the assertion is on
        rows, not only on events.
        """
        charter = _yard()
        charter["needs"] = {}
        charter["triggers"] = _only({
            "id": "everything_is_harm", "on": "act:greet",
            "then": [{"op": "emit", "kind": "harm_done",
                      "actor": "actor", "subject": "subject"}]})

        per_window = []
        for window in range(60):
            charter, events = step(charter, hours=4.0, seed=3 + window)
            per_window.append(
                sum(1 for e in events if e.get("trigger")))

        assert max(per_window) <= TRIGGER_YIELD_CAP
        rows = {holder: len(held)
                for holder, held in charter["experiences"].items()}
        assert max(rows.values()) <= EXPERIENCE_CAP, rows


class TestTheSameSeedFiresTheSameTriggers:
    """Mirrors `tests/test_charter_run.py::TestReplay`, which is what
    checkpoint restore and branching rest on. The `nearby` referent is a
    seeded draw over a sorted roster, so this is the assertion that stops it
    being `random` or a set iteration order."""

    def test_two_runs_of_the_same_seed_fire_identically(self):
        a, _ = run(_yard(), hours=400.0, window=4.0, seed=11)
        b, _ = run(_yard(), hours=400.0, window=4.0, seed=11)

        assert a["fired"] == b["fired"]
        assert a["marks"] == b["marks"]
        assert sorted(a["practices"]) == sorted(b["practices"])
        assert a["trigger_last"] == b["trigger_last"]
        assert a["heard_blame"] == b["heard_blame"]


# ------------------------------------------------------------ the firewall

class TestTheFirewall:
    def test_a_rule_may_not_reach_a_head_from_the_institutions_own_books(
            self):
        """The `on` side of the same allowlist `TRIGGER_EMITTABLE` is the
        `then` side of.

        Which kinds a rule may MINT has been closed since this shipped; which
        changes it may mint them FROM was open, so the hole stayed reachable
        from the other end. Both of these normalized clean and fired on
        `.venv` before `perceivable_change` landed:

          * `emit harm_done` off `blame_landed` put a first-hand claim into
            every head in the room off a move of the institution's private
            counter, and `charter_social.DEFAULT_SIGNALS` then moved
            trust/fear/suspicion in each of them, citing evidence no witness
            could have seen.
          * `set_mark accused` off `event:post_unfilled` left a body feeling
            it at `charter_feel`'s -0.6 and showing it in the presence slice
            with nothing said aloud, no accuser and `heard_blame` empty --
            and `post_unfilled` is the exact event
            `tests/test_charter_promote.py` calls "a conclusion in the
            institution's books that no one in a room could perceive."

        A REFUSAL AND NOT A DROP, because an author has to be able to see
        what they wrote (`normalize_triggers`' own contract).
        """
        register = [
            {"id": "harm_from_the_books", "on": "blame_landed",
             "then": [{"op": "emit", "kind": "harm_done",
                       "actor": "subject", "subject": "nearby"}]},
            {"id": "shame_from_the_books", "on": "event:post_unfilled",
             "then": [{"op": "set_mark", "mark": "accused", "on": "nearby"}]},
        ]
        perceived = [
            {"id": "harm_from_an_act", "on": "act:greet",
             "then": [{"op": "emit", "kind": "harm_done",
                       "actor": "subject", "subject": "nearby"}]},
            {"id": "shame_from_an_act", "on": "act:accuse",
             "then": [{"op": "set_mark", "mark": "accused", "on": "subject"}]},
        ]

        refused = trigger_warnings(register)

        assert len(refused) == 2
        assert trigger_warnings(perceived) == []
        assert all(not row["then"]
                   for row in normalize_triggers(register)
                   if row["id"].endswith("_the_books"))
        # `disgraced` is the REGISTER'S OWN mark and is register-scoped
        # wherever it comes from, so the gate does not touch it -- the
        # allowlist being narrowed here is `charter_mark.BODY_MARKS`.
        assert trigger_warnings([
            {"id": "books_note_a_disgrace", "on": "blame_landed",
             "then": [{"op": "set_mark", "mark": "disgraced",
                       "on": "subject"}]}]) == []

    def test_the_pass_is_not_given_a_head_to_read(self):
        """THE STRUCTURAL FIREWALL TEST. DO NOT DELETE IT.

        A firewall held by a signature is checkable and one held by a
        docstring is not. `fire_triggers` decides from objective change and a
        body index; the moment somebody passes it the charter "because it
        needs one more field", a rule can weight a consequence on what is
        inside somebody's head. The import half is the same assertion from
        the other end: the module cannot reach a head even by accident.
        """
        forbidden = {"minds", "judgments", "needs", "feel", "heard_blame",
                     "roster", "charter", "politics", "regard", "experiences",
                     "served_beside", "ties", "marks"}
        named = set(inspect.signature(fire_triggers).parameters)
        assert not (named & forbidden), sorted(named & forbidden)

        source = pathlib.Path(
            inspect.getsourcefile(fire_triggers)).read_text("utf-8")
        imports = [line for line in source.splitlines()
                   if line.startswith(("import ", "from "))]
        for sibling in ("charter_mind", "charter_social", "charter_feel",
                        "charter_needs", "charter_talk", "charter_observe",
                        "charter_politics", "charter_model"):
            assert not any(sibling in line for line in imports), sibling

    def test_a_trigger_may_not_emit_a_register_conclusion(self):
        """`TRIGGER_EMITTABLE` is an allowlist for the reason
        `charter_news.WITNESSABLE` is one, and it is a TIGHTER one.

        `post_unfilled` is a conclusion the institution reached in its own
        books and `institution_order_executed` is an institutional fact at
        full first-hand strength with a stable news key two witnesses would
        agree on. A rule that could mint either would put a false register
        fact into every head in the room.
        """
        for kind in ("post_unfilled", "institution_order_executed",
                     "commitment_defaulted", "report_confirmed"):
            assert kind not in TRIGGER_EMITTABLE
            stored = _only({"id": "forge", "on": "blame_landed",
                            "then": [{"op": "emit", "kind": kind}]})
            row = next(r for r in normalize_triggers(stored)
                       if r["id"] == "forge")

            assert row["then"] == []
            assert kind in row["refused"]
            assert any("forge" in notice for notice in
                       trigger_warnings(stored))

            events, opened, onsets, _, fired, _ = fire_triggers(
                [_change()], BODIES, 1.0, seed=3, rules=stored)
            assert (events, opened, onsets, fired) == ([], {}, {}, [])

    def test_a_rule_may_not_match_on_something_a_change_does_not_carry(self):
        """`where` is restricted to `MATCHABLE`, which is narrower than the
        change row itself and very much narrower than the charter.

        An author who could write ``where: {"strain": ...}`` would have
        written a rule that reads a body's interior to decide what happens to
        somebody else -- the leak this layer exists not to open, arriving
        through the one field an author fills in by hand.
        """
        stored = [{"id": "peek", "on": "blame_landed",
                   "where": {"strain": "0.9", "subject": "ilse"},
                   "then": [{"op": "set_mark", "mark": "accused"}]}]
        row = next(r for r in normalize_triggers(stored) if r["id"] == "peek")

        assert row["where"] == {"subject": "ilse"}
        assert "strain" in row["refused"]

    def test_a_trigger_cannot_put_a_claim_in_a_head(self):
        """The consequence goes through `witness`, not around it.

        A rule minting an `aid_given` at the yard reaches the heads standing
        in the yard and no others, and moves no judgment axis in the window it
        fires -- `update_judgments_from_minds` runs before `enact`, so the
        opinion forms next window from a claim its holder can cite. Writing an
        axis here would produce a stance with no evidence behind it.
        """
        charter = _yard(folk=("ilse", "raul", "mira", "tomas"))
        charter["bodies"]["tomas"]["place"] = "cellar"
        # `on: act:greet` rather than `blame_landed`: a rule may not mint an
        # event from the institution's private counter (`perceivable_change`),
        # because a `witness` pass over it would put a first-hand claim about
        # something nobody saw into every head in the room. What this test is
        # about is where the minted event GOES, and that is unchanged.
        charter["triggers"] = [{
            "id": "aid_is_seen", "on": "act:greet",
            "then": [{"op": "emit", "kind": "aid_given",
                      "actor": "subject", "subject": "actor"}]}]
        charter["pending_changes"] = [_change(kind="act:greet", at_hours=0.0,
                                             subject="ilse")]
        before = copy.deepcopy(charter["judgments"])

        after, events = step(charter, hours=4.0, seed=3)

        minted = [e for e in events if e.get("trigger") == "aid_is_seen"]
        assert len(minted) == 1 and minted[0]["place"] == "yard"
        holders = {holder for holder, claims in after["minds"].items()
                   if any(str(key).startswith("news:") for key in claims)}
        assert "tomas" not in holders
        assert holders & {"raul", "mira"}
        assert after["judgments"] == before

    def test_the_diagnostic_carries_counts_and_not_the_rows(self):
        """`trigger_view` is author-only and stays a summary. A diagnostic
        that grows with the window is how a payload becomes a transcript --
        the same rule `charter_run`'s trace is held to."""
        view = trigger_view(
            None, [_change(), _change(subject="raul")], {"a|b|c": 1.0})

        assert view["pending_changes"] == 2
        assert view["refractory_rows"] == 1
        assert [row["id"] for row in view["rules"]] == \
            [rule["id"] for rule in DEFAULT_TRIGGERS]
        assert "changes" not in json.dumps(view["rules"])


# ---------------------------------------------------------- what it buys

class TestBlameFinallyReachesThePersonItLandedOn:
    """The measured dead edge, and the whole argument for the shipped rule.

    `accuse` is offered only inside a `quarrel`. Until 2026-08-27 `quarrel`
    opened only from `accuse`'s own effect or from an author, so an accusation
    was unreachable in pure simulation. `charter_practice.opportunities` now
    opens it from the blame ledger ON SCREEN; off screen it still does not --
    `quarrel` is not in `COARSE_PRACTICES` and the offscreen branch passes no
    blame -- and the measurement is design 4's: `twin_towns(240)` driven into
    famine for a simulated month recorded 48 bodies ever `posted`, 2 ever
    `disgraced`, and ZERO ever `accused`. A blame that lands where nobody is
    looking still lands on a person.
    """

    def test_a_blame_that_lands_offscreen_is_said_out_loud(self):
        charter = _yard()
        assert not charter["active_places"]

        after, _ = run(charter, hours=120.0, window=4.0, seed=3)

        assert after["politics"]["blame"]
        blamed = sorted(after["politics"]["blame"])
        assert after["heard_blame"], "nobody was ever told"
        # THE BLAMED BODY IS TOLD -- that is the dead edge this rule closes.
        # The containment is this way round and no longer the other: until
        # 2026-08-27 this line read `set(heard_blame) <= set(blamed)`, which
        # asserted that ONLY the people the books blame are ever accused, and
        # that was the leak stated as a guarantee. An accusation now follows
        # the accuser's own perception (`charter_practice.grievance_against`),
        # so a body the register never blamed can be rounded on by somebody
        # who watched the granary fail beside them -- measured here: blame
        # lands on ilse alone, and the run ends with ilse and tomas each
        # holding `accused` by the other. The institution's books being wrong
        # about who is answerable is now VISIBLE as that divergence instead of
        # being laundered into an accuser's mouth.
        assert set(blamed) <= set(after["heard_blame"])
        for subject, tellers in after["heard_blame"].items():
            assert tellers and subject not in tellers
            assert after["marks"][subject]["accused"]["by"] in tellers

    def test_a_trigger_opened_situation_is_actable_in_the_window_it_opens(
            self):
        """THE REGRESSION GUARD FOR THE PLACEMENT TRAP.

        `close_stale` sweeps a practice that has produced nothing for
        `IDLE_CLOSE_HOURS` (2.0), and every shipped presim window is 4.0 or
        8.0 hours. So a situation opened AFTER `enact` carries
        `last_effect_at = at + hours` and is swept by the next window before
        anybody can act in it -- silently, with no error and no failing test.
        Run at window 8.0, well above the sweep, so the assertion can only
        pass if the act happened in the window the situation opened.
        """
        after, _ = run(_yard(), hours=240.0, window=8.0, seed=3)

        assert after["heard_blame"], \
            "the quarrel was swept before anybody acted"

    def test_a_busy_window_still_deposits_a_blame_that_landed(self):
        """The frame is capped and a busy window overflows it, so the cap must
        not be able to starve one family of changes with another's volume.

        Measured 2026-08-27 on a famine week of `twin_towns(240)`: the busiest
        window produced 184 changes, of which 150 were `act:` rows and 2 were
        `event:` rows. A flat most-recent cap survives that only by an
        alphabetical accident (all rows share an hour, so recency degenerates
        to a sort by key, and `"act:" < "blame_landed"`). Whether a rule ever
        gets a chance must not depend on how its family name spells.
        """
        acts = [{"actor": "raul", "act": "greet", "other": key}
                for key in BODIES for _ in range(30)]
        events = [{"kind": "aid_given", "at_hours": 1.0, "place": "yard",
                   "actor": "mira", "subject": "ilse"}] * 30

        frame = changes_from(events=events, acts=acts, blamed=["ilse"],
                             bodies=BODIES, at_hours=1.0)

        assert len(frame) == PENDING_CHANGE_CAP
        assert [row for row in frame if row["kind"] == "blame_landed"]
        assert {row["kind"].split(":", 1)[0] for row in frame} == \
            {"act", "blame_landed", "event"}


class TestMarksAreTheOneStoreOfTemporaryFacts:
    """Design 5 ships NO `statuses` key. `charter_mark` (`RESEARCH.md` §1.7.6
    item 4) landed first and already holds socially temporary facts with a
    lifetime per kind, an expiry prune, a body-scope allowlist and three
    readers. Two stores of the same idea can only ever disagree, which is the
    argument `charter_social`'s tie layer makes about labels and numbers."""

    def test_a_rule_may_set_a_mark_and_the_mark_expires(self):
        """A triggered mark is the SAME ROW a lived one is, which is the whole
        reason `set_mark` writes here: it is minted through `advance_marks`
        with the four onset lists, so it carries `MARK_HOURS["aided"]` (48.0)
        and is pruned by the same pass that prunes an ordinary tending. A
        second store would have needed a second prune.

        The fixture deliberately has no needs seeded: with them, bodies go
        under their floor and are tended for real, and the arm would pass on a
        mark the trigger did not set.
        """
        charter = _yard()
        charter["needs"] = {}
        charter["triggers"] = _only({
            "id": "credit_the_helped", "on": "act:tend",
            "then": [{"op": "set_mark", "mark": "aided",
                      "on": "subject", "by": "actor"}]})
        charter["pending_changes"] = [_change(
            kind="act:tend", at_hours=0.0, actor="raul", subject="ilse")]

        after, _ = step(charter, hours=4.0, seed=3)
        assert after["marks"]["ilse"]["aided"]["by"] == "raul"

        after, _ = run(after, hours=60.0, window=4.0, seed=3)
        assert "aided" not in (after["marks"].get("ilse") or {})

    def test_a_rule_may_not_invent_a_status_with_no_lifetime(self):
        """`MARKS` is the vocabulary, for the reason `normalize_marks` gives:
        a row whose kind has no lifetime could never expire, so it would be a
        permanent trait wearing the word 'temporary'."""
        stored = [{"id": "coin_one", "on": "blame_landed",
                   "then": [{"op": "set_mark", "mark": "owed_favour"}]}]
        row = next(r for r in normalize_triggers(stored)
                   if r["id"] == "coin_one")

        assert row["then"] == []
        assert "owed_favour" in row["refused"]


# ------------------------------------------------------- the author surface

class TestTheAuthoringSurface:
    def test_an_unknown_op_is_refused_with_a_notice_and_changes_nothing(self):
        """Mirrors `charter_intervene.intervention_warnings`' contract: the
        row SURVIVES so the author can see what they wrote, it appears in the
        warnings, and it applies nothing. Dropping it silently is how an
        author debugs a rule that was never loaded."""
        stored = _only({"id": "wishful", "on": "blame_landed",
                        "then": [{"op": "set_judgment", "axis": "trust"}]})

        row = next(r for r in normalize_triggers(stored)
                   if r["id"] == "wishful")
        assert row["then"] == []
        assert "set_judgment" in row["refused"]
        assert trigger_warnings(stored) == [
            f"wishful: {row['refused']}"]

        events, opened, onsets, _, fired, _ = fire_triggers(
            [_change()], BODIES, 1.0, seed=3, rules=stored)
        assert (events, opened, onsets, fired) == ([], {}, {}, [])

    def test_a_default_rule_is_disabled_by_an_authored_empty_consequence(self):
        """The override path, mirroring how `social_norms.signals` overrides
        `charter_social.DEFAULT_SIGNALS`: merged BY ID, so writing the id back
        with an empty `then` is how an author switches a default off."""
        default = DEFAULT_TRIGGERS[0]["id"]
        charter = _yard()
        charter["triggers"] = [{"id": default, "on": "blame_landed",
                                "then": []}]

        after, _ = run(charter, hours=120.0, window=4.0, seed=3)

        assert after["politics"]["blame"], "the arm proves nothing if no blame"
        assert after["fired"] == []
        assert after["heard_blame"] == {}
        assert [row for row in after["triggers"] if row["id"] == default] == [
            {"id": default, "on": "blame_landed", "where": {}, "odds": 1.0,
             "refractory_hours": 0.0, "then": []}]

    def test_an_unknown_change_kind_is_refused_rather_than_ignored(self):
        stored = [{"id": "guesswork", "on": "when_they_are_sad",
                   "then": [{"op": "set_mark", "mark": "accused"}]}]
        row = next(r for r in normalize_triggers(stored)
                   if r["id"] == "guesswork")

        assert "when_they_are_sad" in row["refused"]

    @pytest.mark.parametrize("stored", [None, [], "nonsense", [42, None]])
    def test_a_charter_that_never_heard_of_triggers_loads_the_defaults(
            self, stored):
        """A charter saved before this existed, and three shapes that are not
        a rule set. All four load the defaults rather than raising."""
        rules = normalize_triggers(stored)

        assert [row["id"] for row in rules] == \
            sorted(rule["id"] for rule in DEFAULT_TRIGGERS)


class TestItSurvivesPersistence:
    def test_the_three_new_keys_survive_a_json_round_trip(self):
        """`charter_model`'s own rule: the state has to survive a JSON round
        trip into `world` storage without a second representation to keep in
        step. Normalize -> dumps -> loads -> normalize is a fixed point."""
        charter = _yard()
        charter, _ = run(charter, hours=120.0, window=4.0, seed=3)
        charter = normalize_charter(charter)
        assert charter["trigger_last"], "the arm proves nothing if never fired"

        reloaded = normalize_charter(json.loads(json.dumps(charter)))

        for key in ("triggers", "pending_changes", "trigger_last"):
            assert reloaded[key] == charter[key], key

    def test_a_restored_run_does_not_refire_what_it_already_fired(self):
        """The reason the refractory store rides the CHARTER and not a runner,
        which is the argument `reported` already carries at
        `charter_model.py`: a caller that checkpoints and restores without it
        replays every consequence it had already produced."""
        charter, _ = run(_yard(), hours=120.0, window=4.0, seed=3)
        restored = normalize_charter(json.loads(json.dumps(charter)))

        straight, _ = run(copy.deepcopy(charter), hours=120.0, window=4.0,
                          seed=33)
        resumed, _ = run(restored, hours=120.0, window=4.0, seed=33)

        assert resumed["fired"] == straight["fired"]
        assert resumed["heard_blame"] == straight["heard_blame"]
