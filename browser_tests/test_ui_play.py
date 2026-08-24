"""Real-browser contracts for the WP-04 replacement Play workflow."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, expect


def _bootstrap() -> dict:
    return {
        "ui_language": "en",
        "ui_direction": "ltr",
        "ui_messages": {},
        "chats": [
            {"id": 1, "name": "Lantern Archive"},
            {"id": 2, "name": "Winter Road"},
        ],
        "characters": [],
        "personas": [],
        "lorebooks": [],
        "providers": [],
        "language_packs": [],
        "extensions": [],
        "extension_errors": [],
        "extension_lanes": [],
    }


def _turn(turn_id: int, idx: int, player: str, prose: str) -> dict:
    return {
        "id": turn_id,
        "idx": idx,
        "player_input": player,
        "prose": prose,
        "stale": False,
        "stale_from": None,
        "prose_stale": False,
        "frame_id": None,
        "speech": [],
    }


def _story(chat_id: int, turns: list[dict] | None = None) -> dict:
    name = "Lantern Archive" if chat_id == 1 else "Winter Road"
    return {
        "chat": {"id": chat_id, "name": name, "scenario": ""},
        "turns": turns or [],
        "frames": [{"id": None, "label": "Present", "kind": "present", "ordinal": 0}],
        "participants": [],
        "dialogue_colors": {},
        "lorebook": None,
        "lorebooks": [],
        "embedding_bank": None,
        "story_language": "en",
    }


def _open_play(
    page: Page,
    ui_base_url: str,
    *,
    chat: int | None = 1,
    story_handler=None,
) -> None:
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(_bootstrap())
        ),
    )

    def serve_story(route) -> None:
        chat_id = int(urlparse(route.request.url).path.rsplit("/", 1)[1])
        payload = story_handler(chat_id) if story_handler else _story(chat_id)
        route.fulfill(content_type="application/json", body=json.dumps(payload))

    page.route(re.compile(r".*/api/chats/\d+$"), serve_story)
    hash_value = "#/play" if chat is None else f"#/play?chat={chat}"
    response = page.goto(f"{ui_base_url}/static/ui-next.html{hash_value}")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )
    if chat is not None:
        page.wait_for_selector("[data-play-composer]", timeout=10000)


def test_no_story_offers_real_recent_stories_and_library(
    page: Page, ui_base_url: str
) -> None:
    _open_play(page, ui_base_url, chat=None)

    expect(page.get_by_role("heading", name="Choose a story to begin")).to_be_visible()
    expect(page.get_by_role("button", name="Lantern Archive")).to_be_visible()
    expect(page.get_by_role("button", name="Winter Road")).to_be_visible()
    page.get_by_role("button", name="Lantern Archive").click()
    expect(page).to_have_url(re.compile(r"#/play\?chat=1$"))
    expect(page.get_by_role("heading", name="Lantern Archive", level=2)).to_be_visible()


def test_story_switching_keeps_drafts_owned_by_story(
    page: Page, ui_base_url: str
) -> None:
    _open_play(page, ui_base_url)
    composer = page.get_by_role("textbox", name="What do you do or say?")
    composer.fill("Light the lantern")

    story_actions = page.get_by_role("button", name="Story actions")
    assert story_actions.locator("use").get_attribute("href").endswith("#icon-more")
    story_actions.click()
    page.get_by_role("combobox", name="Switch story").select_option("2")
    expect(page.get_by_role("heading", name="Winter Road", level=2)).to_be_visible()
    expect(composer).to_have_value("")
    composer.fill("Follow the tracks")

    page.get_by_role("button", name="Story actions").click()
    page.get_by_role("combobox", name="Switch story").select_option("1")
    expect(page.get_by_role("heading", name="Lantern Archive", level=2)).to_be_visible()
    expect(page.get_by_role("textbox", name="What do you do or say?")).to_have_value(
        "Light the lantern"
    )


def test_empty_installation_offers_new_story_without_inert_story_tools(
    page: Page, ui_base_url: str
) -> None:
    empty = {**_bootstrap(), "chats": []}
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(empty)),
    )
    page.goto(f"{ui_base_url}/static/ui-next.html#/play")
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")

    expect(page.get_by_role("heading", name="Choose a story to begin")).to_be_visible()
    expect(page.get_by_role("button", name="New story", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Open Library", exact=True)).to_be_visible()
    expect(page.locator("[data-story-tool-list]:visible button")).to_have_count(0)
    expect(
        page.get_by_role("complementary", name="Story tools").get_by_text(
            "Choose a story to use Story Tools.", exact=True
        )
    ).to_be_visible()
    page.get_by_role("button", name="New story", exact=True).click()
    expect(page.get_by_role("dialog", name="New story")).to_be_visible()


def test_send_uses_ndjson_and_refreshes_authoritative_turn(
    page: Page, ui_base_url: str
) -> None:
    generated = {"done": False, "body": None}

    def story_handler(chat_id: int) -> dict:
        turns = []
        if generated["done"] and chat_id == 1:
            turns = [_turn(11, 0, "Open the door", "The archive door opens.")]
        return _story(chat_id, turns)

    _open_play(page, ui_base_url, story_handler=story_handler)

    def serve_turn(route) -> None:
        generated["body"] = route.request.post_data_json
        generated["done"] = True
        events = [
            {"type": "step_start", "key": "narrator", "label": "Narrator"},
            {
                "type": "step",
                "key": "narrator",
                "label": "Narrator",
                "content": {"prose": "The archive door opens."},
            },
            {"type": "done", "turn_id": 11},
        ]
        route.fulfill(
            status=200,
            content_type="application/x-ndjson",
            body="".join(json.dumps(event) + "\n" for event in events),
        )

    page.route("**/api/chats/1/turns", serve_turn)
    composer = page.get_by_role("textbox", name="What do you do or say?")
    composer.fill("Open the door")
    page.get_by_role("button", name="Send", exact=True).click()

    expect(page.get_by_text("The archive door opens.", exact=True)).to_be_visible()
    expect(composer).to_have_value("")
    assert generated["body"] == {"input": "Open the door", "frame_id": None}


def test_turn_actions_and_reroll_warning_are_touch_discoverable(
    page: Page, ui_base_url: str
) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    _open_play(
        page,
        ui_base_url,
        story_handler=lambda chat_id: _story(
            chat_id,
            [_turn(12, 0, "Wait", "Rain crosses the windows in silver threads.")],
        ),
    )
    for name in ("Edit", "Reroll", "Versions", "More"):
        expect(page.get_by_role("button", name=name, exact=True)).to_be_visible()
    page.get_by_role("button", name="Reroll", exact=True).click()
    dialog = page.get_by_role("dialog", name="Reroll this turn?")
    expect(dialog).to_contain_text(
        "world state, memories, and lorebooks to the start of this turn"
    )
    expect(dialog.get_by_role("button", name="Reroll", exact=True)).to_be_focused()


def test_keyboard_send_and_short_landscape_keep_composer_action_visible(
    page: Page, ui_base_url: str
) -> None:
    page.set_viewport_size({"width": 844, "height": 390})
    _open_play(page, ui_base_url)
    expect(page.get_by_role("button", name="New turn", exact=True)).to_be_hidden()
    requests: list[dict] = []

    def serve_turn(route) -> None:
        requests.append(route.request.post_data_json)
        route.fulfill(
            content_type="application/x-ndjson",
            body=json.dumps({"type": "done", "turn_id": 13}) + "\n",
        )

    page.route("**/api/chats/1/turns", serve_turn)
    composer = page.get_by_role("textbox", name="What do you do or say?")
    composer.fill("Keep moving")
    composer.press("Control+Enter")
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_visible()
    assert requests == [{"input": "Keep moving", "frame_id": None}]
    geometry = page.evaluate(
        """() => ({
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          composer: document.querySelector('[data-play-composer]').getBoundingClientRect().toJSON(),
          action: document.querySelector('[data-play-send]').getBoundingClientRect().toJSON(),
          viewport: { width: innerWidth, height: innerHeight },
        })"""
    )
    assert geometry["overflow"] <= 1
    assert geometry["action"]["width"] >= 44
    assert geometry["action"]["bottom"] <= geometry["viewport"]["height"]


def test_play_runtime_refuses_a_late_story_response(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=alpha98-ui12-7eaf6b3481a3`);
          const playModule = await import(`${base}/static/js/ui-next/play-runtime.js?release=alpha98-ui12-7eaf6b3481a3`);
          const store = storeModule.createStore({
            library: { status: "ready", chats: [{ id: 1 }, { id: 2 }] },
            route: { status: "ready", destination: "play", query: { chat: "1" },
              segments: [], layers: [], canonicalHash: "#/play?chat=1" },
          });
          const pending = new Map();
          const apiClient = {
            get: path => new Promise(resolve => pending.set(path, resolve)),
            request: async () => ({ data: {} }),
            stream: async () => ({ data: null }),
            post: async () => ({ data: {} }),
          };
          const drafts = new Map();
          const localState = {
            getDraft: (_kind, owner) => drafts.get(owner) ?? null,
            setDraft: (_kind, owner, value) => { drafts.set(owner, value); return true; },
            clearDraft: (_kind, owner) => drafts.delete(owner),
          };
          const tasks = { start: () => "task", update() {}, complete() {}, fail() {} };
          const notices = { problem() {} };
          const router = { navigate: route => route };
          const runtime = playModule.createPlayRuntime({
            store, apiClient, localState, tasks, notices, router,
          });
          store.dispatch({ type: "presentation/replace", slice: "route", value: {
            status: "ready", destination: "play", query: { chat: "2" },
            segments: [], layers: [], canonicalHash: "#/play?chat=2",
          }});
          const payload = id => ({ chat: { id, name: `Story ${id}` }, turns: [], frames: [] });
          pending.get("/api/chats/2")({ data: payload(2) });
          await Promise.resolve(); await Promise.resolve();
          pending.get("/api/chats/1")({ data: payload(1) });
          await Promise.resolve(); await Promise.resolve();
          const active = store.getSnapshot().story.data?.chat?.id;
          runtime.teardown();
          return active;
        }""",
        ui_base_url,
    )
    assert result == 2


def test_stop_targets_the_story_that_started_the_run_after_navigation(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=alpha98-ui12-7eaf6b3481a3`);
          const playModule = await import(`${base}/static/js/ui-next/play-runtime.js?release=alpha98-ui12-7eaf6b3481a3`);
          const route = chat => ({ status: "ready", destination: "play",
            query: { chat: String(chat) }, segments: [], layers: [],
            canonicalHash: `#/play?chat=${chat}` });
          const store = storeModule.createStore({
            library: { status: "ready", chats: [{ id: 1 }, { id: 2 }] },
            route: route(1),
          });
          let finishStream;
          let streamOptions;
          const posts = [];
          const payload = id => ({ chat: { id, name: `Story ${id}` }, turns: [], frames: [] });
          const apiClient = {
            get: async path => ({ data: payload(Number(path.split("/").pop())) }),
            request: async () => ({ data: {} }),
            stream: async (_path, options) => {
              streamOptions = options;
              return new Promise(resolve => { finishStream = resolve; });
            },
            post: async path => { posts.push(path); return { data: { aborted: true } }; },
          };
          const drafts = new Map();
          const localState = {
            getDraft: (_kind, owner) => drafts.get(owner) ?? null,
            setDraft: (_kind, owner, value) => { drafts.set(owner, value); return true; },
            clearDraft: (_kind, owner) => drafts.delete(owner),
          };
          const tasks = { start: () => "task", update() {}, complete() {}, fail() {} };
          const notices = { problem() {} };
          const router = { navigate: value => value };
          const runtime = playModule.createPlayRuntime({
            store, apiClient, localState, tasks, notices, router,
          });
          await Promise.resolve(); await Promise.resolve();
          const run = runtime.send("Wait here");
          await Promise.resolve();
          streamOptions.onEvent({ type: "step_start", key: "narrator", label: "Narrator" });
          store.dispatch({ type: "presentation/replace", slice: "route", value: route(2) });
          await Promise.resolve(); await Promise.resolve();
          await runtime.stop();
          streamOptions.onEvent({ type: "aborted" });
          finishStream({ data: null });
          await run;
          runtime.teardown();
          return { posts, activeStory: store.getSnapshot().story.data?.chat?.id };
        }""",
        ui_base_url,
    )
    assert result == {
        "posts": ["/api/chats/1/abort"],
        "activeStory": 2,
    }


def test_500_turn_render_stays_inside_the_recorded_budget(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=alpha98-ui12-7eaf6b3481a3`);
          const viewModule = await import(`${base}/static/js/ui-next/play-view.js?release=alpha98-ui12-7eaf6b3481a3`);
          const prose = await import(`${base}/static/js/ui-next/prose.js?release=alpha98-ui12-7eaf6b3481a3`);
          const turns = Array.from({ length: 500 }, (_, index) => ({
            id: index + 1, idx: index, player_input: `Action ${index + 1}`,
            prose: `Turn ${index + 1}. Rain crosses the windows while the archive keeper waits.`,
            stale: false, stale_from: null, prose_stale: false, frame_id: null, speech: [],
          }));
          const story = { chat: { id: 1, name: "Scale Story" }, turns,
            frames: [{ id: null, label: "Present" }], dialogue_colors: {} };
          const store = storeModule.createStore({
            story: { status: "ready", owner: "chat-1:frame-present", frameId: null, data: story },
            transcript: { status: "ready", owner: "chat-1:frame-present", items: turns, preview: null },
            composer: { status: "ready", owner: "chat-1:frame-present", draft: "", run: null },
            library: { status: "ready", chats: [{ id: 1, name: "Scale Story" }] },
          });
          const services = {
            store,
            router: { navigate() {} },
            play: new Proxy({}, { get: () => (() => Promise.resolve({})) }),
          };
          const started = performance.now();
          const mount = viewModule.createPlayView({ document, services, prose, state: store.getSnapshot() });
          document.body.replaceChildren(mount.element);
          const elapsed = performance.now() - started;
          const count = document.querySelectorAll("[data-turn-id]").length;
          const dom = document.querySelectorAll("*").length;
          mount.teardown();
          return { elapsed, count, dom };
        }""",
        ui_base_url,
    )
    assert result["count"] == 500
    assert result["elapsed"] <= 198.73
    assert result["dom"] < 10_000


def test_scrollback_review_is_preserved_when_a_new_turn_arrives(
    page: Page, ui_base_url: str
) -> None:
    generated = {"done": False}
    old_turns = [
        _turn(
            index + 1,
            index,
            f"Action {index + 1}",
            (f"Turn {index + 1}. The long gallery continues. " * 8),
        )
        for index in range(80)
    ]

    def story_handler(chat_id: int) -> dict:
        turns = list(old_turns)
        if generated["done"]:
            turns.append(_turn(81, 80, "Continue", "A new bell sounds."))
        return _story(chat_id, turns)

    _open_play(page, ui_base_url, story_handler=story_handler)

    def serve_turn(route) -> None:
        generated["done"] = True
        route.fulfill(
            content_type="application/x-ndjson",
            body=json.dumps({"type": "done", "turn_id": 81}) + "\n",
        )

    page.route("**/api/chats/1/turns", serve_turn)
    transcript = page.locator("[data-play-transcript]")
    geometry = transcript.evaluate(
        "node => ({ top: node.scrollTop, height: node.clientHeight, scroll: node.scrollHeight, outer: node.parentElement.getBoundingClientRect().height })"
    )
    assert geometry["scroll"] > geometry["height"], geometry
    before = transcript.evaluate("node => { node.scrollTop = 900; return node.scrollTop; }")
    page.get_by_role("textbox", name="What do you do or say?").fill("Continue")
    page.get_by_role("button", name="Send", exact=True).click()
    expect(page.get_by_role("button", name="New turn", exact=True)).to_be_visible()
    after = transcript.evaluate("node => node.scrollTop")
    assert abs(after - before) <= 2


def test_story_chrome_does_not_change_prose_line_breaks(
    page: Page, ui_base_url: str
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    _open_play(
        page,
        ui_base_url,
        story_handler=lambda chat_id: _story(
            chat_id,
            [_turn(1, 0, "Wait", "The archive keeper crosses the gallery and pauses beneath the high windows." * 5)],
        ),
    )
    prose = page.locator(".ui-play__prose")
    before = prose.evaluate(
        "node => ({ width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height })"
    )
    page.get_by_role("button", name="Close context panel").click()
    after = prose.evaluate(
        "node => ({ width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height })"
    )
    assert abs(after["width"] - before["width"]) <= 1
    assert abs(after["height"] - before["height"]) <= 1


def test_prose_emphasis_and_speaker_color_never_parse_model_html(
    page: Page, ui_base_url: str
) -> None:
    payload = _story(
        1,
        [_turn(1, 0, "Listen", 'Mara says, "<i>Come in.</i>" <script>stay literal</script>')],
    )
    payload["turns"][0]["speech"] = [
        {"speaker": "Mara", "exact_quote": "Come in."}
    ]
    payload["dialogue_colors"] = {"Mara": "rgb(110, 191, 153)"}
    _open_play(page, ui_base_url, story_handler=lambda _chat_id: payload)

    prose = page.locator(".ui-play__prose")
    expect(prose.locator("em")).to_have_text("Come in.")
    expect(prose.locator(".ui-play__said")).to_have_attribute("title", "Mara")
    expect(prose).to_contain_text("<script>stay literal</script>")
    assert prose.locator("script").count() == 0


def test_recoverable_send_failure_preserves_draft_and_offers_retry(
    page: Page, ui_base_url: str
) -> None:
    _open_play(page, ui_base_url)
    page.route("**/api/chats/1/turns", lambda route: route.abort("failed"))
    composer = page.get_by_role("textbox", name="What do you do or say?")
    composer.fill("Do not lose this")
    page.get_by_role("button", name="Send", exact=True).click()

    expect(page.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    expect(composer).to_have_value("Do not lose this")


def test_story_network_failure_has_a_distinct_offline_state(
    page: Page, ui_base_url: str
) -> None:
    attempts = {"count": 0}
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(_bootstrap())
        ),
    )

    def offline(route) -> None:
        attempts["count"] += 1
        route.abort("failed")

    page.route("**/api/chats/1", offline)
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/play?chat=1")
    assert response is not None and response.ok
    state = page.get_by_role("heading", name="Sonder is offline")
    expect(state).to_be_visible()
    expect(page.get_by_text("Sonder could not reach the engine. Your work is still here.")).to_be_visible()
    expect(page.get_by_role("button", name="Try again", exact=True)).to_be_visible()
    assert attempts["count"] == 1


def test_stream_transport_can_discard_token_history_while_delivering_events(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const apiModule = await import(`${base}/static/js/ui-next/api.js?release=alpha98-ui12-7eaf6b3481a3`);
          const encoder = new TextEncoder();
          const lines = [
            { type: "step_start", key: "narrator", label: "Narrator" },
            { type: "token", key: "narrator", delta: "A" },
            { type: "done", turn_id: 1 },
          ];
          const fetchImpl = async () => new Response(new ReadableStream({
            start(controller) {
              for (const line of lines) controller.enqueue(encoder.encode(JSON.stringify(line) + "\\n"));
              controller.close();
            },
          }), { status: 200, headers: { "content-type": "application/x-ndjson" } });
          const seen = [];
          const api = apiModule.createApiClient({ fetchImpl, baseUrl: location.origin });
          const response = await api.stream("/turn", {
            method: "POST", body: {}, collectEvents: false,
            onEvent: event => seen.push(event.type),
          });
          return { data: response.data, seen };
        }""",
        ui_base_url,
    )
    assert result == {
        "data": None,
        "seen": ["step_start", "token", "done"],
    }


def test_whitespace_only_input_is_not_confused_with_empty_continue(
    page: Page, ui_base_url: str
) -> None:
    _open_play(page, ui_base_url)
    requests: list[dict] = []
    page.route("**/api/chats/1/turns", lambda route: requests.append(route.request.post_data_json))
    composer = page.get_by_role("textbox", name="What do you do or say?")
    composer.fill("   ")
    page.get_by_role("button", name="Send", exact=True).click()
    expect(page.get_by_role("alert")).to_have_text(
        "Remove the spaces to send an empty continue turn."
    )
    assert requests == []


def test_story_rename_and_portable_archive_export_use_current_routes(
    page: Page, ui_base_url: str
) -> None:
    name = {"value": "Lantern Archive"}

    def story_handler(chat_id: int) -> dict:
        payload = _story(chat_id)
        if chat_id == 1:
            payload["chat"]["name"] = name["value"]
        return payload

    _open_play(page, ui_base_url, story_handler=story_handler)

    def save_name(route) -> None:
        if route.request.method == "GET":
            route.fulfill(
                content_type="application/json",
                body=json.dumps(story_handler(1)),
            )
            return
        name["value"] = route.request.post_data_json["name"]
        route.fulfill(content_type="application/json", body='{"ok":true}')

    page.route("**/api/chats/1", save_name)
    page.route(
        "**/api/chats/1/export",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({"chat": {"name": name["value"]}, "turns": []}),
        ),
    )
    page.get_by_role("button", name="Story actions").click()
    page.get_by_role("button", name="Rename story", exact=True).click()
    dialog = page.get_by_role("dialog", name="Rename story")
    dialog.get_by_role("textbox", name="Rename story").fill("The Brass Archive")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_role("heading", name="The Brass Archive", level=2)).to_be_visible()

    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export archive", exact=True).click()
    assert download_info.value.suggested_filename == "The_Brass_Archive.json"


def test_latest_turn_versions_switch_immediately_and_persist(
    page: Page, ui_base_url: str
) -> None:
    selected: list[int] = []
    _open_play(
        page,
        ui_base_url,
        story_handler=lambda chat_id: _story(
            chat_id,
            [_turn(12, 0, "Wait", "The first telling.")],
        ),
    )

    def narration(route) -> None:
        if route.request.method == "GET":
            route.fulfill(
                content_type="application/json",
                body=json.dumps(
                    {
                        "variants": [
                            {"id": 1, "active": True, "prose": "The first telling."},
                            {"id": 2, "active": False, "prose": "The second telling."},
                        ]
                    }
                ),
            )
            return
        selected.append(route.request.post_data_json["variant_id"])
        route.fulfill(content_type="application/json", body='{"ok":true}')

    page.route("**/api/turns/12/narration", narration)
    page.get_by_role("button", name="Versions", exact=True).click()
    dialog = page.get_by_role("dialog", name="Versions")
    dialog.get_by_role("button", name="Next version").click()
    expect(dialog).to_contain_text("The second telling.")
    expect(dialog).to_contain_text("2 of 2")
    dialog.press("ArrowLeft")
    expect(dialog).to_contain_text("The first telling.")
    assert selected == [2, 1]


def test_confirmed_reroll_uses_the_existing_streaming_endpoint(
    page: Page, ui_base_url: str
) -> None:
    rerolls: list[str] = []
    _open_play(
        page,
        ui_base_url,
        story_handler=lambda chat_id: _story(
            chat_id,
            [_turn(12, 0, "Wait", "Rain crosses the windows.")],
        ),
    )

    def reroll(route) -> None:
        rerolls.append(route.request.method)
        route.fulfill(
            content_type="application/x-ndjson",
            body=json.dumps({"type": "done", "turn_id": 12}) + "\n",
        )

    page.route("**/api/turns/12/reroll", reroll)
    page.get_by_role("button", name="Reroll", exact=True).click()
    with page.expect_request("**/api/turns/12/reroll"):
        page.get_by_role("dialog", name="Reroll this turn?").get_by_role(
            "button", name="Reroll", exact=True
        ).click()
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_visible()
    assert rerolls == ["POST"]


def test_story_threads_filter_transcript_without_copying_drafts(
    page: Page, ui_base_url: str
) -> None:
    def story_handler(chat_id: int) -> dict:
        payload = _story(
            chat_id,
            [
                _turn(1, 0, "Present action", "The present continues."),
                {**_turn(2, 1, "Elsewhere", "The side thread continues."), "frame_id": 5},
            ],
        )
        payload["frames"] = [
            {"id": None, "label": "Present", "kind": "present", "ordinal": 0},
            {"id": 5, "label": "Courtyard", "kind": "branch", "ordinal": 1},
        ]
        return payload

    _open_play(page, ui_base_url, story_handler=story_handler)
    expect(page.get_by_text("The present continues.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Courtyard", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/play\?chat=1&frame=5$"))
    expect(page.get_by_text("The side thread continues.", exact=True)).to_be_visible()
    assert page.get_by_text("The present continues.", exact=True).count() == 0


def test_japanese_localizes_late_play_dialogs_but_not_story_data(
    page: Page, ui_base_url: str
) -> None:
    catalog = json.loads(
        (Path(__file__).parents[1] / "language_packs" / "ja" / "ui.json")
        .read_text(encoding="utf-8")
    )
    boot = _bootstrap()
    boot.update({"ui_language": "ja", "ui_messages": catalog})
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(boot, ensure_ascii=False)
        ),
    )
    payload = _story(
        1, [_turn(12, 0, "Wait beneath the window", "Rain crosses the archive windows.")]
    )
    page.route(
        re.compile(r".*/api/chats/\d+$"),
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(payload)
        ),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/play?chat=1")
    assert response is not None and response.ok
    page.wait_for_selector("[data-play-composer]")

    expect(page.get_by_role("heading", name="Lantern Archive", level=2)).to_be_visible()
    expect(page.get_by_text("Rain crosses the archive windows.", exact=True)).to_be_visible()
    expect(page.get_by_role("textbox", name="何をする、または何と言いますか？")).to_be_visible()
    expect(page.get_by_role("button", name="送信", exact=True)).to_be_visible()
    page.get_by_role("button", name="リロール", exact=True).click()
    dialog = page.get_by_role("dialog", name="このターンを再生成しますか？")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("button", name="リロール", exact=True)).to_be_focused()


def test_turn_edit_details_delete_and_branch_use_current_routes(
    page: Page, ui_base_url: str
) -> None:
    calls: list[tuple[str, str, dict | None]] = []
    _open_play(
        page,
        ui_base_url,
        story_handler=lambda chat_id: _story(
            chat_id,
            [_turn(12, 0, "Wait", "Rain crosses the windows.")],
        ),
    )

    def mutation(route) -> None:
        body = route.request.post_data_json if route.request.post_data else None
        calls.append((route.request.method, urlparse(route.request.url).path, body))
        route.fulfill(content_type="application/json", body='{"ok":true}')

    page.route("**/api/turns/12/input", mutation)
    page.route("**/api/turns/12/prose", mutation)
    page.route("**/api/turns/12", mutation)
    page.route(
        "**/api/turns/12/pipeline",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps({"steps": [{"key": "narrator", "label": "Write the scene"}]}),
        ),
    )
    page.route(
        "**/api/turns/12/branch",
        lambda route: route.fulfill(content_type="application/json", body='{"id":2}'),
    )

    page.get_by_role("button", name="Edit", exact=True).click()
    edit_input = page.get_by_role("dialog", name="Edit player input")
    edit_input.get_by_role("textbox", name="Edit player input").fill("Open the door")
    edit_input.get_by_role("button", name="Save", exact=True).click()

    page.get_by_role("button", name="More", exact=True).click()
    page.get_by_role("menuitem", name="Edit narration", exact=True).click()
    edit_prose = page.get_by_role("dialog", name="Edit narration")
    edit_prose.get_by_role("textbox", name="Edit narration").fill("The door opens.")
    edit_prose.get_by_role("button", name="Save", exact=True).click()

    page.get_by_role("button", name="More", exact=True).click()
    page.get_by_role("menuitem", name="Turn details", exact=True).click()
    details = page.get_by_role("dialog", name="Turn details")
    expect(details).to_contain_text("Write the scene")
    details.get_by_role("button", name="Close", exact=True).click()

    page.get_by_role("button", name="More", exact=True).click()
    page.get_by_role("menuitem", name="Delete turn", exact=True).click()
    page.get_by_role("dialog", name="Delete the latest turn?").get_by_role(
        "button", name="Delete turn", exact=True
    ).click()

    page.get_by_role("button", name="More", exact=True).click()
    with page.expect_request("**/api/turns/12/branch"):
        page.get_by_role("menuitem", name="Branch here", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/play\?chat=2$"))

    assert calls == [
        ("PUT", "/api/turns/12/input", {"input": "Open the door"}),
        ("PUT", "/api/turns/12/prose", {"prose": "The door opens."}),
        ("DELETE", "/api/turns/12", None),
    ]
