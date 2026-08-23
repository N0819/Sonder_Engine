"""Behavioral smoke tests for the browser-global, no-bundler frontend."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect


BOOTSTRAP = {
    "providers": [],
    "provider_presets": {},
    "roles": [],
    "sampler_keys": [],
    "default_samplers": {},
    "lore_categories": [],
    "lorebook_types": [],
    "memory_categories": [],
    "memory_provenance": [],
    "agent_models": {},
    "max_output_tokens": {},
    "reasoning_effort": {},
    "reasoning_effort_levels": [],
    "openrouter_routing": {},
    "max_output_tokens_bounds": {},
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "chats": [],
    "nsfw_enabled": False,
    "image_model": None,
    "backdrops_enabled": False,
    "ambience": {"enabled": False, "source": "local", "configured": True,
                 "library": "/tmp/lib", "has_key": False,
                 "licenses": ["Creative Commons 0", "Attribution"]},
    "ambience_licenses": ["Creative Commons 0", "Attribution",
                          "Attribution NonCommercial"],
    "auto_promote": True,
    "default_prompts": {},
    "prompt_presets": {},
    "active_preset": None,
    "lorebook_link_types": [],
}


def _chat_payload(chat_id: int, name: str, prose: str) -> dict:
    return {
        "chat": {"id": chat_id, "name": name},
        "participants": [],
        "turns": [{
            "id": chat_id * 10,
            "idx": 0,
            "player_input": "",
            "prose": prose,
            "stale": False,
            "frame_id": None,
        }],
        "lorebook": None,
        "lorebooks": [],
        "frames": [],
    }


def _mock_api(page: Page, bootstrap: dict, chats: dict[int, dict] | None = None) -> None:
    chats = chats or {}

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/bootstrap":
            body = bootstrap
        elif path.startswith("/api/chats/") and path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        elif path.startswith("/api/chats/") and path.count("/") == 3:
            body = chats.get(int(path.rsplit("/", 1)[1]), {})
        else:
            body = {}
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
        )

    page.route("**/api/**", handle)


def _defer_api_paths(page: Page, paths: list[str]) -> None:
    """Hold selected fetches until the test resolves them out of order."""

    page.add_init_script(
        """
        (() => {
          const originalFetch = window.fetch.bind(window);
          const paths = %s;
          window.__pendingApi = Object.fromEntries(paths.map(path => [path, []]));
          window.__resolveApi = (path, body) => {
            const resolve = window.__pendingApi[path].shift();
            if (!resolve) throw new Error("No pending API request for " + path);
            resolve(new Response(JSON.stringify(body), {
              status: 200,
              headers: {"Content-Type": "application/json"},
            }));
          };
          window.fetch = (url, options) => {
            const path = new URL(url, window.location.href).pathname;
            if (Object.hasOwn(window.__pendingApi, path)) {
              return new Promise(resolve => window.__pendingApi[path].push(resolve));
            }
            return originalFetch(url, options);
          };
        })();
        """ % json.dumps(paths)
    )


def _wait_pending(page: Page, path: str) -> None:
    page.wait_for_function(
        "path => window.__pendingApi[path].length > 0",
        arg=path,
    )


def _resolve(page: Page, path: str, body: dict) -> None:
    page.evaluate(
        "args => window.__resolveApi(args.path, args.body)",
        {"path": path, "body": body},
    )


def _install_deferred_stream(page: Page, path: str) -> None:
    """Return one real ReadableStream whose final chunks the test controls."""

    page.add_init_script(
        """
        (() => {
          const originalFetch = window.fetch.bind(window);
          const streamPath = %s;
          window.__streamStarted = false;
          window.__finishStream = null;
          window.fetch = (url, options) => {
            const path = new URL(url, window.location.href).pathname;
            if (path !== streamPath) return originalFetch(url, options);
            const encoder = new TextEncoder();
            return Promise.resolve(new Response(new ReadableStream({
              start(controller) {
                window.__streamStarted = true;
                controller.enqueue(encoder.encode(JSON.stringify({
                  type: "step_start",
                  key: "director_interpret",
                  label: "Director · interpret",
                }) + "\\n"));
                window.__finishStream = () => {
                  controller.enqueue(encoder.encode(JSON.stringify({
                    type: "step",
                    key: "director_interpret",
                    label: "Director · interpret",
                    content: {flow: {}},
                  }) + "\\n"));
                  controller.enqueue(encoder.encode(JSON.stringify({
                    type: "done",
                    turn_id: 11,
                  }) + "\\n"));
                  controller.close();
                };
              },
            }), {
              status: 200,
              headers: {"Content-Type": "application/x-ndjson"},
            }));
          };
        })();
        """ % json.dumps(path)
    )


def test_appearance_choice_survives_a_reload(page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_api(page, BOOTSTRAP)

    page.goto(f"{ui_base_url}/static/index.html")
    expect(page.locator("#send")).to_be_visible()
    expect(page.locator("#sidelist")).to_contain_text("No stories yet")

    page.locator("#b-theme").click()
    expect(page.locator("#modal")).to_be_visible()
    expect(page.locator("#modaltitle")).to_have_text("Appearance")
    page.get_by_role("button", name="Use Tavern theme").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "tavern")

    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "tavern")
    assert page_errors == []


def test_quick_start_explains_the_featured_character_handoff(
    page: Page,
    ui_base_url: str,
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "personas": [{"id": 3, "name": "Researcher"}],
    }
    _mock_api(page, bootstrap)
    page.goto(f"{ui_base_url}/static/index.html")

    page.evaluate("quickStartModal({id: 9, name: 'Sarah Moon'}, 0)")

    modal = page.locator("#modal")
    expect(modal).to_contain_text("How does Sarah Moon relate to this place?")
    expect(modal).to_contain_text("using only public card details")
    expect(modal).to_contain_text("Arrives with authored or canon travels")
    expect(modal).to_contain_text("Charter stops speaking or deciding for them")


def test_story_quick_start_offers_history_routing_for_each_cast_member(
    page: Page,
    ui_base_url: str,
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "characters": [{"id": 9, "name": "Sarah Moon"}],
        "personas": [{"id": 3, "name": "Researcher"}],
        "language_packs": [{
            "id": "en", "name": "English", "native_name": "English",
            "story": True,
        }],
    }
    _mock_api(page, bootstrap)
    page.goto(f"{ui_base_url}/static/index.html")

    page.evaluate("""
      (() => {
        const state = wizardState();
        state.personaMode = 'existing';
        state.personaId = 3;
        state.existingCharacterIds.add(9);
        state.characterBriefs = ['Nadia Voss, an exhausted containment engineer.'];
        state.characterBriefsKnown = [false];
        state.livedLocation = {brief: 'Site 17', horizon_hours: 720};
        modal('New story', body => renderWizardScenario(body, state), {wide: true});
      })();
    """)

    modal = page.locator("#modal")
    expect(modal).to_contain_text("Give each story character the right kind of past")
    expect(modal).to_contain_text("How does Sarah Moon relate to this place?")
    expect(modal).to_contain_text("How does Nadia Voss relate to this place?")
    expect(modal.get_by_placeholder("Past guidance (optional)")).to_have_count(2)


def test_failed_story_setup_can_remove_the_incomplete_story(
    page: Page,
    ui_base_url: str,
) -> None:
    deleted: list[str] = []

    def delete_story(route) -> None:
        deleted.append(route.request.method)
        route.fulfill(status=200, content_type="application/json", body='{"ok":true}')

    _mock_api(page, BOOTSTRAP)
    page.route("**/api/chats/41", delete_story)
    page.goto(f"{ui_base_url}/static/index.html")

    page.evaluate("discardFailedStorySetup({id: 41})")

    expect(page.locator("#send")).to_be_visible()
    assert deleted == ["DELETE"]


def test_charter_diagnostics_explain_a_safe_character_handoff(
    page: Page,
    ui_base_url: str,
) -> None:
    _mock_api(page, BOOTSTRAP)
    page.goto(f"{ui_base_url}/static/index.html")
    page.evaluate("""
      document.body.append(charterDiagnosticsPanel({
        summary: {hours: 720, bodies: 84, posts: 12, events: 41, failing: []},
        judgment_holders: 17,
        commitments: [{id: 'promise:1'}],
        decisions: {orders: [{id: 'order:1'}]},
        featured_resident_histories: {
          9: {
            binding: {name: 'Sarah Moon', place: 'Medical Wing'},
            career_reflection: 'The routine made careful work feel dependable.',
            memory_event_keys: ['prestory:1', 'prestory:2'],
            grounding: {dropped: [{reason: 'uncited'}]},
            error: ''
          }
        }
      }));
    """)

    expect(page.get_by_text("Featured character handoffs")).to_be_visible()
    expect(page.get_by_text("Sarah Moon", exact=True)).to_be_visible()
    expect(page.get_by_text(
        "Independent memory records carried into full cognition: 2."
    )).to_be_visible()
    expect(page.get_by_text("Unsupported history claims discarded: 1.")).to_be_visible()
    expect(page.get_by_text("Full evidence and ledgers")).to_be_visible()


def test_latest_story_navigation_wins_out_of_order_responses(
    page: Page,
    ui_base_url: str,
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "chats": [{"id": 1, "name": "First"}, {"id": 2, "name": "Second"}],
    }
    _defer_api_paths(page, ["/api/chats/1", "/api/chats/2"])
    _mock_api(page, bootstrap)
    page.goto(f"{ui_base_url}/static/index.html")

    page.get_by_label("Open First").click()
    _wait_pending(page, "/api/chats/1")
    page.get_by_label("Open Second").click()
    _wait_pending(page, "/api/chats/2")

    _resolve(page, "/api/chats/2", _chat_payload(2, "Second", "second prose"))
    expect(page.locator("#chatname")).to_have_text("Second")
    expect(page.locator("#msgs")).to_contain_text("second prose")

    _resolve(page, "/api/chats/1", _chat_payload(1, "First", "stale first prose"))
    page.wait_for_timeout(50)
    expect(page.locator("#chatname")).to_have_text("Second")
    expect(page.locator("#msgs")).not_to_contain_text("stale first prose")
    expect(page.get_by_label("Open Second")).to_have_attribute(
        "aria-current",
        "true",
    )


def test_story_switch_closes_and_rejects_an_old_relationship_modal(
    page: Page,
    ui_base_url: str,
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "chats": [{"id": 1, "name": "First"}, {"id": 2, "name": "Second"}],
    }
    chats = {
        1: _chat_payload(1, "First", "first prose"),
        2: _chat_payload(2, "Second", "second prose"),
    }
    relationship_path = "/api/chats/1/characters/9/relationships"
    _defer_api_paths(page, [relationship_path])
    _mock_api(page, bootstrap, chats)
    page.goto(f"{ui_base_url}/static/index.html")

    page.get_by_label("Open First").click()
    expect(page.locator("#chatname")).to_have_text("First")
    page.evaluate("relationshipModal({id: 9, name: 'Ada'}, 1)")
    _wait_pending(page, relationship_path)
    expect(page.locator("#modal")).to_be_visible()
    expect(page.locator("#modaltitle")).to_have_text("Relationships — Ada")

    # The modal backdrop intentionally blocks sidebar pointer events. Exercise
    # the navigation entry point directly, as branch/import flows do.
    page.evaluate("() => openChat(2)")
    expect(page.locator("#chatname")).to_have_text("Second")
    expect(page.locator("#modal")).to_be_hidden()

    _resolve(page, relationship_path, {
        "Old Story Person": {
            "trust": 0.7,
            "familiarity": 0.4,
            "emotional_valence": 0.5,
            "fear": 0,
        },
    })
    page.wait_for_timeout(50)
    expect(page.locator("#modal")).to_be_hidden()
    expect(page.locator("body")).not_to_contain_text("Old Story Person")


def test_streamed_turn_shows_progress_and_cleans_up_after_completion(
    page: Page,
    ui_base_url: str,
) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    bootstrap = {
        **BOOTSTRAP,
        "chats": [{"id": 1, "name": "First"}],
    }
    chats = {1: _chat_payload(1, "First", "settled prose")}
    _install_deferred_stream(page, "/api/chats/1/turns")
    _mock_api(page, bootstrap, chats)
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#chatname")).to_have_text("First")

    page.get_by_label("Story input").fill("Open the door.")
    page.locator("#send").click()
    page.wait_for_function("() => window.__streamStarted")

    expect(page.locator("#stop")).to_be_visible()
    expect(page.locator("#send")).to_be_disabled()
    expect(page.locator("#turnstatus")).to_be_visible()
    expect(page.locator("#turnstatus-phase")).to_have_text(
        "Reading what you did"
    )
    expect(page.get_by_label("Story input")).to_have_value("")

    page.evaluate("() => window.__finishStream()")

    expect(page.locator("#stop")).to_be_hidden()
    expect(page.locator("#send")).to_be_enabled()
    expect(page.locator("#turnstatus")).to_be_hidden()
    expect(page.locator("#msgs")).to_contain_text("settled prose")
    assert page_errors == []


def test_ambience_mute_is_global_and_survives_a_reload(
    page: Page,
    ui_base_url: str,
) -> None:
    """Mute is the panic button: instant, needing no network, and remembered
    across rooms, stories and reloads. It lives in localStorage rather than in
    a server setting precisely so none of that depends on a request."""
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_api(page, BOOTSTRAP)

    page.goto(f"{ui_base_url}/static/index.html")
    mute = page.locator("#b-amb-mute")
    expect(mute).to_be_visible()
    expect(mute).to_have_text("🔊")

    mute.click()
    expect(mute).to_have_text("🔇")
    expect(mute).to_have_class("icon-button muted")

    page.reload()
    expect(page.locator("#b-amb-mute")).to_have_text("🔇")
    assert page.evaluate("() => AMB.muted") is True
    assert page_errors == []


def test_ambience_volume_persists_and_reroll_needs_a_sound(
    page: Page,
    ui_base_url: str,
) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_api(page, BOOTSTRAP)

    # Wide enough that the composer still has room beside the 720px column for
    # the volume slider -- below that the container query sheds it, which is
    # the behaviour the panel test covers.
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(f"{ui_base_url}/static/index.html")
    # Rerolling before anything is playing has nothing to reroll, and a live
    # button that silently does nothing is worse than a disabled one.
    expect(page.locator("#b-amb-reroll")).to_be_disabled()
    expect(page.locator("#amb-vol")).to_be_visible()

    # Driven by the keyboard rather than by setting .value, so this exercises
    # the same input events a dragged slider produces.
    slider = page.locator("#amb-vol")
    slider.focus()
    for _ in range(5):
        slider.press("ArrowRight")
    assert abs(page.evaluate("() => AMB.volume") - 0.40) < 0.005

    page.reload()
    assert abs(page.evaluate("() => AMB.volume") - 0.40) < 0.005
    assert page.evaluate("() => document.querySelector('#amb-vol').value") == "0.4"
    assert page_errors == []


def test_ambience_panel_opens_beside_the_composer(
    page: Page,
    ui_base_url: str,
) -> None:
    """The controls belong next to the input box, not in the top toolbar:
    muting and rerolling are mid-scene reflexes, not one-off configuration."""
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_api(page, BOOTSTRAP)

    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{ui_base_url}/static/index.html")
    bar = page.locator("#composer > #ambience-bar")
    expect(bar).to_be_visible()
    # It floats in the composer's right-hand margin. Inside #composer-inner it
    # would take width from the input, so the two invariants are: the typing
    # column is the SAME column the story is read in, and the cluster does not
    # sit on top of it.
    #
    # This used to assert `width == 720` outright. That was true when the
    # column was a constant and stopped being true when `--story-width` became
    # dynamic (`syncVitalsGutter` reserves room for whichever float is wider
    # and lets the column take the rest, up to STORY_MAX_WIDTH). Pinning the
    # old constant would now fail for the RIGHT behaviour, so what is pinned
    # is the relationship the CSS comment actually states: composer and
    # transcript must read one variable, or the input stops lining up with the
    # story above it.
    column = page.locator("#composer-inner").bounding_box()
    controls = bar.bounding_box()
    story_width = page.evaluate(
        "() => parseFloat(getComputedStyle(document.documentElement)"
        ".getPropertyValue('--story-width')) || 720")
    assert column["width"] == story_width, (column["width"], story_width)
    assert column["width"] >= 720
    # The overlap this guards is real and was live until 2026-08-19: at a
    # 1400px window the cluster still carried its volume slider, the column
    # was clamped back up to STORY_MIN_WIDTH, and the controls sat 27px INSIDE
    # the input -- over the right-hand end of the box being typed into.
    assert controls["x"] >= column["x"] + column["width"], (
        f"the ambience cluster overlaps the typing column by "
        f"{column['x'] + column['width'] - controls['x']:.0f}px")

    page.locator("#b-ambience").click()
    expect(page.locator("#modal")).to_be_visible()
    expect(page.locator("#modaltitle")).to_have_text("Room ambience")
    expect(page.locator("#modalbody")).to_contain_text("Nothing playing yet.")
    # The reassignment surface is in the panel, not hidden behind a gesture.
    expect(page.locator("#modalbody")).to_contain_text("Choose the sound for")
    assert page_errors == []


def _weather_bootstrap() -> dict:
    return {**BOOTSTRAP, "chats": [{"id": 1, "name": "First"}],
            "image_model": None, "backdrops_enabled": False}


def _mock_with_weather(page: Page, weather: dict) -> None:
    """Serve a turn whose room reports the given scoped weather."""
    chats = {1: _chat_payload(1, "First", "settled prose")}

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/bootstrap":
            body = _weather_bootstrap()
        elif path.endswith("/backdrop"):
            body = {"enabled": False, "configured": False, "room": "Courtyard",
                    "signature": None, "ready": False, "url": None,
                    "status": "absent", "weather": weather}
        elif path.startswith("/api/chats/") and path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        elif path.startswith("/api/chats/") and path.count("/") == 3:
            body = chats.get(int(path.rsplit("/", 1)[1]), {})
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)


def test_rain_draws_only_where_the_sky_is_visible(page: Page, ui_base_url: str) -> None:
    """The engine decides whether a room can see the sky; this only draws what
    it is handed. A cellar under the same downpour gets no canvas at all."""
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_with_weather(page, {"sky": "overcast", "precipitation": "rain",
                              "intensity": "heavy", "sky_visible": True,
                              "wind": "breeze", "audible": True})
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    page.wait_for_function("() => document.querySelector('#weather-fx.on')",
                           timeout=10000)
    # What this owns is the decision to draw at all, and with what shape. The
    # drawing itself is three tiled layers moved by a CSS transform.
    assert page.evaluate("() => WFX.kind").startswith("rain")
    page.wait_for_function("() => WFX.layers.length === 3", timeout=10000)
    # Each layer is a real repeating tile, and each travels exactly one tile so
    # the loop cannot be seen.
    # Quote-tolerant: Chromium serialises `background-image` as
    # url("data:...") on some versions and url(data:...) on others, so
    # matching the bare form made this assert a browser build rather than the
    # feature. The tile itself is what matters.
    assert page.evaluate(
        "() => WFX.layers.every(l =>"
        " /^url\\([\"']?data:image\\/png/.test(l.style.backgroundImage))")
    assert page.evaluate(
        "() => WFX.layers.every(l => l.style.getPropertyValue('--wfx-travel')"
        " === l.style.backgroundSize.split(' ')[0])")
    # It must never intercept a click meant for the story.
    assert page.evaluate(
        "() => getComputedStyle(document.querySelector('#weather-fx')).pointerEvents"
    ) == "none"

    # The same storm, from a room with no sky.
    page.evaluate("() => weatherFxApply({sky: 'overcast', precipitation: 'rain',"
                  " intensity: 'heavy', sky_visible: false, audible: true})")
    assert page.evaluate("() => WFX.kind") == ""
    assert page.evaluate("() => !!document.querySelector('#weather-fx.on')") is False
    assert page.evaluate("() => WFX.layers.length") == 0
    assert page_errors == []


def test_snow_falls_differently_from_rain(page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_with_weather(page, {"sky": "overcast", "precipitation": "snow",
                              "intensity": "moderate", "sky_visible": True,
                              "wind": "still", "audible": False})
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    page.wait_for_function("() => WFX.kind.startsWith('snow')", timeout=10000)
    page.wait_for_function("() => WFX.layers.length === 3", timeout=10000)
    # Snow and rain are different tiles, not the same one relabelled, and snow
    # drifts where rain falls: a much longer time to cross one tile.
    snow_tile = page.evaluate("() => WFX.layers[0].style.backgroundImage")
    snow_fall = page.evaluate("() => parseFloat(WFX.layers[0].style.animationDuration)")
    page.evaluate("() => weatherFxApply({sky: 'overcast', precipitation: 'rain',"
                  " intensity: 'moderate', weather_visible: true, wind: 'still',"
                  " visible_reach: 1})")
    assert page.evaluate("() => WFX.layers[0].style.backgroundImage") != snow_tile
    assert page.evaluate(
        "() => parseFloat(WFX.layers[0].style.animationDuration)") < snow_fall
    assert page_errors == []


def test_a_hidden_tab_pauses_every_weather_animation(
    page: Page,
    ui_base_url: str,
) -> None:
    """Snow animates on two nodes, and only one of them used to stop.

    `wfx-sway` runs on the drift wrapper -- which is what `WFX.layers` holds --
    and `wfx-fall` on the tile layer inside it. The visibilitychange handler
    walked `WFX.layers`, so a hidden tab kept three infinite composited
    animations falling forever. Nothing caught it because nothing checked the
    inner node, which is the whole reason this test names it explicitly.
    """
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_with_weather(page, {"sky": "overcast", "precipitation": "snow",
                              "intensity": "moderate", "sky_visible": True,
                              "wind": "still", "audible": False})
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    page.wait_for_function("() => WFX.kind.startsWith('snow')", timeout=10000)
    # Snow really does nest: wrappers outside, tile layers within.
    assert page.evaluate(
        "() => WFX.layers.filter(l => l.querySelector('.wfx-layer')).length") > 0

    def play_states() -> list[str]:
        return page.evaluate(
            "() => WFX.layers.flatMap(l => [l, ...l.querySelectorAll('.wfx-layer')])"
            "        .map(n => getComputedStyle(n).animationPlayState)")

    assert set(play_states()) == {"running"}

    page.evaluate("""() => {
        Object.defineProperty(document, "hidden",
                              { value: true, configurable: true });
        document.dispatchEvent(new Event("visibilitychange"));
    }""")
    assert set(play_states()) == {"paused"}, "a hidden tab must stop all of it"

    page.evaluate("""() => {
        Object.defineProperty(document, "hidden",
                              { value: false, configurable: true });
        document.dispatchEvent(new Event("visibilitychange"));
    }""")
    assert set(play_states()) == {"running"}, "and coming back must resume it"
    assert page_errors == []


def test_thunder_follows_the_flash_rather_than_leading_it(
    page: Page,
    ui_base_url: str,
) -> None:
    """The gap between the flash and the sound is the distance, and it is the
    whole reason the effect reads as a storm rather than as a glitch."""
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_with_weather(page, {"sky": "storm", "precipitation": "rain",
                              "intensity": "heavy", "sky_visible": True,
                              "wind": "wind", "audible": True})
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    page.wait_for_function("() => WFX.kind.startsWith('rain')", timeout=10000)

    # Record when the flash happens and when the sound is asked for.
    page.evaluate("""() => {
      window.__fx = {flash: 0, thunder: 0};
      window.playAmbienceOneshot = () => { window.__fx.thunder = performance.now(); };
      window.__fx.flash = performance.now();
      weatherFxFlash();
    }""")
    page.wait_for_function("() => window.__fx.thunder > 0", timeout=15000)
    gap = page.evaluate("() => window.__fx.thunder - window.__fx.flash")
    assert gap > 500, f"thunder arrived {gap}ms after the flash"
    assert page_errors == []


def test_a_muted_reader_never_hears_thunder(page: Page, ui_base_url: str) -> None:
    """A thunderclap that ignored the mute button would be the single most
    annoying thing this feature could do."""
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_with_weather(page, {"sky": "storm", "precipitation": "rain",
                              "intensity": "heavy", "sky_visible": True,
                              "audible": True})
    page.goto(f"{ui_base_url}/static/index.html")
    page.locator("#b-amb-mute").click()          # global, instant, no network
    page.get_by_label("Open First").click()
    page.wait_for_timeout(300)
    played = page.evaluate("""async () => {
      window.__audios = 0;
      const RealAudio = window.Audio;
      window.Audio = function (src) { window.__audios++; return new RealAudio(src); };
      AMB.enabled = true; AMB.configured = true;
      await playAmbienceOneshot('thunder', 0.9);
      return window.__audios;
    }""")
    assert played == 0
    assert page_errors == []


def _mix_payload() -> dict:
    return {
        "enabled": True, "configured": True, "source": "local",
        "room": "Courtyard", "room_id": "yard", "signature": "a" * 24,
        "pinned": False, "ready": True, "status": "ready",
        "error": None, "url": "/static/assets/none.mp3",
        "token": "a" * 24 + "#0",
        "layers": [
            {"index": 0, "role": "tone", "gain": 1.0, "title": "stone yard",
             "source": "local", "path": "yard.ogg", "id": None, "license": "",
             "username": "", "credit_url": "", "query": "courtyard ambience",
             "url": "/static/assets/none.mp3?layer=0"},
            {"index": 1, "role": "weather", "gain": 0.3, "title": "rain",
             "source": "local", "path": "rain.ogg", "id": None, "license": "",
             "username": "", "credit_url": "", "query": "rain heavy",
             "url": "/static/assets/none.mp3?layer=1"},
        ],
    }


def test_a_mix_plays_every_layer_at_its_own_level(page: Page, ui_base_url: str) -> None:
    """The reason layering exists: rain two rooms in is a quiet layer over an
    undiminished room tone, which one clip cannot express."""
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    chats = {1: _chat_payload(1, "First", "settled prose")}
    mix = _mix_payload()

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/bootstrap":
            body = {**BOOTSTRAP, "chats": [{"id": 1, "name": "First"}],
                    "ambience": {**BOOTSTRAP["ambience"], "enabled": True}}
        elif path.endswith("/ambience"):
            body = mix
        elif path.endswith("/backdrop"):
            body = {"enabled": False, "configured": False, "room": None,
                    "signature": None, "ready": False, "url": None, "weather": {}}
        elif path.startswith("/api/chats/") and path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        elif path.startswith("/api/chats/") and path.count("/") == 3:
            body = chats.get(int(path.rsplit("/", 1)[1]), {})
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    page.wait_for_function("() => AMB.layers.length === 2", timeout=15000)

    # One element per layer, each carrying its own share of the reader's volume.
    gains = page.evaluate("() => AMB.layers.map(l => l.gain)")
    assert gains == [1.0, 0.3]

    # The panel stages the mix: one row per bed, with a live level on each.
    page.locator("#b-ambience").click()
    expect(page.locator("#modaltitle")).to_have_text("Room ambience")
    expect(page.locator("#modalbody")).to_contain_text("stone yard")
    expect(page.locator("#modalbody")).to_contain_text("rain")
    assert page.locator("#modalbody .badge").all_inner_texts()[:2] == ["room", "weather"]
    assert page.locator("#modalbody input[type=range]").count() == 2
    assert page_errors == []


def test_dragging_one_layer_does_not_move_the_others(page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.route("**/api/**", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps({})))
    page.goto(f"{ui_base_url}/static/index.html")
    # Drive the mixer directly: the point under test is the level maths, not
    # the fetch that delivered the layers.
    page.evaluate("""() => {
      AMB.playing = new Map([
        [0, {gain: 1, audio: {volume: 0.5, paused: false}}],
        [1, {gain: 0.4, audio: {volume: 0.2, paused: false}}],
      ]);
      AMB.layers = [{index: 0, gain: 1}, {index: 1, gain: 0.4}];
      AMB.volume = 0.5;
      setLayerGain(1, 0.1);
    }""")
    levels = page.evaluate("() => [...AMB.playing.values()].map(e => e.audio.volume)")
    assert levels[0] == 0.5          # untouched
    assert abs(levels[1] - 0.05) < 1e-9
    assert page_errors == []
