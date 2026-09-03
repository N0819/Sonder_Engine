"""The round between institutions: a creature hunts, a town is hunted, and
both find out only what reached them.

``docs/design/DESIGN_CREATURES_AS_CHARTER.md`` §3. `charter_run.step`
advances ONE institution and reads nothing outside it -- the ownership
boundary the whole package rests on. Predation is cross-institutional by
definition (the pack is one charter, the town another, and they meet by
place), so it cannot live inside a step. It lives here, in a ROUND run
after every charter in a registry has stepped one window:

  1. **Senses.** A hunting body that notices prey within its range walks
     toward it, through the graph its own footprint and doors allow.
  2. **Encounters.** Where a creature body and prey share a place, an
     attack is drawn from the run's seed at odds the creature authored,
     scaled by its hunger and boldness. The target is the first category
     of the creature's prey table the place holds.
  3. **The contest**, seeded and deterministic: what the creature bodies
     standing there bring against what the target brings with everyone
     beside it. A posted body is not an unposted one; a group is not a
     straggler; a guarded place is guarded for everybody in it.
  4. **The outcome lands in each institution's own vocabulary.** A body
     is hurt, killed or taken through `charter_harm.apply_harm` in ITS
     charter; a lot is taken through the economy; the creature's fed
     upkeep is restored; a losing attacker is hurt by the guard it lost
     to. Every event is CARRIED into the next window's step of the charter
     it belongs to, where it is witnessed by presence, appraised, deposited
     as a change for triggers and remembered by whoever stood there --
     one window of lag, the same lag triggers and judgments already carry.
  5. **Spoor.** A landed predation leaves a record standing at the place
     for a named number of hours, and a body of ANY institution standing
     there reads it: a claim in its own head, provenance ``read``, the same
     door a posted bill's copy enters by. Nobody learns of a kill because
     it happened; they learn because they saw it, were told, or came upon
     what it left.
  6. **Tribute.** A bargain the creature holds with an institution is a
     commitment in the creature's own ledger and a transfer of lots on its
     own cadence; while it stands the creature does not hunt that
     institution. An institution that cannot pay defaults; a creature left
     hungry under a bargain repudiates it. Both are events.

`run_registry` is the stepper that interleaves: every charter one window,
then the round, then the next window. It is what `charter_runtime` uses in
place of the per-charter `run` the moment a registry holds a creature, and
a registry without one never enters it -- so an ordinary town is advanced
by exactly the code it always was.

THE FIREWALL, restated for this seam: a creature's own mind holds only what
its senses reached (a body it stood beside, a place it hunted); an
institution's bodies learn of harm through the room, the report or the
spoor and never from this module writing into a head. `read_spoor` writes
a claim only into a body standing where the spoor lies.
"""

from __future__ import annotations

import copy
import hashlib

from .charter_creature import (
    attack_odds, contest, creature_neighbors, hunger_of, is_active,
    normalize_creature, normalize_spoor, predator_capability,
    prey_capability, win_chance)
from .charter_harm import apply_harm, is_gone
from .charter_model import _clamp, normalize_charter
from .charter_move import en_route, walk

#: How many rooms out `senses` may look, whatever a creature authored: the
#: walk is BFS over the creature's own graph and a range past the reach the
#: planner uses would cost the graph every window for nothing a body could
#: reach in one.
SENSE_RANGE_CAP = 8

#: The smallest holding that counts as stock to be taken: one whole lot.
STOCK_WHOLE_LOT = 1.0


def _draw(*parts):
    digest = hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / float(0xFFFFFFFF)


def creature_keys(states):
    """The charters in a registry that are creatures, sorted."""
    return sorted(key for key, state in (states or {}).items()
                  if isinstance(state, dict) and state.get("creature"))


def qualified(charter_key, body_key):
    """A body's registry-wide name, as another institution names it. The
    same spelling `charter_runtime.person_id` uses."""
    return "%s/%s" % (str(charter_key), str(body_key))


# ---------------------------------------------------------------- the view

def _company(states):
    """``{place: {charter: [body keys]}}`` of every available body standing
    somewhere, and ``{place: [(charter, holder, good, amount)]}`` of every
    stocked market. Built once per round; everything below indexes it."""
    bodies_at, stock_at = {}, {}
    for charter_key, state in sorted((states or {}).items()):
        for body_key, body in sorted((state.get("bodies") or {}).items()):
            if not body.get("available", True) or is_gone(body):
                continue
            place = str(body.get("place") or "")
            if place:
                bodies_at.setdefault(place, {}).setdefault(
                    charter_key, []).append(body_key)
        economy = state.get("economy") or {}
        for market in sorted((economy.get("markets") or {}).values(),
                             key=lambda m: (m.get("place"), m.get("holder"))):
            place = str(market.get("place") or "")
            holder = str(market.get("holder") or "")
            for good, amount in sorted(
                    ((economy.get("stocks") or {}).get(holder) or {}).items()):
                # A WHOLE LOT, or nothing to take. A pen that lambs at a
                # hundredth of a head an hour is not raided for the hundredth:
                # measured before this held, a month of "raids" on a pen that
                # never held a whole head, ninety-five of them, and not one
                # turn toward the bodies the table ranked next.
                if float(amount) >= STOCK_WHOLE_LOT:
                    stock_at.setdefault(place, []).append(
                        (charter_key, holder, good, float(amount)))
    return bodies_at, stock_at


def _truce(state, partner):
    """Does this creature hold a standing bargain with ``partner``."""
    from .charter_commitment import OPEN_STATES

    for record in (state.get("commitments") or {}).values():
        if record.get("kind") == "bargain" \
                and record.get("beneficiary") == partner \
                and record.get("state") in OPEN_STATES \
                and record.get("state") != "proposed":
            return True
    return False


def _fed(state, amount):
    """Restore the creature's fed upkeep by ``amount``, in place."""
    creature = state.get("creature") or {}
    key = (creature.get("fed") or {}).get("upkeep") or ""
    upkeep = (state.get("upkeeps") or {}).get(key)
    if isinstance(upkeep, dict):
        upkeep["level"] = _clamp(float(upkeep.get("level", 1.0))
                                 + float(amount))


def _hoard(state):
    creature = state.get("creature") or {}
    return str(creature.get("hoard_holder") or state.get("key") or "hoard")


# ---------------------------------------------------------------- senses

def _reachable(neighbors, origin, limit):
    """Rooms within ``limit`` steps of ``origin`` on ``neighbors``, with
    their distance, BFS. Excludes the origin."""
    seen = {origin: 0}
    frontier = [origin]
    for depth in range(1, int(limit) + 1):
        nxt = []
        for room in frontier:
            for other in sorted(neighbors.get(room, ())):
                if other not in seen:
                    seen[other] = depth
                    nxt.append(other)
        frontier = nxt
        if not frontier:
            break
    seen.pop(origin, None)
    return seen


def _prey_here(place, own, bodies_at, stock_at, states, prey_order):
    """The first category of the prey table this place holds, and what."""
    for category in prey_order:
        if category == "stock":
            rows = [row for row in stock_at.get(place, ()) if row[0] != own
                    and not _truce(states[own], row[0])]
            if rows:
                return category, rows
        elif category in ("unposted", "posted"):
            found = []
            for charter_key, keys in sorted(
                    (bodies_at.get(place) or {}).items()):
                if charter_key == own or _truce(states[own], charter_key):
                    continue
                watch = set((states[charter_key].get("watch") or {}).values())
                for key in keys:
                    posted = key in watch
                    if (category == "posted") == posted:
                        found.append((charter_key, key))
            if found:
                return category, found
    return "", []


def hunt_moves(states, own, bodies_at, stock_at, neighbors, seed, at_hours):
    """``{body: place}`` for the creature bodies that noticed prey nearby
    and are not already going somewhere."""
    state = states[own]
    creature = state.get("creature") or {}
    limit = min(SENSE_RANGE_CAP, int(
        (creature.get("senses") or {}).get("range_rooms") or 0))
    moves = {}
    if limit <= 0:
        return moves
    prey_order = list(creature.get("prey") or ())
    for body_key, body in sorted((state.get("bodies") or {}).items()):
        if not body.get("available", True) or is_gone(body) or en_route(body):
            continue
        here = str(body.get("place") or "")
        if not here:
            continue
        category, _rows = _prey_here(here, own, bodies_at, stock_at, states,
                                     prey_order)
        if category:
            continue
        best = None
        for room, distance in _reachable(neighbors, here, limit).items():
            category, _rows = _prey_here(room, own, bodies_at, stock_at,
                                         states, prey_order)
            if not category:
                continue
            rank = prey_order.index(category)
            candidate = (rank, distance,
                         _draw(seed, at_hours, own, body_key, room), room)
            if best is None or candidate < best:
                best = candidate
        if best is not None:
            moves[body_key] = best[3]
    return moves


# ------------------------------------------------------------ the contest

def _spoor_row(own, kind, place, at_hours, description, about, actor,
               hours, index):
    return {
        "key": "spoor:%s:%0.4f:%s:%d" % (own, float(at_hours), place, index),
        "place": str(place), "at_hours": round(float(at_hours), 6),
        "until_hours": round(float(at_hours) + float(hours), 6),
        "description": str(description)[:80], "kind": str(kind),
        "about": str(about)[:120], "actor": str(actor)[:120],
    }


def _attack(states, own, body_keys, place, category, rows, at_hours, seed,
            events, spoor, index):
    """One attack at one place. Returns the number of bodies killed or
    taken (for the ceiling). Mutates ``states``."""
    state = states[own]
    creature = state.get("creature") or {}
    contest_spec = creature.get("contest") or {}
    hunters = [state["bodies"][k] for k in body_keys]
    landed = 0

    def _seen(prey_key):
        # A watch called out to this place has seen the thing it was
        # called for, whether or not it lost anything to it.
        mob = (states[prey_key].get("mobilisations") or {}).get(place)
        if isinstance(mob, dict):
            mob["harm_seen"] = True

    if category == "stock":
        prey_key, holder, good, amount = rows[
            int(_draw(seed, at_hours, own, place, "stock") * len(rows))
            % len(rows)]
        lots = min(float(amount), float(creature.get("stock_lots") or 0.0))
        if lots <= 0.0:
            return 0
        from .charter_economy import take_stock

        prey = states[prey_key]
        prey["economy"], taken_event = take_stock(
            prey.get("economy"), holder=holder, good=good, amount=lots,
            at_hours=at_hours, place=place, by=own)
        if taken_event is None:
            return 0
        _seen(prey_key)
        events.setdefault(prey_key, []).append(taken_event)
        hoard = state.setdefault("economy", {})
        stocks = hoard.setdefault("stocks", {})
        goods = hoard.setdefault("goods", {})
        if good not in goods:
            goods[good] = {"label": good, "base_value": 1.0, "unit": "lot"}
        held = stocks.setdefault(_hoard(state), {})
        held[good] = round(float(held.get(good, 0.0)) + lots, 6)
        _fed(state, float((creature.get("fed") or {}).get("per_lot") or 0.0)
             * lots)
        events.setdefault(own, []).append(dict(
            taken_event, holder=_hoard(state), by=body_keys[0],
            took_from=qualified(prey_key, holder)))
        text = (creature.get("spoor") or {}).get("stock")
        if text:
            spoor.append(_spoor_row(
                own, "stock_taken", place, at_hours, text, good, own,
                (creature.get("spoor") or {}).get("hours") or 0.0, index))
        return 0

    prey_key, target_key = rows[
        int(_draw(seed, at_hours, own, place, "body") * len(rows))
        % len(rows)]
    prey = states[prey_key]
    target = prey["bodies"][target_key]
    posted = target_key in set((prey.get("watch") or {}).values())
    company = sum(1 for k, b in (prey.get("bodies") or {}).items()
                  if str(b.get("place") or "") == place
                  and b.get("available", True) and not is_gone(b))
    pred = predator_capability(hunters, contest_spec)
    defence = prey_capability(target, posted, company, contest_spec)
    if win_chance(pred, defence) < float(contest_spec.get("caution") or 0.0):
        # Not worth it. The creature turns away; nothing happened here that
        # anybody could see, so nothing is recorded.
        return 0
    _seen(prey_key)
    won = contest(pred, defence, _draw(seed, at_hours, own, place, "contest",
                                       target_key))
    attacker = body_keys[0]
    if won:
        outcome = "missing" if creature.get("take") else "dead"
        # IN PLACE. The round owns its states outright, and a caller keeping
        # a reference to one sees the harm land (`run_registry`, and every
        # test that holds `town`); a deep copy per kill was most of the
        # round's cost on a thousand-body town.
        _prey, harm_events = apply_harm(
            prey, target_key, by=qualified(own, attacker), at_hours=at_hours,
            outcome=outcome, place=place, cause="predation",
            copy_state=False)
        events.setdefault(prey_key, []).extend(harm_events)
        events.setdefault(own, []).append({
            "kind": "harm_done", "at_hours": round(float(at_hours), 6),
            "place": place, "about": attacker, "actor": attacker,
            "body": attacker, "subject": qualified(prey_key, target_key),
            "outcome": outcome, "cause": "predation",
        })
        _fed(state, float((creature.get("fed") or {}).get("per_body") or 0.0))
        text = (creature.get("spoor") or {}).get("body")
        if text and outcome == "dead":
            spoor.append(_spoor_row(
                own, "harm_done", place, at_hours, text,
                qualified(prey_key, target_key), own,
                (creature.get("spoor") or {}).get("hours") or 0.0, index))
        landed = 1
    elif posted:
        # The guard it lost to hurts it. An unposted body that wins its
        # contest has merely got away.
        _own, harm_events = apply_harm(
            state, attacker, by=qualified(prey_key, target_key),
            at_hours=at_hours, outcome="hurt", place=place, cause="repelled",
            copy_state=False)
        events.setdefault(own, []).extend(harm_events)
        events.setdefault(prey_key, []).append({
            "kind": "harm_done", "at_hours": round(float(at_hours), 6),
            "place": place, "about": target_key, "actor": target_key,
            "body": target_key, "subject": qualified(own, attacker),
            "outcome": "hurt", "cause": "repelled",
        })
    tracks = (creature.get("spoor") or {}).get("tracks")
    if tracks:
        spoor.append(_spoor_row(
            own, "harm_done" if won else "sighting", place, at_hours, tracks,
            "", own, (creature.get("spoor") or {}).get("hours") or 0.0,
            index + 1000))
    return landed


def predation_round(states, at_hours, *, seed=0, hours=4.0):
    """One round between every creature and everything it can reach.

    Returns ``{charter: [events]}`` -- the events each institution is
    handed at its next window (`charter_run.step`'s ``carried``). Mutates
    ``states``: harm, stock, hoards, fed upkeeps, spoor and walks.
    """
    events = {}
    keys = creature_keys(states)
    if not keys:
        return events
    at = float(at_hours)
    bodies_at, stock_at = _company(states)
    for own in keys:
        state = states[own]
        creature = normalize_creature(state.get("creature"))
        if not creature:
            continue
        state["creature"] = creature
        _tribute(states, own, at, events)
        if not is_active(state, at):
            continue
        scene = state.get("scene")
        neighbors = creature_neighbors(scene, creature) if scene else {}
        # 1. Senses: walk toward what was noticed, on this creature's graph.
        moves = hunt_moves(states, own, bodies_at, stock_at, neighbors, seed,
                           at)
        if moves:
            bodies, travelled, walked = walk(
                state["bodies"], moves, scene, state.get("travelled"),
                hours=hours, neighbors=neighbors or None,
                walked=state.get("walked"))
            state["bodies"], state["travelled"], state["walked"] = \
                bodies, travelled, walked
            bodies_at, stock_at = _company(states)
        # 2. Encounters, by place.
        hunger = hunger_of(state)
        odds = attack_odds(creature, hunger)
        ceiling = int(creature.get("kill_ceiling") or 0)
        landed = 0
        spoor = []
        by_place = {}
        for body_key, body in sorted((state.get("bodies") or {}).items()):
            if not body.get("available", True) or is_gone(body):
                continue
            place = str(body.get("place") or "")
            if place:
                by_place.setdefault(place, []).append(body_key)
        index = 0
        for place, body_keys in sorted(by_place.items()):
            if landed >= ceiling:
                break
            category, rows = _prey_here(place, own, bodies_at, stock_at,
                                        states, creature.get("prey") or ())
            if not category:
                continue
            if _draw(seed, at, own, place, "attack") >= odds:
                continue
            landed += _attack(states, own, body_keys, place, category, rows,
                              at, seed, events, spoor, index)
            index += 1
            bodies_at, stock_at = _company(states)
        if spoor:
            state["spoor"] = normalize_spoor(
                list(state.get("spoor") or ()) + spoor)
    read_spoor(states, at)
    return events


# --------------------------------------------------------------- spoor

def standing_spoor(states, at_hours):
    """Every spoor record still standing, ``[(creature, row)]``."""
    out = []
    for key, state in sorted((states or {}).items()):
        for row in normalize_spoor(state.get("spoor")):
            if float(row["until_hours"]) > float(at_hours):
                out.append((key, row))
    return out


def read_spoor(states, at_hours):
    """Bodies standing where spoor lies come to know what it says.

    A claim in the reader's own head, provenance ``read``, keyed by the
    spoor so two readers hold the SAME fact and can compare it. The
    creature that left it does not read it (it knows), and a body that has
    read this spoor before does not read it twice. Expired spoor is swept
    here, which is the only place it is read.
    """
    from .charter_news import WITNESS_STRENGTH

    at = float(at_hours)
    rows = standing_spoor(states, at)
    read = 0
    for key, state in sorted((states or {}).items()):
        kept = [row for row in normalize_spoor(state.get("spoor"))
                if float(row["until_hours"]) > at]
        if kept or state.get("spoor"):
            state["spoor"] = kept
    if not rows:
        return read
    for key, state in sorted((states or {}).items()):
        minds = state.setdefault("minds", {})
        for body_key, body in sorted((state.get("bodies") or {}).items()):
            if not body.get("available", True) or is_gone(body):
                continue
            place = str(body.get("place") or "")
            for owner, row in rows:
                if owner == key or row["place"] != place:
                    continue
                held = minds.setdefault(body_key, {})
                if row["key"] in held:
                    continue
                held[row["key"]] = {
                    "kind": "news", "body": row["key"],
                    "event_kind": row["kind"],
                    "about": row["about"] or row["description"],
                    "actor": row["actor"], "toward": row["about"],
                    "claim_text": row["description"],
                    "place": place, "happened_at": float(row["at_hours"]),
                    "strength": WITNESS_STRENGTH, "as_of_hours": at,
                    "heard_from": None, "provenance": "read",
                }
                read += 1
        if read:
            from .charter_news import news_keys_in
            state["news_keys"] = sorted(news_keys_in(minds))
    return read


# ------------------------------------------------------------- tribute

def _tribute(states, own, at_hours, events):
    """Bargains this creature holds: open the record, collect what is due,
    default the partner that cannot pay, repudiate when left hungry."""
    from .charter_commitment import (OPEN_STATES, open_commitment)
    from .charter_economy import trade
    from .charter_model import out_of_band

    state = states[own]
    creature = state.get("creature") or {}
    for bargain in creature.get("bargains") or ():
        partner = bargain["with"]
        if partner not in states or partner == own:
            continue
        source = "bargain:%s:%s" % (own, partner)
        state["commitments"], cid, _opened = open_commitment(
            state.get("commitments"), source_id=source, kind="bargain",
            promisor=own, beneficiary=partner,
            terms="no hunting of %s while tribute is paid" % partner,
            state="accepted", at_hours=at_hours)
        record = state["commitments"].get(cid) or {}
        if record.get("state") not in OPEN_STATES:
            continue
        fed_key = (creature.get("fed") or {}).get("upkeep") or ""
        fed = (state.get("upkeeps") or {}).get(fed_key)
        if isinstance(fed, dict) and out_of_band(fed):
            record["state"] = "repudiated"
            record["lifecycle"].append({
                "kind": "repudiated", "at_hours": round(float(at_hours), 6),
                "evidence_id": source, "by": own, "to": partner,
                "note": "left hungry under the bargain"})
            events.setdefault(own, []).append({
                "kind": "commitment_repudiated",
                "at_hours": round(float(at_hours), 6),
                "place": _lair(state), "commitment_id": cid, "by": own,
                "actor": own, "subject": partner})
            continue
        last = bargain.get("last_paid_hours")
        every = float(bargain.get("every_hours") or 168.0)
        if last is not None and float(at_hours) - float(last) < every:
            continue
        good, lots = bargain.get("good"), float(bargain.get("lots") or 0.0)
        partner_state = states[partner]
        economy = partner_state.get("economy") or {}
        holder = bargain.get("holder") or next(
            (h for h, held in sorted((economy.get("stocks") or {}).items())
             if float((held or {}).get(good, 0.0)) > 0.0), "")
        available = float(((economy.get("stocks") or {}).get(holder) or {})
                          .get(good, 0.0)) if holder else 0.0
        place = next((m.get("place") for m in
                      (economy.get("markets") or {}).values()
                      if m.get("holder") == holder), "") or _lair(state)
        if good and lots > 0.0 and available >= lots:
            # The lot leaves the partner's books and enters the hoard: one
            # trade on each side, each in its own economy.
            partner_state["economy"], out_event, moved = trade(
                economy, seller=holder, buyer="tribute:%s" % own, good=good,
                quantity=lots, at_hours=at_hours, place=place,
                reason="tribute")
            if out_event is not None:
                partner_state["economy"]["stocks"].pop(
                    "tribute:%s" % own, None)
                events.setdefault(partner, []).append(dict(
                    out_event, buyer=own))
                hoard = state.setdefault("economy", {})
                goods = hoard.setdefault("goods", {})
                if good not in goods:
                    goods[good] = {"label": good, "base_value": 1.0,
                                   "unit": "lot"}
                held = hoard.setdefault("stocks", {}).setdefault(
                    _hoard(state), {})
                held[good] = round(float(held.get(good, 0.0)) + moved, 6)
                _fed(state, float((creature.get("fed") or {})
                                  .get("per_lot") or 0.0) * moved)
                events.setdefault(own, []).append({
                    "kind": "goods_exchanged",
                    "at_hours": round(float(at_hours), 6),
                    "place": _lair(state), "holder": _hoard(state),
                    "good": good, "amount": moved, "seller": partner,
                    "buyer": own, "reason": "tribute"})
                bargain["last_paid_hours"] = float(at_hours)
                continue
        if last is None:
            # Nothing was ever owed before the first due date.
            bargain["last_paid_hours"] = float(at_hours)
            continue
        record["state"] = "defaulted"
        record["lifecycle"].append({
            "kind": "defaulted", "at_hours": round(float(at_hours), 6),
            "evidence_id": source, "by": partner, "to": own,
            "note": "tribute not paid"})
        events.setdefault(partner, []).append({
            "kind": "commitment_defaulted",
            "at_hours": round(float(at_hours), 6), "place": place,
            "commitment_id": cid, "by": holder or partner,
            "actor": holder or partner, "subject": own})


def _lair(state):
    for body in (state.get("bodies") or {}).values():
        if body.get("berth"):
            return str(body["berth"])
    return ""


# ------------------------------------------------------------- stepper

class _Caches:
    """The per-charter run caches `charter_run.run` keeps for one
    institution, kept here per institution across an interleaved run."""

    def __init__(self, state, creature=None):
        from .charter_space import frequented_places, reach_map

        self.scene = state.get("scene")
        self.places = frequented_places(state) if self.scene else ()
        self.paths = {}
        self.reach = reach_map(self.scene, self.places, state["bodies"],
                               cache=self.paths) if self.scene else None
        self.neighbors = None
        if self.scene:
            if creature:
                self.neighbors = creature_neighbors(self.scene, creature)
            else:
                from .spatial import passable_neighbors
                self.neighbors = passable_neighbors(self.scene)
        self.routes = {}
        self.where = {k: b["place"] for k, b in state["bodies"].items()}

    def refresh(self, state):
        from .charter_space import refresh_reach

        if not self.scene:
            return
        now = {k: b["place"] for k, b in state["bodies"].items()}
        if now != self.where:
            moved = {k for k, place in now.items()
                     if self.where.get(k) != place}
            self.reach = refresh_reach(self.reach, self.scene, self.places,
                                       state["bodies"], moved,
                                       cache=self.paths)
            self.where = now


def run_registry(states, hours, *, window=4.0, seed=0, seeds=None,
                 simulate_bound=False):
    """Advance every institution together, one window at a time, with the
    predation round between windows. Returns ``(states, events)`` where
    ``events`` is ``{charter: [events]}``.

    ``seeds`` is ``{charter: seed}``; a charter not named draws from
    ``seed``. Each window advances every charter's seed by the window index
    exactly as `charter_run.run` does, so a registry of ONE ordinary charter
    is byte-identical to `run` on the same seed (`tests/test_charter_creature.py`
    pins it), and a caller advancing several hands each its own seed the way
    `charter_runtime.advance_snapshot` already did.
    """
    from .charter_run import step

    states = {str(k): normalize_charter(v) for k, v in (states or {}).items()}
    seeds = {str(k): int(v) for k, v in (seeds or {}).items()}
    caches = {k: _Caches(state, state.get("creature"))
              for k, state in states.items()}
    events = {k: [] for k in states}
    remaining = max(0.0, float(hours))
    window = max(1e-6, float(window))
    index = 0
    while remaining > 0.0:
        span = min(window, remaining)
        for key in sorted(states):
            state, cache = states[key], caches[key]
            cache.refresh(state)
            state, produced = step(
                state, hours=span, seed=seeds.get(key, int(seed)) + index,
                reach=cache.reach, paths=cache.paths,
                simulate_bound=simulate_bound, neighbors=cache.neighbors,
                routes=cache.routes)
            states[key] = state
            events[key].extend(produced)
        # Every charter counts its own hours; the round is stamped on each
        # institution's own clock as it stands after this window.
        clocks = {k: float(s.get("clock_hours") or 0.0)
                  for k, s in states.items()}
        round_events = {}
        for own in creature_keys(states):
            produced = predation_round(
                states, clocks[own], seed=int(seed) + index, hours=span)
            for k, rows in produced.items():
                round_events.setdefault(k, []).extend(rows)
            # `predation_round` runs every creature it is handed; one
            # call per registry is the whole round.
            break
        # CARRIED, NOT RETURNED. The institution returns a round's events
        # as its own produced events at the window that lives through them
        # (`charter_run.step` extends its list with `carried_events`), so
        # they are reported once, where they are witnessed, and a caller
        # that schedules them schedules each once.
        for key, rows in round_events.items():
            carried = list(states[key].get("carried_events") or ())
            states[key]["carried_events"] = carried + [
                copy.deepcopy(row) for row in rows]
        remaining -= span
        index += 1
    return states, events


__all__ = [
    "SENSE_RANGE_CAP", "creature_keys", "hunt_moves", "predation_round",
    "qualified", "read_spoor", "run_registry", "standing_spoor",
]
