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

#: HOW LONG A CREATURE KEEPS LOOKING AFTER THE TRAIL RUNS OUT.
#:
#: A scent hunter that loses the trail and simply stops is defeated for ever
#: by one shut door, which is the opposite of what the sense is for -- a
#: nose should be slower to notice and HARDER to shake than an ear.
#: Measured before this existed (`docs/UNBUILT.md` s1.141), a body walking a
#: five-room corridor and pulling the door shut behind them left the hunter
#: standing at a local maximum with no uphill step and nothing to do.
#:
#: The behaviour is the one the plume-tracking literature finds and that
#: trained agents rediscover on their own (`docs/guides/RESEARCH.md` s1.8):
#: SURGE while the odour is there, CAST across the neighbourhood when it is
#: not. This is the cast half, and this constant is its bound.
#:
#: Bounded because a creature that searches for ever is a creature that
#: never lets a story move on. Six beats: long enough that shutting one door
#: buys distance rather than safety, short enough that a body who has
#: actually broken the trail gets to leave.
CAST_BEATS = 6

#: The smallest holding that counts as stock to be taken: one whole lot.
STOCK_WHOLE_LOT = 1.0


def _pull(state):
    """What is DRAWING this creature, as `{room: rank}` -- every sense it
    has, on one scale, loudest/strongest wins where two name a room.

    `overheard` says where prey IS and is gone with the beat; `smelled` says
    where prey WAS and persists for as long as the trail does. A creature
    with one sense reads one; a creature with both reads both and the walk
    does not need to know which told it.
    """
    pull = dict(state.get("overheard") or {})
    for room, rank in (state.get("smelled") or {}).items():
        if rank > pull.get(room, 0):
            pull[room] = rank
    return pull


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


def _scene_figures_at(state, place):
    """The scene-owned people standing at `place`: the player and the cast,
    read off the charter's own copy of the scene.

    A FIGURE IS NOT A BODY (`charter_figure`): it is not rostered, holds no
    post and stands no watch, so it never appears in `_company`'s index --
    which is built from charter bodies alone. That is why the `figure` prey
    category, declared in `PREY_CATEGORIES` since it was written and
    documented as "a scene-owned person is the Director's to endanger", had
    no branch in the table below and matched nothing: a creature authored to
    hunt the cast could track them for ever and never register that it had
    arrived.

    Measured live, chat 117 turns 58-61: the carbonic stalker followed a CO2
    trail to the exact room the cast stood in (`smelled` read 4.0 there
    against 3.0 either side), and then stood in it emitting its `idle`
    voice, because `_prey_here` returned "" for a room holding two people it
    was written to hunt.

    An entity is not a person: `positions` carries lamps and doors beside
    bodies, and `entities` is what tells them apart -- the scene's own
    discriminator, the one every other reader uses.
    """
    scene = state.get("scene") if isinstance(state.get("scene"), dict) else {}
    positions = scene.get("positions") or {}
    entities = scene.get("entities") or {}
    if not isinstance(positions, dict) or not place:
        return []
    own_bodies = set((state.get("bodies") or {}).keys())
    out = []
    for name, room in sorted(positions.items()):
        if str(room or "") != str(place):
            continue
        key = str(name)
        if key in entities or key in own_bodies:
            continue
        out.append(key)
    return out


def _prey_here(place, own, bodies_at, stock_at, states, prey_order):
    """The first category of the prey table this place holds, and what."""
    for category in prey_order:
        if category == "figure":
            found = _scene_figures_at(states[own], place)
            if found:
                return category, [(own, key) for key in found]
        elif category == "stock":
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


def hunt_moves(states, own, bodies_at, stock_at, neighbors, seed, at_hours,
               noises=None):
    """``{body: place}`` for the creature bodies that noticed prey nearby
    and are not already going somewhere.

    TWO WAYS TO NOTICE, and the second is the one a player can provoke.

    The first is the SENSE range: rooms out on the creature's own graph, a
    standing awareness of what is near, which is what a thing knows about a
    place it lives in. The second is a NOISE -- something audible happened in
    a room this window, and the creature goes to look. That is the half a
    body can do something about, because a body makes noise by acting, and it
    is the whole of what makes a dark room tense: what you do is what brings
    it.

    IT NEVER PARSES WHAT IT HEARD. `noises` is `{room: rank}` -- where, and
    how strongly it pulls -- carried by the caller from the sound field,
    which is the same field a body hears through. No words, no speaker, no
    content: a creature learns that something happened over there, which is
    all a thing without language gets and all this needs.

    A heard room outranks a sensed one at the same distance, because a noise
    is evidence of something happening NOW and a sense range is only evidence
    of geography.

    AND A THIRD, FOR A NOSE ONLY: CASTING. A trail ends somewhere, and where
    it ends is not where the prey is -- it is where the prey stopped leaving
    one, by shutting a door or by simply being gone long enough. A creature
    that reads its own room as the strongest and then stops is defeated for
    ever by one door. So a scent hunter that loses the trail SEARCHES: it
    steps to the nearest room it has not already tried, and keeps widening
    for `CAST_BEATS` before giving up. Surge while you have it, cast when you
    do not -- the behaviour the plume literature finds in every animal that
    does this for a living (`docs/guides/RESEARCH.md` s1.8).

    A hearing creature does not cast, and the asymmetry is deliberate: a
    noise is over the moment it happens, so there is nothing to have lost.
    """
    from world.charter_creature import normalize_creature

    state = states[own]
    creature = state.get("creature") or {}
    senses = normalize_creature(creature).get("senses") or {}
    tracks_scent = bool(senses.get("scent"))
    limit = min(SENSE_RANGE_CAP, int(senses.get("range_rooms") or 0))
    casting = {str(k): dict(v) for k, v in (state.get("casting") or {}).items()
               if isinstance(v, dict)}
    moves = {}
    if limit <= 0:
        return moves
    prey_order = list(creature.get("prey") or ())
    for body_key, body in sorted((state.get("bodies") or {}).items()):
        if not body.get("available", True) or is_gone(body):
            continue
        # A HUNTER TURNS FOR PREY. IT DOES NOT TURN FOR GEOGRAPHY.
        #
        # A body mid-walk was skipped outright, which is right for every
        # other errand a charter runs -- re-planning a route every window
        # is how a body dithers in a doorway -- and wrong for the one
        # errand that is about something that MOVES. `_dispatch` already
        # holds the rule for this ("a body walking somewhere ELSE is
        # re-dispatched from where it stands ... the watch changed, and the
        # body turns"); prey appearing is that case exactly.
        #
        # Measured live, chat 117 turn 63. The carbonic stalker had given
        # up and turned for its berth while `figure` prey was still
        # unimplemented and the cast were invisible to it. The category was
        # implemented the same hour, the cast walked into the next room and
        # left a fresh trail -- `smelled` read 4.0 there, equal to the room
        # it stood in -- and it kept walking home, because it was already
        # going somewhere. A predator that strolls past its dinner because
        # it decided to go to bed earlier is not a predator.
        #
        # Scoped to the PREY half. A body mid-walk is still refused as a
        # casting candidate below: casting is SEARCHING, and re-opening a
        # search every window is the dithering the exclusion exists to
        # stop. What may interrupt a walk is evidence of something to eat.
        _walking = en_route(body)
        here = str(body.get("place") or "")
        if not here:
            continue
        category, _rows = _prey_here(here, own, bodies_at, stock_at, states,
                                     prey_order)
        if category:
            continue
        best = None
        reach = _reachable(neighbors, here, limit)
        for room, distance in reach.items():
            category, _rows = _prey_here(room, own, bodies_at, stock_at,
                                         states, prey_order)
            if not category:
                continue
            rank = prey_order.index(category)
            candidate = (0, rank, distance,
                         _draw(seed, at_hours, own, body_key, room), room)
            if best is None or candidate < best:
                best = candidate
        # A noise reaches as far as the SOUND did, which is the caller's
        # answer and not this graph's -- a shout through an open stairwell
        # carries further than a sense range, and a whisper behind a shut
        # door carries less. Ranked ahead of a sensed room, and only for a
        # room this body could actually walk to.
        # A ROOM IT HAS ALREADY PUT ITS HEAD INTO IS NOT NEWS. While a body
        # is casting, the rooms on its `tried` list are refused as surge
        # targets -- otherwise the room the trail DIED in is a local maximum
        # that pulls it straight back the beat after it leaves, and the
        # creature paces between two doorways for ever instead of searching.
        # The list is cleared the moment it surges to something new or gives
        # up, so a fresh trail laid in the same room is followed normally.
        _tried = set((casting.get(body_key) or {}).get("tried") or ())
        for room, rank in sorted((noises or {}).items()):
            if room == here or room not in reach or room in _tried:
                continue
            candidate = (-1, -float(rank), reach[room],
                         _draw(seed, at_hours, own, body_key, room), room)
            if best is None or candidate < best:
                best = candidate
        if best is not None:
            moves[body_key] = best[-1]
            casting.pop(body_key, None)   # surging: the trail is live again
            continue
        if _walking:
            continue                      # mid-walk: it casts for nothing
        # NOTHING TO WALK AT. Either the pull names this body's own room --
        # the trail ends where it stands -- or it has run out entirely. A
        # hearing creature has nothing to do about that, because a noise is
        # over; a NOSE has, because a trail that ends here was left by
        # something that went on somewhere.
        if not tracks_scent:
            continue
        cast = casting.get(body_key)
        if cast is None:
            if str(here) not in (noises or {}):
                continue                  # never had it; nothing to lose
            # SEEDED WITH WHERE IT IS STANDING. The trail died here and
            # this body has already searched it by being in it.
            cast = {"beats": 0, "tried": [str(here)]}
        if int(cast.get("beats") or 0) >= CAST_BEATS:
            casting.pop(body_key, None)   # given up; back to its own business
            continue
        tried = [str(r) for r in cast.get("tried") or ()]
        # WIDENING, which is what casting IS: the rooms it has already put
        # its head into are refused, so the search opens outward from where
        # the trail died rather than pacing between two doorways.
        options = sorted(
            room for room in reach
            if room != here and room not in tried)
        if not options:
            casting.pop(body_key, None)
            continue
        step = min(options,
                   key=lambda room: (reach[room],
                                     _draw(seed, at_hours, own, body_key,
                                           room), room))
        moves[body_key] = step
        casting[body_key] = {"beats": int(cast.get("beats") or 0) + 1,
                             "tried": tried + [step]}
    state["casting"] = casting
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

    if category == "figure":
        # A SCENE-OWNED PERSON IS THE DIRECTOR'S TO ENDANGER
        # (`charter_creature`'s own note on this category). The charter
        # simulates a world offscreen; the moment the thing it simulates is
        # standing in the room the story is being told in, what happens to
        # the people there is the pipeline's ruling and not a dice roll in
        # a background window. So nothing is harmed here and nothing is
        # taken: the encounter is FILED, and the Director -- which is
        # already shown this body's prey table, senses and hunger
        # (`common._creature_stance`) -- decides what a hunter does about
        # the meal standing in front of it.
        #
        # Filed even so, rather than skipped, because the alternative is
        # the silence this branch was written to end: for three beats a
        # creature stood in the room with its declared prey and the round
        # returned "" for the place, so nothing anywhere recorded that the
        # hunt had arrived (chat 117 turns 58-61).
        who = sorted(key for _own, key in rows)
        events.setdefault(own, []).append({
            "kind": "creature_on_figure",
            "place": place,
            "at_hours": at_hours,
            "by": body_keys[0],
            "figures": who,
            "hunger": round(float(hunger_of(state)), 3),
        })
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
                           at, noises=_pull(state))
        # WHAT IT IS DOING IS WHAT CAN BE HEARD. Recorded here, where the
        # round already knows it, and emitted at the runtime boundary --
        # this module is pure and owns no scene. The list is REPLACED every
        # round, like `engine_notices`: a noise is a thing that happened in
        # this window and never a standing fact.
        heard = []
        if moves:
            bodies, travelled, walked = walk(
                state["bodies"], moves, scene, state.get("travelled"),
                hours=hours, neighbors=neighbors or None,
                walked=state.get("walked"))
            state["bodies"], state["travelled"], state["walked"] = \
                bodies, travelled, walked
            bodies_at, stock_at = _company(states)
            for body_key, room in sorted(moves.items()):
                _noise(heard, creature, "moving", room, own)
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
            before = landed
            landed += _attack(states, own, body_keys, place, category, rows,
                              at, seed, events, spoor, index)
            if landed > before:
                _noise(heard, creature, "attacking", place, own)
                _noise(heard, creature, "feeding", place, own)
            index += 1
            bodies_at, stock_at = _company(states)
        if spoor:
            state["spoor"] = normalize_spoor(
                list(state.get("spoor") or ()) + spoor)
        # Standing where it stands, wanting nothing it can reach. Only a
        # creature authored with an `idle` voice makes any sound doing it.
        if (creature.get("voice") or {}).get("idle"):
            for _body_key, body in sorted((state.get("bodies") or {}).items()):
                if not body.get("available", True) or is_gone(body):
                    continue
                place = str(body.get("place") or "")
                if place and place not in moves.values():
                    _noise(heard, creature, "idle", place, own)
        state["heard"] = heard
    read_spoor(states, at)
    return events


def _noise(heard, creature, activity, place, own):
    """Record one thing a creature was heard doing, if it has a voice for it.

    An activity a creature was never given a rung for is SILENT, which is how
    a stealthy thing is written -- the same rule `light_source` holds, where
    prose about a glow lights nothing.
    """
    entry = (creature.get("voice") or {}).get(activity) or {}
    rung = str(entry.get("level") or "")
    if not rung or not place:
        return
    row = {"creature": own, "activity": activity, "place": str(place),
           "level": rung, "sound": str(entry.get("sound") or "")}
    if row not in heard:
        heard.append(row)


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
