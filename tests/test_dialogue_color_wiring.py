"""Getting a speaker's colour from the card to the transcript.

The design in one line: **store the speaker, never the colour.** The engine
already commits `dialogue_log` -- `{speaker, exact_quote}` per beat -- and
DIALOGUE FIDELITY requires each of those lines to appear in the narrator's
prose verbatim. So the transcript colours by finding a quote in the text it
was required to be in, and a colour change repaints three hundred turns of
backlog because nothing was ever baked into a turn.

What IS stored is one string per character per story: the host's pick, or ""
meaning "derive it from the card". That distinction is the whole feature --
"no choice" is the default, and it is not the same as "no colour".
"""

import json

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from core import db
from web import guest_access as guest
#: What SHEET's card derives to, written out rather than recomputed.
#: These assertions used to read `== auto_dialogue_color("Wren", SHEET)`,
#: which holds for any pair of agreeing wrong answers -- and held at all only
#: because the fixture cast has ONE member, so the collision spreading
#: `resolve_cast_colors` applies is the identity. A literal is the only form
#: of this assertion that can fail when the route stops deriving from the
#: card.
WREN_DERIVED = "#7e8df1"


SHEET = {
    "identity": {"name": "Wren"},
    "psychology": {"traits": [{"name": "patience", "strength": 0.9}]},
}


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        r = c.post("/api/auth/setup",
                   json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield c
    guest.reset_host_account()


def _story(client, name="Wren", sheet=None):
    # `sheet` is a dict here, not a JSON string: char_create normalizes the
    # raw object and falls back to a default card named "Unnamed" for
    # anything it cannot read -- which silently loses the psychology the
    # colour is derived from.
    ch = client.post("/api/characters", json={
        "name": name, "sheet": sheet or SHEET}).json()
    chat = client.post("/api/chats", json={"title": "t"}).json()
    cid = chat["id"]
    client.post(f"/api/chats/{cid}/characters", json={"char_id": ch["id"]})
    return cid, ch["id"]


def test_the_column_exists_and_defaults_to_derive(temp_db):
    """'' is the live default and means "follow the card". No backfill was
    possible or needed -- every pre-existing row wants exactly that, which is
    also why the migration is a bare ADD COLUMN."""
    assert db.SCHEMA_VERSION >= 29
    cols = {r["name"]: r for r in db.q("PRAGMA table_info(chat_chars)")}
    assert "dialogue_color" in cols
    assert cols["dialogue_color"]["dflt_value"] == "''"
    assert cols["dialogue_color"]["notnull"] == 1


def test_an_unpicked_character_is_coloured_from_their_card(client):
    cid, _ch = _story(client)
    body = client.get(f"/api/chats/{cid}").json()
    assert body["dialogue_colors"]["Wren"] == WREN_DERIVED
    assert body["participants"][0]["dialogue_color"] == ""


def test_an_unpromoted_charter_speaker_has_a_stable_transcript_colour(
        temp_db):
    import time
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("charter", "", time.time()))
    from world.charter_runtime import save_registry
    save_registry(cid, {"watch": {
        "naming": {
            "titles": {"ranks": {"captain": "Captain"}},
        },
        "key": "watch",
        "bodies": {"ysra": {
            "name": "Ysra Vale", "rank": "captain", "place": "gate",
            "dialogue_color": "#4A90E2",
        }},
    }})

    body = app_module.chat_get(cid)
    assert body["dialogue_colors"]["Captain Ysra Vale"] == "#4a90e2"
    assert body["dialogue_colors"]["Ysra Vale"] == "#4a90e2"


def test_a_pick_is_stored_and_wins(client):
    cid, ch = _story(client)
    r = client.put(f"/api/chats/{cid}/characters/{ch}/dialogue_color",
                   json={"color": "#FF8800"})
    assert r.status_code == 200, r.text
    assert r.json()["color"] == "#ff8800"
    assert r.json()["dialogue_colors"]["Wren"] == "#ff8800"

    body = client.get(f"/api/chats/{cid}").json()
    assert body["dialogue_colors"]["Wren"] == "#ff8800"
    assert body["participants"][0]["dialogue_color"] == "#ff8800"


def test_clearing_a_pick_returns_the_character_to_their_card(client):
    """"auto" must CLEAR rather than store the derived value -- store it and
    the colour silently stops following the card it came from."""
    cid, ch = _story(client)
    client.put(f"/api/chats/{cid}/characters/{ch}/dialogue_color",
               json={"color": "#ff8800"})
    r = client.put(f"/api/chats/{cid}/characters/{ch}/dialogue_color",
                   json={"color": ""})
    assert r.json()["color"] == ""
    assert r.json()["dialogue_colors"]["Wren"] == WREN_DERIVED


def test_an_unreadable_colour_is_refused_rather_than_stored(client):
    """A stored unreadable colour looks identical to an unset one on screen
    and is much harder to explain."""
    cid, ch = _story(client)
    r = client.put(f"/api/chats/{cid}/characters/{ch}/dialogue_color",
                   json={"color": "rgb(1,2,3)"})
    assert r.status_code == 400
    assert client.get(f"/api/chats/{cid}").json()[
        "participants"][0]["dialogue_color"] == ""


def test_a_colour_for_a_character_not_in_this_story_is_404(client):
    cid, _ch = _story(client)
    assert client.put(f"/api/chats/{cid}/characters/99999/dialogue_color",
                      json={"color": "#ff8800"}).status_code == 404


def test_the_speaker_index_rides_the_turn_and_stores_no_colour(client, temp_db):
    """The turn carries WHO SAID WHAT, never what colour it was. That is what
    makes a later colour change repaint the backlog, and what makes a prose
    edit unable to desync anything -- there is no offset to invalidate."""
    cid, _ch = _story(client)
    tid = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 0, "hi", 0.0))
    temp_db.qi(
        "INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
        (cid, tid, json.dumps({"dialogue_log": [
            {"speaker": "Wren", "exact_quote": '"I will go ahead of him."'}]})))

    turn = client.get(f"/api/chats/{cid}").json()["turns"][0]
    assert turn["speech"] == [
        {"speaker": "Wren", "quote": '"I will go ahead of him."'}]
    assert "color" not in json.dumps(turn)


def test_a_turn_with_no_dialogue_carries_an_empty_index(client, temp_db):
    cid, _ch = _story(client)
    temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 0, "hi", 0.0))
    assert client.get(f"/api/chats/{cid}").json()["turns"][0]["speech"] == []


def test_a_pick_survives_export_and_import(client):
    """chat_archive lists chat_chars columns explicitly on the way back in, so
    a new column that is not named there is silently dropped on every import."""
    cid, ch = _story(client)
    client.put(f"/api/chats/{cid}/characters/{ch}/dialogue_color",
               json={"color": "#ff8800"})

    archive = client.get(f"/api/chats/{cid}/export").json()
    r = client.post("/api/chats/import", json={"data": archive})
    assert r.status_code == 200, r.text
    new_cid = r.json().get("chat_id") or r.json().get("id")

    body = client.get(f"/api/chats/{new_cid}").json()
    assert body["participants"][0]["dialogue_color"] == "#ff8800"
    assert body["dialogue_colors"]["Wren"] == "#ff8800"


def test_a_pick_survives_branching(client, temp_db):
    """A cast that changed colour the moment you branched would read as a
    rendering fault, not as a new timeline."""
    cid, ch = _story(client)
    client.put(f"/api/chats/{cid}/characters/{ch}/dialogue_color",
               json={"color": "#ff8800"})
    temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 0, "hi", 0.0))
    tid = temp_db.q("SELECT id FROM turns WHERE chat_id=?", (cid,),
                    one=True)["id"]

    r = client.post(f"/api/turns/{tid}/branch", json={})
    assert r.status_code == 200, r.text
    new_cid = r.json().get("chat_id") or r.json().get("id")
    assert client.get(f"/api/chats/{new_cid}").json()[
        "participants"][0]["dialogue_color"] == "#ff8800"


class TestTheTintedUnitIsTheQuotedRegion:
    """Colouring the MATCHED SUBSTRING leaves parts of a line bare, twice over.

    Both seen on chat 70 turn 16. The stored quote has its marks stripped so
    it can survive matching at all, so tinting the match leaves the `"` at
    each end uncoloured. And the narrator legitimately merges several
    dialogue_log entries into one utterance -- "Right." and "Stars. After
    Kyoto..." came back inside a single pair of quotes -- so matching per
    entry tints two islands with bare punctuation between them.

    Colouring the region a match falls INSIDE fixes both at once: the whole
    line, marks included, however many logged entries it contains.
    """

    @staticmethod
    def _chat_js():
        from pathlib import Path
        return (Path(__file__).resolve().parents[1] / "static" / "js"
                / "chat.js").read_text(encoding="utf-8")

    def test_regions_are_scanned_and_include_both_marks(self):
        js = self._chat_js()
        assert "function quotedRegions(" in js
        block = js[js.index("function quotedRegions("):]
        block = block[:block.index("\n}")]
        # end is the closing mark's index PLUS ONE, or the span stops just
        # short of the quote it is supposed to include.
        assert "end: i + 1" in block

    def test_an_unclosed_quote_is_dropped_rather_than_guessed_at(self):
        js = self._chat_js()
        block = js[js.index("function quotedRegions("):]
        assert "unclosed final quote is dropped" in block[:block.index("\n}") + 400]

    def test_two_speakers_in_one_region_leaves_it_uncoloured(self):
        """Uncoloured beats coloured-as-the-wrong-person. Same rule as a quote
        that does not match at all."""
        js = self._chat_js()
        block = js[js.index("function speechSpans("):]
        block = block[:block.index("\n}\n")]
        assert "claimed.set(idx, null)" in block
        assert "if (!speaker) continue;" in js

    def test_terminal_punctuation_is_stripped_before_matching(self):
        """A dialogue tag changes it mechanically: the logged `Right then.`
        is rendered `"Right then," he answers`."""
        js = self._chat_js()
        block = js[js.index("function quoteBody("):]
        block = block[:block.index("\n}")]
        assert r"/[.,!?…;:]+$/" in block

    def test_nothing_reaches_an_html_parser(self):
        """The prose is model output. createTextNode/createElement only.

        SCOPED TO THE WHOLE PAINTING PATH, not to `paintProse` alone. Text
        emission moved out into `appendEmphasized` when inline markup landed,
        and this guard -- which had named one function -- went green on a
        `paintProse` that no longer created a single text node. A guard that
        names a function stops covering the thing it protects the moment the
        code is split, which is the failure mode this repository has now seen
        often enough to expect.
        """
        js = self._chat_js()
        block = js[js.index("function appendEmphasized("):]
        block = block[:block.index("function proseEl(")]
        assert "createTextNode" in block
        for parser_door in ("innerHTML", "outerHTML", "insertAdjacentHTML",
                            "document.write", "DOMParser"):
            assert parser_door not in block, parser_door


def test_two_unpicked_characters_are_pushed_apart(client):
    """The property the oracle could never see: `resolve_cast_colors` spreads
    derived hues in cast order, and with one member spreading is the identity
    -- so a route that skipped it entirely passed the old assertion."""
    from story.dialogue_colors import MIN_HUE_SEPARATION, _hue_of

    cid, _ch = _story(client)
    twin = client.post("/api/characters", json={
        "name": "Bram", "sheet": {"identity": {"name": "Bram"},
                                  "psychology": SHEET["psychology"]}}).json()
    client.post(f"/api/chats/{cid}/characters", json={"char_id": twin["id"]})

    colors = client.get(f"/api/chats/{cid}").json()["dialogue_colors"]
    assert colors["Wren"] == WREN_DERIVED
    # Identically authored, so they derive the SAME hue and must not render
    # as the same colour.
    assert colors["Bram"] != colors["Wren"]
    gap = abs(_hue_of(colors["Bram"]) - _hue_of(colors["Wren"])) % 360.0
    assert min(gap, 360.0 - gap) >= MIN_HUE_SEPARATION
