"""Research for the Writers' Room (`story/room_research.py`, the provider
seam `llm/research_providers.py`): the web under a mandate, disclosed in
the thread before it leaves, cached per story, budgeted per beat, and usable
in the world only as a filed lore operation. No test here touches the
network: a stub provider is installed on the seam's OVERRIDE.
"""
from __future__ import annotations

import json
import time

import pytest

import web.app as app_module
from llm import research_providers as rp
from story import mandates as md
from web import guest_access as guest
from story import room_conversation as room
from story import room_research as rr
from story.room_tools import TOOL_INDEX, run_tool, tool_manifest


class _Stub:
    """A provider that records what it was asked and answers from a table."""

    def __init__(self, results=None, page=None, fail=False):
        self.results = results if results is not None else [
            {"title": "Tanneries of the Middle Ages", "url": "https://example.org/tan",
             "snippet": "Hides were soaked in lime, then bated in dung and bark liquor."},
            {"title": "Guild records", "url": "https://example.org/guild",
             "snippet": "Tanners were kept downstream of the town by ordinance."},
        ]
        self.page = page or {"url": "https://example.org/tan", "title": "Tanneries",
                             "text": "Lime pits. " * 200}
        self.fail = fail
        self.searches, self.fetches = [], []
        self.thread_at_call = []

    def search(self, query, k):
        if self.fail:
            raise rp.ResearchError("the search provider answered 500")
        self.searches.append((query, k))
        return list(self.results)

    def fetch(self, url):
        if self.fail:
            raise rp.ResearchError("the page answered 404")
        self.fetches.append(url)
        return dict(self.page)


@pytest.fixture
def stub(monkeypatch):
    provider = _Stub()
    monkeypatch.setattr(rp, "OVERRIDE", provider)
    return provider


@pytest.fixture
def vocabulary(monkeypatch):
    """The `research` capability in the mandate vocabulary -- the wiring the
    owning fork does; here it is granted for the test's duration."""
    if rr.RESEARCH_CAPABILITY not in md.MANDATE_CAPABILITIES:
        monkeypatch.setattr(md, "MANDATE_CAPABILITIES",
                            tuple(md.MANDATE_CAPABILITIES) + (rr.RESEARCH_CAPABILITY,))


def _story(db, turns=3):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Research", "A tannery town.", time.time()))
    for i in range(turns):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def _grant(cid):
    return md.grant_mandate(cid, None, text="You may read the web about the trades.",
                            capabilities=[rr.RESEARCH_CAPABILITY], scope="the trades")


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

class TestTheTable:
    def test_both_tools_are_in_the_table_and_the_manifest_and_marked_long(self):
        for name in rr.RESEARCH_TOOL_NAMES:
            assert name in TOOL_INDEX
            assert TOOL_INDEX[name].get("long") is True
            assert not TOOL_INDEX[name].get("host_only")
        names = {t["name"] for t in tool_manifest()}
        assert set(rr.RESEARCH_TOOL_NAMES) <= names

    def test_the_descriptions_say_reference_and_filing(self):
        for name in rr.RESEARCH_TOOL_NAMES:
            text = TOOL_INDEX[name]["description"]
            assert "as_lore" in text and "mandate" in text


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

class TestTheGate:
    def test_without_the_word_in_the_vocabulary_nothing_can_grant_it(self, temp_db, stub,
                                                                        monkeypatch):
        monkeypatch.setattr(md, "MANDATE_CAPABILITIES", tuple(
            c for c in md.MANDATE_CAPABILITIES if c != rr.RESEARCH_CAPABILITY))
        cid = _story(temp_db)
        out = run_tool(cid, "web_search", {"query": "tanneries"})
        assert "vocabulary" in out["refused"]
        assert stub.searches == []

    def test_without_a_grant_the_tool_refuses_and_names_the_grant(self, temp_db, stub,
                                                                   vocabulary):
        cid = _story(temp_db)
        out = run_tool(cid, "web_search", {"query": "tanneries"})
        assert "no standing mandate permits research" in out["refused"]
        out = run_tool(cid, "fetch_page", {"url": "https://example.org/tan"})
        assert "no standing mandate permits research" in out["refused"]
        assert stub.searches == [] and stub.fetches == []
        # And nothing was disclosed, because nothing left.
        assert room.messages(cid) == []

    def test_a_revoked_grant_refuses_again(self, temp_db, stub, vocabulary):
        cid = _story(temp_db)
        row = _grant(cid)
        assert "results" in run_tool(cid, "web_search", {"query": "tanneries"})
        room.revoke_mandate(cid, row["uid"])
        out = run_tool(cid, "web_search", {"query": "guild ordinances"})
        assert "no standing mandate" in out["refused"]

    def test_with_no_provider_configured_the_tool_says_so(self, temp_db, vocabulary,
                                                          monkeypatch):
        monkeypatch.setattr(rp, "OVERRIDE", None)
        cid = _story(temp_db)
        _grant(cid)
        out = run_tool(cid, "web_search", {"query": "tanneries"})
        assert out["refused"] == "no research provider configured"
        # The grant was honoured, the provider was not there: nothing left,
        # so nothing is disclosed.
        assert room.messages(cid) == []


# ---------------------------------------------------------------------------
# Disclosure, cache, budget, filing
# ---------------------------------------------------------------------------

class TestDisclosureAndCache:
    def test_the_query_is_in_the_thread_before_the_provider_is_asked(self, temp_db, stub,
                                                                        vocabulary):
        cid = _story(temp_db)
        _grant(cid)
        seen = {}
        real = stub.search

        def spying(query, k):
            seen["thread"] = [m["text"] for m in room.messages(cid)]
            return real(query, k)
        stub.search = spying
        out = run_tool(cid, "web_search", {"query": "medieval tanneries", "k": 2})
        assert seen["thread"] == ["%s: medieval tanneries" % rr.SEARCH_NOTICE]
        assert [m["role"] for m in room.messages(cid)] == ["room"]
        assert out["cached"] is False and len(out["results"]) == 2
        assert out["cited"]  # the mandate that permitted it

    def test_a_repeat_reads_the_cache_and_never_the_web(self, temp_db, stub, vocabulary):
        cid = _story(temp_db)
        _grant(cid)
        first = run_tool(cid, "web_search", {"query": "Medieval Tanneries"})
        again = run_tool(cid, "web_search", {"query": "medieval tanneries"})
        assert len(stub.searches) == 1
        assert again["cached"] is True
        assert [r["url"] for r in again["results"]] == [r["url"] for r in first["results"]]
        # One disclosure: the cached read left nothing.
        assert len(room.messages(cid)) == 1
        # The cache row carries its date, for replay.
        store = temp_db.wget(cid, rr.RESEARCH_CACHE_KEY)
        (row,) = store["searches"].values()
        assert row["fetched_at"] > 0 and row["query"] == "Medieval Tanneries"

    def test_a_stale_cache_row_is_fetched_again(self, temp_db, stub, vocabulary):
        cid = _story(temp_db)
        _grant(cid)
        run_tool(cid, "web_search", {"query": "tanneries"})
        store = temp_db.wget(cid, rr.RESEARCH_CACHE_KEY)
        for row in store["searches"].values():
            row["fetched_at"] -= (rr.CACHE_TTL_DAYS + 1) * 86400
        temp_db.wset(cid, rr.RESEARCH_CACHE_KEY, store)
        out = run_tool(cid, "web_search", {"query": "tanneries"})
        assert out["cached"] is False and len(stub.searches) == 2

    def test_the_cache_is_not_frame_scoped(self):
        from core.db import FRAME_SCOPED_WORLD_KEYS
        assert rr.RESEARCH_CACHE_KEY not in FRAME_SCOPED_WORLD_KEYS

    def test_results_are_capped_and_k_is_bounded(self, temp_db, vocabulary, monkeypatch):
        many = [{"title": "t%d" % i, "url": "https://example.org/%d" % i,
                 "snippet": "x" * 2000} for i in range(20)]
        provider = _Stub(results=many)
        monkeypatch.setattr(rp, "OVERRIDE", provider)
        cid = _story(temp_db)
        _grant(cid)
        out = run_tool(cid, "web_search", {"query": "many", "k": 50})
        assert len(out["results"]) == rr.RESULTS_PER_SEARCH_CAP
        assert all(len(r["snippet"]) <= rr.RESULT_CHARS for r in out["results"])
        assert provider.searches == [("many", rr.RESULTS_PER_SEARCH_CAP)]

    def test_the_budget_is_per_beat_and_refuses_past_it(self, temp_db, stub, vocabulary):
        cid = _story(temp_db)
        _grant(cid)
        for i in range(rr.SEARCHES_PER_BEAT):
            assert "results" in run_tool(cid, "web_search", {"query": "q%d" % i})
        out = run_tool(cid, "web_search", {"query": "one more"})
        assert "budget is spent" in out["refused"]
        # A cached query is still served past the budget: nothing leaves.
        assert run_tool(cid, "web_search", {"query": "q0"})["cached"] is True
        # The story moves: a new beat, a new budget.
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                   (cid, 3, "", time.time()))
        assert "results" in run_tool(cid, "web_search", {"query": "one more"})

    def test_the_ingest_ceiling_stops_a_page_flood(self, temp_db, vocabulary, monkeypatch):
        provider = _Stub(page={"url": "https://example.org/big", "title": "Big",
                               "text": "word " * 100_000})
        monkeypatch.setattr(rp, "OVERRIDE", provider)
        monkeypatch.setattr(rr, "INGEST_CHARS_PER_BEAT", 7000)
        cid = _story(temp_db)
        _grant(cid)
        first = run_tool(cid, "fetch_page", {"url": "https://example.org/big"})
        assert len(first["text"]) <= rr.PAGE_CHARS
        second = run_tool(cid, "fetch_page", {"url": "https://example.org/other"})
        # 6000 spent of 7000: the second page is cut to what is left.
        assert len(second["text"]) <= 1000
        third = run_tool(cid, "fetch_page", {"url": "https://example.org/third"})
        assert "budget is spent" in third["refused"]

    def test_a_page_is_disclosed_cached_and_templated(self, temp_db, stub, vocabulary):
        cid = _story(temp_db)
        _grant(cid)
        out = run_tool(cid, "fetch_page", {"url": "https://example.org/tan"})
        assert [m["text"] for m in room.messages(cid)] == [
            "%s: https://example.org/tan" % rr.FETCH_NOTICE]
        assert out["title"] == "Tanneries" and out["cached"] is False
        again = run_tool(cid, "fetch_page", {"url": "https://example.org/tan"})
        assert again["cached"] is True and len(stub.fetches) == 1
        lore = out["as_lore"]
        assert lore["op"] == "file_lore" and lore["content_from"] == "text"
        assert lore["disposition"] == rr.WEB_REFERENCE_DISPOSITION
        assert lore["source_url"] == "https://example.org/tan"
        assert lore["provenance"].startswith("web_reference https://example.org/tan fetched 20")
        assert lore["subject_id"] == ""  # the room's to fill

    def test_a_provider_failure_is_a_refusal_the_model_reads(self, temp_db, vocabulary,
                                                             monkeypatch):
        monkeypatch.setattr(rp, "OVERRIDE", _Stub(fail=True))
        cid = _story(temp_db)
        _grant(cid)
        out = run_tool(cid, "web_search", {"query": "tanneries"})
        assert "could not be searched" in out["refused"]
        # Disclosed anyway: the query DID leave before the provider failed.
        assert len(room.messages(cid)) == 1

    def test_every_result_carries_only_the_filing_path(self, temp_db, stub, vocabulary):
        """No result carries a room, a plan or a body: the only key shaped
        like a write is `as_lore`, and it is a file_lore operation."""
        cid = _story(temp_db)
        _grant(cid)
        out = run_tool(cid, "web_search", {"query": "tanneries"})
        for r in out["results"]:
            assert set(r) == {"title", "url", "snippet", "fetched_at", "as_lore"}
            assert r["as_lore"]["op"] == "file_lore"
            assert r["as_lore"]["content_from"] == "snippet"


# ---------------------------------------------------------------------------
# The provider seam
# ---------------------------------------------------------------------------

class TestTheSeam:
    def test_unconfigured_by_default(self, temp_db, monkeypatch):
        monkeypatch.setattr(rp, "OVERRIDE", None)
        assert rp.configured() is None
        with pytest.raises(rp.ResearchError):
            rp.search("x", 3)

    def test_a_provider_and_a_key_configure_it(self, temp_db, monkeypatch):
        monkeypatch.setattr(rp, "OVERRIDE", None)
        from core.db import set_setting
        set_setting(rp.RESEARCH_PROVIDER_SETTING, "tavily")
        assert rp.configured() is None  # no key yet
        set_setting(rp.RESEARCH_KEY_SETTING, "k")
        assert rp.configured() == {"provider": "tavily", "key": "k"}
        set_setting(rp.RESEARCH_PROVIDER_SETTING, "nonesuch")
        assert rp.configured() is None

    def test_fetch_refuses_anything_but_http(self, temp_db, stub):
        with pytest.raises(rp.ResearchError):
            rp.fetch("file:///etc/passwd")
        with pytest.raises(rp.ResearchError):
            rp.fetch("ftp://example.org/x")

    def test_html_becomes_text_without_scripts_or_styles(self):
        title, text = rp.html_to_text(
            "<html><head><title>Lime  Pits</title><style>p{}</style></head>"
            "<body><script>alert(1)</script><p>Hides &amp; bark.</p><p>Downstream.</p>"
            "</body></html>")
        assert title == "Lime Pits"
        assert text == "Hides & bark. Downstream."

    def test_the_route_sets_provider_and_key_without_echoing_the_key(self, temp_db,
                                                                      monkeypatch):
        monkeypatch.setattr(rp, "OVERRIDE", None)
        from fastapi.testclient import TestClient
        guest.reset_host_account()
        guest._join_attempts.clear()
        guest._login_attempts.clear()
        try:
            with TestClient(app_module.app) as client:
                r = client.post("/api/auth/setup",
                                json={"username": "host", "password": "pw12345"})
                assert r.status_code == 200, r.text
                out = client.put("/api/research",
                                 json={"provider": "brave", "key": "secret"}).json()
                assert out == {"provider": "brave", "providers": ["tavily", "brave"],
                               "has_key": True}
                assert "secret" not in json.dumps(out)
                assert rp.configured() == {"provider": "brave", "key": "secret"}
                # A blank key keeps the stored one; clearing is explicit.
                client.put("/api/research", json={"key": ""})
                assert rp.configured()["key"] == "secret"
                out = client.put("/api/research", json={"clear_key": True}).json()
                assert out["has_key"] is False and rp.configured() is None
                assert client.put("/api/research",
                                  json={"provider": "google"}).status_code == 400
                assert client.get("/api/research").json()["provider"] == "brave"
                # The key is a host setting: a guest never reaches it.
                from web.auth_routes import GUEST_ALLOWED_API_PATHS
                assert "/api/research" not in GUEST_ALLOWED_API_PATHS
        finally:
            guest.reset_host_account()
            guest._join_attempts.clear()
            guest._login_attempts.clear()
