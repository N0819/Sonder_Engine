"""A speaker's view of who is who is read once per speaker, not per target.

`_bodies_addressed_as` built `observer_label_fn` -- a `known` read, the
persona, a normalize of every cast sheet -- on EVERY call, and read the
stored scene from the database whenever it was handed none. Its callers call
it per target per event (`_name_declared_targets`), per declaration with an
untargeted line, and per line; on a resolve with speech that is the same
speaker's labels rebuilt for every word aimed at anyone (review 2026-11-01,
director core E3). The answer is unchanged: the same labels, the same scene.
"""

from __future__ import annotations

import agents.director as director

from tests.director_fakes import _make_ctx, _speech_interp


def test_one_speakers_targets_build_its_labels_once(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, interp=_speech_interp())
    built = []
    real = director.observer_label_fn
    monkeypatch.setattr(director, "observer_label_fn",
                        lambda *a, **k: built.append(a[1]) or real(*a, **k))
    scene = {"positions": {"The Stranger": "keeper_room", "Mara": "keeper_room"}}
    groups = [{"entity_id": "character:1", "events": [
        {"targets": ["The Stranger", "the stranger"]},
        {"targets": ["The Stranger"]}]}]

    director._name_declared_targets(ctx, scene, groups, {"character:1": "Mara"})

    assert built == ["Mara"], built
    assert groups[0]["events"][0]["target_bodies"] == ["The Stranger"]
    assert groups[0]["events"][1]["target_bodies"] == ["The Stranger"]
