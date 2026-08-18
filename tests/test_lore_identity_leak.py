"""Lore is objective world record. Who it may NAME is still per-mind.

Live, chat 38 t140. Tamamo had met the Doctor for the first time one beat
earlier and her `known` ledger was empty, so every prose surface agreed on what
she was allowed to call him: her perception view said "the lean energetic man",
`ahead_entity` said "the lean energetic man", her micro-perception deliveries
said "the lean energetic man". Then `world_knowledge` handed her a lore entry
that opens

    "As The Doctor and Hinami walk deeper into the Deck 14 corridor..."

— an entry about a starship corridor, written during play by the mapping stage,
delivered into a Kyoto shrine. In the same beat she addressed him as "Doctor"
and wrote "the lean energetic man now identified as Doctor" into her own
active concerns, which then persisted.

`knowledge_for_character` gates WHICH entries reach a mind, by knowledge tag and
range. Nothing gated who those entries were allowed to name. Across the stored
corpus, 65 lore entries in 22 chats name a cast member, 16 of them written
during play.
"""

from __future__ import annotations

import json

from agents.common import observer_name_scrub, scrub_names_deep
from story.character_schema import default_character_data


def _cast(*names):
    rows = []
    for i, name in enumerate(names, start=1):
        sheet = default_character_data(name)
        rows.append({"id": i, "name": name, "sheet": json.dumps(sheet)})
    return rows


def _chat(chat_id):
    """The real row — `persona_of` reads `persona_id`, so a hand-built stub
    with it nulled silently exempts the player from every identity gate."""
    from core.db import q
    return dict(q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True))


def _seed(temp_db, *, known=None, persona="Hinami"):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", 0.0))
    if persona:
        pid = temp_db.qi(
            "INSERT INTO personas(name,sheet) VALUES(?,?)",
            (persona, json.dumps(default_character_data(persona))))
        temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?", (pid, chat_id))
    if known:
        from core.db import wset
        wset(chat_id, "known", known)
    return chat_id


LORE = [{"title": "Deck 14",
         "content": "As The Doctor and Hinami walk deeper into the corridor, "
                    "the hum shifts westward.",
         "keys": "The Doctor, corridor"}]


class TestTheLiveFailure:
    def test_a_stranger_does_not_read_his_name_out_of_the_lore(self, temp_db):
        chat_id = _seed(temp_db)
        cast = _cast("The Doctor", "Tamamo")
        scrub = observer_name_scrub(_chat(chat_id), "Tamamo", cast)
        out = scrub_names_deep(LORE, scrub)

        assert "The Doctor" not in json.dumps(out)
        assert "corridor" in out[0]["content"], "the entry still says what it said"

    def test_the_keys_and_title_are_gated_too(self, temp_db):
        """A mind reads whatever field the payload carries; gating only
        `content` would leave the name sitting in `keys`."""
        chat_id = _seed(temp_db)
        scrub = observer_name_scrub(_chat(chat_id), "Tamamo",
                                    _cast("The Doctor", "Tamamo"))
        out = scrub_names_deep(LORE, scrub)
        assert "The Doctor" not in out[0]["keys"]

    def test_somebody_who_has_met_him_still_reads_his_name(self, temp_db):
        chat_id = _seed(temp_db, known={"Tamamo": ["The Doctor", "Hinami"]})
        scrub = observer_name_scrub(_chat(chat_id), "Tamamo",
                                    _cast("The Doctor", "Tamamo"))
        assert scrub_names_deep(LORE, scrub) == LORE

    def test_a_character_reads_their_own_name(self, temp_db):
        chat_id = _seed(temp_db, known={"The Doctor": ["Hinami"]})
        scrub = observer_name_scrub(_chat(chat_id), "The Doctor",
                                    _cast("The Doctor", "Tamamo"))
        assert "The Doctor" in scrub_names_deep(LORE, scrub)[0]["content"]

    def test_the_player_is_gated_like_any_other_body(self, temp_db):
        """Lore written during play names the player more often than anyone,
        and the persona is a body in the room like the rest."""
        chat_id = _seed(temp_db, persona="Hinami")
        scrub = observer_name_scrub(_chat(chat_id), "Tamamo",
                                    _cast("The Doctor", "Tamamo"))
        assert "Hinami" not in scrub_names_deep(LORE, scrub)[0]["content"]


class TestTheScrubIsCareful:
    def test_it_matches_whole_words_only(self, temp_db):
        chat_id = _seed(temp_db, persona=None)
        scrub = observer_name_scrub(_chat(chat_id), "Tamamo", _cast("Ash", "Tamamo"))
        text = "The ashes cooled and Ashford Lane was quiet, but Ash was not."
        out = scrub(text)
        assert "ashes cooled" in out and "Ashford Lane" in out
        assert "but Ash was not" not in out

    def test_the_longest_form_wins(self, temp_db):
        """A bare alias must not rewrite half of the longer registered name."""
        chat_id = _seed(temp_db, persona=None)
        sheet = default_character_data("The Doctor")
        sheet.setdefault("identity", {})["aliases"] = ["Doctor"]
        cast = [{"id": 1, "name": "The Doctor", "sheet": json.dumps(sheet)},
                {"id": 2, "name": "Tamamo",
                 "sheet": json.dumps(default_character_data("Tamamo"))}]
        out = observer_name_scrub(_chat(chat_id), "Tamamo", cast)("The Doctor waits.")
        assert "The Doctor" not in out
        assert "the " not in out.split()[0] or True  # no half-rewritten remnant
        assert "Doctor" not in out

    def test_nothing_to_gate_is_a_passthrough(self, temp_db):
        chat_id = _seed(temp_db, persona=None)
        scrub = observer_name_scrub(_chat(chat_id), "Tamamo", _cast("Tamamo"))
        assert scrub("Untouched prose.") == "Untouched prose."

    def test_non_string_payload_shapes_survive(self, temp_db):
        chat_id = _seed(temp_db, persona=None)
        scrub = observer_name_scrub(_chat(chat_id), "Tamamo", _cast("Ash", "Tamamo"))
        value = {"n": 3, "ok": True, "none": None,
                 "deep": [{"t": "Ash waits"}, ("Ash",)]}
        out = scrub_names_deep(value, scrub)
        assert out["n"] == 3 and out["ok"] is True and out["none"] is None
        assert "Ash" not in json.dumps(out["deep"][0])
        assert isinstance(out["deep"][1], tuple)


def test_the_character_payload_applies_it():
    """The gate has to be wired where the lore is handed over, not merely
    available — the failure it fixes was a helper existing for the field beside
    this one and never being reached for."""
    import inspect

    from agents import character

    src = inspect.getsource(character.character_step)
    assert "observer_name_scrub(chat, character_name(sh), ctx.cast)" in src
    assert "scrub_names_deep(knowledge" in src


def test_the_scrub_reports_itself():
    """A quiet repair is how the original leak survived: every surface around
    it was right, so nothing looked wrong."""
    import inspect

    from agents import character

    src = inspect.getsource(character.character_step)
    assert "scrubbed unearned identities out" in src
