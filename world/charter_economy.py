"""A bounded material economy for institutions, markets and caravans.

Quantities are abstract lots and prices are relative value units.  The model
does not count coins, loaves or individual meals; it records only holdings
whose movement can change a story.  Goods and holders are author vocabulary.
"""

from __future__ import annotations

from .charter_model import number as _number


STOCK_MAX = 1_000_000.0
FLOW_CAP = 64
MARKET_CAP = 32
TRADE_CAP = 32
SUPPLY_POINT_CAP = 32


def _amount(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = default
    return round(max(0.0, min(STOCK_MAX, value)), 6)


def _keyed(value, fields=("key", "id", "name")):
    """Read either an id-keyed object or a model's list of named objects."""
    if isinstance(value, dict):
        return list(value.items())
    rows = []
    for raw in value if isinstance(value, list) else ():
        if isinstance(raw, str) and raw.strip():
            rows.append((raw, {"label": raw}))
            continue
        if not isinstance(raw, dict):
            continue
        key = next((str(raw.get(field) or "").strip() for field in fields
                    if str(raw.get(field) or "").strip()), "")
        if key:
            rows.append((key, raw))
    return rows


def _holdings(value, *, target=False):
    """Normalize holder maps and flat [{holder, good, amount}] shorthand."""
    if isinstance(value, dict):
        return value
    out = {}
    for raw in value if isinstance(value, list) else ():
        if not isinstance(raw, dict):
            continue
        holder = str(raw.get("holder") or raw.get("owner") or "").strip()
        if not holder:
            continue
        nested = raw.get("goods") or raw.get("stock") or raw.get("targets")
        if isinstance(nested, dict):
            out.setdefault(holder, {}).update(nested)
            continue
        good = str(raw.get("good") or raw.get("item") or "").strip()
        if not good:
            continue
        if target:
            out.setdefault(holder, {})[good] = {
                key: raw[key] for key in ("minimum", "desired", "capacity")
                if key in raw}
        else:
            out.setdefault(holder, {})[good] = raw.get(
                "amount", raw.get("quantity", 0.0))
    return out


def normalize_economy(stored):
    stored = stored if isinstance(stored, dict) else {}
    goods = {}
    for key, raw in _keyed(
            stored.get("goods"), ("key", "id", "good", "name")):
        raw = raw if isinstance(raw, dict) else {}
        goods[str(key)] = {
            "label": str(raw.get("label") or key),
            "base_value": max(0.01, _amount(raw.get("base_value"), 1.0)),
            "unit": str(raw.get("unit") or "lot"),
        }
    stocks = {}
    for holder, held in _holdings(stored.get("stocks")).items():
        if not isinstance(held, dict):
            continue
        stocks[str(holder)] = {
            str(good): _amount(amount) for good, amount in held.items()
            if str(good) in goods and _amount(amount) > 0.0}
    targets = {}
    for holder, held in _holdings(
            stored.get("targets"), target=True).items():
        if not isinstance(held, dict):
            continue
        targets[str(holder)] = {}
        for good, raw in held.items():
            if str(good) not in goods:
                continue
            raw = raw if isinstance(raw, dict) else {}
            minimum = _amount(raw.get("minimum"), 0.0)
            desired = max(minimum, _amount(raw.get("desired"), minimum))
            capacity = max(desired, _amount(raw.get("capacity"), desired))
            targets[str(holder)][str(good)] = {
                "minimum": minimum, "desired": desired,
                "capacity": capacity}
    flows = {}
    for key, raw in _keyed(
            stored.get("flows"), ("key", "id", "name"))[:FLOW_CAP]:
        if not isinstance(raw, dict):
            continue
        holder, good = str(raw.get("holder") or ""), str(raw.get("good") or "")
        kind = str(raw.get("kind") or "consume")
        if not holder or good not in goods or kind not in ("produce", "consume"):
            continue
        flows[str(key)] = {
            "holder": holder, "good": good, "kind": kind,
            "lots_per_hour": _amount(raw.get("lots_per_hour")),
            "requires_upkeep": str(raw.get("requires_upkeep") or ""),
        }
    markets = {}
    for key, raw in _keyed(
            stored.get("markets"), ("key", "id", "name", "place"))[:MARKET_CAP]:
        if not isinstance(raw, dict):
            continue
        holder = str(raw.get("holder") or key)
        place = str(raw.get("place") or "")
        if not place:
            continue
        markets[str(key)] = {
            "place": place, "holder": holder,
            "margin": max(0.0, min(2.0, _number(raw.get("margin"), 0.15))),
            "route_burden": max(0.0, min(
                4.0, _number(raw.get("route_burden"), 0.0))),
            "currency": str(raw.get("currency") or
                            stored.get("currency") or "value"),
        }
    supply_points = {}
    for key, raw in _keyed(
            stored.get("supply_points"),
            ("key", "id", "name", "place"))[:SUPPLY_POINT_CAP]:
        if not isinstance(raw, dict):
            continue
        holder = str(raw.get("holder") or "").strip()
        place = str(raw.get("place") or "").strip()
        supplied = raw.get("goods") if isinstance(raw.get("goods"), dict) else {}
        supplied = {str(good): _amount(rate) for good, rate in supplied.items()
                    if str(good) in goods and _amount(rate) > 0.0}
        if not holder or not place or not supplied:
            continue
        supply_points[str(key)] = {
            "place": place, "holder": holder, "goods": supplied,
            "reliability": max(0.0, min(
                1.0, _number(raw.get("reliability"), 1.0))),
            "route_burden": max(0.0, min(
                4.0, _number(raw.get("route_burden"), 0.25))),
            "mode": str(raw.get("mode") or "external route"),
        }
    raw_bands = stored.get("bands")
    bands = {str(k): str(v) for k, v in
             (raw_bands.items() if isinstance(raw_bands, dict) else ())}
    trades = [dict(t) for t in (stored.get("recent_trades") or ())
              if isinstance(t, dict)][-TRADE_CAP:]
    return {"goods": goods, "stocks": stocks, "targets": targets,
            "flows": flows, "markets": markets,
            "supply_points": supply_points, "bands": bands,
            "recent_trades": trades,
            "currency": str(stored.get("currency") or "value")}


def ensure_supply_points(economy, rooms=None):
    """Add explicit boundary supply for net-consumed goods.

    This is a temporary compression of an upstream chain, not local creation:
    the point names where deliveries cross into the simulated location, their
    route burden and reliability. Once caravans/routes exist they can replace
    the point without changing local holders, stocks, targets, or prices.
    """
    out = normalize_economy(economy)
    rooms = rooms if isinstance(rooms, dict) else {}
    produced, consumed = {}, {}
    for flow in out["flows"].values():
        bucket = produced if flow["kind"] == "produce" else consumed
        bucket[flow["good"]] = bucket.get(flow["good"], 0.0) \
            + float(flow["lots_per_hour"])
    already = {
        good for point in out["supply_points"].values()
        for good in point["goods"]}
    boundary_tokens = (
        "gate", "entrance", "dock", "loading", "port", "checkpoint",
        "station", "depot", "surface")
    boundary = next((uid for uid, room in rooms.items()
                     if any(token in (str(uid) + " " + str(
                         (room or {}).get("name") or "") + " " + str(
                         (room or {}).get("purpose") or "")).casefold()
                            for token in boundary_tokens)), "")
    boundary = boundary or next(iter(rooms), "boundary")
    for good in sorted(out["goods"]):
        deficit = consumed.get(good, 0.0) - produced.get(good, 0.0)
        if deficit <= 0.0 or good in already:
            continue
        holder = next((holder for holder, held in out["targets"].items()
                       if good in held), "")
        holder = holder or next((holder for holder, held in out["stocks"].items()
                                 if good in held), "")
        holder = holder or "stores"
        key = "external_" + "_".join(str(good).casefold().split())
        suffix, base = 2, key
        while key in out["supply_points"]:
            key = f"{base}_{suffix}"
            suffix += 1
        out["supply_points"][key] = {
            "place": boundary, "holder": holder,
            "goods": {good: round(deficit, 6)},
            "reliability": 0.95, "route_burden": 0.25,
            "mode": "abstract external supply",
        }
    return normalize_economy(out)


def stock_band(economy, holder, good):
    economy = normalize_economy(economy)
    amount = float((economy["stocks"].get(str(holder)) or {}).get(str(good), 0.0))
    target = (economy["targets"].get(str(holder)) or {}).get(str(good)) or {}
    minimum = float(target.get("minimum") or 0.0)
    desired = float(target.get("desired") or minimum)
    capacity = float(target.get("capacity") or desired)
    if amount <= 0.0:
        return "empty"
    if minimum and amount < minimum:
        return "low"
    if capacity and amount >= capacity:
        return "surplus"
    if desired and amount >= desired:
        return "healthy"
    return "adequate"


def quote(economy, market, good, *, quantity=1.0,
          relationship_adjustment=0.0):
    """Route/scarcity-sensitive price in author-labelled value units."""
    economy = normalize_economy(economy)
    market = economy["markets"].get(str(market)) or {}
    holder = market.get("holder") or str(market)
    spec = economy["goods"].get(str(good))
    if spec is None:
        return None
    amount = float((economy["stocks"].get(holder) or {}).get(str(good), 0.0))
    target = (economy["targets"].get(holder) or {}).get(str(good)) or {}
    desired = max(1.0, float(target.get("desired") or 1.0))
    scarcity = max(0.65, min(4.0, desired / max(0.25, amount)))
    route = 1.0 + float(market.get("route_burden") or 0.0)
    margin = 1.0 + float(market.get("margin") or 0.0)
    relation = max(0.65, min(
        1.5, 1.0 + _number(relationship_adjustment)))
    unit = float(spec["base_value"]) * scarcity * route * margin * relation
    return {
        "market": str(market.get("place") or market), "holder": holder,
        "good": str(good), "quantity": _amount(quantity, 1.0),
        "unit_value": round(unit, 3),
        "total_value": round(unit * _amount(quantity), 3),
        "currency": str(market.get("currency") or economy["currency"]),
        "scarcity": round(scarcity, 3),
        "route_burden": round(float(market.get("route_burden") or 0.0), 3),
    }


def _event(kind, at_hours, holder, good, amount, **extra):
    return {"kind": kind, "at_hours": round(float(at_hours), 6),
            "place": str(extra.pop("place", "")), "holder": str(holder),
            "good": str(good), "amount": round(float(amount), 6), **extra}


def advance_economy(economy, hours, *, upkeeps=None, at_hours=0.0):
    """Advance aggregate production/consumption and emit threshold changes."""
    before = normalize_economy(economy)
    out = normalize_economy(economy)
    hours = max(0.0, _number(hours))
    old_bands = {}
    for holder, held in out["targets"].items():
        for good in held:
            old_bands[(holder, good)] = stock_band(before, holder, good)
    deltas = {}
    for point in out["supply_points"].values():
        reliability = float(point.get("reliability") or 0.0)
        for good, rate in point["goods"].items():
            key = (point["holder"], good)
            deltas[key] = deltas.get(key, 0.0) \
                + float(rate) * hours * reliability
    for flow in out["flows"].values():
        required = flow.get("requires_upkeep")
        factor = 1.0
        if required:
            factor = max(0.0, min(1.0, float(
                ((upkeeps or {}).get(required) or {}).get("level", 0.0))))
        sign = 1.0 if flow["kind"] == "produce" else -1.0
        key = (flow["holder"], flow["good"])
        deltas[key] = deltas.get(key, 0.0) + sign * flow["lots_per_hour"] \
            * hours * factor
    for (holder, good), delta in deltas.items():
        held = out["stocks"].setdefault(holder, {})
        target = (out["targets"].get(holder) or {}).get(good) or {}
        capacity = float(target.get("capacity") or STOCK_MAX)
        held[good] = round(max(0.0, min(
            capacity, float(held.get(good, 0.0)) + delta)), 6)
    events = []
    for (holder, good), old in old_bands.items():
        new = stock_band(out, holder, good)
        key = f"{holder}:{good}"
        if new != old:
            out["bands"][key] = new
            kind = {"empty": "stock_empty", "low": "stock_low",
                    "surplus": "stock_surplus"}.get(new, "stock_restored")
            place = next((m["place"] for m in out["markets"].values()
                          if m["holder"] == holder), "")
            events.append(_event(
                kind, at_hours + hours, holder, good,
                (out["stocks"].get(holder) or {}).get(good, 0.0),
                previous_band=old, band=new, place=place))
    return normalize_economy(out), events


def trade(economy, *, seller, buyer, good, quantity, at_hours=0.0,
          place="", price=None, reason="exchange"):
    """Transfer abstract lots.  Returns state, event, and actual quantity."""
    out = normalize_economy(economy)
    seller, buyer, good = str(seller), str(buyer), str(good)
    if good not in out["goods"] or not seller or not buyer or seller == buyer:
        return out, None, 0.0
    available = float((out["stocks"].get(seller) or {}).get(good, 0.0))
    wanted = _amount(quantity)
    target = (out["targets"].get(buyer) or {}).get(good) or {}
    room = max(0.0, float(target.get("capacity") or STOCK_MAX)
               - float((out["stocks"].get(buyer) or {}).get(good, 0.0)))
    moved = round(min(available, wanted, room), 6)
    if moved <= 0.0:
        return out, None, 0.0
    out["stocks"].setdefault(seller, {})[good] = round(available - moved, 6)
    out["stocks"].setdefault(buyer, {})[good] = round(
        float((out["stocks"].get(buyer) or {}).get(good, 0.0)) + moved, 6)
    event = _event("goods_exchanged", at_hours, seller, good, moved,
                   place=place, seller=seller, buyer=buyer,
                   total_value=(price or {}).get("total_value"), reason=reason)
    out["recent_trades"] = (out["recent_trades"] + [event])[-TRADE_CAP:]
    return normalize_economy(out), event, moved


def take_stock(economy, *, holder, good, amount, at_hours=0.0, place="",
               by=""):
    """Lots leaving a holder's books without a buyer: taken, spoiled, lost.

    The one movement `trade` cannot express, because a trade has two
    parties on ONE set of books and this has one party on these books and
    another somewhere else entirely (`charter_predation`). Returns
    ``(economy, event)``; the event is ``stock_taken`` at the place, which
    a bystander perceives as plainly as goods changing hands, and the band
    change it causes is reported by `advance_economy` on the next window
    like any other. ``None`` for nothing to take.
    """
    out = normalize_economy(economy)
    holder, good = str(holder), str(good)
    if good not in out["goods"] or not holder:
        return out, None
    available = float((out["stocks"].get(holder) or {}).get(good, 0.0))
    moved = round(min(available, _amount(amount)), 6)
    if moved <= 0.0:
        return out, None
    out["stocks"].setdefault(holder, {})[good] = round(available - moved, 6)
    event = _event("stock_taken", at_hours, holder, good, moved, place=place,
                   by=str(by or ""), actor=str(by or ""))
    return normalize_economy(out), event


def caravan_exchange(economy, freight, room, *, at_hours=0.0):
    """Trade a caravan's freight with every authored market at one stop."""
    out = normalize_economy(economy)
    freight = freight if isinstance(freight, dict) else {}
    stock = {str(k): _amount(v) for k, v in
             (freight.get("stock") or {}).items() if _amount(v) > 0.0}
    wants = {str(k): _amount(v) for k, v in
             (freight.get("wants") or {}).items() if _amount(v) > 0.0}
    wagon = "caravan"
    out["stocks"][wagon] = stock
    out["targets"].setdefault(wagon, {})
    for good, desired in wants.items():
        out["targets"][wagon][good] = {
            "minimum": 0.0, "desired": desired, "capacity": desired}
    events = []
    for market_key, market in sorted(out["markets"].items()):
        if market["place"] != str(room):
            continue
        holder = market["holder"]
        # Sell into shortages first.
        for good, amount in list((out["stocks"].get(wagon) or {}).items()):
            target = (out["targets"].get(holder) or {}).get(good) or {}
            desired = float(target.get("desired") or 0.0)
            current = float((out["stocks"].get(holder) or {}).get(good, 0.0))
            price = quote(out, market_key, good, quantity=min(amount, max(
                0.0, desired - current)))
            out, event, _ = trade(
                out, seller=wagon, buyer=holder, good=good,
                quantity=max(0.0, desired - current), at_hours=at_hours,
                place=room, price=price, reason="caravan_sale")
            if event:
                events.append(event)
        # Buy what this caravan was configured to seek.
        for good, desired in wants.items():
            current = float((out["stocks"].get(wagon) or {}).get(good, 0.0))
            price = quote(out, market_key, good,
                          quantity=max(0.0, desired - current))
            out, event, _ = trade(
                out, seller=holder, buyer=wagon, good=good,
                quantity=max(0.0, desired - current), at_hours=at_hours,
                place=room, price=price, reason="caravan_purchase")
            if event:
                events.append(event)
    freight = dict(freight)
    freight["stock"] = dict(out["stocks"].pop(wagon, {}))
    out["targets"].pop(wagon, None)
    return normalize_economy(out), freight, events


__all__ = [
    "advance_economy", "caravan_exchange", "normalize_economy", "quote",
    "stock_band", "take_stock", "trade",
]
