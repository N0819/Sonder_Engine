"""The encoder's repair continues the draft's own request, read from cache.

Measured on the Brackwater run (chat 166, 30 kept beats): the encoder
(google/gemini-3.8-flash through OpenRouter) was 41-52% of the run's spend and
read 0 cached tokens in 224 calls; its repair calls were 85 of 142 kept encoder
calls and 51% of its input, each re-sending a world byte-identical to the
draft call's under a sheet of its own. Probed 2026-10-08 on that chat's
captured requests: a breakpoint on the LAST message writes nothing; one with a
message after it writes the prefix, billed $0.1167/M on the writing call
itself; a later call sending the same messages that far reads them at
$0.075/M -- against $0.75/M uncached.

So, where the route caches a prefix (`providers.cache_breakpoint_honoured`):
the draft call's user message is a cache breakpoint with one line after it
(`encoder_cue`), and each repair is that request continued -- its system and
user messages byte-identical, then the cue, the draft as the answer it was,
and the repair's turn. Everywhere else every request is exactly what it was.
"""

from __future__ import annotations

import json

import pytest

import agents.director as director
from agents import director_repair as repair
from llm import decisions, llm_quality, providers
from llm.prompts import encoder_sheet_additions, prose_contract_text
from llm.providers import ToolsUnsupported
from core.pipeline_context import current_exchange_sink

from tests.director_fakes import _action_interp, _make_ctx

GEMINI = "google/gemini-3.8-flash"
OPENROUTER = {"id": 3, "name": "openrouter", "kind": "openrouter",
              "base_url": "http://openrouter.invalid/api/v1", "api_key": "k"}
NANOGPT = {"id": 1, "name": "nanogpt", "kind": "nanogpt",
           "base_url": "http://nanogpt.invalid/api/v1", "api_key": "k"}
GENERIC = {"id": 6, "name": "Fireworks", "kind": "generic",
           "base_url": "http://fireworks.invalid/v1", "api_key": "k"}


def _is_marked(message):
    content = message["content"]
    return (isinstance(content, list) and len(content) == 1
            and content[0].get("cache_control") == {"type": "ephemeral"})


# ---- which routes honour a breakpoint ---------------------------------------

@pytest.mark.parametrize("prov, model, honoured", [
    (OPENROUTER, GEMINI, True),
    (OPENROUTER, "anthropic/claude-sonnet-4", True),
    (NANOGPT, "anthropic/claude-sonnet-4", True),
    # nanogpt documents implicit caching for Gemini, explicit for Claude only.
    (NANOGPT, GEMINI, False),
    (GENERIC, GEMINI, False),
    # A family that caches implicitly is sent no marker anywhere.
    (OPENROUTER, "z-ai/glm-5.2", False),
    (OPENROUTER, "deepseek/deepseek-v4.1-flash", False),
    # A native connection builds no OpenAI-style body.
    ({"kind": "anthropic", "name": "claude"}, "claude-sonnet-4", False),
    ({"kind": "claude_cli", "name": "claude_cli"}, "claude-sonnet-4", False),
])
def test_a_breakpoint_goes_only_where_the_route_builds_a_cache_from_it(
        temp_db, prov, model, honoured):
    assert providers.cache_breakpoint_honoured(prov, model) is honoured


def test_the_hosts_cache_switches_hold_for_gemini_too(temp_db, monkeypatch):
    """One switch, as for Claude: the deny list outranks the built-in kind,
    the allow list opts a gateway in, the kill switch ends it all."""
    temp_db.set_setting("prompt_cache_deny", "openrouter")
    assert not providers.cache_breakpoint_honoured(OPENROUTER, GEMINI)
    temp_db.set_setting("prompt_cache_deny", "")
    temp_db.set_setting("prompt_cache_allow", "fireworks")
    assert providers.cache_breakpoint_honoured(GENERIC, GEMINI)
    monkeypatch.setattr(providers, "PROMPT_CACHE_ENABLED", False)
    assert not providers.cache_breakpoint_honoured(OPENROUTER, GEMINI)


# ---- the wire ----------------------------------------------------------------

class _Response:
    def __init__(self, content):
        self.status_code = 200
        self.text = ""
        self._lines = [("data: " + json.dumps(chunk)).encode("utf-8") for chunk in (
            {"model": GEMINI, "choices": [{"delta": {"content": content}}]},
            {"model": GEMINI, "choices": [{"delta": {}, "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        )] + [b"data: [DONE]"]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self):
        return iter(self._lines)

    def json(self):
        # What a plain (unstreamed) post reads: the write beside a call, where
        # the host has turned that on, which reports the prefix it wrote --
        # the count the next call's marker waits on.
        return {"model": GEMINI, "choices": [{"finish_reason": "length"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 1,
                          "prompt_tokens_details": {"cached_tokens": 9,
                                                    "cache_write_tokens": 9}}}

    def close(self):
        pass


class _Wire:
    """Records every body posted, and answers each from `answer(body)`."""

    def __init__(self, answer):
        self.answer = answer
        self.bodies = []

    def post(self, url, **kw):
        body = json.loads(json.dumps(kw.get("json")))
        self.bodies.append(body)
        return _Response(self.answer(body))


def _route(monkeypatch, prov, model, answer):
    wire = _Wire(answer)
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: [(prov, model, {})])
    monkeypatch.setattr(providers, "_session", lambda: wire)
    return wire


def _user_text(message):
    content = message["content"]
    return content if isinstance(content, str) else content[0]["text"]


def test_a_caller_that_asks_gets_its_user_message_marked_with_what_follows_it(
        temp_db, monkeypatch):
    wire = _route(monkeypatch, OPENROUTER, GEMINI, lambda body: "{}")
    after = [{"role": "user", "content": "Encode the beat in the message above."}]
    providers.chat_complete("encoder", "SHEET", '{"prose": "x"}', json_mode=False,
                            history=after, cache_user=True)
    messages = wire.bodies[0]["messages"]
    assert messages[0]["role"] == "system" and messages[0]["content"].startswith("SHEET")
    assert _is_marked(messages[1]) and messages[1]["content"][0]["text"] == '{"prose": "x"}'
    assert messages[2:] == after


@pytest.mark.parametrize("prov, model", [
    (NANOGPT, GEMINI), (GENERIC, GEMINI), (OPENROUTER, "z-ai/glm-5.2")])
def test_a_route_that_builds_no_cache_gets_the_plain_user_message(
        temp_db, monkeypatch, prov, model):
    wire = _route(monkeypatch, prov, model, lambda body: "{}")
    providers.chat_complete("encoder", "SHEET", '{"prose": "x"}', json_mode=False,
                            cache_user=True)
    assert wire.bodies[0]["messages"][1] == {"role": "user", "content": '{"prose": "x"}'}
    assert "cache_control" not in json.dumps(wire.bodies[0])


def test_the_user_message_stays_plain_unless_a_caller_asks(temp_db, monkeypatch):
    """A payload marked on its own is written once and never read back --
    the rule `test_only_the_system_prompt_is_ever_cache_marked` keeps."""
    wire = _route(monkeypatch, OPENROUTER, GEMINI, lambda body: "{}")
    providers.chat_complete("narrator", "SHEET", '{"scene": "varies"}', json_mode=False)
    assert "cache_control" not in json.dumps(wire.bodies[0])


def test_a_hosts_refusal_of_tools_does_not_refuse_plain_history(temp_db, monkeypatch):
    """`_NO_TOOLS` is about `tools`: a character's refused tool round on the
    same model must not cost the encoder its repair."""
    wire = _route(monkeypatch, OPENROUTER, GEMINI, lambda body: "{}")
    providers._NO_TOOLS.add((OPENROUTER["id"], GEMINI))
    try:
        after = [{"role": "assistant", "content": "{}"}, {"role": "user", "content": "go on"}]
        providers.chat_complete("encoder", "S", "U", json_mode=False, history=after)
        assert wire.bodies[0]["messages"][2:] == after
    finally:
        providers._NO_TOOLS.discard((OPENROUTER["id"], GEMINI))


@pytest.mark.parametrize("kind", ["anthropic", "claude_cli"])
def test_history_never_reaches_a_backend_that_would_drop_it(temp_db, kind):
    with pytest.raises(ToolsUnsupported):
        providers._chat_complete_once(
            "encoder", "S", "U", None, False, 100, None,
            resolved=(dict(OPENROUTER, kind=kind), "claude-sonnet-4", {}),
            history=[{"role": "user", "content": "go on"}])


# ---- the validated call ---------------------------------------------------------

class _Scripted:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, role, system, user, **kw):
        self.calls.append({"role": role, "system": system, "user": user, **kw})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


PREFIX = {"system": "DRAFT SHEET", "user": json.dumps({"prose": "p", "world_index": {"a": 1}}),
          "after": [{"role": "user", "content": "cue"},
                    {"role": "assistant", "content": '{"events": []}'},
                    {"role": "user", "content": "REPAIR TURN"}]}
ANSWER = json.dumps({"answers": [{"id": "j1", "none": "already encoded"}], "notes": []})


@pytest.fixture
def captured(monkeypatch):
    seen = []
    token = current_exchange_sink.set(seen.append)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    yield seen
    current_exchange_sink.reset(token)


def _ask(monkeypatch, answers, **kw):
    llm = _Scripted(answers)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    out = llm_quality.complete_validated_json(
        role="encoder", step_key="director_repair", system="REPAIR SHEET",
        payload={"jobs": [{"id": "j1"}]}, prefix=PREFIX, **kw)
    return out, llm


def test_a_prefix_is_what_the_first_call_and_every_reask_of_it_send(
        monkeypatch, captured):
    truncated = '{"answers": [{"id": "j1", "none": "already enc'
    out, llm = _ask(monkeypatch, [truncated, ANSWER])
    assert out["answers"][0]["id"] == "j1"
    assert len(llm.calls) == 2
    for call in llm.calls:
        assert call["system"] == "DRAFT SHEET" and call["user"] == PREFIX["user"]
        assert call["history"] == PREFIX["after"] and call["cache_user"] is True
    # The capture records what was sent: the user message's object, and
    # what followed it.
    assert captured[0]["system"] == "DRAFT SHEET"
    assert captured[0]["payload"]["world_index"] == {"a": 1}
    assert captured[0]["payload"]["messages_after"] == PREFIX["after"]
    assert captured[1]["payload"]["messages_after"] == PREFIX["after"]


def test_the_rungs_that_rebuild_send_the_calls_own_sheet_and_payload(
        monkeypatch, captured):
    """A rebuild continues nothing: it is the repair sheet and the wrapped
    payload, exactly as before the prefix existed."""
    # The broken answer, the cheap field patch's empty reply, the rebuild.
    out, llm = _ask(monkeypatch, ['{"answers": "not a list"}', "{}", ANSWER])
    assert out["answers"][0]["id"] == "j1"
    assert [call["role"] for call in llm.calls] == ["encoder", "repair", "encoder"]
    rebuild = llm.calls[2]
    assert rebuild["system"].startswith("REPAIR SHEET")
    assert "history" not in rebuild and "cache_user" not in rebuild
    assert json.loads(rebuild["user"])["original_request"] == {"jobs": [{"id": "j1"}]}


def test_a_route_that_takes_no_prefix_is_asked_the_plain_request(
        monkeypatch, captured):
    out, llm = _ask(monkeypatch, [ToolsUnsupported("no history here"), ANSWER])
    assert out["answers"][0]["id"] == "j1"
    plain = llm.calls[1]
    assert plain["system"] == "REPAIR SHEET" and "history" not in plain
    assert json.loads(plain["user"]) == {"jobs": [{"id": "j1"}]}
    assert [row["ok"] for row in captured] == [False, True]


# ---- the repair's turn -------------------------------------------------------------

def test_a_repair_turn_carries_what_it_is_asked_and_only_the_slices_that_differ(
        temp_db, monkeypatch):
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: [(OPENROUTER, GEMINI, {})])
    held = {"system": "DRAFT SHEET",
            "user": json.dumps({"prose": "Mara climbs.", "world_index": {"here": "hall"},
                                "rooms": {"hall": {"adjacent": []}},
                                "granted_tools": ["positions"]}),
            "after": [{"role": "user", "content": "cue"}],
            "answer": '{"events": []}', "channels": ["positions"], "parts": []}
    payload = {"prose": "[s1] Mara climbs.", "world_index": {"here": "hall"},
               "rooms": {"hall": "Hall"}, "granted_tools": ["positions"],
               "draft": [], "minted": {}, "jobs": [{"id": "j1"}],
               "places_authored_elsewhere": False}
    prefix = repair.continuation(held, payload, ["positions"], [], "en")
    assert prefix["system"] == "DRAFT SHEET" and prefix["user"] == held["user"]
    cue, answer, turn = prefix["after"]
    assert cue == held["after"][0]
    assert answer == {"role": "assistant", "content": '{"events": []}'}
    text = turn["content"]
    assert text.startswith(prose_contract_text("encoder_repair_continues", "en").strip())
    assert prose_contract_text("encoder_repair", "en").strip() in text
    sent = json.loads(text[text.rindex("\n\n{") + 2:])
    # What the repair is asked and may write rides every turn; a slice its
    # grant shapes differently rides along; one shown the same above does not.
    assert set(sent) == {"prose", "granted_tools", "draft", "minted", "jobs", "rooms",
                         "places_authored_elsewhere"}


def test_nothing_is_continued_off_a_caching_route_or_without_a_held_request(
        temp_db, monkeypatch):
    held = {"system": "S", "user": "{}", "after": [], "answer": "{}"}
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: [(NANOGPT, GEMINI, {})])
    assert repair.continuation(held, {"jobs": []}, [], [], "en") is None
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: [(OPENROUTER, GEMINI, {})])
    assert repair.continuation(None, {"jobs": []}, [], [], "en") is None


def test_a_repair_turn_is_handed_the_encoder_pieces_the_drafts_sheet_lacked(temp_db):
    """A record being mended ships whole, parts and all, and a repair that
    mints holds `positions`: the draft's sheet may lack both."""
    assert encoder_sheet_additions(["entities"], [], ["entities"], [], "en") == ""
    extra = encoder_sheet_additions(["entities", "positions"], ["entities__new"],
                                    ["entities"], [], "en")
    assert "POSITIONS:" in extra and "A NEW PERSON OR THING" in extra
    assert "THINGS: entities records" not in extra


# ---- end to end: the draft call and its repair, on the wire ------------------------

PROSE = ("Mara climbs the stair into the lamp room. "
         "\"The lamp is cold,\" she calls down.")
DRAFT = {"events": [
    {"source_entity_id": "character:1", "source_event_id": "x",
     "event": "Mara climbs the stair into the lamp room.", "speech": False,
     "item_names": ["Mara"], "commitment": "asserted",
     "transforms": [{"item": "Mara", "patch": {"positions": {"Mara": "lamp_room"}}}]},
], "missing_tools": [], "missing_referents": [], "notes": []}
RECOVERED = {"answers": [{"id": "j1", "after": "e1", "events": [
    {"source_entity_id": "character:1", "source_event_id": "x",
     "event": "The lamp is cold.", "speech": True, "targets": ["The Stranger"],
     "volume": "loud", "item_names": ["Mara"], "commitment": "asserted",
     "transforms": []}]}], "notes": []}


def _answer(body):
    messages = body["messages"]
    if any(m["role"] == "assistant" for m in messages):
        return json.dumps(RECOVERED)
    sent = json.loads(_user_text(messages[1]))
    if "jobs" in sent:
        return json.dumps(RECOVERED)
    if "granted_tools" in sent:
        return json.dumps(DRAFT)
    return json.dumps({"prose": PROSE})


def _jev(state, questions):
    out = {}
    for key in questions:
        if key == "ev:s2":
            out[key] = {"type": "noul", "noul": 0.96}
        elif key.startswith(("ev:", "led:", "bad:")):
            out[key] = {"type": "noul", "noul": 0.03}
        else:
            out[key] = {"type": "noul", "noul": 0.95 if key in ("positions", "poses") else 0.02}
    return out


def _resolve(temp_db, monkeypatch, prov, model):
    temp_db.set_setting(repair.REPAIR_SETTING, "1")
    temp_db.set_setting("prose_contract_room_agent", "0")
    monkeypatch.setattr(decisions, "OVERRIDE", _jev)
    wire = _route(monkeypatch, prov, model, _answer)
    out = director.director_resolve(_make_ctx(temp_db, interp=_action_interp()), nonce=0)
    return out, wire


def _by_kind(wire):
    """The draft calls and the repair calls on the wire; a cache write beside
    the draft (unstreamed, `providers._write_prefix_beside`) is neither."""
    calls = [b for b in wire.bodies if b.get("stream")]
    draft = [b for b in calls if not any(m["role"] == "assistant" for m in b["messages"])
             and "granted_tools" in json.loads(_user_text(b["messages"][1]))
             and "jobs" not in json.loads(_user_text(b["messages"][1]))]
    repairs = [b for b in calls if b not in draft
               and (any(m["role"] == "assistant" for m in b["messages"])
                    or "jobs" in json.loads(_user_text(b["messages"][1])))]
    return draft, repairs


def test_the_repair_continues_the_draft_request_byte_for_byte(temp_db, monkeypatch):
    out, wire = _resolve(temp_db, monkeypatch, OPENROUTER, GEMINI)
    (draft,), (fix,) = _by_kind(wire)
    # The draft call: its payload a breakpoint, one line after it.
    assert len(draft["messages"]) == 3 and _is_marked(draft["messages"][1])
    assert draft["messages"][2] == {"role": "user",
                                    "content": prose_contract_text("encoder_cue", "en")}
    # The repair: the draft's request byte for byte, its answer, the turn.
    assert len(fix["messages"]) == 5
    assert json.dumps(fix["messages"][:3]) == json.dumps(draft["messages"][:3])
    assert fix["messages"][3]["role"] == "assistant"
    assert json.loads(fix["messages"][3]["content"])["events"][0]["event"] == \
        "Mara climbs the stair into the lamp room."
    turn = fix["messages"][4]
    assert turn["role"] == "user" and "REPAIR." in turn["content"]
    sent = json.loads(turn["content"][turn["content"].rindex("\n\n{") + 2:])
    # The jobs and the grant are today's.
    assert sent["jobs"] == [{"id": "j1", "kind": "event", "sentences": ["s2"],
                             "text": "\"The lamp is cold,\" she calls down."}]
    assert sent["prose"].startswith("[s1] Mara climbs")
    assert sent["draft"][0]["ref"] == "e1" and "granted_tools" in sent
    # And the answer it got is applied as before.
    assert [row["chrono_id"] for row in out["ledgers"]] == [1, 2]
    assert out["orchestration"]["prose_contract"]["repair"]["applied"]["applied"] == ["j1"]


def test_where_the_host_writes_beside_the_repair_continues_the_written_request(
        temp_db, monkeypatch):
    """Where the host has the cache written beside the call
    (`prompt_cache_write_beside`, pinned in
    tests/test_a_cache_write_rides_beside_the_call_only_where_the_host_asks.py),
    the draft goes plain and the breakpoint rides on the write beside it --
    and the repair continues THAT request byte for byte, which is what the
    cache holds."""
    temp_db.set_setting("prompt_cache_write_beside", "openrouter")
    # In line, so the wire holds the write in order; the engine runs it on a
    # thread of its own.
    monkeypatch.setattr(providers, "_run_beside", lambda fn: fn())
    monkeypatch.setattr(providers, "_PREFIX_WRITTEN", {})
    monkeypatch.setattr(providers, "_BESIDE_REFUSED", set())
    out, wire = _resolve(temp_db, monkeypatch, OPENROUTER, GEMINI)
    (draft,), (fix,) = _by_kind(wire)
    (write,) = [b for b in wire.bodies if not b.get("stream")]
    # The write: the draft's request, its payload the breakpoint with one
    # line after it, cut short...
    assert len(write["messages"]) == 3 and _is_marked(write["messages"][1])
    assert write["messages"][2] == {"role": "user",
                                    "content": prose_contract_text("encoder_cue", "en")}
    assert write["max_tokens"] == providers.CACHE_WRITE_BESIDE_TOKENS
    # ...while the draft itself goes plain, its messages otherwise the same.
    assert draft["messages"][1] == {"role": "user",
                                    "content": write["messages"][1]["content"][0]["text"]}
    assert draft["messages"][0] == write["messages"][0]
    assert draft["messages"][2:] == write["messages"][2:]
    # The repair: the written request byte for byte, the draft's answer, the turn.
    assert len(fix["messages"]) == 5
    assert json.dumps(fix["messages"][:3]) == json.dumps(write["messages"][:3])
    assert fix["messages"][3]["role"] == "assistant"
    assert out["orchestration"]["prose_contract"]["repair"]["applied"]["applied"] == ["j1"]


@pytest.mark.parametrize("prov, model, deny", [
    (NANOGPT, GEMINI, ""), (OPENROUTER, "z-ai/glm-5.2", ""), (OPENROUTER, GEMINI, "openrouter")])
def test_off_a_caching_route_the_draft_and_its_repair_go_as_they_always_did(
        temp_db, monkeypatch, prov, model, deny):
    temp_db.set_setting("prompt_cache_deny", deny)
    out, wire = _resolve(temp_db, monkeypatch, prov, model)
    (draft,), (fix,) = _by_kind(wire)
    assert len(draft["messages"]) == 2 and isinstance(draft["messages"][1]["content"], str)
    assert len(fix["messages"]) == 2 and "REPAIR." in fix["messages"][0]["content"]
    assert json.loads(fix["messages"][1]["content"])["jobs"][0]["id"] == "j1"
    assert all("cache_control" not in json.dumps(body) for body in wire.bodies)
    assert [row["chrono_id"] for row in out["ledgers"]] == [1, 2]
