"""What the two POLLED DRESSING routes cost, and proof they answer the same.

`GET /api/turns/{id}/backdrop` and `GET /api/turns/{id}/ambience` are asked
again and again while nobody is typing: the reader's scrolling polls them for
whichever beat is on screen, and both serve cache hits. Review 2026-09-07
(C22b) found each of them re-deriving work the payload never carries -- the
room projection an image PROMPT is written from, the room soundscape a sound
QUERY is written from, the backdrop's cache status read twice, the acoustic
fingerprint derived twice -- and gzip level 9 applied to the already-compressed
image and audio bytes those same routes hand back.

This measures all of that against a real story, and for the two routes it also
re-enacts the OLD shape in the same process and diffs the two payloads, which
is what makes "the same answer, faster" a measurement rather than a claim.

Run it against a COPY of a database (it only reads, but a copy is the habit):

    ENGINE_DB=/path/to/copy.db \\
        python tools/bench/bench_poll_paths.py <chat_id> [--json out.json]

It makes no model calls and writes nothing to the database.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import core.db as db  # noqa: E402
import dressing.ambience as amb  # noqa: E402
import dressing.backdrops as bd  # noqa: E402
import web.app as app_mod  # noqa: E402


def _best(fn, runs=9):
    """The fastest of `runs` rounds, in ms, after one warm-up.

    The minimum rather than the mean: everything that makes a round slower (a
    page fault, another process) is noise on top of the same work.
    """
    fn()
    rounds = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        rounds.append((time.perf_counter() - start) * 1000)
    return round(min(rounds), 2)


def _ab(after_fn, before_fn, runs=9):
    """Interleave the two shapes and take each one's best round.

    Alternating matters more than the round count: run one shape five times
    and then the other, and the second one reads a page cache the first
    warmed.
    """
    after_fn()
    before_fn()
    after_ms, before_ms = [], []
    for _ in range(runs):
        start = time.perf_counter()
        after = after_fn()
        after_ms.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        before = before_fn()
        before_ms.append((time.perf_counter() - start) * 1000)
    return {"after": after, "before": before,
            "after_ms": round(min(after_ms), 2),
            "before_ms": round(min(before_ms), 2)}


def _last_turn(chat_id):
    return db.q("SELECT id, idx FROM turns WHERE chat_id=? "
                "ORDER BY idx DESC LIMIT 1", (chat_id,), one=True)


# --- the two builders as they stood before C22b ----------------------------
#
# Transcribed rather than approximated, because the difference IS the
# measurement: the old backdrop builder derived `place` unconditionally, and
# the old ambience builder derived the acoustic fingerprint TWICE off one
# scene -- once inside `acoustic_signature`, once for the dict's own
# `fingerprint`. Calling today's builder with `for_prompt=True` and adding a
# fingerprint on the side would charge the "before" for a second
# `scene_after_turn` it never paid (0.57 ms on chat 117), which would flatter
# the saving.

def _legacy_backdrop_request(chat_id, turn_idx, player_name=None, style=None):
    scene = bd.scene_after_turn(chat_id, turn_idx)
    room_id = bd._room_of_player(scene, player_name)
    if not room_id:
        return None
    regions = bd._regions_for(chat_id, turn_idx)
    viewer_camera = bd._continuity_enabled()
    signature = bd.visual_signature(scene, room_id, style, viewer=player_name,
                                    regions=regions,
                                    viewer_camera=viewer_camera)
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    return {
        "room": room_id,
        "room_name": room.get("name") or room_id,
        "signature": signature,
        "cached": bd.cached_backdrop(chat_id, signature),
        "place": bd.room_projection(scene, room_id, viewer=player_name,
                                    regions=regions,
                                    viewer_camera=viewer_camera),
        "location": scene.get("location") or "",
        "weather": bd.weather_for_room(scene, room_id),
    }


def _legacy_ambience_request(chat_id, turn_idx, player_name=None, style=None):
    scene = amb.scene_after_turn(chat_id, turn_idx)
    room_id = amb._room_of_player(scene, player_name)
    if not room_id:
        return None
    pin = amb.ambience_pin_for(chat_id, room_id)
    signature = amb.acoustic_signature(scene, room_id, style, pin)
    room = ((scene.get("rooms") or {}).get(room_id) or {})
    return {
        "room": room_id,
        "room_name": room.get("name") or room_id,
        "signature": signature,
        "pin": pin,
        "fingerprint": amb.acoustic_fingerprint(scene, room_id, style),
        "cached": amb.cached_ambience(chat_id, signature),
        "place": amb.room_soundscape(scene, room_id),
        "weather": amb.weather_for_room(scene, room_id),
    }


def _routes(cid, out):
    turn = _last_turn(cid)
    tid = turn["id"]

    # The old READ ROUTES, whole: the same turn/player/style lookups the live
    # ones do, the old builders above, and the backdrop cache status asked a
    # second time for the `error` field.
    def legacy_backdrop():
        row = app_mod._backdrop_turn(tid)
        chat_id = row["chat_id"]
        req = _legacy_backdrop_request(
            chat_id, row["idx"], app_mod._backdrop_player(chat_id),
            app_mod.style_guide(chat_id))
        if req:
            bd.backdrop_status(chat_id, req["signature"])
        return app_mod._backdrop_payload(chat_id, req)

    def legacy_ambience():
        row = app_mod._backdrop_turn(tid)
        chat_id = row["chat_id"]
        req = _legacy_ambience_request(
            chat_id, row["idx"], app_mod._backdrop_player(chat_id),
            app_mod.style_guide(chat_id))
        if not req:
            return app_mod._ambience_payload(chat_id, None)
        return app_mod._ambience_payload(chat_id, req)

    picture = _ab(lambda: app_mod.turn_backdrop(tid), legacy_backdrop)
    sound = _ab(lambda: app_mod.turn_ambience(tid), legacy_ambience)

    out["turn_backdrop"] = {
        "before_ms": picture["before_ms"], "after_ms": picture["after_ms"],
        "same_answer": picture["before"] == picture["after"],
    }
    room_id = sound["after"]["room_id"]
    out["turn_ambience"] = {
        "before_ms": sound["before_ms"], "after_ms": sound["after_ms"],
        "same_answer": sound["before"] == sound["after"],
        # The one thing in this patch that could move a CACHE KEY: the
        # signature is now hashed from the fingerprint the caller already
        # holds rather than from one derived a second time inside
        # `acoustic_signature`. Same three arguments, so it must be the same
        # string -- asserted here rather than assumed.
        "signature_matches_rederived": room_id is not None and (
            sound["after"]["signature"] == amb.acoustic_signature(
                bd.scene_after_turn(cid, turn["idx"]), room_id,
                app_mod.style_guide(cid), amb.ambience_pin_for(cid, room_id))),
    }
    return {"backdrop": picture["after"], "ambience": sound["after"]}


def _pieces(cid, out):
    """Where the time inside one build goes, so the saving has a denominator.

    `player_name` is not optional here: `_room_of_player` answers None without
    one and both builders then return None, which is why a re-measure that
    omits it reads a fraction of a millisecond and proves nothing.
    """
    turn = _last_turn(cid)
    idx = turn["idx"]
    player, style = app_mod._backdrop_player(cid), app_mod.style_guide(cid)
    scene = bd.scene_after_turn(cid, idx)
    room = bd._room_of_player(scene, player)
    regions = bd._regions_for(cid, idx)
    camera = bd._continuity_enabled()

    out["pieces"] = {
        "player": player, "room": room, "turn_idx": idx,
        "backdrop_request_before_ms": _best(
            lambda: _legacy_backdrop_request(cid, idx, player, style)),
        "backdrop_request_after_ms": _best(
            lambda: bd.build_backdrop_request(cid, idx, player, style)),
        "backdrop_request_for_prompt_ms": _best(
            lambda: bd.build_backdrop_request(cid, idx, player, style,
                                              for_prompt=True)),
        "ambience_request_before_ms": _best(
            lambda: _legacy_ambience_request(cid, idx, player, style)),
        "ambience_request_after_ms": _best(
            lambda: amb.build_ambience_request(cid, idx, player, style)),
        "ambience_request_for_prompt_ms": _best(
            lambda: amb.build_ambience_request(cid, idx, player, style,
                                               for_prompt=True)),
        "room_projection_ms": _best(
            lambda: bd.room_projection(scene, room, viewer=player,
                                       regions=regions,
                                       viewer_camera=camera)) if room else None,
        "room_soundscape_ms": _best(
            lambda: amb.room_soundscape(scene, room)) if room else None,
        "acoustic_fingerprint_ms": _best(
            lambda: amb.acoustic_fingerprint(scene, room, style))
        if room else None,
    }

    # THE ANSWER, byte for byte. `for_prompt=True` must reproduce the old dict
    # exactly, and the read-path dict must be that dict minus the one key the
    # read path never carried -- including the signature, which is the cache
    # key an image and a bed are filed under.
    def _blob(value):
        return json.dumps(value, sort_keys=True, default=str)

    before = _legacy_backdrop_request(cid, idx, player, style)
    before_sound = _legacy_ambience_request(cid, idx, player, style)
    out["answers"] = {
        "backdrop_for_prompt_identical": _blob(before) == _blob(
            bd.build_backdrop_request(cid, idx, player, style,
                                      for_prompt=True)),
        "backdrop_read_path_is_before_minus_place": _blob(
            {k: v for k, v in (before or {}).items() if k != "place"}) == _blob(
                bd.build_backdrop_request(cid, idx, player, style)),
        "ambience_for_prompt_identical": _blob(before_sound) == _blob(
            amb.build_ambience_request(cid, idx, player, style,
                                       for_prompt=True)),
        "ambience_read_path_is_before_minus_place": _blob(
            {k: v for k, v in (before_sound or {}).items()
             if k != "place"}) == _blob(
                amb.build_ambience_request(cid, idx, player, style)),
    }


def _gzip(out):
    """What level-9 gzip costs on the bytes the media routes serve.

    `os.urandom` stands in for a PNG or an MP3 deliberately: both are already
    deflated, so an incompressible buffer is the honest model of them.
    """
    rows = {}
    for name, size in (("png_1mb", 1 << 20), ("audio_2mb", 2 << 20)):
        blob = os.urandom(size)
        best, body = None, b""
        for _ in range(3):                   # best round, like _best
            start = time.perf_counter()
            compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
            body = compressor.compress(blob) + compressor.flush()
            round_ms = (time.perf_counter() - start) * 1000
            best = round_ms if best is None else min(best, round_ms)
        rows[name] = {"ms": round(best, 1),
                      "bytes_in": size, "bytes_out": len(body),
                      "compressed_now": app_mod.SelectiveGZipMiddleware.is_text(
                          "image/png" if name.startswith("png")
                          else "audio/mpeg")}
    rows["json_is_still_text"] = \
        app_mod.SelectiveGZipMiddleware.is_text("application/json")
    out["gzip"] = rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chat_id", type=int)
    parser.add_argument("--json", dest="out_path", default="")
    args = parser.parse_args()

    out = {}
    payloads = _routes(args.chat_id, out)
    _pieces(args.chat_id, out)
    _gzip(out)

    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    if args.out_path:
        with open(args.out_path, "w", encoding="utf-8") as fh:
            json.dump({"measurements": out, "payloads": payloads}, fh,
                      indent=2, sort_keys=True, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
