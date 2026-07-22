"""Regression tests for physical-disguise enforcement.

A `physical_disguise` condition conceals a subject's real appearance from
observers who don't already know the truth. Before this, nothing consumed the
condition -- perception rendered the true appearance, so a concealed feature
(a kitsune's hidden fox ears) was still perceived by, and shown to, a guard she
was passing herself off in front of. These pin the deterministic core: the
condition reader, the per-observer appearance resolution, the knowledge
partition, and the leak tripwire. The LLM-facing prompt layer is not unit
tested here; the point is that the disguised appearance is what the model is
handed and what the deterministic injection pastes, so a leak cannot originate
in code even if the model behaves.
"""

from __future__ import annotations

import json
import time

from scene import (
    active_disguises,
    disguised_visible_appearance,
    disguise_known_to,
)
from agents.perception import _disguise_leak_check


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _add_disguise(db, chat_id, subject, state, active=1):
    payload = {"subject_id": subject, "kind": "physical_disguise", "state": state}
    db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,payload,active) VALUES(?,?,?,?,?,?,?)",
        (f"disg_{subject}", chat_id, subject, "physical_disguise",
         0.0, json.dumps(payload), active),
    )


class _Ctx:
    def __init__(self):
        self.warnings = []


def test_active_disguises_reads_condition(temp_db):
    chat_id = _make_chat(temp_db)
    _add_disguise(temp_db, chat_id, "Hinami", {
        "description": "Fox ears and tails concealed; cosmetic human ears.",
        "presented_appearance": "a young woman in dusty traveler's robes",
        "concealed_terms": ["fox ears", "tails", "kitsune"],
        "known_to": ["Dr. Moon"],
    })
    disg = active_disguises(chat_id)
    assert "hinami" in disg
    d = disg["hinami"]
    assert d["presented_appearance"] == "a young woman in dusty traveler's robes"
    assert d["concealed_terms"] == ["fox ears", "tails", "kitsune"]
    assert d["known_to"] == ["Dr. Moon"]


def test_inactive_disguise_ignored(temp_db):
    chat_id = _make_chat(temp_db)
    _add_disguise(temp_db, chat_id, "Hinami", {"description": "x"}, active=0)
    assert active_disguises(chat_id) == {}


def test_presented_appearance_preferred():
    d = {"presented_appearance": "a plain human girl",
         "concealed_terms": ["fox ears"]}
    assert disguised_visible_appearance(
        "golden fox ears and six tails", d) == "a plain human girl"


def test_concealed_terms_stripped_when_no_presented_form():
    d = {"concealed_terms": ["fox ears", "six tails"]}
    out = disguised_visible_appearance(
        "a girl with golden fox ears and six tails; wearing robes", d)
    assert "fox ears" not in out.lower()
    assert "six tails" not in out.lower()
    assert "robes" in out  # legitimate, non-concealed detail survives


def test_legacy_disguise_falls_back_to_generic_not_true_form():
    # No presented_appearance and no concealed_terms: must NOT return the true
    # appearance (that is the leak). Fail toward concealment.
    d = {"description": "fox features hidden"}
    out = disguised_visible_appearance("golden fox ears and six tails", d)
    assert "fox" not in out.lower()
    assert "tail" not in out.lower()


def test_known_to_partition():
    d = {"known_to": ["Dr. Moon"]}
    known = disguise_known_to(d, "Hinami", {})
    assert "hinami" in known        # subject always knows
    assert "dr. moon" in known
    assert "security guard alpha" not in known


def test_known_to_falls_back_to_known_map_when_unlisted():
    # Legacy condition with no explicit known_to: an observer who knows the
    # subject's identity is treated as aware; a stranger is not.
    d = {}
    known = disguise_known_to(d, "Hinami", {"Dr. Moon": ["Hinami"]})
    assert "dr. moon" in known
    assert "security guard alpha" not in known


def test_leak_tripwire_warns_for_unaware_only():
    ctx = _Ctx()
    perceivers = [
        {"id": "player", "name": "Hinami"},
        {"id": 25, "name": "Dr. Moon"},          # aware
        {"id": "g1", "name": "Security Guard Alpha"},  # unaware
    ]
    views = {
        "player": "You feel your fox ears twitch under the disguise.",
        "25": "The girl beside you keeps her fox nature hidden.",
        "g1": "A young woman, and — is that a fox tail? — stands beside the doctor.",
    }
    known = {"hinami", "dr. moon"}
    _disguise_leak_check(ctx, "perception_outcome", views, perceivers,
                         "Hinami", ["fox ears", "fox tail", "kitsune"], known)
    # Only the unaware guard's leak is flagged; player + aware Moon are exempt.
    assert len(ctx.warnings) == 1
    assert "Security Guard Alpha" in ctx.warnings[0]
    assert "fox tail" in ctx.warnings[0]


def test_leak_tripwire_silent_without_terms():
    ctx = _Ctx()
    perceivers = [{"id": "g1", "name": "Guard"}]
    views = {"g1": "A woman with obvious fox ears."}
    _disguise_leak_check(ctx, "perception_act", views, perceivers,
                         "Hinami", [], set())
    assert ctx.warnings == []  # no terms -> cannot tripwire (avoids false hits)
