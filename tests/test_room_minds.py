"""The Writers' Room reads minds and writes only the world.

`inspect_minds` (`story/room_tools.py`) is the room's read of a cast
member's psychology as AUTHOR knowledge -- what a character wants and
believes, so the world the room places can invite it. Four claims, each a
test class:

* SHAPE: the drive is the effective one (a rupture-shifted drive shows
  shifted, with the former drives), the ledgers are the interior commit's
  own, projects carry probation and beats unserved, intentions merge the
  authored standing ones the way the character payload does, beliefs come
  by credence, and what the mind holds of other people is the leading claim.
* CAPS: every ledger is cut under a named `MIND_*` constant with the whole
  count beside it, and no prose field exceeds `MIND_TEXT_CHARS`.
* FIREWALL: the view is read by the AUTHOR seam alone. The handler is
  reachable through `run_tool` only; no module under `agents/` other than
  the Story Planner and the Dramaturge (which refuses every tool but lore)
  imports the facade, and no module of the pipeline -- `persist/`, `mind/`,
  `world/`, `core/`, `llm/`, `dressing/` -- names the tool; and the read
  leaves every row of the story byte-identical.
* FLOOR: no kind in `plot_packages.OPERATIONS` writes a mind, a memory, a
  relationship or a view; `director_note` writes nothing at all; and the
  naturalness guard above the floor is a CLAUSE in both packs plus the
  note's field text, never a check over prose.
"""
from __future__ import annotations

import ast
import json
import time
from pathlib import Path

import pytest

from story.room_tools import (
    MIND_BELIEFS_CAP, MIND_FORMER_CAP, MIND_INTENTIONS_CAP, MIND_LINE_CHARS,
    MIND_OTHERS_CAP, MIND_TEXT_CHARS, TOOL_INDEX, TOOLS, ToolError,
    cast_minds_summary, run_tool, tool_manifest)

ROOT = Path(__file__).resolve().parents[1]
PLAYER = "Wren Ashby"
LONG = "x" * (MIND_TEXT_CHARS + 80)


def _sheet(name, **psych):
    return {"name": name, "psychology": {
        "drive": {"essence": "Keep the harbour's ledgers honest.",
                  "expression": "Audits, quietly.",
                  "taboo": "Letting a false entry stand."},
        **psych,
    }, "initial_state": {"goals": [
        {"goal": "Find who forged the March entry.", "priority": 0.9},
        {"goal": "Keep the clerks' trust.", "priority": 0.4},
    ]}}


def _state(turn_idx=10, *, beliefs=None, others=None):
    beliefs = beliefs if beliefs is not None else [
        {"belief": "The harbourmaster is careless, not corrupt.", "confidence": 0.4,
         "protected": False, "authored": False},
        {"belief": "Numbers do not lie; people do.", "confidence": 0.95,
         "protected": True, "authored": True},
        {"belief": "Someone in the counting house is paid twice.", "confidence": 0.7,
         "protected": False, "authored": False},
    ]
    return {
        "active_state": {
            "goal": "Compare the March ledger against the warehouse tally.",
            "stress": {"activation": 0.61, "strain": 0.3, "load": 0.2,
                       "overloaded": False, "coping_mode": "method",
                       "memory_threat_bias": 0.0},
        },
        "interior": {
            "intentions": [
                {"id": "ia1", "intent": "Find who forged the March entry.",
                 "status": "active", "progress": 0.5, "authored": True,
                 "priority": 0.9, "last_progress_turn": 7},
                {"id": "i1", "intent": "Get the night watchman talking.",
                 "status": "dormant", "progress": 0.2, "formed_turn": 2,
                 "last_progress_turn": 3},
                {"id": "i2", "intent": "Read the warehouse tally tonight.",
                 "status": "active", "progress": 0.0, "formed_turn": 9,
                 "last_progress_turn": 9},
            ],
            "projects": [
                {"id": "p1", "project": "Clear the clerks' names before the assize.",
                 "about": "world", "satisfied_when": "the assize sits and names nobody",
                 "adopted_turn": 4, "probation": True, "last_served_turn": 6},
            ],
            "former_projects": [
                {"id": "pa1", "project": "Retire to the hill farm.", "why": "The ledgers "
                 "will not audit themselves.", "turn": 3, "end": "displaced"},
            ],
            "drive_strain": 0.7,
            "strain_log": [{"source": "contradiction", "why": "A forged page in "
                            "his own hand.", "delta": 0.25, "turn": 9}],
            "drive_rupture": {"turn": 9, "opened_turn": 9, "direction": "contradiction",
                              "why": "A forged page in his own hand.",
                              "window_expires": 12},
            "former_drives": [{"essence": "Keep the harbour's ledgers honest.",
                               "expression": "Audits, quietly.",
                               "taboo": "Letting a false entry stand.",
                               "ended_turn": 8, "by_event": "the forged page"}],
            "drive_override": {"essence": "Find out what he is capable of.",
                               "expression": "Tests himself against the rule.",
                               "taboo": "Pretending the page was not his.",
                               "since_turn": 8, "by_event": "the forged page"},
            "beliefs": beliefs,
            "associations": [],
            "project_review": {"turn": turn_idx, "why": "your task i1 closed this beat"},
        },
        "mind_models": others if others is not None else {
            "Tam Ashwell": {"hypotheses": [
                {"about_entity": "Tam Ashwell", "kind": "goal",
                 "claim": "Tam wants the audit to stall.", "confidence": 0.6,
                 "last_updated_turn": turn_idx},
                {"about_entity": "Tam Ashwell", "kind": "goal",
                 "claim": "Tam wants to be left alone.", "confidence": 0.3,
                 "last_updated_turn": turn_idx},
                {"about_entity": "Tam Ashwell", "kind": "trait",
                 "claim": "Tam is careful with paper.", "confidence": 0.5,
                 "last_updated_turn": turn_idx},
            ]},
        },
    }


def _story(db, *, turns=11):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Minds", "A port at dusk.", time.time()))
    db.wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone.", "adjacent": []}},
        "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}})
    for i in range(turns):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def _attach(db, cid, name, sheet, state, *, status="active", story_sheet=None):
    char_id = db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                    (name, json.dumps(sheet), time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) VALUES(?,?,?,?,?)",
          (cid, char_id, status, json.dumps(state),
           json.dumps(story_sheet) if story_sheet is not None else None))
    return char_id


@pytest.fixture
def story(temp_db):
    cid = _story(temp_db)
    _attach(temp_db, cid, "Orrin Vale", _sheet("Orrin Vale"), _state())
    return temp_db, cid


# ---------------------------------------------------------------------------
# SHAPE
# ---------------------------------------------------------------------------

class TestShape:
    def test_the_tool_is_in_the_table_and_the_manifest(self):
        tool = TOOL_INDEX["inspect_minds"]
        assert not tool.get("host_only") and not tool.get("long")
        assert tool["args"]["properties"] == {"name": {"type": "string"}}
        names = {t["name"] for t in tool_manifest()}
        assert "inspect_minds" in names
        # The description states the class the owner agreed to, in one line.
        assert "you cannot place a want or a belief" in tool["description"]

    def test_one_mind_per_present_cast_member(self, story):
        db, cid = story
        _attach(db, cid, "Away Person", _sheet("Away Person"), _state(),
                status="dormant")
        out = run_tool(cid, "inspect_minds")
        assert out["turn_idx"] == 10
        assert [m["name"] for m in out["minds"]] == ["Orrin Vale"]
        mind = out["minds"][0]
        assert set(mind) >= {"drive", "former_drives", "strain", "stress", "goal",
                             "projects", "former_projects", "intentions",
                             "beliefs", "about_others", "counts", "project_review"}

    def test_the_drive_is_the_effective_one_and_says_it_shifted(self, story):
        _db, cid = story
        mind = run_tool(cid, "inspect_minds")["minds"][0]
        assert mind["drive"]["essence"] == "Find out what he is capable of."
        assert mind["drive"]["shifted"] == {"since_turn": 8, "by_event": "the forged page"}
        assert mind["former_drives"] == [{
            "essence": "Keep the harbour's ledgers honest.", "ended_turn": 8,
            "by_event": "the forged page"}]

    def test_the_strain_ledger_is_read_against_the_engine_thresholds(self, story):
        from mind.affect import CRISIS_STRAIN_MIN, RUPTURE_STRAIN_MIN
        _db, cid = story
        strain = run_tool(cid, "inspect_minds")["minds"][0]["strain"]
        assert strain["drive_strain"] == 0.7
        assert strain["at_rupture_level"] is (0.7 >= RUPTURE_STRAIN_MIN)
        assert strain["crisis"] is (0.7 >= CRISIS_STRAIN_MIN)
        assert strain["rupture_window"] == {"direction": "contradiction",
                                            "why": "A forged page in his own hand.",
                                            "window_expires": 12}
        assert strain["last_moved_by"]["source"] == "contradiction"
        assert strain["last_moved_by"]["delta"] == 0.25

    def test_stress_is_the_resolved_row(self, story):
        _db, cid = story
        stress = run_tool(cid, "inspect_minds")["minds"][0]["stress"]
        assert stress == {"activation": 0.61, "strain": 0.3, "load": 0.2,
                          "overloaded": False, "coping_mode": "method"}

    def test_projects_carry_probation_and_beats_unserved(self, story):
        _db, cid = story
        mind = run_tool(cid, "inspect_minds")["minds"][0]
        assert mind["projects"] == [{
            "id": "p1", "aim": "Clear the clerks' names before the assize.",
            "about": "world", "satisfied_when": "the assize sits and names nobody",
            "status": "probation", "adopted_turn": 4, "last_served_turn": 6,
            "unserved_beats": 4}]
        assert mind["former_projects"] == [{
            "id": "pa1", "aim": "Retire to the hill farm.", "end": "displaced",
            "why": "The ledgers will not audit themselves.", "turn": 3}]
        assert mind["project_review"] == {"why": "your task i1 closed this beat",
                                          "turn": 10}

    def test_authored_projects_show_only_before_any_live_or_former_one(self, temp_db):
        cid = _story(temp_db)
        state = _state()
        state["interior"]["projects"] = []
        state["interior"]["former_projects"] = []
        _attach(temp_db, cid, "Orrin Vale",
                _sheet("Orrin Vale", projects=[{"project": "Map every cellar.",
                                                "about": "world"}]), state)
        mind = run_tool(cid, "inspect_minds")["minds"][0]
        assert [p["aim"] for p in mind["projects"]] == ["Map every cellar."]
        assert mind["projects"][0]["status"] == "established"   # authored: no probation

    def test_intentions_merge_the_authored_standing_ones_active_first(self, story):
        _db, cid = story
        intents = run_tool(cid, "inspect_minds")["minds"][0]["intentions"]
        ids = [i["id"] for i in intents]
        # ia1 restated by the live ledger (carries its progress); ia2 authored
        # and not restated, so present; active ones by priority (a formed
        # intention with none sorts after the authored ones); the dormant
        # one last.
        assert ids == ["ia1", "ia2", "i2", "i1"]
        by_id = {i["id"]: i for i in intents}
        assert by_id["ia1"]["progress"] == 0.5 and by_id["ia1"]["idle_beats"] == 3
        assert by_id["ia2"]["authored"] is True and "idle_beats" not in by_id["ia2"]
        assert by_id["i1"]["status"] == "dormant"

    def test_beliefs_come_by_credence(self, story):
        _db, cid = story
        beliefs = run_tool(cid, "inspect_minds")["minds"][0]["beliefs"]
        assert [b["confidence"] for b in beliefs] == [0.95, 0.7, 0.4]
        assert beliefs[0]["protected"] is True and beliefs[0]["authored"] is True

    def test_what_the_mind_holds_of_others_is_the_leading_claim(self, story):
        _db, cid = story
        others = run_tool(cid, "inspect_minds")["minds"][0]["about_others"]
        assert set(others) == {"Tam Ashwell"}
        assert others["Tam Ashwell"]["goal"]["claim"] == "Tam wants the audit to stall."
        assert set(others["Tam Ashwell"]) == {"goal", "trait"}
        assert "competitors" not in json.dumps(others)

    def test_the_per_story_card_resolves_over_the_reusable_one(self, temp_db):
        cid = _story(temp_db)
        story_sheet = _sheet("Orrin Vale")
        story_sheet["psychology"]["drive"]["essence"] = "Burn the ledgers."
        state = _state()
        state["interior"].pop("drive_override")
        _attach(temp_db, cid, "Orrin Vale", _sheet("Orrin Vale"), state,
                story_sheet=story_sheet)
        mind = run_tool(cid, "inspect_minds")["minds"][0]
        assert mind["drive"]["essence"] == "Burn the ledgers."
        assert "shifted" not in mind["drive"]

    def test_one_named_member_or_a_refusal(self, story):
        db, cid = story
        _attach(db, cid, "Second Person", _sheet("Second Person"), _state())
        out = run_tool(cid, "inspect_minds", {"name": "second person"})
        assert [m["name"] for m in out["minds"]] == ["Second Person"]
        with pytest.raises(ToolError):
            run_tool(cid, "inspect_minds", {"name": "Nobody Here"})

    def test_a_bare_state_reads_as_an_empty_mind_not_an_error(self, temp_db):
        cid = _story(temp_db)
        _attach(temp_db, cid, "Blank Slate", {"name": "Blank Slate"}, {})
        mind = run_tool(cid, "inspect_minds")["minds"][0]
        assert mind["drive"] == {"essence": "", "expression": "", "taboo": ""}
        assert mind["projects"] == [] and mind["beliefs"] == []
        assert mind["strain"]["drive_strain"] == 0.0
        assert mind["counts"]["beliefs"] == 0


# ---------------------------------------------------------------------------
# CAPS
# ---------------------------------------------------------------------------

class TestCaps:
    def test_every_cap_is_named_and_owner_visible(self):
        source = (ROOT / "story" / "room_tools.py").read_text(encoding="utf-8")
        assert "LIMITS THE OWNER SHOULD KNOW ABOUT (`inspect_minds`)" in source
        for name in ("MIND_BELIEFS_CAP", "MIND_INTENTIONS_CAP", "MIND_FORMER_CAP",
                     "MIND_OTHERS_CAP", "MIND_TEXT_CHARS", "MIND_LINE_CHARS"):
            assert f"\n{name} = " in source

    def test_ledgers_are_cut_and_the_whole_count_stands_beside(self, temp_db):
        cid = _story(temp_db)
        beliefs = [{"belief": f"Belief number {n}.", "confidence": n / 100.0}
                   for n in range(MIND_BELIEFS_CAP + 5)]
        state = _state(beliefs=beliefs, others={
            f"Person {n}": {"hypotheses": [{"about_entity": f"Person {n}", "kind": "goal",
                                            "claim": "wants something",
                                            "confidence": 0.5, "last_updated_turn": 10}]}
            for n in range(MIND_OTHERS_CAP + 2)})
        state["interior"]["intentions"] = [
            {"id": f"i{n}", "intent": f"Intention {n}.", "status": "active",
             "progress": 0.0, "formed_turn": 1} for n in range(MIND_INTENTIONS_CAP + 3)]
        state["interior"]["former_projects"] = [
            {"id": f"p{n}", "project": f"Project {n}.", "why": "w", "turn": n,
             "end": "displaced"} for n in range(MIND_FORMER_CAP + 2)]
        state["interior"]["former_drives"] = [
            {"essence": f"Drive {n}", "ended_turn": n, "by_event": "e"}
            for n in range(MIND_FORMER_CAP + 2)]
        _attach(temp_db, cid, "Orrin Vale", _sheet("Orrin Vale"), state)
        mind = run_tool(cid, "inspect_minds")["minds"][0]
        assert len(mind["beliefs"]) == MIND_BELIEFS_CAP
        assert mind["beliefs"][0]["confidence"] == (MIND_BELIEFS_CAP + 4) / 100.0
        assert mind["counts"]["beliefs"] == MIND_BELIEFS_CAP + 5
        # Two authored standing intentions join the ledger's; the cap holds.
        assert len(mind["intentions"]) == MIND_INTENTIONS_CAP
        assert mind["counts"]["intentions"] == MIND_INTENTIONS_CAP + 3 + 2
        assert len(mind["former_projects"]) == MIND_FORMER_CAP
        assert mind["counts"]["former_projects"] == MIND_FORMER_CAP + 2
        assert len(mind["former_drives"]) == MIND_FORMER_CAP
        assert mind["counts"]["former_drives"] == MIND_FORMER_CAP + 2
        assert len(mind["about_others"]) == MIND_OTHERS_CAP
        assert mind["counts"]["others_modelled"] == MIND_OTHERS_CAP + 2

    def test_no_prose_field_exceeds_the_text_cap(self, temp_db):
        cid = _story(temp_db)
        sheet = _sheet("Orrin Vale")
        sheet["psychology"]["drive"] = {"essence": LONG, "expression": LONG, "taboo": LONG}
        state = _state(beliefs=[{"belief": LONG, "confidence": 0.5}])
        state["interior"].pop("drive_override")
        state["interior"]["projects"][0]["project"] = LONG
        state["interior"]["intentions"][0]["intent"] = LONG
        state["active_state"]["goal"] = LONG
        _attach(temp_db, cid, "Orrin Vale", sheet, state)
        mind = run_tool(cid, "inspect_minds")["minds"][0]

        def prose(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for v in value.values():
                    yield from prose(v)
            elif isinstance(value, list):
                for v in value:
                    yield from prose(v)
        longest = max(len(s) for s in prose(mind))
        assert longest <= MIND_TEXT_CHARS
        assert mind["drive"]["essence"].endswith("…")
        assert mind["goal"].endswith("…")

    def test_the_summary_is_one_line_per_member_under_the_line_cap(self, temp_db):
        cid = _story(temp_db)
        sheet = _sheet("Orrin Vale")
        sheet["psychology"]["drive"]["essence"] = LONG
        state = _state()
        state["interior"].pop("drive_override")
        state["interior"]["projects"][0]["project"] = LONG
        _attach(temp_db, cid, "Orrin Vale", sheet, state)
        _attach(temp_db, cid, "Away Person", _sheet("Away Person"), _state(),
                status="dormant")
        lines = cast_minds_summary(cid, None)
        assert [line["name"] for line in lines] == ["Orrin Vale"]
        assert set(lines[0]) == {"name", "drive", "projects"}
        assert len(lines[0]["drive"]) <= MIND_LINE_CHARS
        assert all(len(p) <= MIND_LINE_CHARS for p in lines[0]["projects"])
        assert cast_minds_summary(_story(temp_db), None) == []


# ---------------------------------------------------------------------------
# FIREWALL: read by the author seam alone
# ---------------------------------------------------------------------------

#: The author seam: the two modules under `agents/` that may import the
#: facade. The Dramaturge refuses every tool but lore (`LORE_TOOLS`).
AUTHOR_SEAM = {"agents/story_planner.py", "agents/dramaturge.py"}
#: The pipeline's packages, none of which may name the facade or the tool.
PIPELINE_PACKAGES = ("agents", "persist", "mind", "world", "core", "llm", "dressing")
MIND_TOOL_NAMES = {"inspect_minds", "cast_minds_summary", "_t_inspect_minds",
                   "_mind_of"}


def _module_paths():
    for package in PIPELINE_PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            yield path


def _imports_facade(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "story.room_tools" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "story.room_tools":
                return True
            if node.module == "story" and any(a.name == "room_tools" for a in node.names):
                return True
    return False


def _names_the_tool(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in MIND_TOOL_NAMES:
            return node.id
        if isinstance(node, ast.Attribute) and node.attr in MIND_TOOL_NAMES:
            return node.attr
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value in MIND_TOOL_NAMES:
            return node.value
    return None


class TestFirewall:
    def test_no_pipeline_module_imports_the_facade_or_names_the_tool(self):
        """The exact claim: under every pipeline package, the facade is
        imported by the author seam alone, and the tool is named nowhere
        (not as a name, an attribute or a string a loop could dispatch on)."""
        importers, namers = [], []
        for path in _module_paths():
            rel = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if _imports_facade(tree) and rel not in AUTHOR_SEAM:
                importers.append(rel)
            if rel not in AUTHOR_SEAM and _names_the_tool(tree):
                namers.append(rel)
        assert not importers, importers
        assert not namers, namers

    def test_the_author_seam_names_only_the_summary_and_run_tool(self):
        """The Planner reaches the tool through `run_tool` and the payload
        line through `cast_minds_summary`; the handler itself is named by
        the facade's own table and nothing else in the repository."""
        planner = ast.parse((ROOT / "agents" / "story_planner.py").read_text("utf-8"))
        assert _names_the_tool(planner) == "cast_minds_summary"
        for path in ROOT.rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith((".", "tests/")) or "/." in rel or rel == "story/room_tools.py":
                continue
            source = path.read_text(encoding="utf-8")
            assert "_t_inspect_minds" not in source, rel
            assert "_mind_of(" not in source, rel

    def test_the_dramaturge_refuses_it(self):
        from agents.dramaturge import LORE_TOOLS
        assert "inspect_minds" not in LORE_TOOLS

    def test_the_handler_is_reachable_through_run_tool_alone(self):
        tool = TOOL_INDEX["inspect_minds"]
        assert tool["handler"].__name__ == "_t_inspect_minds"
        assert sum(1 for t in TOOLS if t["handler"] is tool["handler"]) == 1
        # And it is not a name the facade exports for a caller to bypass the
        # table with.
        import story.room_tools as facade
        public = [n for n in dir(facade) if not n.startswith("_")]
        assert "inspect_minds" not in public

    def test_reading_leaves_every_row_byte_identical(self, story):
        db, cid = story

        def snapshot():
            return {
                "chars": [dict(r) for r in db.q(
                    "SELECT char_id, status, state, sheet FROM chat_chars WHERE chat_id=?",
                    (cid,))],
                "world": [dict(r) for r in db.q(
                    "SELECT key, value FROM world WHERE chat_id=? ORDER BY key", (cid,))],
                "memories": [dict(r) for r in db.q(
                    "SELECT * FROM memories WHERE chat_id=?", (cid,))],
                "events": [dict(r) for r in db.q(
                    "SELECT * FROM events WHERE chat_id=?", (cid,))],
            }
        before = snapshot()
        run_tool(cid, "inspect_minds")
        run_tool(cid, "inspect_minds", {"name": "Orrin Vale"})
        cast_minds_summary(cid, None)
        assert snapshot() == before

    def test_the_planner_payload_carries_the_summary_line(self, story):
        from agents import story_planner as sp
        _db, cid = story
        payload = sp._payload(cid, None, text="hello", task=None, transcript=[],
                              step=1, calls_left=5, seconds_left=30.0, turn_idx=10)
        assert payload["minds"] == cast_minds_summary(cid, None)
        assert payload["minds"][0]["drive"] == "Find out what he is capable of."


# ---------------------------------------------------------------------------
# FLOOR: no operation writes a mind; the guard above it is a clause
# ---------------------------------------------------------------------------

class TestFloor:
    def test_every_kind_is_over_a_world_or_author_seam(self):
        from story.plot_packages import OPERATION_FIELDS, OPERATIONS
        assert set(OPERATIONS) == set(OPERATION_FIELDS)
        for kind, spec in OPERATIONS.items():
            assert callable(spec["shape"]) and callable(spec["preview"]), kind
            assert callable(spec.get("apply") or spec.get("prepare")), kind
            seam = spec["seam"]
            # Every seam is a world or author module; none is a mind's ledger,
            # a memory writer, a relationship or a perception view.
            assert not seam.startswith(("mind.memory", "mind.psychology",
                                        "mind.affect", "mind.theory_of_mind",
                                        "agents.perception", "agents.composer",
                                        "agents.character")), (kind, seam)

    def test_director_note_applies_nothing(self):
        """The note's apply path makes no call at all: it returns the turn
        it is delivered from, and the Director READS it off the package."""
        from story import plot_packages as pp
        tree = ast.parse((ROOT / "story" / "plot_packages.py").read_text("utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_apply_director_note")
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
        assert [ast.unparse(c.func) for c in calls] == ["int"]
        assert pp.OPERATIONS["director_note"]["apply"] is pp._apply_director_note

    def test_a_published_note_changes_no_mind(self, story):
        from story.plot_packages import (
            activate_due_packages, active_director_notes, draft_operation,
            get_package, new_package, publish_package, validate_package)
        db, cid = story

        def snapshot():
            return {
                "chars": [dict(r) for r in db.q(
                    "SELECT char_id, status, state, sheet FROM chat_chars WHERE chat_id=?",
                    (cid,))],
                "memories": [dict(r) for r in db.q(
                    "SELECT * FROM memories WHERE chat_id=?", (cid,))],
                "mind_rows": [dict(r) for r in db.q(
                    "SELECT key, value FROM world WHERE chat_id=? AND key NOT IN "
                    "('plot_packages') AND key NOT LIKE 'plot_%' ORDER BY key", (cid,))],
            }
        before = snapshot()
        pkg = new_package(cid, title="The ledger", premise="p")
        draft_operation(cid, pkg["uid"], {
            "op": "director_note",
            "text": "The forged page under the counting-house floor is the March "
                    "entry Orrin is auditing; it is there for him to find."})
        validate_package(cid, pkg["uid"])
        publish_package(cid, pkg["uid"],
                        expected_revision=get_package(cid, pkg["uid"])["revision"])
        activate_due_packages(cid, 11)
        assert snapshot() == before
        notes = active_director_notes(cid, None, 11)
        assert any("forged page" in n for n in notes)
        # The mind is unchanged in what the room reads too.
        mind = run_tool(cid, "inspect_minds")["minds"][0]
        assert "forged page under" not in json.dumps(mind)

    def test_the_guard_is_a_clause_in_both_packs_and_the_field_text(self):
        """No code reads the note's prose for what a character will think,
        feel or decide (the repo rule on guards over free text); the class
        is stated once, in every place the model reads."""
        from story.plot_packages import OPERATION_FIELDS
        text = OPERATION_FIELDS["director_note"]["text"]
        assert "never how a character will take it" in text
        for language in ("en", "ja"):
            card = (ROOT / "language_packs" / language / "cards" / "system_prompts"
                    / "prompts" / "story_planner.txt").read_text(encoding="utf-8")
            assert "inspect_minds" in card
            assert "director_note" in card
        en = (ROOT / "language_packs" / "en" / "cards" / "system_prompts"
              / "prompts" / "story_planner.txt").read_text(encoding="utf-8")
        assert "what a character MEETS" in en and "what a character CONCLUDES" in en
        ja = (ROOT / "language_packs" / "ja" / "cards" / "system_prompts"
              / "prompts" / "story_planner.txt").read_text(encoding="utf-8")
        assert "「出会う」" in ja and "「結論する」" in ja
        ledger = json.loads((ROOT / "tests" / "data" / "prompt_cards_presplit"
                             / "EXPECTED_DIVERGENCE.json").read_text("utf-8"))
        assert "inspect_minds" in ledger["prompts.story_planner"]

    def test_no_prose_field_is_read_by_a_word_list(self):
        """The one deterministic thing the floor does with a note's text is
        measure it: `_shape_director_note` normalises whitespace and refuses
        an empty or over-long note, and compiles no pattern over it."""
        tree = ast.parse((ROOT / "story" / "plot_packages.py").read_text("utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_shape_director_note")
        called = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
        assert not any(name.startswith("re.") or name.endswith((".search", ".match",
                                                                 ".findall"))
                       for name in called), called
