"""The research provider seam: web search and page fetch for the Writers' Room.

This sits beside the model providers because it is the same kind of thing --
a service outside the machine, configured by a setting row and a key, that
story text is sent to. It is NOT a model seam: nothing here calls a model,
and nothing here is reached by the turn pipeline. Its only consumer is
`story/room_research.py`, which gates every call behind a standing mandate,
writes the query into the room thread before it leaves, and caches the
answer so a replay reads the cache and never the web.

ONE interface (`search`, `fetch`), two adapters (Tavily, Brave), and a
module-level `OVERRIDE` a test installs so no test touches the network.
`configured()` answers whether a provider and its key are set; with neither,
every call refuses with the same sentence, because a tool that silently
works without a key is a tool the host did not agree to.

Settings: `research_provider` is one of `RESEARCH_PROVIDERS` or empty;
`research_key` is that provider's key. Both are settings rows like the
ambience source's, set through `/api/research`.
"""

from __future__ import annotations

import codecs
import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from core.db import get_setting

#: The setting rows. Empty provider means "not configured", never a default.
RESEARCH_PROVIDER_SETTING = "research_provider"
RESEARCH_KEY_SETTING = "research_key"

#: The adapters this module ships. A closed set the engine owns.
RESEARCH_PROVIDERS = ("tavily", "brave")

#: Connect / read timeouts for a search or a page, in seconds. A page that
#: takes longer is a page the room does without.
RESEARCH_TIMEOUT = (10, 30)

#: Bytes of a page read before conversion to text; past it the page is cut.
#: A page is reference material, not a corpus.
FETCH_BYTES_CAP = 400_000

#: What a fetched page identifies itself as. Honest, and enough for a
#: server that refuses anonymous clients to refuse us by name.
USER_AGENT = "SonderEngine-WritersRoom/1.0 (research; local interactive fiction)"

#: Redirects one page may take before the room does without it. Each hop is
#: followed by hand so its address can be checked (`_refuse_private`);
#: requests' own default is 30. Named per the owner's ask-before-limiting
#: rule.
FETCH_REDIRECTS_MAX = 5

#: Installed by a test (an object with `.search(query, k)` and `.fetch(url)`).
#: When set, no adapter and no key is consulted. Never set in production code.
OVERRIDE = None


class ResearchError(Exception):
    """A provider could not answer: unconfigured, refused, unreachable, or
    the page was not something text can be read from."""


def configured():
    """`{"provider", "key"}` when a provider and a key are set, else None."""
    if OVERRIDE is not None:
        return {"provider": "override", "key": ""}
    provider = str(get_setting(RESEARCH_PROVIDER_SETTING) or "").strip().casefold()
    key = str(get_setting(RESEARCH_KEY_SETTING) or "").strip()
    if provider not in RESEARCH_PROVIDERS or not key:
        return None
    return {"provider": provider, "key": key}


def _session():
    from llm.providers import _session as model_session
    return model_session()


def _adapter():
    if OVERRIDE is not None:
        return OVERRIDE
    conf = configured()
    if conf is None:
        raise ResearchError("no research provider configured")
    if conf["provider"] == "tavily":
        return _Tavily(conf["key"])
    return _Brave(conf["key"])


def search(query, k):
    """`[{title, url, snippet}]`, at most ``k``. Raises `ResearchError`."""
    query = " ".join(str(query or "").split())
    if not query:
        raise ResearchError("a search needs a query")
    rows = _adapter().search(query, int(k))
    out = []
    for row in rows or ():
        if not isinstance(row, dict) or not row.get("url"):
            continue
        out.append({"title": str(row.get("title") or "").strip(),
                    "url": str(row["url"]).strip(),
                    "snippet": " ".join(str(row.get("snippet") or "").split())})
        if len(out) >= int(k):
            break
    return out


def fetch(url):
    """`{url, title, text}` for one http(s) page, as readable text."""
    url = str(url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        raise ResearchError("only an http or https page can be fetched")
    page = _adapter().fetch(url)
    if not isinstance(page, dict):
        raise ResearchError("the page could not be read")
    return {"url": str(page.get("url") or url),
            "title": str(page.get("title") or "").strip(),
            "text": " ".join(str(page.get("text") or "").split())}


# ---------------------------------------------------------------------------
# HTML to text
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """The readable text of a page: everything but scripts, styles and
    markup, with the title kept separately."""

    SKIP = {"script", "style", "noscript", "template", "svg", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.title, self._skip, self._in_title = [], "", 0, False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw):
    """`(title, text)` from an HTML document string."""
    parser = _TextExtractor()
    try:
        parser.feed(str(raw or ""))
        parser.close()
    except Exception:
        pass
    text = html.unescape("".join(parser.parts))
    return " ".join(parser.title.split()), " ".join(text.split())


# ---------------------------------------------------------------------------
# Only public pages
# ---------------------------------------------------------------------------
#
# `fetch_page` is "Read one page the search returned", and nothing held it to
# that: the address was checked for its scheme alone, and requests followed
# any redirect. So under a granted research mandate the Room's model -- or
# text injected into a page or snippet it read -- could ask for
# `http://127.0.0.1:8181/` (the owner's own embedding host), a LAN address,
# or on a cloud VM `http://169.254.169.254/`, or a public page that 302s
# there, and the body came back into a third-party model's context and could
# be filed as `web_reference` lore (review 2026-11-01, llm_providers_quality
# F4). A search engine returns public pages; the room reads nothing else.

def _resolve(host):
    """Every address `host` resolves to. The seam a test replaces."""
    return [info[4][0] for info in socket.getaddrinfo(
        host, None, type=socket.SOCK_STREAM)]


def _public_address(text):
    """Is `text` an IP address on the public internet?"""
    try:
        ip = ipaddress.ip_address(str(text).split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def _refuse_private(url):
    """Raise unless every address `url`'s host resolves to is public:
    loopback, private, link-local (cloud metadata), shared and reserved
    ranges are this machine or its network, never a page."""
    parts = urlsplit(url)
    if parts.scheme.casefold() not in ("http", "https"):
        raise ResearchError("only an http or https page can be fetched")
    host = parts.hostname or ""
    if not host:
        raise ResearchError("the page's address names no host")
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
        addresses = [host]
    except ValueError:
        try:
            addresses = _resolve(host)
        except OSError as exc:
            raise ResearchError("the page's host could not be found: %s" % exc)
    # EVERY address, not any: a name that resolves to one public and one
    # private address may be connected to the private one.
    if not addresses or not all(_public_address(a) for a in addresses):
        raise ResearchError(
            "the page is not on a public address (%s); the room reads public "
            "pages, never this machine or its network" % host)


def _peer_address(resp):
    """The address the response actually came from, where the transport
    shows it -- the check after the connection, against a name that
    resolved one way for `_refuse_private` and another for the socket.
    Best-effort: None where it cannot be read."""
    raw = getattr(resp, "raw", None)
    for conn in (getattr(raw, "_connection", None), getattr(raw, "connection", None)):
        sock = getattr(conn, "sock", None)
        if sock is None:
            continue
        try:
            return sock.getpeername()[0]
        except (OSError, TypeError, IndexError, AttributeError):
            continue
    return None


# ---------------------------------------------------------------------------
# A page's own charset
# ---------------------------------------------------------------------------
#
# requests gives a `text/*` reply that names no charset the HTTP default,
# ISO-8859-1, so the `"utf-8"` fallback that stood here was never reached: a
# Japanese UTF-8 page that declares its charset only in `<meta charset>`
# arrived as `æ¥æ¬èªã®ãã¼ã`, cached for thirty days and fileable as lore
# (review 2026-11-01, llm_providers_quality F9). The header's charset is
# used only when the header NAMES one; then the page's own declaration;
# then UTF-8.

_CHARSET = re.compile(r"""charset\s*=\s*["']?([A-Za-z0-9._:-]+)""", re.I)
_META_CHARSET = re.compile(
    r"""<meta[^>]+charset\s*=\s*["']?([A-Za-z0-9._:-]+)""", re.I)


def _page_charset(ctype, body):
    named = _CHARSET.search(str(ctype or ""))
    if named:
        return named.group(1)
    if body.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if body.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    declared = _META_CHARSET.search(body[:4096].decode("ascii", errors="ignore"))
    return declared.group(1) if declared else None


def _decode_page(body, ctype):
    charset = _page_charset(ctype, body)
    if charset:
        try:
            return body.decode(charset, errors="replace")
        except LookupError:
            pass
    try:
        # Incremental, so a page cut at `FETCH_BYTES_CAP` mid-character is
        # still read as the UTF-8 it is rather than as Windows-1252.
        return codecs.getincrementaldecoder("utf-8")(errors="strict").decode(
            body, final=False)
    except UnicodeDecodeError:
        return body.decode("cp1252", errors="replace")


def _fetch_html(url):
    """GET one public page under the byte cap and return its text."""
    import requests
    for _hop in range(FETCH_REDIRECTS_MAX + 1):
        _refuse_private(url)
        try:
            resp = _session().get(url, timeout=RESEARCH_TIMEOUT, stream=True,
                                  allow_redirects=False,
                                  headers={"User-Agent": USER_AGENT})
        except requests.exceptions.RequestException as exc:
            raise ResearchError("the page could not be reached: %s" % exc)
        if not getattr(resp, "is_redirect", False):
            break
        target = str(resp.headers.get("location") or "")
        _close(resp)
        url = urljoin(url, target)
    else:
        raise ResearchError("the page redirected more than %d times"
                            % FETCH_REDIRECTS_MAX)
    try:
        peer = _peer_address(resp)
        if peer is not None and not _public_address(peer):
            raise ResearchError(
                "the page answered from an address that is not public (%s)" % peer)
        if resp.status_code >= 400:
            raise ResearchError("the page answered %d" % resp.status_code)
        ctype = str(resp.headers.get("content-type") or "").casefold()
        if "html" not in ctype and "text" not in ctype:
            raise ResearchError("the page is not text (%s)" % (ctype or "unknown type"))
        body = b""
        for chunk in resp.iter_content(chunk_size=16_384):
            body += chunk
            if len(body) >= FETCH_BYTES_CAP:
                break
    finally:
        # Closed on every way out: a streamed response left open held its
        # connection until garbage collection, after the byte cap included.
        _close(resp)
    raw = _decode_page(body, ctype)
    if "html" in ctype:
        title, text = html_to_text(raw)
    else:
        title, text = "", " ".join(raw.split())
    return {"url": url, "title": title, "text": text}


def _close(resp):
    try:
        resp.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

class _Tavily:
    ENDPOINT = "https://api.tavily.com/search"

    def __init__(self, key):
        self.key = key

    def search(self, query, k):
        import requests
        try:
            resp = _session().post(
                self.ENDPOINT, timeout=RESEARCH_TIMEOUT,
                json={"api_key": self.key, "query": query,
                      "max_results": int(k), "include_answer": False},
                headers={"User-Agent": USER_AGENT})
        except requests.exceptions.RequestException as exc:
            raise ResearchError("the search provider could not be reached: %s" % exc)
        if resp.status_code >= 400:
            raise ResearchError("the search provider answered %d" % resp.status_code)
        data = resp.json() if resp.content else {}
        return [{"title": r.get("title"), "url": r.get("url"),
                 "snippet": r.get("content")}
                for r in (data.get("results") or []) if isinstance(r, dict)]

    def fetch(self, url):
        return _fetch_html(url)


class _Brave:
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, key):
        self.key = key

    def search(self, query, k):
        import requests
        try:
            resp = _session().get(
                self.ENDPOINT, timeout=RESEARCH_TIMEOUT,
                params={"q": query, "count": int(k)},
                headers={"X-Subscription-Token": self.key, "Accept": "application/json",
                         "User-Agent": USER_AGENT})
        except requests.exceptions.RequestException as exc:
            raise ResearchError("the search provider could not be reached: %s" % exc)
        if resp.status_code >= 400:
            raise ResearchError("the search provider answered %d" % resp.status_code)
        data = resp.json() if resp.content else {}
        web = data.get("web") if isinstance(data.get("web"), dict) else {}
        return [{"title": r.get("title"), "url": r.get("url"),
                 "snippet": r.get("description")}
                for r in (web.get("results") or []) if isinstance(r, dict)]

    def fetch(self, url):
        return _fetch_html(url)
