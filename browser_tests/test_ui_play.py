"""Real-browser contracts for the WP-04 replacement Play workflow."""

from __future__ import annotations

import json
import re
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

    page.get_by_role("combobox", name="Switch story").select_option("2")
    expect(page.get_by_role("heading", name="Winter Road", level=2)).to_be_visible()
    expect(composer).to_have_value("")
    composer.fill("Follow the tracks")

    page.get_by_role("combobox", name="Switch story").select_option("1")
    expect(page.get_by_role("heading", name="Lantern Archive", level=2)).to_be_visible()
    expect(page.get_by_role("textbox", name="What do you do or say?")).to_have_value(
        "Light the lantern"
    )


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

    for name in ("Edit", "Reroll", "More"):
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
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=wp04.1`);
          const playModule = await import(`${base}/static/js/ui-next/play-runtime.js?release=wp04.1`);
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
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=wp04.1`);
          const playModule = await import(`${base}/static/js/ui-next/play-runtime.js?release=wp04.1`);
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
