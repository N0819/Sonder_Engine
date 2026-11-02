"""Far sight: vistas on the horizon, far places and far looks, laid out as
lines (`landscape_lines`) and realised in any pack's words
(`compose_landscape_line`).

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from agents.composer_common import (
    Percept,
    _ENGLISH_COMPOSITOR,
    _cap,
    _en,
    _noun_phrase,
    _short_hash,
    standing_key,
)


def vista_percepts(seen, looked=()):
    """What stands on the horizon, to a body that can see it
    (`world.vistas.visible_vistas`): one line each, by compass bearing, in
    the pack's own words -- a skyline under a moon as a silhouette. A
    distant thing is seen and may be spoken of; nothing here makes it a
    thing a hand reaches (`world/vistas.py`).

    `looked` is `[(vista, clarity | "unseen")]` for the vistas this body's
    own act LOOKED AT this beat: what the look found is the beat's, so it is
    an EVENT, ordered first -- right after the body's own words -- never
    standing background the player tier's delta may suppress, and a look
    that finds nothing (fog, the dark, a ridge) says so. Live, Larch Hill
    (2026-10-04): Ren went to the north windows and looked at the range,
    the range sat in present_scene, and the page never said what she saw."""
    from language_runtime import compositor_text
    from world.spatial import _phrase_table
    compass = _phrase_table("compass_words")
    looked = list(looked or ())
    looked_ids = {v["id"] for v, _how in looked}
    out = []

    def line(vista, clarity, nearer=""):
        where = compass.get(vista["bearing"], vista["bearing"])
        if str(clarity).startswith("unseen"):
            # WHAT THE EYE MEETS INSTEAD, never a placeholder (owner,
            # 2026-10-07): the walls, the weather closing in, the dark, the
            # curve of the earth, nearer ground standing higher.
            why, _sep, air = str(clarity).partition(":")
            why = why[len("unseen_"):] if why.startswith("unseen_") else "nearer"
            return compositor_text("vista_unseen_" + why, compass=where,
                                   name=vista["name"], air=air_phrase(air))
        # Past a nearer one on the same bearing, a vista is "beyond" it, named
        # in the line itself -- a standing line is said alone on a later
        # beat, so it cannot lean on the line before it
        # (`_beside_on_one_bearing`).
        more = "_beyond" if nearer else ""
        if clarity == "silhouette":
            return compositor_text("vista_silhouette" + more, compass=where,
                                   name=vista["name"], nearer=nearer)
        if clarity == "lights":
            return compositor_text("vista_lit_night" + more, compass=where,
                                   name=vista["name"], nearer=nearer)
        desc = compositor_text("vista_desc_join", desc=vista["desc"]) if vista["desc"] else ""
        return compositor_text("vista_seen" + more, compass=where, name=vista["name"],
                               desc=desc, nearer=nearer)

    for vista, clarity in looked:
        # A LOOK IS THE VIEW'S NEWS, AND IT FILES WHAT IT SAW: the standing
        # line the look stands in for goes into the ledger with it, or the
        # next beat announced the same range again as if first seen
        # (`files_standing`, read by every pack's view as a voice key is).
        data = {"desc": line(vista, clarity)}
        if not str(clarity).startswith("unseen"):
            data["files_standing"] = standing_key("vista", (vista["id"],), (clarity,))
        out.append(Percept(
            kind="ambient", channel="sight", source_label=vista["name"],
            data=data, order_key=-1, salience=0.6,
            dedupe_key=standing_key("vista_look", (vista["id"],), (clarity,))))
    previous = None
    for vista, clarity in _beside_on_one_bearing(
            [(v, c) for v, c in (seen or ()) if v["id"] not in looked_ids]):
        nearer = ""
        if previous is not None and previous[0]["bearing"] == vista["bearing"] \
                and not str(previous[1]).startswith("unseen") \
                and not str(clarity).startswith("unseen") \
                and previous[0].get("distance_given") and vista.get("distance_given") \
                and float(previous[0]["distance_km"]) < float(vista["distance_km"]):
            nearer = previous[0]["name"]
        previous = (vista, clarity)
        # Under the room's own salience, as far places are: the horizon is
        # never a memory's gist over where the body stood.
        out.append(Percept(
            kind="ambient", channel="sight", source_label=vista["name"],
            data={"desc": line(vista, clarity, nearer)}, salience=0.15,
            dedupe_key=standing_key("vista", (vista["id"],), (clarity,))))
    return out


def _beside_on_one_bearing(seen):
    """`seen` with the vistas on one bearing side by side, nearest first, the
    bearings in the order they first appear. Three standing lines in a row
    each opened "To the south," (Kirinoura, scratch chat 167, 2026-10-05):
    the river, the fields across it, the hills that close the valley."""
    order = []
    for vista, _clarity in seen:
        if vista["bearing"] not in order:
            order.append(vista["bearing"])
    return sorted(seen, key=lambda vc: (order.index(vc[0]["bearing"]),
                                        float(vc[0].get("distance_km") or 0.0)))


#: FAR SIGHT: the standing lines about what is seen past the near field --
#: the horizon (`vista_percepts`) and the far places on the way to it
#: (`landscape_percepts`). Two rules read them by this tag and nothing else:
#: they are ADDED to a view and are never the whole of one (the roll-call
#: rule below and `perception`'s empty-view floor decide on the near spans,
#: so a first sighting never stands in for the room the narrator is handed),
#: and they are what English memory files of a view's far half
#: (`_files_as_memory`).
FAR_SIGHT_TAGS = frozenset(("vista", "landscape"))


def far_sight(percept):
    """Is this a standing line of far sight -- a vista or a far place?"""
    if percept.kind != "ambient" or percept.order_key is not None:
        return False
    return str(percept.dedupe_key or "").split(":", 1)[0] in FAR_SIGHT_TAGS


def near_text(rendered):
    """A rendered view's text without its far-sight spans -- what the
    roll-call rule and the empty-view floor ask about."""
    return " ".join(sentence for p, sentence in (rendered.spans or ())
                    if not far_sight(p)).strip()


def is_landscape(percept):
    return (percept.kind == "ambient"
            and isinstance((percept.data or {}).get("landscape"), dict))


#: What a far place's percept may carry and nothing more, so a field added
#: upstream cannot ride into a view (`DISTANT_SOUND_LEVELS`' precedent).
#: Room ids ride only inside hashes; a name only when the mind knows it.
LANDSCAPE_GROUNDS = ("open", "sheltered", "building")
LANDSCAPE_HEIGHTS = ("one", "two", "tall")
LANDSCAPE_GRAINS = ("mid", "outline")
LANDSCAPE_COVERS = ("building", "ground")


def air_phrase(word):
    """The pack's word for what the air holds (`vistas.VISIBILITY_KM`'s
    words: fog, mist, rain...), as it closes a view."""
    from world.spatial import _phrase_table
    table = _phrase_table("air_words")
    return str(table.get(str(word or ""), table.get("fog", word or "")))


def _far_line_text(line):
    """One far line in the ACTIVE pack's words: English's own renderer, or
    the pack's templates through the layout every pack shares."""
    from language_runtime import compositor_text, current_language_id
    from world.spatial import _phrase_table
    if str(current_language_id.get() or "en").startswith("en"):
        return render_landscape_line(line)
    return str(compose_landscape_line(
        line, compositor_text, compass_words=_phrase_table("compass_words")))


def landscape_look_percepts(findings):
    """What this body's own act LOOKED AT far off this beat
    (`world.landscape.looked_far`): an EVENT each, ordered first -- right
    after the body's own words, as a look at the horizon is
    (`vista_percepts`) -- never standing background a view's delta may
    suppress.

    A place seen is its own far line, named by the name the look used when
    the mind knows no other ("a two-storey building where the bell loft
    is"). A place hidden is what stands in the way: the roofs or the ground
    nearer in, the weather closing in, the dark, the walls or buildings
    round the looker. NEVER A PLACEHOLDER (owner, 2026-10-07: "nothing can
    be made out and similar place holders are quite frustrating"). Live
    case: scratch story 166 turn 4589, a look up at the bell loft from the
    low walk reached no view at all."""
    from language_runtime import compositor_text
    out = []
    for found in findings or ():
        if not isinstance(found, dict) or not found.get("room"):
            continue
        label = str(found.get("label") or "")
        place = found.get("place")
        if isinstance(place, dict):
            shown = dict(place, order=0)
            if label and not shown.get("name"):
                shown["name"] = label
            standing = landscape_percepts([shown])
            lines = landscape_lines(standing)
            if not lines:
                continue
            desc = _cap(_far_line_text(lines[0][1]))
            kind = "seen:" + str(place.get("shows") or "whole")
            data = {"desc": desc, "files_standing": standing[0].dedupe_key}
        else:
            cover = found.get("hidden_by") if isinstance(found.get("hidden_by"), dict) else {}
            kind = str(cover.get("kind") or "around")
            if kind not in ("building", "ground", "air", "dark", "walls", "around"):
                kind = "around"
            named = "_named" if kind in ("building", "ground") and cover.get("name") else ""
            desc = _cap(compositor_text("far_look_hidden_" + kind + named, label=label,
                                        cover=str(cover.get("name") or ""),
                                        air=air_phrase(cover.get("air"))))
            data = {"desc": desc}
        out.append(Percept(
            kind="ambient", channel="sight", source_label=label, data=data,
            order_key=-1, salience=0.6,
            dedupe_key=standing_key("far_look", (found["room"],), (kind,))))
    return out


def landscape_percepts(places):
    """The far places a body sees (`world.landscape.far_places`), one
    standing sight percept per PLACE.

    Keyed by the place and what is seen of it -- never by the way the eye
    reached it, its compass or the name -- so walking along a path does not
    re-announce, or re-file in memory, a place already seen, and learning a
    place's name is not news about it (the scent precedent). Salience under
    the room's own, so a far line never takes a memory's gist from where the
    body stood. Grouped back into lines by `landscape_lines`.

    A place's FAR LOOK (`world.landscape`: the planner's own field, admitted
    to this mind or "") rides as `look`, and joins the key only where there
    is one: a look rewritten -- the reeds burned, the quay flooded -- is
    news about the place, and a place that declares none keeps the key it
    always had."""
    from world.landscape import BIG_PER_PLACE, normalize_far_look
    out = []
    for place in places or ():
        if not isinstance(place, dict) or not place.get("room"):
            continue
        ground = place.get("ground")
        grain = place.get("grain")
        if ground not in LANDSCAPE_GROUNDS or grain not in LANDSCAPE_GRAINS:
            continue
        lead = place.get("lead") if isinstance(place.get("lead"), dict) else {}
        subject = place.get("key_room") or place["room"]
        data = {
            "line": _short_hash("landscape-line", place.get("line")),
            "order": int(place.get("order") or 0),
            "id": _short_hash("landscape-place", subject),
            "front": (_short_hash("landscape-place", place["front"])
                      if place.get("front") else ""),
            "lead": {"compass": str(lead.get("compass") or ""),
                     "via": str(lead.get("via") or ""),
                     "rise": str(lead.get("rise") or ""),
                     "via_id": (_short_hash("landscape-place", lead["via_room"])
                                if lead.get("via_room") else "")},
            "ground": ground,
            "breadth": "wide" if place.get("breadth") == "wide" else "",
            "name": str(place.get("name") or ""),
            "height": (place.get("height") if place.get("height") in LANDSCAPE_HEIGHTS
                       else ""),
            "lights": int(place.get("lights") or 0),
            "high": bool(place.get("high")),
            "dark": bool(place.get("dark")),
            "big": [str(t) for t in (place.get("big") or ()) if str(t).strip()][:BIG_PER_PLACE],
            "tier": "outline" if place.get("tier") == "outline" else "mid",
            "grain": grain,
            # Only its top shows, over the roofs or the ground nearer in.
            "over": (place.get("over") if place.get("shows") == "top"
                     and place.get("over") in LANDSCAPE_COVERS else ""),
            "look": normalize_far_look(place.get("look")),
        }
        signature = (data["grain"], data["ground"], data["breadth"], data["height"],
                     data["lights"], data["high"], data["dark"], len(data["big"]),
                     data["over"])
        if data["look"]:
            signature += (_short_hash("landscape-look", data["look"]),)
        out.append(Percept(
            kind="ambient", channel="sight", source_label=data["name"],
            data={"landscape": data}, salience=0.15,
            dedupe_key=standing_key("landscape", (subject,), signature)))
    return out


def _plain_ground(row):
    """What a row of bare ground IS, for the run that folds a line of it
    into one item: its kind and breadth, as it always was, so a far look
    never costs a mind a place the run said (`landscape.LOOKS_SPLIT_RUNS`,
    the owner's switch, off). With the switch on, a place's far look is part
    of what it is, and only places that read alike fold."""
    from world.landscape import LOOKS_SPLIT_RUNS
    g = row.get("ground")
    if (g is None or row.get("buildings") or g.get("name") or g.get("big")
            or g.get("lights") or g.get("dark")):
        return None
    if LOOKS_SPLIT_RUNS and g.get("look"):
        return ("look", g["look"])
    return ("plain", g.get("ground"), g.get("breadth"))


def landscape_lines(percepts):
    """[(representative percept, line)] -- the far places of one view laid
    out as lines, for EVERY language pack (`player_view_order`'s
    precedent): one line per way out, nearest first; ground in order along
    it, each with the buildings fronting it; the buildings fronting the way
    out itself said beside it; a run of plain unnamed ground of one kind said
    once ("stretching on"), by its nearest and farthest far looks where they
    have them (`_plain_ground`); at most `SEGMENTS_PER_LINE` rows, the
    nearest two and the farthest. The representative is the line's first
    place, the one an observation is filed against."""
    from world.landscape import SEGMENTS_PER_LINE
    groups, order = {}, []
    for p in percepts or ():
        data = (p.data or {}).get("landscape") if is_landscape(p) else None
        if not isinstance(data, dict):
            continue
        key = data.get("line")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((p, data))
    out = []
    for key in order:
        members = sorted(groups[key], key=lambda pd: pd[1].get("order", 0))
        percept_of = {id(d): p for p, d in members}
        rep, first = members[0]
        lead = first.get("lead") or {}
        grounds = [d for _p, d in members if d.get("ground") != "building"]
        buildings = [d for _p, d in members if d.get("ground") == "building"]
        ground_ids = {d.get("id") for d in grounds}
        beside = [b for b in buildings
                  if lead.get("via_id") and b.get("front") == lead.get("via_id")]
        rows = [{"ground": g, "buildings": [b for b in buildings
                                            if b.get("front") == g.get("id")],
                 "tier": g.get("tier"), "order": g.get("order", 0)} for g in grounds]
        rows += [{"ground": None, "buildings": [b], "tier": b.get("tier"),
                  "order": b.get("order", 0)} for b in buildings
                 if b not in beside and b.get("front") not in ground_ids]
        rows.sort(key=lambda r: r["order"])
        merged = []
        for row in rows:
            plain = _plain_ground(row)
            if plain and merged and merged[-1]["plain"] == plain:
                merged[-1]["run"] = True
                merged[-1]["also"].append(row["ground"])
                continue
            merged.append({**row, "plain": plain, "run": False, "also": []})
        if len(merged) > SEGMENTS_PER_LINE:
            merged = merged[:SEGMENTS_PER_LINE - 1] + merged[-1:]
        # WHAT THE LINE SAYS: every place it shows -- a run's places are said
        # as the run -- and the names among them, so memory files what the
        # view delivered and indexes what the line names (review 2026-10-05:
        # an episode re-laid from the changed places alone filed a place the
        # view had trimmed away).
        said = list(beside)
        for row in merged:
            said += ([row["ground"]] if row.get("ground") else []) + row["also"]
            said += row.get("buildings") or []
        out.append((rep, {
            "lead": lead, "beside": beside, "rows": merged,
            "shown": [percept_of[id(d)] for d in said if id(d) in percept_of],
            "names": [d["name"] for d in said if d.get("name")]}))
    return out


def compose_landscape_line(line, text, *, episode=False, thing=None,
                           compass_words=None):
    """One far line in a language's own words: `text(key, **values)` is the
    pack's template reader, `thing` how an authored desc is spliced into a
    list (English's `_noun_phrase`), `compass_words` the pack's compass. The
    layout is `landscape_lines`'; nothing here decides what is shown."""
    thing = thing or (lambda s: str(s).strip().rstrip(".。"))
    compass_words = compass_words or {}
    joiner = str(text("landscape_and"))
    sep = str(text("landscape_items"))
    # Every kind of building this line has said so far, in the words it said
    # it -- a look's phrase, a named or notable building's, and the plain
    # ones counted -- so a row whose buildings read as the ONE kind said
    # before is said as more of them (`building_parts`).
    said_kinds = set()

    def count_bucket(n):
        """The count words' bucket, as plain buildings are counted."""
        return "1" if n == 1 else "2" if n == 2 else "few" if n <= 5 else "many"

    def lights_word(d):
        if not d.get("lights"):
            return ""
        if d.get("high") and d["lights"] == 1:
            return text("landscape_light_high")
        return text("landscape_light_n") if d["lights"] > 1 else text("landscape_light_1")

    def building(d):
        whole = _building_whole(d)
        if whole and d.get("over"):
            # ONLY ITS TOP SHOWS, over what stands nearer -- the roofs or the
            # rise of the ground (`landscape._seen_part`).
            return text("landscape_top_over_" + d["over"], place=whole)
        return whole

    def _building_whole(d):
        lights = lights_word(d)
        # ITS FAR LOOK, where the planner wrote one, in place of the words
        # that say only that a building stands there (`world.landscape`) --
        # never when its mass is dark: then only its lights show, and a mind
        # that knows the place by name is told where they are, not what it
        # is built of (review 2026-10-08, F5).
        look = thing(d["look"]) if d.get("look") and not d.get("dark") else ""
        base = look or text("landscape_building_" + (d.get("height") or "one"))
        if d.get("name"):
            base = text("landscape_building_named", building=base, name=d["name"])
            # The light at the named building, never trailing its name: "a
            # building where The Mill is with a light" said the mill was.
            if lights:
                return text("landscape_lit_known", lights=lights, place=base)
            return base if not d.get("dark") else ""
        if d.get("dark"):
            return lights
        if lights and d.get("look"):
            # A look carries its own phrase ("hung with coils of rope"), so
            # what stands with it is set apart from it (`landscape_with_look`).
            return text("landscape_with_look", place=base, things=lights)
        return text("landscape_with_lights", place=base, lights=lights) if lights else base

    def building_parts(bs):
        """``(again, parts)``: a row's buildings as phrases. `again` is the
        back-reference, when there is one, which the caller says FIRST.

        A building with a look of its own, its mass in view, is said by it
        and never counted -- and buildings that read the same (the look,
        and whatever light or top shows with it) are said once with their
        count, so a row of alike houses is one phrase, never the same
        phrase over and over (review 2026-10-08, F6: four alike houses ran
        a line to 1,270 characters). With the owner's cap, the nearest that
        many phrases of a row are said and the rest of its buildings are
        said as if they had no look -- by their height, their lights and
        their top (review R2-8: counted as plain, a lit one lost its light).
        A building with no look is said or counted exactly as it was.

        MORE OF THEM, ONLY WHERE NOTHING ELSE CAN BE WHAT THEY ARE MORE OF
        (review R2-1). A row whose buildings read as the one kind of
        building this line has said so far is said as more of them, with
        their count ("two more such buildings"), and before anything else
        on the row: said after a new phrase it read as more of THAT -- "a
        tall brick warehouse with a hoist and more of the same" told the
        mind of warehouses that were tarred houses, in both packs. Where the
        line has said other kinds as well, the phrase is said again whole,
        since a back-reference would leave the mind to guess which kind."""
        from world.landscape import DESCRIBED_BUILDINGS_PER_ROW
        named = [b for b in bs if b.get("name")]
        looked = [b for b in bs if not b.get("name") and b.get("look") and not b.get("dark")]
        alike = {}
        for b in looked:
            alike.setdefault(str(building(b)), []).append(b)
        phrases = list(alike)
        cap = DESCRIBED_BUILDINGS_PER_ROW
        described = phrases if cap is None else phrases[:cap]
        unlooked = [b for b in bs if b not in named and b not in looked] + [
            dict(b, look="") for phrase in phrases[len(described):] for b in alike[phrase]]
        plain = [b for b in unlooked if (b.get("height") or "one") == "one"
                 and not b.get("lights") and not b.get("dark") and not b.get("over")]
        notable = [b for b in unlooked if b not in plain]
        before = set(said_kinds)
        again, parts = [], []
        for b in named + notable:
            phrase = str(building(b))
            if phrase:
                parts.append(phrase)
                said_kinds.add(phrase)
        for phrase in described:
            bucket = count_bucket(len(alike[phrase]))
            if before == {phrase}:
                again.append(text("landscape_again_" + bucket))
            elif bucket == "1":
                parts.append(phrase)
            else:
                parts.append(text("landscape_alike_" + bucket, look=phrase))
            said_kinds.add(phrase)
        if plain:
            parts.append(text("landscape_building_one") if len(plain) == 1
                         else text("landscape_buildings_" + count_bucket(len(plain))))
            said_kinds.add("\0plain")
        return ([str(x) for x in again if x], [str(x) for x in parts if x])

    def joined(parts):
        if len(parts) <= 1:
            return parts[0] if parts else ""
        return str(text("landscape_list")).join(parts[:-1]) + joiner + parts[-1]

    def buildings(bs):
        again, parts = building_parts(bs)
        return joined(again + parts)

    def ground(d, run=False, standing=(), also=()):
        # A RUN, said by its two ends: the nearest place's far look and the
        # farthest's, where they have them -- the places between are said by
        # the run, as they always were (`_plain_ground`).
        head = thing(d["look"]) if d.get("look") and not d.get("name") else ""
        tail = also[-1] if run and also else {}
        far = thing(tail["look"]) if tail.get("look") else ""
        if run and far and far != head:
            kind = text("landscape_sheltered" if d.get("ground") == "sheltered"
                        else "landscape_open")
            base = text("landscape_look_run_to" if head else "landscape_run_to",
                        place=head or kind, far=far)
        elif run and head:
            base = text("landscape_look_run", place=head)
        elif d.get("name"):
            base = d["name"]
        elif head:
            # How it reads from afar, where the world declares it.
            base = head
        elif d.get("ground") == "sheltered":
            base = text("landscape_sheltered")
        elif run:
            base = text("landscape_open_run")
        else:
            base = text("landscape_open_wide" if d.get("breadth") == "wide"
                        else "landscape_open")
        lights = lights_word(d)
        if d.get("dark"):
            return text("landscape_lit_known", lights=lights, place=base) if d.get("name") else lights
        # What stands on it -- its big things, then its buildings -- is ONE
        # list after "with", so nothing in it can read as standing on the
        # last noun of another (review: "an oak, and on it two buildings").
        # More of the buildings said before leads it, so nothing new on the
        # row can be what they are more of (`building_parts`).
        again, bparts = building_parts(standing)
        things = again + [thing(t) for t in d.get("big") or () if thing(t)]
        bs = joined(bparts)
        things += ([bs] if bs else []) + ([lights] if lights else [])
        if not things:
            return base
        # A look is a phrase of its own and often ends in one ("lined with
        # stalls"), so the list after it is set apart rather than read as
        # part of it: "lined with stalls, with a narrow office" -- never
        # "lined with stalls with a narrow office".
        key = "landscape_with_look" if (d.get("look") and not d.get("name")) else "landscape_with"
        return text(key, place=base, things=joiner.join(things))

    def row_phrase(row):
        if row.get("ground") is None:
            return buildings(row.get("buildings") or ())
        return ground(row["ground"], run=row.get("run"), standing=row.get("buildings") or (),
                      also=row.get("also") or ())

    lead = line.get("lead") or {}
    compass = compass_words.get(lead.get("compass") or "", "") if lead.get("compass") else ""
    rows = line.get("rows") or []
    suffix = "_episode" if episode else ""
    beside = buildings(line.get("beside") or ())
    via = lead.get("via") or ""
    # What fronts an UNNAMED way out is simply the line's first item, so the
    # connectors are given after it takes its place (it was spliced in front
    # of a first item that kept no "then": "a building, open ground").
    phrases = ([(beside, "mid")] if beside and not via else []) + [
        (row_phrase(row), row.get("tier")) for row in rows]
    items, far_said = [], False
    for phrase, tier in phrases:
        if not phrase:
            continue
        outline = tier == "outline"
        if not items:
            items.append(phrase)
            far_said = outline           # the lead says it (`_outline` leads)
        elif outline and not far_said:
            items.append(text("landscape_far", item=phrase))
            far_said = True
        else:
            items.append(text("landscape_then", item=phrase))
    if beside and via:
        if items:
            key = "landscape_line_beside" if compass else "landscape_line_beside_bare"
            return text(key + suffix, compass=compass, beside=beside, via=via,
                        items=sep.join(str(i) for i in items))
        key = "landscape_beside_only" if compass else "landscape_beside_only_bare"
        return text(key + suffix, compass=compass, beside=beside, via=via)
    first_far = bool(rows) and rows[0].get("tier") == "outline" and not beside
    if not items:
        return ""
    far = "_outline" if first_far else ""
    if lead.get("rise") == "below":
        # A memory is the mind's own: "below me", never "below you".
        lead_text = (text("landscape_lead_compass_below" + suffix, compass=compass) if compass
                     else text("landscape_lead_below" + suffix))
    elif via:
        lead_text = (text("landscape_lead_compass_via" + far, compass=compass, via=via) if compass
                     else text("landscape_lead_via" + far, via=via))
    elif compass:
        lead_text = text("landscape_lead_compass" + far, compass=compass)
    else:
        lead_text = text("landscape_lead_outline" if first_far else "landscape_lead_mid")
    return text("landscape_line" + suffix, lead=lead_text,
                items=sep.join(str(i) for i in items))


def render_landscape_line(line, episode=False):
    """A far line in English (`compose_landscape_line`), with the English
    pack's own compass whatever language scope the caller is in."""
    return _cap(str(compose_landscape_line(
        line, _en, episode=episode, thing=_noun_phrase,
        compass_words=dict(_ENGLISH_COMPOSITOR.get("compass_words") or {}))))
