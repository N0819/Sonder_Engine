"""A NOISE WAKES A SLEEPER BY THE ENGINE (DESIGN_SOUND_FIELD.md § 15, lane
A, 2026-10-20; § 13.7 item 15).

Since wave B1 the engine wakes a sleeper a noise DID reach: the outcome
pass prices every sound at the sleeper's ear (`perception._sleep_hears`)
and the commit ends the sleep (`commit_entities._with_sound_wakings`). The
encoder's awareness part still told the model "WAKING IS YOURS ... a noise
reaches them", so the model could wake a sleeper on a noise the hearing
rule says never reached them -- a judgement it has no ear to make. ONE
clause, en + ja, no guard: a sound is the engine's; what stays the model's
is the prose waking them, a hand on them, the night passing, the drug
wearing off, a body waking of itself.

And the double write is harmless, which these verify: where the encoder
ALSO ends the sleep the engine would end, the commit's sound waking keeps
the diff's own ending (`_ended_in`) and writes no second one; where the
encoder re-asserts the sleep the engine ends, the engine's ending stands.
"""

from __future__ import annotations

import json

from language_runtime import raw_card
from persist.commit import _with_sound_wakings

from tests.test_a_sleeper_wakes_to_sound import _make_ctx


# --- the clause ----------------------------------------------------------------

def test_the_card_leaves_sound_to_the_engine_and_keeps_the_rest_for_the_model():
    en = raw_card("en")["encoder"]["conditions__awareness"]
    assert "a noise reaches them" not in en
    assert "Sound is the engine's" in en
    assert "it hears for every sleeper and wakes the one a noise reaches" in en
    assert "never your reason to end a sleep" in en
    # what stays the model's
    assert "whenever the prose wakes them" in en
    for kept in ("a hand on them", "the night passing", "the drug wearing off",
                 "a body waking of itself"):
        assert kept in en
    ja = raw_card("ja")["encoder"]["conditions__awareness"]
    assert "物音が届く――" not in ja
    assert "音はエンジンのものです" in ja
    assert "眠りを終わらせる理由にしてはいけません" in ja
    for kept in ("記述がその人を目覚めさせるとき", "手が触れる", "夜が明ける", "薬が切れる",
                 "身体が自ら目覚める"):
        assert kept in ja


# --- the double write ------------------------------------------------------------

def _woken(ctx):
    ctx.perception_outcome = {"woken": {"Hinami": {"by": "shout"}}}
    return ctx


def test_an_ending_the_encoder_also_wrote_is_written_once(temp_db):
    """The encoder ended the same condition_id (the prose said the crash
    woke her); the engine's waking adds nothing to it -- the diff's record,
    its own `ended_reason` included, is what commits."""
    ctx, chat_id = _make_ctx(temp_db)
    theirs = {"condition_id": "cond_sleep_hinami", "subject_id": "Hinami",
              "kind": "awareness", "active": 0,
              "ended_reason": "the crash woke her"}
    out = _with_sound_wakings(_woken(ctx), chat_id,
                              {"cond_sleep_hinami": [theirs]})
    assert out["cond_sleep_hinami"] == [theirs]
    assert not [w for w in ctx.warnings if "woke them" in w]


def test_a_sleep_the_encoder_reasserts_is_still_ended_by_the_sound(temp_db):
    ctx, chat_id = _make_ctx(temp_db)
    again = {"condition_id": "cond_sleep_hinami", "subject_id": "Hinami",
             "kind": "awareness", "active": 1,
             "state": {"level": "asleep", "cause": "a long night"}}
    out = _with_sound_wakings(_woken(ctx), chat_id,
                              {"cond_sleep_hinami": again})
    ended = out["cond_sleep_hinami"]
    assert int(ended["active"]) == 0
    assert "woken by a sound" in ended["ended_reason"]


def test_a_sleep_the_encoder_left_alone_is_ended_by_the_engine(temp_db):
    ctx, chat_id = _make_ctx(temp_db)
    out = _with_sound_wakings(_woken(ctx), chat_id, {})
    ended = out["cond_sleep_hinami"]
    assert int(ended["active"]) == 0
    assert ended["ended_reason"] == "woken by a sound (shout)"
    assert json.loads(json.dumps(ended))["subject_id"] == "Hinami"
