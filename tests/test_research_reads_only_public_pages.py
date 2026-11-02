"""The Writers' Room reads public pages, and reads them in their own charset.

`fetch_page` is documented as "Read one page the search returned", and
`research_providers.fetch` checked only the scheme: under a granted research
mandate the Room's model -- or text injected into a page it read -- could ask
for `http://127.0.0.1:8181/` (the owner's own embedding host), a LAN address,
or on a cloud VM `http://169.254.169.254/`, or a public page that 302s there,
and the body came back into a third-party model's context and could be filed
as lore (review 2026-11-01, llm_providers_quality F4). The address is now
resolved and every destination -- the first and each redirect hop -- must be
a public one; redirects are followed by hand so each hop is checked.

And a page whose `Content-Type` named no charset was decoded as Latin-1
(requests' HTTP default for `text/*`), so a UTF-8 Japanese page arrived as
`æ¥æ¬èªã®ãã¼ã` and was cached for thirty days (F9). The charset is the
header's only when the header names one; otherwise the page's own
declaration, then UTF-8.

No network: the resolver and the session are faked.
"""
from __future__ import annotations

import pytest

from llm import research_providers as rp


class _Resp:
    def __init__(self, status=200, body=b"", ctype="text/html",
                 location=None, encoding="ISO-8859-1"):
        self.status_code = status
        self.headers = {"content-type": ctype}
        if location:
            self.headers["location"] = location
        self._body = body
        # What requests sets for a `text/*` reply with no charset.
        self.encoding = encoding
        self.closed = False

    @property
    def is_redirect(self):
        return "location" in self.headers and self.status_code in (
            301, 302, 303, 307, 308)

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


class _Session:
    def __init__(self, replies):
        self.replies = dict(replies)
        self.asked = []

    def get(self, url, **kw):
        self.asked.append((url, kw.get("allow_redirects", True)))
        return self.replies[url]


PUBLIC = {"example.org": ["93.184.215.14"], "news.example": ["2606:4700::1"],
          "localhost": ["127.0.0.1"], "intranet.example": ["10.1.2.3"],
          "sneaky.example": ["93.184.215.14", "192.168.1.9"]}


@pytest.fixture
def wire(monkeypatch):
    def install(replies):
        session = _Session(replies)
        monkeypatch.setattr(rp, "_session", lambda: session)
        monkeypatch.setattr(rp, "_resolve", lambda host: list(PUBLIC.get(host, [])))
        return session
    return install


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8181/v1/embeddings",
    "http://localhost/admin",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/",
    "http://192.168.1.2:8008/api/chats",
    "http://[::1]:8008/",
    "http://intranet.example/wiki",
    "http://sneaky.example/",        # one public address, one private
    "http://0.0.0.0:8008/",
])
def test_a_private_or_local_address_is_never_fetched(wire, url):
    session = wire({})
    with pytest.raises(rp.ResearchError, match="public"):
        rp._fetch_html(url)
    assert session.asked == [], "nothing may be sent to a refused address"


def test_a_redirect_to_a_private_address_is_refused_at_the_hop(wire):
    session = wire({
        "http://example.org/page": _Resp(302, location="http://169.254.169.254/latest/"),
    })
    with pytest.raises(rp.ResearchError, match="public"):
        rp._fetch_html("http://example.org/page")
    assert session.asked == [("http://example.org/page", False)]


def test_a_public_redirect_is_followed_and_each_hop_checked(wire):
    session = wire({
        "http://example.org/old": _Resp(301, location="/new"),
        "http://example.org/new": _Resp(200, b"<title>T</title><p>Body text</p>",
                                        ctype="text/html; charset=utf-8"),
    })
    page = rp._fetch_html("http://example.org/old")
    assert page["text"] == "Body text"
    assert page["url"] == "http://example.org/new"
    assert [url for url, _ in session.asked] == [
        "http://example.org/old", "http://example.org/new"]
    assert all(follow is False for _, follow in session.asked)


def test_the_response_is_closed(wire):
    reply = _Resp(200, b"<p>x</p>" * 10, ctype="text/html; charset=utf-8")
    wire({"http://example.org/p": reply})
    rp._fetch_html("http://example.org/p")
    assert reply.closed


class TestTheCharsetIsThePagesOwn:
    def test_utf8_without_a_charset_header_is_read_as_utf8(self, wire):
        body = "<html><body><p>日本語のページ</p></body></html>".encode("utf-8")
        wire({"http://example.org/ja": _Resp(200, body, ctype="text/html")})
        assert rp._fetch_html("http://example.org/ja")["text"] == "日本語のページ"

    def test_a_meta_charset_is_honoured(self, wire):
        body = ('<html><head><meta charset="shift_jis"></head>'
                '<body><p>日本語</p></body></html>').encode("shift_jis")
        wire({"http://example.org/sj": _Resp(200, body, ctype="text/html")})
        assert rp._fetch_html("http://example.org/sj")["text"] == "日本語"

    def test_a_header_charset_still_wins(self, wire):
        body = "<p>café</p>".encode("latin-1")
        wire({"http://example.org/l1": _Resp(
            200, body, ctype="text/html; charset=ISO-8859-1")})
        assert rp._fetch_html("http://example.org/l1")["text"] == "café"
