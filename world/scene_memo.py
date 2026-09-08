"""One derivation per READ PASS, not one per lookup (review C12).

Every spatial derivation in this package is a pure function of the scene
blob: `visual_level_between`, `proximity_rel`, `effective_anchors`,
`effective_station`, `anchor_cells`, `light_field` and `sound_field` read
the scene and nothing else -- rooms and their edges, positions, entities,
stations, orientation, poses, contacts, containment, crossings, the day
phase, the weather, the beat index, and `passages`, which an edge resolves
through before any reader sees its barrier (`spatial_barriers.resolve_edge`
-> `passage_of`). `SCENE_READS` below is that list, and it is the whole of
what a pass fingerprints. A stage asks each of those functions for the same
answer many times over -- sight 5-9x per (observer, body) at nine call
sites, `effective_station` from fifteen callers, `effective_anchors` from
twenty-one -- and each ask ran the whole derivation again.

The two content-keyed caches under those functions did not help, because
the KEY cost as much as the answer: `spatial_light_field._cache_key` and
`spatial_sound_field._cache_key` both `json.dumps` the scene's whole read
set on every lookup, hit or miss. Measured 2026-09-07 on chat 117's
38-room, 22-body scene, one stage's worth of sight: 0.153 s of a 0.303 s
pass was inside `json.encoder.iterencode`, and it bought 157 cache hits.

A READ PASS, NOT A CACHE, and the difference is the whole safety argument.
An identity-keyed memo on the scene object -- the `spatial_sound_field.
far_field_graph` pattern -- cannot see an in-place edit of a value already
in the scene (`sc["entities"]["gen"]["state"] = {...}`), and that edit is
not hypothetical: written as an always-on memo this module failed three
existing tests that do exactly that and then read a field back. So the memo
serves nobody by default. A caller that KNOWS its region derives and never
mutates opens a pass around it:

    with scene_read_pass(sc):
        ... build every observer's view ...

Inside, each derivation runs once per distinct question; outside, every
call behaves exactly as it did before this module existed. The cache is
born with the pass and dies with it, so nothing survives into a turn that
might write, and there is no ceiling to tune and nothing to evict.

THE PASS CHECKS ITSELF. The cache is released on close either way; what
the close adds is a re-fingerprint of the scene's read set, and a warning
if it moved -- a region that turned out to mutate cannot quietly go on
being trusted. The fingerprint costs 0.6-0.9 ms, twice per pass, on a
38-room scene (three separate runs; the spread is machine load, not scene
size), against the 1.1-1.3 s a stage's worth of asking saves there.
"""

import json
import logging

log = logging.getLogger(__name__)

#: The scene sub-blobs the spatial derivations read. Deliberately the UNION
#: over all of them rather than a per-derivation read set: a wider stamp
#: fingerprints more than one derivation needs and can only cost a fraction
#: of a millisecond, where a narrow one short by a key would miss a
#: mutation. It is WIDER than what the two field caches spell into their own
#: keys (`spatial_light_field._cache_key`, `spatial_sound_field._cache_key`):
#: those omit "passages", which `effective_anchors` reads on every edge
#: through `resolve_edge` -> `passage_of` -> `spatial_barriers.
#: scene_passages`. That omission in the two field caches is pre-existing and
#: is not fixed here -- it is a content KEY that can hand back a field built
#: under a passage's old barrier, which is its own finding, not this memo's.
#: "beat_idx" is `world.spatial`'s BEAT_KEY, and `tests/test_scene_memo.py`
#: pins the two together so the spelling here cannot drift from the constant;
#: `test_the_read_set_covers_what_the_derivations_read` pins the whole tuple
#: against what the memoised derivations actually touch, which is what caught
#: "passages" missing (a stamp short by a key is a mutation nobody reports).
#: What the one key costs, measured 2026-09-07: chat 117's 38-room scene
#: stores no passages at all and fingerprints in 0.59 ms either way; the same
#: scene with a passage record on all 38 of its doorways costs 0.089 ms more,
#: twice per pass, against the ~140 ms a composer region saves. A key is
#: cheap; missing one is not.
SCENE_READS = ("rooms", "positions", "entities", "stations", "orientation",
               "poses", "contacts", "contained", "crossings", "passages",
               "day_phase", "weather", "beat_idx")

#: id(scene) -> (scene, fingerprint, cache). Never outlives the outermost
#: `scene_read_pass` for that object, so this global holds nothing between
#: turns and nothing between chats. The scene itself is held, not just its
#: id, so an id cannot be recycled onto another object under a live entry.
_PASSES: dict = {}


def _fingerprint(scene):
    """The scene's read set, for the self-check on close.

    THE SAME SERIALISATION THE TWO FIELD CACHES KEY ON, deliberately: one
    spelling of "what a scene says", and it answers CONTENT rather than
    representation. `marshal` was tried first for its 0.112 ms against this
    0.884 ms and is wrong for the job -- from version 3 it writes back
    references for repeated objects, so two structurally identical read sets
    marshal differently when object sharing differs, and every pass over
    chat 117's scene reported a mutation that had not happened. Twice per
    pass against the seconds a pass saves on that scene is not a cost worth
    being clever about.
    """
    return json.dumps([scene.get(name) for name in SCENE_READS],
                      sort_keys=True, default=str)


class scene_read_pass:
    """Memoise the spatial derivations over `scene` for the duration.

    Open one only around a region that DERIVES and does not mutate -- the
    composer's view building is the case this was written for. Re-entrant:
    a nested pass over the same object joins the outer one and releases
    nothing, and the cache is released by the instance that opened it. That
    is deliberately an OWNERSHIP flag rather than a depth count -- a shared
    counter is a read-modify-write two regions could lose an increment on,
    and a lost decrement would strand an entry holding a scene forever.
    """

    def __init__(self, scene):
        self.scene = scene
        self._opened = False

    def __enter__(self):
        if not isinstance(self.scene, dict):
            return self
        entry = _PASSES.get(id(self.scene))
        if entry is None or entry[0] is not self.scene:
            _PASSES[id(self.scene)] = (
                self.scene, _fingerprint(self.scene), {})
            self._opened = True
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self._opened:
            return False
        self._opened = False
        entry = _PASSES.pop(id(self.scene), None)
        if entry is None or entry[0] is not self.scene:
            return False
        if exc_type is None and _fingerprint(self.scene) != entry[1]:
            # The region's contract was that it only reads. It did not, so
            # some answer it was handed may have been derived from the scene
            # as it stood before the write. Say so loudly: this is a bug in
            # the caller's placement of the pass, not a condition to absorb.
            log.warning(
                "scene_read_pass: the scene changed inside a read pass; "
                "memoised derivations in that region may be stale")
        return False


def scene_memo(scene, key, build):
    """`build()`'s answer, derived at most once per open read pass.

    `key` identifies the question (the derivation's name and its arguments)
    and must be hashable. With no pass open over this scene object `build`
    runs, exactly as before. Inside a pass the answer is handed back BY
    REFERENCE to every later asker, so a caller that hands a mutable answer
    outward must copy it -- the functions behind the two content caches
    already did.
    """
    entry = _PASSES.get(id(scene))
    if entry is None or entry[0] is not scene:
        return build()
    cache = entry[2]
    try:
        return cache[key]
    except KeyError:
        pass
    answer = build()
    cache[key] = answer
    return answer


def clear_scene_memo():
    """Forget every open pass. For a test that wants a derivation to run."""
    _PASSES.clear()
