"""Regression tests for the identity-leak floor found during live play
(Dr. Moon / Hinami, two strangers meeting):

perception computed each perceiver's knows_identity correctly and used
_unknown_actor_label correctly in its OWN deterministic injection helpers
-- but the perception LLM's free-text view prose was never checked
against that gate. The payload handed the model the actor's canonical
name unconditionally, so a model (of any strength -- no prompt paragraph
even defined knows_identity) writing "You see Hinami..." for a stranger
walked straight past the gate, and the leaked name then fed the
character agent verbatim (agents/character.py perception.view) and
durable memory minting (commit.py).

Three sibling deterministic channels leaked the same way regardless of
model output: _inject_visible_actor pasted the raw appearance summary
(which routinely LEADS with the canonical name) into a stranger's view,
_unknown_actor_label built its descriptor from that same summary without
dropping the name tokens, and loops.py's deterministic_micro_perception
delivered NPC speech/actions under the canonical actor name with no
recognition check at all.

Fix: _scrub_unknown_identities (agents/common.py) is applied as the last
transform to every view in all three perception stages -- quoted spans
are preserved verbatim (a name legitimately spoken aloud this beat is
sensory signal; recognition still only flips at commit via
validated_introductions), everything outside quotes is scrubbed against
the observer's recognized set -- plus name-token stripping at the
appearance source and recognition gating in the loops.py and fallback
delivery paths.
"""

from __future__ import annotations

import json
import re
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

HINAMI_APPEARANCE = (
    "Hinami, a fox-eared young woman with amber eyes and a white-tipped tail."
)

_QUOTE_RE = re.compile(r'["“][^"“”]+["”]')


def _outside_quotes(text):
    return _QUOTE_RE.sub("", str(text or ""))


def _name_outside_quotes(text, name="hinami"):
    return re.search(
        r"(?<!\w)" + re.escape(name) + r"(?!\w)",
        _outside_quotes(text), re.I,
    ) is not None


def _make_ctx(temp_db, known=None, extra_char=None):
    sheet = default_persona_data("Hinami")
    sheet["embodiment"]["visible"]["summary"] = HINAMI_APPEARANCE
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(sheet), "{}"),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Test", "", time.time(), persona_id),
    )

    def add_character(name):
        csheet = default_character_data(name)
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(csheet), "{}", time.time(),
             f"char_{name.lower().replace(' ', '_').replace('.', '')}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"),
        )
        return char_id

    moon_id = add_character("Dr. Moon")
    extra_id = add_character(extra_char) if extra_char else None

    positions = {"Hinami": "room1", "Dr. Moon": "room1"}
    if extra_char:
        positions[extra_char] = "room1"
    temp_db.wset(chat_id, "scene", {
        "location": "the lab", "time": "day",
        "rooms": {"room1": {"name": "Room 1", "adjacent": []}},
        "positions": positions,
        "entities": {}, "attire": {}, "overlays": {},
    })
    if known is not None:
        temp_db.wset(chat_id, "known", known)

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "step forward", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="step forward", created=time.time()),
        cast=cast, input="step forward",
    )
    ctx["_player_room"] = "room1"
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "flow": {"reactors": [moon_id], "resolution_flags": {}},
    }
    return ctx, moon_id, extra_id


# These tests used to hand a stubbed model the ADVERSARIAL view below and
# check that the identity floor scrubbed it back out. That framing died with
# the model: nothing writes a canonical name into a stranger's view any more,
# because the name is never admitted to the IR the view is composed from.
#
# So the assertions moved from "the scrub caught it" to "it was never there",
# which is the stronger claim and the one the firewall actually makes. The
# scrub survives as a tripwire and has its own tests in
# test_composer_admission_gate.py; what is pinned HERE is the outcome.


ADVERSARIAL = "You see Hinami. Hinami steps forward and Hinami's tail sways."


def test_stranger_view_is_scrubbed_of_canonical_name(temp_db, monkeypatch):
    """The canonical fixture: Dr. Moon has never met Hinami, the model
    writes her name into the view prose anyway -- the floor must catch it."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})

    result = perception.perception_act(ctx, nonce=0)
    view = result["views"][str(moon_id)]

    assert not _name_outside_quotes(view), (
        f"canonical name leaked into a stranger's view: {view!r}"
    )
    assert "fox-eared" in view, (
        "the stranger should get a descriptor label derived from appearance"
    )


def test_unknown_actor_label_drops_name_tokens_from_appearance():
    """An appearance summary that LEADS with the canonical name must not
    smuggle it into the unknown-actor descriptor itself."""
    from agents.common import _unknown_actor_label

    label = _unknown_actor_label("Hinami", HINAMI_APPEARANCE)
    assert "hinami" not in label.lower()
    assert "fox-eared" in label


def test_injected_appearance_is_scrubbed_of_name(temp_db, monkeypatch):
    """_inject_visible_actor pastes the appearance summary into a stranger's
    view -- the deterministic path itself must not print the name."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})

    result = perception.perception_act(ctx, nonce=0)
    view = result["views"][str(moon_id)]

    assert "fox-eared" in view, "stranger should still see the appearance"
    assert not _name_outside_quotes(view), (
        f"appearance injection leaked the canonical name: {view!r}"
    )


def test_recognizing_observer_view_passes_through_unmodified(temp_db, monkeypatch):
    """No false positive: once Dr. Moon legitimately knows Hinami, the same
    adversarial view must survive untouched."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={"Dr. Moon": ["Hinami"]})

    view = perception.perception_act(ctx, nonce=0)["views"][str(moon_id)]
    assert "Hinami" in view, (
        "an observer who knows her must read her name, not a descriptor: "
        f"{view!r}")


def test_player_own_view_keeps_own_name(temp_db, monkeypatch):
    """The observer IS the actor: the player's own view referring to the
    player by name is legitimate self-knowledge, never scrubbed."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": []}
    result = perception.perception_outcome(ctx, nonce=0)
    view = result["views"]["player"] or ""
    assert "Hinami" not in view or "You" in view, (
        "the player's own view is written to them in the second person; "
        f"their name is never withheld from themselves: {view!r}")


def test_outcome_stage_scrubs_stranger_view(temp_db, monkeypatch):
    """The floor applies at the outcome pass too, per-source against the
    observer's recognized set."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": []}

    result = perception.perception_outcome(ctx, nonce=0)
    view = result["views"][str(moon_id)]

    assert not _name_outside_quotes(view), (
        f"canonical name leaked into stranger's outcome view: {view!r}"
    )


def test_outcome_payload_previews_attire_and_delivers_exposed_region_detail(
        temp_db, monkeypatch):
    """Chat 68's two missing seams together: perception must see commit's
    canonicalized removal, and the body detail it exposes must enter only the
    observer-scoped payload rather than the shared omniscient context."""
    from story import attire
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(
        temp_db, known={"Dr. Moon": ["Hinami"]})
    temp_db.set_setting("attire_beneath", "1")
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["attire"] = {"Hinami": attire.authored_entry(
        ["fitted tank top"], [], {"torso": {
            "garments": [{"name": "fitted tank top"}],
            "beneath": "a distinctive silver scar across the ribs",
        }})}
    temp_db.wset(ctx.chat.id, "scene", sc)
    ctx.director_resolve = {
        "resolved_event": "The fitted tank top comes off.",
        "dialogue_log": [], "dialogue_order": [],
        "state_diff": {"attire": {"Hinami": {"remove": ["tank top"]}}},
    }
    monkeypatch.setattr(attire, "decisive_targets",
                        lambda *a, **k: {"Hinami"})
    # There is no payload to inspect: the observer-scoped projection this
    # test was written to guard now flows straight into the composed view,
    # which is a shorter path to the same guarantee.
    view = perception.perception_outcome(ctx, nonce=0)["views"][str(moon_id)]

    assert "distinctive silver scar" in view
    # THE GUARANTEE IS THAT SHE IS NOT SHOWN STILL DRESSED, not that the
    # garment is unmentionable. This asserted `"fitted tank top" not in view`
    # until 2026-08-23, which also forbade the view from saying the top came
    # OFF -- and since a change of dress now renders as the change ("Hinami
    # is no longer wearing fitted tank top") rather than as a re-issued
    # inventory, the honest rendering of the removal tripped a check meant
    # to catch the opposite error. Naming a garment the observer watched
    # come off discloses nothing; presenting it as current dress is the
    # defect, and that is what this now says.
    assert not re.search(r"(?<!no longer )wearing fitted tank top", view), view
    # Previewing is pure with respect to the stored pre-commit scene.
    stored = temp_db.wget(ctx.chat.id, "scene", {})
    assert stored["attire"]["Hinami"]["wearing"] == ["fitted tank top"]


def test_outcome_payload_withholds_exposed_body_detail_in_darkness(
        temp_db, monkeypatch):
    """A hostile marker must be absent from the actual model payload when
    the observer has no visual channel, even though the garment came off and
    the observer recognizes the body."""
    from story import attire
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(
        temp_db, known={"Dr. Moon": ["Hinami"]})
    temp_db.set_setting("attire_beneath", "1")
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["rooms"]["room1"]["light"] = "dark"
    sc["attire"] = {"Hinami": attire.authored_entry(
        ["fitted tank top"], [], {"torso": {
            "garments": [{"name": "fitted tank top"}],
            "beneath": "HOSTILE-HIDDEN-SCAR-MARKER",
        }})}
    temp_db.wset(ctx.chat.id, "scene", sc)
    ctx.director_resolve = {
        "resolved_event": "The fitted tank top comes off.",
        "dialogue_log": [], "dialogue_order": [],
        "state_diff": {"attire": {"Hinami": {"remove": ["tank top"]}}},
    }
    monkeypatch.setattr(attire, "decisive_targets",
                        lambda *a, **k: {"Hinami"})
    view = perception.perception_outcome(ctx, nonce=0)["views"][str(moon_id)]

    assert "HOSTILE-HIDDEN-SCAR-MARKER" not in (view or "")


def test_outcome_payload_previews_partial_midriff_coverage_without_chest_leak(
        temp_db, monkeypatch):
    """The live Hinami case: commit and perception read the same structured
    coverage diff while the still-worn top protects the covered zone."""
    from story import attire
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(
        temp_db, known={"Dr. Moon": ["Hinami"]})
    temp_db.set_setting("attire_beneath", "1")
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["attire"] = {"Hinami": attire.authored_entry(
        ["fitted tank top"], [], {
            "torso": {
                "garments": [{"name": "fitted tank top"}],
                "beneath": "HOSTILE-WHOLE-TORSO",
                "beneath_zones": {
                    "chest": "HOSTILE-CHEST",
                    "midriff": "faded scrape scars across the ribs",
                },
            },
            "groin": {
                "garments": [{
                    "name": "travel shorts",
                    "state": "removed",
                }],
                "beneath": "AUTHORED-BARE-GROIN-DETAIL",
            },
        })}
    temp_db.wset(ctx.chat.id, "scene", sc)
    ctx.director_resolve = {
        "resolved_event": "The top rides up, exposing the midriff.",
        "dialogue_log": [], "dialogue_order": [],
        "state_diff": {"attire": {"Hinami": {
            "coverage": {"tank top": {"torso": ["chest"]}},
        }}},
    }
    result = perception.perception_outcome(ctx, nonce=0)

    final_view = result["views"][str(moon_id)]
    assert "faded scrape scars" in final_view
    assert "AUTHORED-BARE-GROIN-DETAIL" in final_view
    # The still-worn top protects the zone it still covers.
    assert "HOSTILE-WHOLE-TORSO" not in final_view
    assert "HOSTILE-CHEST" not in final_view
    assert "HOSTILE-CHEST" not in final_view
    player_view = result["views"]["player"]
    assert "Your exposed midriff" in player_view
    assert "faded scrape scars" in player_view
    assert "Your exposed groin" in player_view
    assert "AUTHORED-BARE-GROIN-DETAIL" in player_view
    assert "HOSTILE-WHOLE-TORSO" not in player_view
    assert "HOSTILE-CHEST" not in player_view
    stored = temp_db.wget(ctx.chat.id, "scene", {})
    stored_garment = stored["attire"]["Hinami"]["regions"]["torso"]["garments"][0]
    assert "covered_zones" not in stored_garment, "preview mutated durable state"


def test_body_detail_floor_does_not_dump_unforegrounded_anatomy():
    """Observer-safe does not mean relevant every beat. The floor preserves a
    detail the model foregrounded; it must not turn the perception view into a
    standing anatomy inventory."""
    import agents.perception as perception

    view = "You listen to rain tick softly against the window."
    projected = [{"body": "you", "regions": {
        "groin": "bare — HOSTILE-UNMENTIONED-ANATOMY",
    }}]

    restored, additions = perception._deliver_foreground_body_details(
        view, projected)

    assert restored == view
    assert additions == []
    assert "HOSTILE-UNMENTIONED-ANATOMY" not in restored


def test_body_detail_floor_accepts_natural_rephrasing():
    """The contract is semantic preservation, not verbatim card recitation."""
    import agents.perception as perception

    view = "Your bare stomach shows old scars along your ribs."
    projected = [{"body": "you", "regions": {
        "torso": (
            "chest: linen top; midriff: bare — "
            "A few faded scrape scars dot your ribs from travel."
        ),
    }}]

    restored, additions = perception._deliver_foreground_body_details(
        view, projected)

    assert restored == view
    assert additions == []


def test_body_detail_floor_rejects_live_generic_inner_thigh_overlap():
    """Chat 68's second reroll: `inner` + `thighs` are positional language,
    not evidence that any authored anatomical detail survived."""
    import agents.perception as perception

    view = (
        "You part your knees slightly, leaving a modest gap between your "
        "thighs. Her fingers press your inner thigh wider as she steps "
        "between your parted legs, flush against your bare entrance. Your "
        "groin registers steady pressure and shared warmth."
    )
    projected = [{"body": "you", "regions": {
        "groin": (
            "bare — A neat patch of copper-gold curls above her vulva, kept "
            "trimmed. Outer labia full and soft, slightly darker than her "
            "tanned skin. Inner folds pink and smooth, tucked within."
        ),
    }}]

    restored, additions = perception._deliver_foreground_body_details(
        view, projected)

    assert additions
    assert "copper-gold curls" in restored
    assert "vulva" in restored
    assert "Your exposed groin" in restored


# `test_perception_prompt_permits_rephrasing_but_forbids_generic_loss`
# lived here. It asserted paragraphs of the `perception` prompt, which no
# model has read since perception became deterministic; the prompt has now
# been deleted from the packs. The rephrasing rule it guarded is enforced
# by the composer's own admission code, which the rest of this file tests.


def test_introduction_quote_survives_but_bare_name_is_scrubbed(temp_db, monkeypatch):
    """Mid-beat introduction: the name spoken aloud is sensory signal and
    must stay verbatim inside the quote; recognition only flips at commit
    (validated_introductions), so the bare narrative mention in the SAME
    view is still unearned and must be scrubbed."""
    import agents.perception as perception

    ctx, moon_id, _ = _make_ctx(temp_db, known={})
    ctx.director_interpret["sequence"] = [{
        "type": "speech", "text": "My name is Hinami.", "volume": "normal",
        "tone": "", "visibility": "overt", "conceal_from": [],
    }]

    result = perception.perception_act(ctx, nonce=0)
    view = result["views"][str(moon_id)]

    assert "My name is Hinami." in view, (
        "legitimately heard speech must be preserved verbatim"
    )
    assert not _name_outside_quotes(view), (
        f"bare post-quote name mention survived the scrub: {view!r}"
    )


def test_micro_perception_gates_actor_name_by_recognition(temp_db):
    """loops.py's deterministic NPC-to-NPC delivery had NO recognition check
    at all -- canonical names flowed between mutually-unknown characters."""
    from agents.loops import deterministic_micro_perception
    from story.scene import get_scene

    ctx, moon_id, kessler_id = _make_ctx(
        temp_db, known={}, extra_char="Kessler")
    scene = get_scene(ctx.chat.id, ctx.chat)
    result = {"sequence": [
        {"type": "speech", "text": "Stay where you are.", "volume": "normal"},
        {"type": "action", "attempt": "raises a hand", "visibility": "overt"},
    ]}

    views, _ = deterministic_micro_perception(ctx, kessler_id, result, scene)
    moon_view = " ".join(views.get(moon_id) or [])
    assert "Stay where you are." in moon_view
    assert not _name_outside_quotes(moon_view, "kessler"), (
        f"canonical NPC name leaked between strangers: {moon_view!r}"
    )

    temp_db.wset(ctx.chat.id, "known", {"Dr. Moon": ["Kessler"]})
    views, _ = deterministic_micro_perception(ctx, kessler_id, result, scene)
    moon_view = " ".join(views.get(moon_id) or [])
    assert "Kessler" in moon_view, "recognized actor should be named"


def test_fallback_views_gate_speaker_name(temp_db):
    """The no-LLM fallback renderer must apply the same recognition gate."""
    from agents.common import _fallback_perception_views

    perceivers = [{"id": 7, "name": "Dr. Moon", "room": "room1",
                   "room_name": "Room 1", "room_notes": ""}]
    dlog = [{"speaker": "Hinami", "exact_quote": '"Hello there."',
             "speaker_room": "room1"}]

    views = _fallback_perception_views(perceivers, dlog, known={})
    assert "Hello there." in views["7"]
    assert not _name_outside_quotes(views["7"]), (
        f"fallback renderer leaked the speaker name: {views['7']!r}"
    )

    views = _fallback_perception_views(
        perceivers, dlog, known={"Dr. Moon": ["Hinami"]})
    assert "Hinami" in views["7"]


def test_single_quoted_spoken_name_survives_the_scrub():
    """A name introduced ALOUD this beat is legitimate sensory signal the
    hearer receives; it must survive the identity scrub verbatim. The
    perception model renders speech with single quotes ('...') as often as
    double, and the double-quote-only span guard let a self-introduction like
    'I-I'm Hinami' get scrubbed out of what the hearer plainly heard -- while a
    third-person narrative reference to the same stranger must still be
    anonymized."""
    from agents.common import _scrub_unknown_identities

    view = ("She mutters, 'Uhm... Hello?' then says clearly, 'I-I'm Hinami.' "
            "Hinami's tails puff as Hinami stands there.")
    out, leaked = _scrub_unknown_identities(
        view,
        allowed_forms=["Dr. Moon"],
        unknown_sources=[{"name": "Hinami",
                          "appearance": "a fox-eared young woman",
                          "aliases": []}],
    )
    # spoken self-introduction preserved
    assert "'I-I'm Hinami.'" in out
    # narrative references (possessive + bare) anonymized
    assert "Hinami's tails" not in out
    assert "as Hinami stands" not in out
    assert leaked == ["Hinami"]


def test_apostrophes_do_not_open_a_protected_span():
    """Contraction/possessive apostrophes ('She's', 'Hinami's') must not be
    mistaken for opening dialogue quotes, or a stranger's name in plain
    narration would slip through the scrub inside a bogus protected span."""
    from agents.common import _scrub_unknown_identities

    view = "She's watching. Hinami's tail sways as Hinami waits. No one speaks."
    out, _ = _scrub_unknown_identities(
        view,
        allowed_forms=["Dr. Moon"],
        unknown_sources=[{"name": "Hinami",
                          "appearance": "a fox-eared young woman",
                          "aliases": []}],
    )
    assert "Hinami" not in out
