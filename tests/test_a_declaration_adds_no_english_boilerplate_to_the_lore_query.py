"""A declaration adds no English boilerplate to `flow.mapping_request`.

Two English cue lists in `director_interpret` ("picks up", "hands ",
"places ", "breaks", "through the door", "step inside"...) appended fixed
English sentences to `flow.mapping_request` -- "Inspect the declaration for
new, moved, transferred, transformed, opened, destroyed, or contained scene
entities and propose the minimum scene graph patch." -- whenever the input
or an attempt carried one. That text is part of the query the beat's lore is
retrieved with (`mapping._query` -> `search_lore`: embedding plus FTS over
the joined text) and the planning need's surface, so a lorebook key such as
"scene" or "room" matched every such beat; and a Japanese story never
triggers a word of it. 13 of 149 recent prose interprets carried it (review
2026-11-01, director core F12). The compiler files typed needs from
`movement`, `location_query` and `generation_requests`; a word list over free
prose is not one of those channels.
"""

from __future__ import annotations

import pytest

import agents.director as director

from tests.director_fakes import _make_ctx, _speech_interp, encoder_event


@pytest.mark.parametrize("said, told", [
    ("I pick up the cup and hand it to Mara.",
     "The Stranger picks up the cup and hands it to Mara."),
    ("I step inside and look around.",
     "The Stranger steps inside and looks around."),
    ("I break the seal on the letter.",
     "The Stranger breaks the seal on the letter."),
])
def test_no_cue_word_writes_english_into_the_mapping_request(
        temp_db, monkeypatch, prose_director, said, told):
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input=said)
    ctx.director_interpret = None

    def fake(role, step_key, system, payload, **kw):
        if step_key == "director_prose":
            return {"prose": told}
        if step_key == "director_specialist":
            return {"events": [encoder_event(told)]}
        return {}
    monkeypatch.setattr(director, "_agent_json", fake)

    out = director.director_interpret(ctx, nonce=0)

    assert (out.get("flow") or {}).get("mapping_request", "") == "", \
        out["flow"]["mapping_request"]
