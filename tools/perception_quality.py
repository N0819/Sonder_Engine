"""Perception quality baseline — Metric A: fact fidelity against entitlement.

Purpose. The deterministic-perception branch is held to one bar: same quality
as the current engine, just faster. This harness makes that bar falsifiable.
It scores a corpus of perception VIEWS against the typed entitled-fact set —
what each perceiver was legitimately entitled to receive, derived from
structured data (dialogue delivery gates, recognition ledgers, concealment,
spatial hearing) — in BOTH directions:

  * LEAKS (the serious direction): information present in a view that the
    observer was NOT entitled to — an unearned canonical identity, a quote
    the hearing gate never delivered, a line concealed from this observer,
    an invented quote nobody spoke, player speech the player never declared,
    the perceiver narrated in the third person from outside their own head.
  * UNDER-GRANTS: entitled information missing — a dialogue line the hearing
    gate delivered at `full` whose body is absent from the view.

It deliberately reuses the engine's OWN checkers (resolved by name, with
graceful degradation when a symbol is absent on a given tree) rather than
reimplementing the rules, so the yardstick is the audited one. It NEVER
scores similarity to stored model prose — stored views contain exactly the
defects the engine's repair passes exist to fix, and resemblance to them is
not quality.

Apples-to-apples by construction: `score_view(view_text, entitlement)` is a
pure function of a text and an entitlement record. To score a future
composer, render its view for the same (turn, observer) and call the same
function — nothing else changes.

The corpus database is opened read-only (`file:...?mode=ro`) and is never
written. Run:

    python tools/perception_quality.py --db /path/to/engine.db [--out out.json]

Engine symbols consumed (import-by-name; each is optional and its absence is
reported, not fatal):
  agents.common:      _scrub_unknown_identities, _scrub_invented_dialogue,
                      _scrub_undeclared_player_speech, _recognizes,
                      _quote_body, _contains_quote, player_speech_lines,
                      character_scene_keys
  agents.perception:  _strip_self_narration, _dialogue_hear_level
  world.spatial:      spatial_rel, room_of
  story.character_schema: character_name

The three the ENTITLEMENT GATE needs (`GATE_SYMBOLS`) are not optional: without
them every dialogue line files as `ungated` and the harness measures nothing in
the direction it exists for, so a run that cannot resolve them exits non-zero
instead of printing zeroes.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PERCEPTION_KEYS = ("perception_establish", "perception_act",
                   "perception_outcome")

# Leads of _compose_residue_view: a view opening with one of these belongs to
# a non-awake mind and had no model call and no hearing entitlement. Residue
# views are excluded from under-grant recall (a sleeping mind is entitled to
# nothing) but still checked for leaks.
RESIDUE_LEADS = ("Darkness.", "A thick, floating dark.",
                 "You are under, below waking.")

# A quote body shorter than this is not evidence of anything on its own
# ("Yes." appears everywhere); presence checks for LEAKED lines require at
# least this many characters. Entitled-line recall has no such floor — a
# short delivered line is still owed.
MIN_LEAK_QUOTE_CHARS = 12

SPOKEN_VOLUMES = ("normal", "loud", "shout")


# --------------------------------------------------------------------------
# Engine checker resolution (portable: by name, optional, reported)
# --------------------------------------------------------------------------

#: Without these three the entitlement gate cannot run: `gate_available` is
#: False for every view, every dialogue line files `ungated`, and the leak and
#: under-grant counts are both structurally zero. Degrading gracefully is right
#: for a metric; it is not right for the metric the harness is FOR. Named here
#: so a run can fail loudly rather than report an instrument that is unplugged
#: — which is exactly what happened when `spatial` became `world.spatial` and
#: the import landed in the tolerant `except` below.
GATE_SYMBOLS = ("_dialogue_hear_level", "spatial_rel", "room_of")


def resolve_engine():
    """Resolve every engine symbol this harness reuses, by name.

    Returns (symbols: dict[str, callable|None], missing: list[str]).
    A missing symbol disables only the metrics that need it; the caller
    reports which metrics were unavailable rather than guessing.
    """
    wanted = {
        "agents.common": [
            "_scrub_unknown_identities", "_scrub_invented_dialogue",
            "_scrub_undeclared_player_speech", "_recognizes",
            "_quote_body", "_contains_quote", "player_speech_lines",
            "character_scene_keys",
        ],
        "agents.perception": ["_strip_self_narration",
                              "_strip_self_narration_quote_safe",
                              "_dialogue_hear_level"],
        "world.spatial": ["spatial_rel", "room_of"],
        "story.character_schema": ["character_name"],
    }
    symbols, missing = {}, []
    for module_name, names in wanted.items():
        try:
            module = __import__(module_name, fromlist=names)
        except Exception as exc:  # pragma: no cover - environment-specific
            for name in names:
                symbols[name] = None
                missing.append(f"{module_name}.{name} (import failed: {exc})")
            continue
        for name in names:
            fn = getattr(module, name, None)
            symbols[name] = fn
            if fn is None:
                missing.append(f"{module_name}.{name}")
    return symbols, missing


# --------------------------------------------------------------------------
# Corpus access (read-only)
# --------------------------------------------------------------------------

class Corpus:
    """Read-only access to a Sonder Engine database snapshot."""

    def __init__(self, path):
        self.path = str(path)
        self.con = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        self.con.row_factory = sqlite3.Row

    def turns(self):
        return self.con.execute(
            "SELECT id, chat_id, idx, created FROM turns "
            "ORDER BY chat_id, idx").fetchall()

    def active_step(self, turn_id, key):
        row = self.con.execute(
            "SELECT v.content FROM steps s "
            "JOIN variants v ON v.step_id = s.id AND v.active = 1 "
            "WHERE s.turn_id = ? AND s.key = ? AND s.stale = 0 "
            "ORDER BY s.id DESC LIMIT 1", (turn_id, key)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["content"])
        except Exception:
            return None

    def steps_for_turn(self, turn_id):
        rows = self.con.execute(
            "SELECT s.key, v.content FROM steps s "
            "JOIN variants v ON v.step_id = s.id AND v.active = 1 "
            "WHERE s.turn_id = ? AND s.stale = 0", (turn_id,)).fetchall()
        out = {}
        for row in rows:
            try:
                out[row["key"]] = json.loads(row["content"])
            except Exception:
                continue
        return out

    def checkpoint_world(self, chat_id, turn_idx):
        row = self.con.execute(
            "SELECT blob FROM checkpoints WHERE chat_id = ? AND turn_idx = ?",
            (chat_id, turn_idx)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["blob"]).get("world") or {}
        except Exception:
            return None

    def chat_roster(self, chat_id, engine):
        """Cast + persona identity roster for one chat.

        Returns (sources, char_names, persona_name) where sources is
        [{name, appearance, aliases}] — the same shape the engine's own
        identity floor consumes — char_names maps char_id -> display name,
        and persona_name is the player's canonical name (or None).
        """
        character_name = engine.get("character_name")
        character_scene_keys = engine.get("character_scene_keys")
        sources, char_names = [], {}
        rows = self.con.execute(
            "SELECT cc.char_id, cc.sheet AS override, c.sheet AS base "
            "FROM chat_chars cc JOIN characters c ON c.id = cc.char_id "
            "WHERE cc.chat_id = ?", (chat_id,)).fetchall()
        for row in rows:
            sheet = None
            for raw in (row["override"], row["base"]):
                if not raw:
                    continue
                try:
                    sheet = json.loads(raw)
                    break
                except Exception:
                    continue
            if not isinstance(sheet, dict):
                continue
            name = character_name(sheet) if character_name else (
                ((sheet.get("identity") or {}).get("name")) or "")
            name = str(name or "").strip()
            if not name:
                continue
            aliases = []
            if character_scene_keys:
                try:
                    aliases = [str(a) for a in
                               (character_scene_keys(sheet)[1:] or [])]
                except Exception:
                    aliases = []
            appearance = (((sheet.get("embodiment") or {})
                           .get("visible") or {}).get("summary")) or None
            char_names[int(row["char_id"])] = name
            sources.append({"name": name, "appearance": appearance,
                            "aliases": aliases})
        persona_name = None
        prow = self.con.execute(
            "SELECT p.sheet FROM chats ch JOIN personas p "
            "ON p.id = ch.persona_id WHERE ch.id = ?", (chat_id,)).fetchone()
        if prow and prow["sheet"]:
            try:
                psheet = json.loads(prow["sheet"])
                persona_name = str(((psheet.get("identity") or {})
                                    .get("name")) or "").strip() or None
                if persona_name:
                    appearance = (((psheet.get("embodiment") or {})
                                   .get("visible") or {}).get("summary"))
                    aliases = [str(a) for a in ((psheet.get("identity") or {})
                                                .get("aliases") or [])]
                    sources.append({"name": persona_name,
                                    "appearance": appearance or None,
                                    "aliases": aliases})
            except Exception:
                persona_name = None
        return sources, char_names, persona_name


# --------------------------------------------------------------------------
# Entitlement derivation — the typed fact set per (turn, observer)
# --------------------------------------------------------------------------

def _walk_spoken_bodies(value, out):
    """Recursively collect every legitimately spoken quote body in a step
    output: `exact_quote` fields, speech-element `text`, bare `speech`
    strings. Deliberately generous — the invented-dialogue metric must not
    flag a line because this walk missed a source."""
    if isinstance(value, dict):
        quote = value.get("exact_quote")
        if isinstance(quote, str) and quote.strip():
            out.append(quote)
        if value.get("type") == "speech" and isinstance(value.get("text"), str):
            if value["text"].strip():
                out.append(value["text"])
        speech = value.get("speech")
        if isinstance(speech, str) and speech.strip():
            out.append(speech)
        for item in value.values():
            _walk_spoken_bodies(item, out)
    elif isinstance(value, list):
        for item in value:
            _walk_spoken_bodies(item, out)


def collect_spoken_bodies(step_contents):
    out = []
    for content in step_contents:
        if content:
            _walk_spoken_bodies(content, out)
    seen, deduped = set(), []
    for line in out:
        key = line.strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(line)
    return deduped


def _overlay_positions(scene, state_diff):
    """Scene copy with the resolve state_diff's position moves applied, so
    outcome-pass hearing is gated where bodies ENDED the beat rather than
    where they started it. Shallow-copies only what it changes."""
    positions = dict((scene or {}).get("positions") or {})
    moved = (state_diff or {}).get("positions") or {}
    if isinstance(moved, dict):
        for name, room in moved.items():
            if isinstance(room, str) and room.strip():
                positions[str(name)] = room
    out = dict(scene or {})
    out["positions"] = positions
    return out


def _is_residue_view(view):
    text = str(view or "").strip()
    return any(text.startswith(lead) for lead in RESIDUE_LEADS)


def _self_forms(name, sources):
    forms = {str(name or "").strip().casefold()}
    for src in sources:
        if src["name"] == name:
            forms.update(str(a).strip().casefold()
                         for a in (src.get("aliases") or []) if str(a).strip())
    forms.discard("")
    return forms


def _concealed_from(entry, observer):
    """True when this dialogue entry is concealed from this observer (the
    outcome-pass rule: visibility 'concealed' with an empty conceal_from list
    means concealed from everyone but the speaker)."""
    if entry.get("visibility") != "concealed":
        return False
    conceal = [str(c).casefold() for c in (entry.get("conceal_from") or [])]
    return (not conceal) or (str(observer).casefold() in conceal)


def _room_lookup(room_of, scene, name, alias_map):
    """room_of with alias fallback: scene positions are keyed by display
    name by convention, but the director sometimes keys by uid or alias."""
    room = room_of(scene, name)
    if room:
        return room
    for form in alias_map.get(name, ()):
        room = room_of(scene, form)
        if room:
            return room
    return None


def build_entitlement(observer, *, stage, is_player, sources, known_map,
                      scene, dialogue_log, spoken_bodies,
                      declared_player_lines, engine, known_map_post=None,
                      scene_pre=None, alias_map=None):
    """The typed entitled-fact set for one (turn, observer) pair.

    Pure data in, dict out; no database access. `scene` is the scene used to
    gate hearing (positions overlaid with the beat's moves); `scene_pre` is
    the start-of-beat scene used to mark high-confidence misses.
    """
    recognizes = engine.get("_recognizes") or (
        lambda name, recognized: name in recognized)
    dialogue_hear_level = engine.get("_dialogue_hear_level")
    spatial_rel = engine.get("spatial_rel")
    room_of = engine.get("room_of")
    alias_map = alias_map or {}

    ledger_present = isinstance(known_map, dict)
    recognized = set((known_map or {}).get(observer) or [])
    unknown_sources = [
        src for src in sources
        if src["name"] and src["name"] != observer
        and not recognizes(src["name"], recognized)]
    unknown_post = None
    if isinstance(known_map_post, dict):
        recognized_post = set(known_map_post.get(observer) or [])
        unknown_post = [
            src for src in sources
            if src["name"] and src["name"] != observer
            and not recognizes(src["name"], recognized_post)]

    self_forms = _self_forms(observer, sources)
    entitled, unentitled, concealed, ungated = [], [], [], 0
    same_room_lines = []
    gate_available = bool(dialogue_hear_level and spatial_rel and room_of
                          and isinstance(scene, dict))
    for entry in dialogue_log or []:
        if not isinstance(entry, dict):
            continue
        speaker = str(entry.get("speaker") or "").strip()
        quote = entry.get("exact_quote")
        if not speaker or not isinstance(quote, str) or not quote.strip():
            continue
        if speaker.casefold() in self_forms:
            continue
        record = {"speaker": speaker, "quote": quote,
                  "volume": str(entry.get("volume") or "normal")}
        if _concealed_from(entry, observer):
            concealed.append(record)
            continue
        if not gate_available:
            ungated += 1
            continue
        speaker_room = entry.get("speaker_room") or _room_lookup(
            room_of, scene, speaker, alias_map)
        observer_room = _room_lookup(room_of, scene, observer, alias_map)
        if not speaker_room or not observer_room:
            ungated += 1
            continue
        rel = spatial_rel(scene, speaker_room, observer_room)
        level = dialogue_hear_level(entry, rel, observer)
        same_room = bool(rel.get("same_room"))
        if same_room and record["volume"].lower() in SPOKEN_VOLUMES:
            same_room_lines.append(record)
        if level == "full":
            pre_same_room = None
            if isinstance(scene_pre, dict):
                pre_sp = entry.get("speaker_room") or _room_lookup(
                    room_of, scene_pre, speaker, alias_map)
                pre_ob = _room_lookup(room_of, scene_pre, observer, alias_map)
                if pre_sp and pre_ob:
                    pre_same_room = bool(
                        spatial_rel(scene_pre, pre_sp, pre_ob).get("same_room"))
            entitled.append({**record, "same_room_pre": pre_same_room,
                             "same_room": same_room})
        elif level == "none":
            unentitled.append(record)
        # fragment/degraded levels: entitled to a degraded form — neither a
        # verbatim obligation nor a verbatim prohibition; not scored.

    return {
        "observer": observer,
        "stage": stage,
        "is_player": is_player,
        "ledger_present": ledger_present,
        "observer_in_ledger": bool(
            ledger_present and observer in (known_map or {})),
        "allowed_forms": [observer, *recognized],
        "unknown_sources": unknown_sources,
        "unknown_sources_post": unknown_post,
        "roster_names": [src["name"] for src in sources],
        "entitled_lines": entitled,
        "unentitled_lines": unentitled,
        "concealed_lines": concealed,
        "ungated_lines": ungated,
        "same_room_lines": same_room_lines,
        "gate_available": gate_available,
        "spoken_bodies": spoken_bodies,
        "declared_player_lines": declared_player_lines,
    }


# --------------------------------------------------------------------------
# Scoring — pure function of (view text, entitlement); composer-ready
# --------------------------------------------------------------------------

def score_view(view, ent, engine):
    """Score one view against one entitlement record.

    Returns a findings dict. Every count is grounded in the typed fact set;
    nothing here compares the view to any other prose.
    """
    findings = {
        "residue": _is_residue_view(view),
        "identity_leaks": [],           # names unearned at beat START
        "identity_leaks_post": [],      # ... still unearned at beat END
        "self_narration": 0,
        "self_narration_refused": 0,
        "invented_quotes": [],
        "undeclared_player_speech": [],
        "unentitled_line_leaks": [],
        "concealed_line_leaks": [],
        "entitled_lines_total": len(ent["entitled_lines"]),
        "entitled_lines_missing": [],
        "entitled_lines_missing_high_confidence": [],
        "same_room_lines_total": len(ent["same_room_lines"]),
        "same_room_lines_missing": 0,
        "checks_skipped": [],
    }
    text = str(view or "")
    if not text.strip():
        return findings

    scrub_ident = engine.get("_scrub_unknown_identities")
    if scrub_ident and ent["ledger_present"]:
        _, leaked = scrub_ident(text, allowed_forms=ent["allowed_forms"],
                                unknown_sources=ent["unknown_sources"])
        findings["identity_leaks"] = leaked
        if leaked and ent["unknown_sources_post"] is not None:
            post_names = {s["name"] for s in ent["unknown_sources_post"]}
            _, leaked_post = scrub_ident(
                text, allowed_forms=ent["allowed_forms"],
                unknown_sources=[s for s in ent["unknown_sources"]
                                 if s["name"] in post_names])
            findings["identity_leaks_post"] = leaked_post
    elif not scrub_ident:
        findings["checks_skipped"].append("identity")
    elif not ent["ledger_present"]:
        findings["checks_skipped"].append("identity_no_ledger")

    # THE QUOTE-SAFE VARIANT WHERE THE TREE HAS ONE. The bare stripper
    # splits on sentence punctuation, sentence punctuation lives inside
    # quoted speech, and so it counts a FRAGMENT OF A DELIVERED LINE as
    # self-narration every time a speaker says the perceiver's name to
    # their face -- which people do constantly.
    #
    # Measured on the composed corpus: all 33 floor-era views this flagged
    # were exactly that, and all 33 were the same views the old repair pass
    # had been deleting a line from. The metric read 0 because the
    # destruction had already removed the evidence. A check that scores its
    # own mis-split as a defect will go on rewarding whatever destroys it.
    strip_self = (engine.get("_strip_self_narration_quote_safe")
                  or engine.get("_strip_self_narration"))
    if strip_self:
        result = strip_self(text, ent["observer"], ent["roster_names"])
        if len(result) == 3:
            _, dropped, refusals = result
        else:
            refusals = []
            _, dropped = strip_self(
                text, ent["observer"], ent["roster_names"],
                refusals=refusals)
        findings["self_narration"] = len(dropped)
        findings["self_narration_refused"] = len(refusals)
    else:
        findings["checks_skipped"].append("self_narration")

    contains_quote = engine.get("_contains_quote")
    quote_body = engine.get("_quote_body") or (lambda q: str(q or ""))
    if contains_quote:
        if not findings["residue"]:
            for line in ent["entitled_lines"]:
                if not contains_quote(text, line["quote"]):
                    findings["entitled_lines_missing"].append(line)
                    if line.get("same_room") and line.get("same_room_pre"):
                        findings["entitled_lines_missing_high_confidence"]\
                            .append(line)
            findings["same_room_lines_missing"] = sum(
                1 for line in ent["same_room_lines"]
                if not contains_quote(text, line["quote"]))
        for line in ent["unentitled_lines"]:
            if len(quote_body(line["quote"]).strip()) < MIN_LEAK_QUOTE_CHARS:
                continue
            if contains_quote(text, line["quote"]):
                findings["unentitled_line_leaks"].append(line)
        for line in ent["concealed_lines"]:
            if len(quote_body(line["quote"]).strip()) < MIN_LEAK_QUOTE_CHARS:
                continue
            if contains_quote(text, line["quote"]):
                findings["concealed_line_leaks"].append(line)
    else:
        findings["checks_skipped"].append("line_recall")

    if ent["stage"] == "perception_outcome":
        scrub_invented = engine.get("_scrub_invented_dialogue")
        if scrub_invented:
            _, invented = scrub_invented(text, ent["spoken_bodies"],
                                         cast_names=ent["roster_names"])
            findings["invented_quotes"] = invented
        else:
            findings["checks_skipped"].append("invented_dialogue")
        if ent["is_player"]:
            scrub_player = engine.get("_scrub_undeclared_player_speech")
            if scrub_player:
                _, undeclared = scrub_player(
                    text,
                    declared_bodies=ent["declared_player_lines"],
                    protected_bodies=[l["quote"] for l in
                                      ent["entitled_lines"]
                                      + ent["same_room_lines"]],
                    cast_names=ent["roster_names"])
                findings["undeclared_player_speech"] = undeclared
            else:
                findings["checks_skipped"].append("undeclared_player_speech")
    return findings


# --------------------------------------------------------------------------
# Corpus iteration
# --------------------------------------------------------------------------

def _observer_for_key(key, char_names, persona_name):
    """Resolve a view key to (display_name, is_player) or (None, None)."""
    if key == "player":
        return persona_name, True
    if key.startswith("extra:"):
        return None, None  # other-player views: identity model not derivable
    try:
        return char_names.get(int(key)), False
    except (TypeError, ValueError):
        return None, None


def iter_view_records(corpus, engine, limit=None):
    """Yield (meta, view_text, entitlement) for every stored perception view.

    `meta` is {chat_id, turn_id, turn_idx, stage, view_key}. A future
    composer is scored by replacing `view_text` with its own rendering for
    the same meta and calling `score_view` unchanged.
    """
    roster_cache = {}
    world_cache = {}  # (chat_id, idx) -> world dict, kept small
    yielded = 0
    for turn in corpus.turns():
        chat_id, turn_idx, turn_id = turn["chat_id"], turn["idx"], turn["id"]
        steps = corpus.steps_for_turn(turn_id)
        perception_steps = {k: steps[k] for k in PERCEPTION_KEYS if k in steps}
        if not perception_steps:
            continue
        if chat_id not in roster_cache:
            sources, char_names, persona_name = corpus.chat_roster(
                chat_id, engine)
            alias_map = {src["name"]: [src["name"],
                                       *(src.get("aliases") or [])]
                         for src in sources}
            roster_cache[chat_id] = (sources, char_names, persona_name,
                                     alias_map)
        sources, char_names, persona_name, alias_map = roster_cache[chat_id]

        def world_at(idx):
            key = (chat_id, idx)
            if key not in world_cache:
                for stale in [k for k in world_cache if k[0] != chat_id
                              or k[1] < idx - 1]:
                    world_cache.pop(stale, None)
                world_cache[key] = corpus.checkpoint_world(chat_id, idx)
            return world_cache[key]

        world_pre = world_at(turn_idx) or {}
        world_post = corpus.checkpoint_world(chat_id, turn_idx + 1)
        scene_pre = world_pre.get("scene") or {}
        known_pre = world_pre.get("known") if "known" in world_pre else None
        known_post = (world_post or {}).get("known") \
            if world_post and "known" in world_post else None

        interp = steps.get("director_interpret") or {}
        resolve = steps.get("director_resolve") or {}
        dialogue_log = resolve.get("dialogue_log") or []
        scene_gate = _overlay_positions(scene_pre, resolve.get("state_diff"))
        player_speech_lines = engine.get("player_speech_lines") or (
            lambda i: [e.get("text") for e in (i.get("sequence") or [])
                       if e.get("type") == "speech" and e.get("text")])
        declared = list(player_speech_lines(interp) or [])
        spoken = collect_spoken_bodies([
            interp, resolve, steps.get("interaction_loop"),
            steps.get("reaction_loop"), steps.get("background_react"),
            *[steps[k] for k in steps if k.startswith("character:")]])
        spoken = list(dict.fromkeys(spoken + declared))

        for stage, content in perception_steps.items():
            views = (content or {}).get("views") or {}
            for view_key, view in views.items():
                if not view:
                    continue
                observer, is_player = _observer_for_key(
                    str(view_key), char_names, persona_name)
                if not observer:
                    yield ({"chat_id": chat_id, "turn_id": turn_id,
                            "turn_idx": turn_idx, "stage": stage,
                            "view_key": str(view_key), "skipped": True},
                           view, None)
                    continue
                ent = build_entitlement(
                    observer, stage=stage, is_player=is_player,
                    sources=sources, known_map=known_pre,
                    scene=scene_gate if stage == "perception_outcome"
                    else scene_pre,
                    dialogue_log=dialogue_log
                    if stage == "perception_outcome" else [],
                    spoken_bodies=spoken,
                    declared_player_lines=declared, engine=engine,
                    known_map_post=known_post, scene_pre=scene_pre,
                    alias_map=alias_map)
                yield ({"chat_id": chat_id, "turn_id": turn_id,
                        "turn_idx": turn_idx, "stage": stage,
                        "view_key": str(view_key), "skipped": False},
                       view, ent)
                yielded += 1
                if limit and yielded >= limit:
                    return


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

def _new_segment():
    return {
        "views_scored": 0,
        "views_residue": 0,
        "views_no_ledger": 0,
        "by_stage": Counter(),
        # leak direction
        "identity_leak_views": 0,
        "identity_leak_names": 0,
        "identity_leak_views_post": 0,
        "identity_leak_views_observer_in_ledger": 0,
        "self_narration_views": 0,
        "self_narration_sentences": 0,
        "self_narration_refusals": 0,
        "invented_quote_views": 0,
        "invented_quotes": 0,
        "undeclared_player_speech_views": 0,
        "unentitled_line_leak_views": 0,
        "unentitled_line_leaks": 0,
        "concealed_line_leak_views": 0,
        "concealed_line_leaks": 0,
        # under-grant direction
        "entitled_lines_total": 0,
        "entitled_lines_missing": 0,
        "entitled_lines_missing_high_confidence": 0,
        "views_with_missing_lines": 0,
        "same_room_lines_total": 0,
        "same_room_lines_missing": 0,
        "ungated_lines": 0,
        "checks_skipped": Counter(),
        # player-only recall slice (comparable to the 30/1549 audit number)
        "player_same_room_lines_total": 0,
        "player_same_room_lines_missing": 0,
    }


def _fold(seg, meta, ent, findings):
    seg["views_scored"] += 1
    seg["by_stage"][meta["stage"]] += 1
    if findings["residue"]:
        seg["views_residue"] += 1
    if not ent["ledger_present"]:
        seg["views_no_ledger"] += 1
    if findings["identity_leaks"]:
        seg["identity_leak_views"] += 1
        seg["identity_leak_names"] += len(findings["identity_leaks"])
        if ent.get("observer_in_ledger"):
            seg["identity_leak_views_observer_in_ledger"] += 1
    if findings["identity_leaks_post"]:
        seg["identity_leak_views_post"] += 1
    if findings["self_narration"]:
        seg["self_narration_views"] += 1
        seg["self_narration_sentences"] += findings["self_narration"]
    seg["self_narration_refusals"] += findings["self_narration_refused"]
    if findings["invented_quotes"]:
        seg["invented_quote_views"] += 1
        seg["invented_quotes"] += len(findings["invented_quotes"])
    if findings["undeclared_player_speech"]:
        seg["undeclared_player_speech_views"] += 1
    if findings["unentitled_line_leaks"]:
        seg["unentitled_line_leak_views"] += 1
        seg["unentitled_line_leaks"] += len(findings["unentitled_line_leaks"])
    if findings["concealed_line_leaks"]:
        seg["concealed_line_leak_views"] += 1
        seg["concealed_line_leaks"] += len(findings["concealed_line_leaks"])
    seg["entitled_lines_total"] += findings["entitled_lines_total"]
    missing_lines = len(findings["entitled_lines_missing"])
    seg["entitled_lines_missing"] += missing_lines
    seg["entitled_lines_missing_high_confidence"] += len(
        findings["entitled_lines_missing_high_confidence"])
    if missing_lines:
        seg["views_with_missing_lines"] += 1
    seg["same_room_lines_total"] += findings["same_room_lines_total"]
    seg["same_room_lines_missing"] += findings["same_room_lines_missing"]
    seg["ungated_lines"] += ent["ungated_lines"]
    if ent["is_player"]:
        seg["player_same_room_lines_total"] += \
            findings["same_room_lines_total"]
        seg["player_same_room_lines_missing"] += \
            findings["same_room_lines_missing"]
    for skipped in findings["checks_skipped"]:
        seg["checks_skipped"][skipped] += 1


def _finish_segment(seg):
    seg["by_stage"] = dict(seg["by_stage"])
    seg["checks_skipped"] = dict(seg["checks_skipped"])
    total = seg["entitled_lines_total"]
    seg["delivered_line_recall"] = (
        round(1 - seg["entitled_lines_missing"] / total, 4) if total else None)
    sr_total = seg["same_room_lines_total"]
    seg["same_room_line_recall"] = (
        round(1 - seg["same_room_lines_missing"] / sr_total, 4)
        if sr_total else None)
    return seg


def find_identity_floor_boundary(corpus):
    """First turn_id whose perception steps carry the runtime identity-floor
    warning — the corpus's own record of when the modern scrub was live.
    Views from earlier turns were produced by an engine without that floor,
    so era segmentation keeps historical defects from being read as the
    current engine's output."""
    row = corpus.con.execute(
        "SELECT MIN(s.turn_id) FROM steps s "
        "JOIN variants v ON v.step_id = s.id "
        "WHERE s.key LIKE 'perception%' "
        "AND v.content LIKE '%scrubbed unearned identity%'").fetchone()
    return row[0] if row else None


def run_baseline(db_path, engine=None, limit=None, progress=None):
    engine_symbols, missing = (engine, []) if engine else resolve_engine()
    corpus = Corpus(db_path)
    boundary = find_identity_floor_boundary(corpus)
    segments = {"all_turns": _new_segment(),
                "identity_floor_era": _new_segment()}
    skipped_views = 0
    for i, (meta, view, ent) in enumerate(
            iter_view_records(corpus, engine_symbols, limit=limit)):
        if progress and i % 500 == 0:
            progress(i)
        if meta.get("skipped"):
            skipped_views += 1
            continue
        findings = score_view(view, ent, engine_symbols)
        _fold(segments["all_turns"], meta, ent, findings)
        if boundary is not None and meta["turn_id"] >= boundary:
            _fold(segments["identity_floor_era"], meta, ent, findings)
    return {
        "db": str(db_path),
        "engine_symbols_missing": missing,
        "entitlement_gate_available": all(
            engine_symbols.get(name) for name in GATE_SYMBOLS),
        "identity_floor_boundary_turn_id": boundary,
        "views_skipped_unresolvable_observer": skipped_views,
        "segments": {name: _finish_segment(seg)
                     for name, seg in segments.items()},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="engine.db",
                        help="path to the corpus database (opened read-only)")
    parser.add_argument("--out", default=None,
                        help="write the aggregate JSON here as well")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after N scored views (smoke runs)")
    args = parser.parse_args(argv)
    agg = run_baseline(args.db, limit=args.limit,
                       progress=lambda i: print(f"  ...{i} views",
                                                file=sys.stderr))
    text = json.dumps(agg, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    if not agg["entitlement_gate_available"]:
        print("FAILED: the entitlement gate could not be assembled, so every "
              "dialogue line filed as ungated and the leak counts above are "
              "structurally zero. Missing: "
              + ", ".join(agg["engine_symbols_missing"]), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
