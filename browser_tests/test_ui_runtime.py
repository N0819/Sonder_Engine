"""Behavioral contracts for the build-free replacement runtime."""

from __future__ import annotations

from playwright.sync_api import Page


def test_release_module_is_importable_without_classic_host_scripts(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const module = await import(`${base}/static/js/ui-next/release.js?release=wp02.1`);
          return {
            release: module.MODULE_RELEASE,
            hasClassicState: Object.hasOwn(window, "S"),
            hasReleaseCheck: typeof module.assertReleaseModules === "function",
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "release": "wp02.1",
        "hasClassicState": False,
        "hasReleaseCheck": True,
    }


def test_runtime_rejects_a_mixed_release_before_boot(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const runtime = await import(
            `${base}/static/js/ui-next/bootstrap.js?release=wp02.1`
          );
          try {
            await runtime.loadRuntimeModules(async path => ({
              MODULE_RELEASE: path.includes("api.js") ? "wp01" : "wp02.1",
            }));
          } catch (error) {
            return {
              name: error.name,
              kind: error.kind,
              moduleName: error.moduleName,
              expected: error.expected,
              received: error.received,
            };
          }
          return null;
        }""",
        ui_base_url,
    )
    assert result == {
        "name": "MixedReleaseError",
        "kind": "mixed-release",
        "moduleName": "api",
        "expected": "wp02.1",
        "received": "wp01",
    }


def test_reboot_replaces_runtime_listeners_instead_of_accumulating_them(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const runtime = await import(
            `${base}/static/js/ui-next/bootstrap.js?release=wp02.1`
          );
          const listeners = new Map();
          let added = 0;
          let removed = 0;
          const target = {
            addEventListener(type, listener) {
              added += 1;
              listeners.set(`${type}:${added}`, listener);
            },
            removeEventListener(type, listener) {
              removed += 1;
              for (const [key, value] of listeners) {
                if (key.startsWith(`${type}:`) && value === listener) {
                  listeners.delete(key);
                  break;
                }
              }
            },
            dispatchEvent() {},
          };
          const importer = async () => ({ MODULE_RELEASE: "wp02.1" });
          const firstRoot = { dataset: {} };
          const secondRoot = { dataset: {} };
          await runtime.bootRuntime({ target, root: firstRoot, importModule: importer });
          const second = await runtime.bootRuntime({
            target,
            root: secondRoot,
            importModule: importer,
          });
          const afterReboot = {
            added,
            removed,
            live: listeners.size,
            firstState: firstRoot.dataset.uiNextState,
            secondState: secondRoot.dataset.uiNextState,
          };
          second.teardown();
          return {
            afterReboot,
            afterStop: {
              removed,
              live: listeners.size,
              state: secondRoot.dataset.uiNextState,
            },
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "afterReboot": {
            "added": 4,
            "removed": 2,
            "live": 2,
            "firstState": "stopped",
            "secondState": "ready",
        },
        "afterStop": {"removed": 4, "live": 0, "state": "stopped"},
    }


def test_api_normalizes_forbidden_malformed_and_session_expired(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        r"""async (base) => {
          const { createApiClient } = await import(
            `${base}/static/js/ui-next/api.js?release=wp02.1`
          );
          let expired = 0;
          const fetchImpl = async url => {
            if (String(url).endsWith("/forbidden")) {
              return new Response('{"detail":"No access"}', {
                status: 403,
                headers: { "Content-Type": "application/json" },
              });
            }
            if (String(url).endsWith("/expired")) {
              return new Response('{"detail":"Expired"}', {
                status: 401,
                headers: { "Content-Type": "application/json" },
              });
            }
            return new Response("{", {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          };
          const client = createApiClient({
            fetchImpl,
            onSessionExpired: () => { expired += 1; },
          });
          const capture = async path => {
            try {
              await client.get(path, { channel: path });
            } catch (error) {
              return {
                kind: error.kind,
                status: error.status,
                detail: error.technicalDetail,
              };
            }
            return null;
          };
          const forbidden = await capture("/forbidden");
          const malformed = await capture("/malformed");
          const firstExpiry = await capture("/expired");
          const secondExpiry = await capture("/expired");
          return { forbidden, malformed, firstExpiry, secondExpiry, expired };
        }""",
        ui_base_url,
    )
    assert result == {
        "forbidden": {"kind": "forbidden", "status": 403, "detail": "No access"},
        "malformed": {
            "kind": "malformed-response",
            "status": 200,
            "detail": "Response was not valid JSON.",
        },
        "firstExpiry": {
            "kind": "session-expired",
            "status": 401,
            "detail": "Expired",
        },
        "secondExpiry": {
            "kind": "session-expired",
            "status": 401,
            "detail": "The host session has expired.",
        },
        "expired": 1,
    }


def test_api_aborts_superseded_channels_and_refuses_stale_owners(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createApiClient } = await import(
            `${base}/static/js/ui-next/api.js?release=wp02.1`
          );
          let settleFirst;
          let firstAborted = false;
          const fetchImpl = (url, init) => {
            if (String(url).endsWith("/first")) {
              init.signal.addEventListener("abort", () => { firstAborted = true; });
              return new Promise(resolve => { settleFirst = resolve; });
            }
            return Promise.resolve(new Response('{"value":2}', {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }));
          };
          const client = createApiClient({ fetchImpl });
          const first = client.get("/first", { channel: "library", owner: "a" })
            .catch(error => ({ kind: error.kind, requestId: error.requestId }));
          const second = await client.get("/second", {
            channel: "library",
            owner: "a",
          });
          settleFirst(new Response('{"value":1}', {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }));
          const firstResult = await first;
          let staleKind = null;
          try {
            await client.get("/second", {
              channel: "owner-check",
              owner: "old-story",
              isCurrent: () => false,
            });
          } catch (error) {
            staleKind = error.kind;
          }
          return {
            firstAborted,
            firstKind: firstResult.kind,
            secondData: second.data,
            identitiesDiffer: firstResult.requestId !== second.requestId,
            staleKind,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "firstAborted": True,
        "firstKind": "aborted",
        "secondData": {"value": 2},
        "identitiesDiffer": True,
        "staleKind": "stale",
    }


def test_api_parses_text_empty_and_ndjson_without_retrying_writes(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        r"""async (base) => {
          const { createApiClient } = await import(
            `${base}/static/js/ui-next/api.js?release=wp02.1`
          );
          const calls = [];
          const fetchImpl = async (url, init) => {
            calls.push({ url: String(url), method: init.method, init });
            if (String(url).endsWith("/text")) {
              return new Response("plain", { status: 200 });
            }
            if (String(url).endsWith("/empty")) {
              return new Response(null, { status: 204 });
            }
            if (String(url).endsWith("/stream")) {
              const encoder = new TextEncoder();
              const body = new ReadableStream({
                start(controller) {
                  controller.enqueue(encoder.encode('{"n":1}\n{"n"'));
                  controller.enqueue(encoder.encode(':2}\n'));
                  controller.close();
                },
              });
              return new Response(body, {
                status: 200,
                headers: { "Content-Type": "application/x-ndjson" },
              });
            }
            throw new TypeError("offline");
          };
          const diagnostics = [];
          const client = createApiClient({
            fetchImpl,
            onDiagnostic: entry => diagnostics.push(entry),
          });
          const text = await client.get("/text", { responseType: "text" });
          const empty = await client.get("/empty");
          const streamed = [];
          const stream = await client.stream("/stream", {
            onEvent: item => streamed.push(item),
          });
          let networkKind = null;
          try {
            await client.post("/write", { secret: "do-not-log" });
          } catch (error) {
            networkKind = error.kind;
          }
          return {
            text: text.data,
            empty: empty.data,
            stream: stream.data,
            streamed,
            methods: calls.map(call => call.method),
            credentials: calls.map(call => call.init.credentials),
            caches: calls.map(call => call.init.cache),
            networkKind,
            writeCalls: calls.filter(call => call.url.endsWith("/write")).length,
            diagnosticHasBody: diagnostics.some(entry => "body" in entry),
            hasCorrelation: diagnostics.every(entry => Boolean(entry.correlationId)),
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "text": "plain",
        "empty": None,
        "stream": [{"n": 1}, {"n": 2}],
        "streamed": [{"n": 1}, {"n": 2}],
        "methods": ["GET", "GET", "GET", "POST"],
        "credentials": ["same-origin"] * 4,
        "caches": ["no-store"] * 4,
        "networkKind": "network",
        "writeCalls": 1,
        "diagnosticHasBody": False,
        "hasCorrelation": True,
    }


def test_store_owns_documented_slices_and_immutable_copied_state(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createStore, SLICE_OWNERS } = await import(
            `${base}/static/js/ui-next/store.js?release=wp02.1`
          );
          const store = createStore();
          const extensionProjection = {
            status: "ready",
            items: [{ id: "example", enabled: true }],
          };
          store.dispatch({
            type: "server/replace",
            slice: "extensions",
            value: extensionProjection,
          });
          extensionProjection.items[0].enabled = false;
          const snapshot = store.getSnapshot();
          const mutationRejected = Reflect.set(
            snapshot.extensions.items[0],
            "enabled",
            false,
          ) === false;
          const errors = [];
          for (const action of [
            { type: "server/replace", slice: "route", value: {} },
            { type: "presentation/replace", slice: "story", value: {} },
            { type: "server/replace", slice: "unknown", value: {} },
            { type: "unknown/action", slice: "story", value: {} },
          ]) {
            try { store.dispatch(action); } catch (error) { errors.push(error.kind); }
          }
          return {
            owners: SLICE_OWNERS,
            sliceNames: Object.keys(snapshot),
            sessionStatus: snapshot.session.status,
            storyStatus: snapshot.story.status,
            routeStatus: snapshot.route.status,
            copiedExtension: snapshot.extensions.items[0].enabled,
            frozen: Object.isFrozen(snapshot)
              && Object.isFrozen(snapshot.extensions.items[0]),
            mutationRejected,
            errors,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "owners": {
            "server": [
                "session",
                "story",
                "transcript",
                "library",
                "settings",
                "extensions",
            ],
            "presentation": [
                "route",
                "composer",
                "inspector",
                "tasks",
                "notices",
                "appearance",
                "diagnostics",
            ],
        },
        "sliceNames": [
            "session",
            "route",
            "story",
            "transcript",
            "composer",
            "inspector",
            "library",
            "settings",
            "tasks",
            "notices",
            "appearance",
            "extensions",
            "diagnostics",
        ],
        "sessionStatus": "unrequested",
        "storyStatus": "unrequested",
        "routeStatus": "ready",
        "copiedExtension": True,
        "frozen": True,
        "mutationRejected": True,
        "errors": ["slice-owner", "slice-owner", "unknown-slice", "unknown-action"],
    }


def test_store_batches_selector_events_and_tears_down_deterministically(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createStore } = await import(
            `${base}/static/js/ui-next/store.js?release=wp02.1`
          );
          const store = createStore();
          const routeEvents = [];
          const allEvents = [];
          const unsubscribeRoute = store.subscribe(
            state => state.route.destination,
            (next, previous, actions) => routeEvents.push({ next, previous, actions }),
          );
          store.subscribe(
            state => state,
            (_next, _previous, actions) => allEvents.push(actions),
          );
          store.dispatch({
            type: "presentation/patch",
            slice: "appearance",
            value: { theme: "ash-brass" },
          });
          store.batch(() => {
            store.dispatch({
              type: "presentation/patch",
              slice: "route",
              value: { destination: "library" },
            });
            store.dispatch({
              type: "presentation/patch",
              slice: "route",
              value: { destination: "settings" },
            });
          });
          unsubscribeRoute();
          store.dispatch({
            type: "presentation/patch",
            slice: "route",
            value: { destination: "play" },
          });
          store.destroy();
          let destroyed = null;
          try {
            store.dispatch({
              type: "presentation/patch",
              slice: "route",
              value: { destination: "library" },
            });
          } catch (error) {
            destroyed = error.kind;
          }
          return {
            routeEvents,
            allEvents,
            finalRoute: store.getSnapshot().route.destination,
            destroyed,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "routeEvents": [
            {
                "next": "settings",
                "previous": "play",
                "actions": ["presentation/patch", "presentation/patch"],
            }
        ],
        "allEvents": [
            ["presentation/patch"],
            ["presentation/patch", "presentation/patch"],
            ["presentation/patch"],
        ],
        "finalRoute": "play",
        "destroyed": "store-destroyed",
    }


def test_router_parses_stable_routes_and_reports_truthful_fallbacks(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { parseHashRoute, serializeRoute } = await import(
            `${base}/static/js/ui-next/router.js?release=wp02.1`
          );
          const explain = code => `localized:${code}`;
          const valid = parseHashRoute(
            "#/library/characters?filter=recent&page=2",
            { explain },
          );
          const unknownDestination = parseHashRoute("#/elsewhere", { explain });
          const unknownChild = parseHashRoute("#/settings/not-real", { explain });
          const malformed = parseHashRoute("#/library/%E0%A4%A", { explain });
          const prototypeQuery = parseHashRoute(
            "#/play?__proto__=polluted",
            { explain },
          );
          const overlong = parseHashRoute(
            `#/play?filter=${"x".repeat(201)}`,
            { explain },
          );
          return {
            valid,
            serialized: serializeRoute({
              destination: "settings",
              segments: ["language"],
              query: { z: "last", a: "first" },
            }),
            unknownDestination,
            unknownChild,
            malformed,
            prototypeQuery,
            overlong,
            prototypeUntouched: ({}).polluted === undefined,
          };
        }""",
        ui_base_url,
    )
    assert result["valid"] == {
        "valid": True,
        "destination": "library",
        "segments": ["characters"],
        "query": {"filter": "recent", "page": "2"},
        "canonicalHash": "#/library/characters?filter=recent&page=2",
        "explanation": "",
        "reason": "",
        "layers": [],
    }
    assert result["serialized"] == "#/settings/language?a=first&z=last"
    assert result["unknownDestination"]["destination"] == "play"
    assert result["unknownDestination"]["reason"] == "unknown-destination"
    assert result["unknownDestination"]["explanation"] == (
        "localized:route.unknown-destination"
    )
    for key, reason in (
        ("unknownChild", "unknown-segment"),
        ("malformed", "malformed-route"),
        ("prototypeQuery", "unsafe-query"),
        ("overlong", "query-too-long"),
    ):
        assert result[key]["valid"] is False
        assert result[key]["reason"] == reason
    assert result["unknownChild"]["destination"] == "settings"
    assert result["malformed"]["destination"] == "library"
    assert result["prototypeUntouched"] is True


def test_router_history_unwinds_layers_and_restores_focus_identity(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html#/play")
    result = page.evaluate(
        """async (base) => {
          const { createRouter } = await import(
            `${base}/static/js/ui-next/router.js?release=wp02.1`
          );
          history.replaceState(null, "", "#/play");
          const routes = [];
          const focusReturns = [];
          const router = createRouter({
            target: window,
            onRoute: route => routes.push({
              destination: route.destination,
              layers: route.layers.map(layer => layer.id),
            }),
            onFocusReturn: identity => focusReturns.push(identity),
          });
          router.start();
          router.navigate({ destination: "library", segments: ["stories"] });
          router.openLayer({ id: "story-actions", focusReturn: "story-card-17" });
          router.openLayer({ id: "delete-confirm", focusReturn: "delete-story-17" });
          const beforeBack = router.current();
          const backOnce = new Promise(resolve => {
            window.addEventListener("popstate", () => setTimeout(resolve, 0), { once: true });
          });
          history.back();
          await backOnce;
          const afterOne = router.current();
          const backTwice = new Promise(resolve => {
            window.addEventListener("popstate", () => setTimeout(resolve, 0), { once: true });
          });
          history.back();
          await backTwice;
          const afterTwo = router.current();
          const beforeStopCount = routes.length;
          router.stop();
          window.dispatchEvent(new HashChangeEvent("hashchange"));
          return {
            beforeBack: beforeBack.layers.map(layer => ({
              id: layer.id,
              focusReturn: layer.focusReturn,
              hasNode: Object.values(layer).some(value => value instanceof Node),
            })),
            afterOne: afterOne.layers.map(layer => layer.id),
            afterTwo: afterTwo.layers.map(layer => layer.id),
            destination: afterTwo.destination,
            focusReturns,
            stopped: routes.length === beforeStopCount,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "beforeBack": [
            {"id": "story-actions", "focusReturn": "story-card-17", "hasNode": False},
            {"id": "delete-confirm", "focusReturn": "delete-story-17", "hasNode": False},
        ],
        "afterOne": ["story-actions"],
        "afterTwo": [],
        "destination": "library",
        "focusReturns": ["delete-story-17", "story-card-17"],
        "stopped": True,
    }


def test_localizer_applies_explicit_chrome_rules_and_preserves_data(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createLocalizer } = await import(
            `${base}/static/js/ui-next/localization.js?release=wp02.1`
          );
          const longSource = `Long ${"explanation ".repeat(30)}`.trim();
          const longTarget = `長い ${"説明".repeat(180)}`;
          const localizer = createLocalizer({
            language: "ja",
            direction: "rtl",
            messages: {
              "Open story": "物語を開く",
              "Story title": "物語のタイトル",
              "Saved {count} stories": "{count}件の物語を保存しました",
              "${name} is ready": "${name}の準備ができました",
              [longSource]: longTarget,
            },
          });
          const doc = document.implementation.createHTMLDocument("test");
          const root = doc.body;
          const chrome = doc.createElement("p");
          chrome.textContent = "Open story";
          chrome.title = "Open story";
          const story = doc.createElement("p");
          story.setAttribute("translate", "no");
          story.textContent = "Open story";
          story.title = "Open story";
          const model = doc.createElement("p");
          model.dataset.noI18n = "";
          model.textContent = "Open story";
          const input = doc.createElement("input");
          input.value = "Open story";
          input.placeholder = "Story title";
          const editable = doc.createElement("div");
          editable.contentEditable = "true";
          editable.textContent = "Open story";
          root.append(chrome, story, model, input, editable);
          localizer.localize(root);
          let invalidProjection = null;
          try {
            createLocalizer({
              language: "ja",
              direction: "ltr",
              messages: { "Saved {count} stories": "保存しました" },
            });
          } catch (error) {
            invalidProjection = error.kind;
          }
          return {
            exact: localizer.t("Open story"),
            variable: localizer.t("Saved {count} stories", { count: 3 }),
            template: localizer.t("Aya is ready"),
            longCopy: localizer.t(longSource) === longTarget,
            chrome: chrome.textContent,
            chromeTitle: chrome.title,
            story: story.textContent,
            storyTitle: story.title,
            model: model.textContent,
            inputValue: input.value,
            inputPlaceholder: input.placeholder,
            editable: editable.textContent,
            language: doc.documentElement.lang,
            direction: doc.documentElement.dir,
            invalidProjection,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "exact": "物語を開く",
        "variable": "3件の物語を保存しました",
        "template": "Ayaの準備ができました",
        "longCopy": True,
        "chrome": "物語を開く",
        "chromeTitle": "物語を開く",
        "story": "Open story",
        "storyTitle": "Open story",
        "model": "Open story",
        "inputValue": "Open story",
        "inputPlaceholder": "物語のタイトル",
        "editable": "Open story",
        "language": "ja",
        "direction": "rtl",
        "invalidProjection": "placeholder-mismatch",
    }


def test_content_boundary_uses_text_nodes_and_rebuilds_allowlisted_rich_text(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { setText, appendSafeRichText } = await import(
            `${base}/static/js/ui-next/content.js?release=wp02.1`
          );
          const textHost = document.createElement("div");
          setText(textHost, '<img src=x onerror="window.pwned=1">');
          const richHost = document.createElement("div");
          appendSafeRichText(richHost, `
            <p class="bad" style="color:red" onclick="evil()">
              Hello <strong data-bad="1">safe</strong>
              <script>window.pwned=2</script>
              <svg><script>window.pwned=3</script></svg>
              <math><mi>bad</mi></math>
              <custom-element>unknown</custom-element>
              <a href="javascript:evil()" target="_blank">unsafe</a>
              <a href="https://example.com/help" target="_blank">safe link</a>
              <a href="/guide">relative</a>
            </p>
          `);
          return {
            text: textHost.textContent,
            textChildren: textHost.children.length,
            pwned: Boolean(window.pwned),
            safeStrong: richHost.querySelector("strong")?.textContent,
            containsUnknownText: richHost.textContent.includes("unknown"),
            scripts: richHost.querySelectorAll("script,svg,math,custom-element").length,
            eventAttributes: richHost.querySelectorAll("[onclick],[style],[data-bad]").length,
            unsafeHref: richHost.querySelector("a")?.hasAttribute("href"),
            safeHref: richHost.querySelectorAll("a")[1]?.getAttribute("href"),
            safeRel: richHost.querySelectorAll("a")[1]?.getAttribute("rel"),
            relativeHref: richHost.querySelectorAll("a")[2]?.getAttribute("href"),
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "text": '<img src=x onerror="window.pwned=1">',
        "textChildren": 0,
        "pwned": False,
        "safeStrong": "safe",
        "containsUnknownText": False,
        "scripts": 0,
        "eventAttributes": 0,
        "unsafeHref": False,
        "safeHref": "https://example.com/help",
        "safeRel": "noopener noreferrer",
        "relativeHref": "/guide",
    }


def test_task_service_tracks_lifecycle_elapsed_time_and_bounded_cleanup(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createTaskService } = await import(
            `${base}/static/js/ui-next/tasks.js?release=wp02.1`
          );
          let now = 100;
          let cancelCalls = 0;
          const changes = [];
          const tasks = createTaskService({
            limit: 2,
            clock: () => now,
            onChange: snapshot => changes.push(snapshot.map(task => task.status)),
          });
          const first = tasks.start({
            owner: "story-a",
            requestId: 4,
            correlationId: "corr-4",
            name: "Load story",
            phase: "reading",
            progress: 0.2,
          });
          now = 175;
          tasks.update(first, { phase: "assembling", progress: 0.75 });
          const running = tasks.snapshot()[0];
          tasks.complete(first, { summary: "Ready" });
          const second = tasks.start({
            owner: "story-a",
            name: "Generate",
            cancel: () => { cancelCalls += 1; },
          });
          await tasks.cancel(second);
          await tasks.cancel(second);
          const third = tasks.start({ owner: "story-b", name: "Refresh" });
          tasks.fail(third, { kind: "network", userMessage: "Offline" });
          const final = tasks.snapshot();
          return {
            running,
            final,
            cancelCalls,
            changeCount: changes.length,
          };
        }""",
        ui_base_url,
    )
    assert result["running"] == {
        "id": "task-1",
        "owner": "story-a",
        "requestId": 4,
        "correlationId": "corr-4",
        "name": "Load story",
        "phase": "assembling",
        "status": "running",
        "progress": 0.75,
        "startedAt": 100,
        "finishedAt": None,
        "elapsedMs": 75,
        "summary": "",
        "error": None,
        "cancellable": False,
    }
    assert result["cancelCalls"] == 1
    assert result["changeCount"] == 7
    assert [task["id"] for task in result["final"]] == ["task-2", "task-3"]
    assert [task["status"] for task in result["final"]] == ["cancelled", "failed"]
    assert result["final"][1]["error"] == {
        "kind": "network",
        "message": "Offline",
    }


def test_notices_distinguish_acknowledgement_condition_and_safe_retry(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createNoticeService } = await import(
            `${base}/static/js/ui-next/notices.js?release=wp02.1`
          );
          const notices = createNoticeService({ limit: 3 });
          let retries = 0;
          const acknowledgement = notices.publish({
            owner: "library",
            kind: "acknowledgement",
            message: "Imported",
          });
          const persistent = notices.problem({
            owner: "story-a",
            condition: "offline",
            message: "Still offline",
            error: { kind: "network", retryable: true },
            retry: () => { retries += 1; return "retried"; },
          });
          const unsafe = notices.problem({
            owner: "story-a",
            condition: "delete-failed",
            message: "Delete failed",
            error: { kind: "network", retryable: false },
            retry: () => { retries += 100; },
          });
          const retryResult = await notices.retry(persistent);
          const unsafeRetry = await notices.retry(unsafe);
          notices.acknowledge(acknowledgement);
          const afterAcknowledge = notices.snapshot();
          const overflow = notices.publish({
            owner: "runtime",
            kind: "acknowledgement",
            message: "Newer acknowledgement",
          });
          const boundedIds = notices.snapshot().map(notice => notice.id);
          notices.clearCondition("story-a", "offline");
          notices.dismiss(unsafe);
          notices.dismiss(overflow);
          const final = notices.snapshot();
          return {
            retryResult,
            unsafeRetry,
            retries,
            afterAcknowledge,
            boundedIds,
            final,
          };
        }""",
        ui_base_url,
    )
    assert result["retryResult"] == "retried"
    assert result["unsafeRetry"] is False
    assert result["retries"] == 1
    assert result["afterAcknowledge"] == [
        {
            "id": "notice-1",
            "owner": "library",
            "condition": "",
            "kind": "acknowledgement",
            "message": "Imported",
            "persistent": False,
            "recoverable": False,
            "acknowledged": True,
            "canRetry": False,
        },
        {
            "id": "notice-2",
            "owner": "story-a",
            "condition": "offline",
            "kind": "problem",
            "message": "Still offline",
            "persistent": True,
            "recoverable": True,
            "acknowledged": False,
            "canRetry": True,
        },
        {
            "id": "notice-3",
            "owner": "story-a",
            "condition": "delete-failed",
            "kind": "problem",
            "message": "Delete failed",
            "persistent": True,
            "recoverable": True,
            "acknowledged": False,
            "canRetry": False,
        },
    ]
    assert result["boundedIds"] == ["notice-2", "notice-3", "notice-4"]
    assert result["final"] == []


def test_diagnostics_are_opt_in_bounded_and_recursively_redacted(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createDiagnostics } = await import(
            `${base}/static/js/ui-next/diagnostics.js?release=wp02.1`
          );
          const diagnostics = createDiagnostics({ enabled: false, limit: 2 });
          diagnostics.record({ ignored: true, password: "first" });
          diagnostics.setEnabled(true);
          diagnostics.record({
            kind: "request",
            password: "hunter2",
            nested: {
              Authorization: "Bearer abc.def.ghi",
              url: "/api/test?token=secret-token&safe=yes",
              note: "uses sk-supersecretvalue",
              safe: "visible",
            },
          });
          const redacted = diagnostics.snapshot()[0];
          diagnostics.record({ kind: "second", cookie: "session=private" });
          diagnostics.record({ kind: "third", value: "plain" });
          const snapshot = diagnostics.snapshot();
          const mutable = snapshot[0];
          const mutationRejected = Reflect.set(mutable, "kind", "changed") === false;
          return { redacted, snapshot, mutationRejected };
        }""",
        ui_base_url,
    )
    assert result == {
        "redacted": {
            "kind": "request",
            "password": "[redacted]",
            "nested": {
                "Authorization": "[redacted]",
                "url": "/api/test?token=[redacted]&safe=yes",
                "note": "uses [redacted]",
                "safe": "visible",
            },
        },
        "snapshot": [
            {"kind": "second", "cookie": "[redacted]"},
            {"kind": "third", "value": "plain"},
        ],
        "mutationRejected": True,
    }


def test_local_storage_migrates_members_and_isolates_story_drafts(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createLocalState } = await import(
            `${base}/static/js/ui-next/storage.js?release=wp02.1`
          );
          const memory = new Map();
          let writes = 0;
          const storage = {
            getItem: key => memory.get(key) ?? null,
            setItem: (key, value) => { writes += 1; memory.set(key, value); },
            removeItem: key => memory.delete(key),
          };
          memory.set("sonder.ui-next", JSON.stringify({
            version: 1,
            theme: "ash-brass",
            lastRoute: "#/library/stories",
            sidePane: "closed",
            drafts: { "story:alpha": "alpha draft" },
          }));
          const first = createLocalState({ storage });
          const migrated = first.snapshot();
          const second = createLocalState({ storage });
          const writesAfterTwoReads = writes;
          second.setDraft("story", "beta", "beta draft");
          const isolated = {
            alpha: second.getDraft("story", "alpha"),
            beta: second.getDraft("story", "beta"),
            otherType: second.getDraft("character", "beta"),
          };
          second.clearDraft("story", "beta");
          return {
            migrated,
            writesAfterTwoReads,
            isolated,
            afterClear: second.getDraft("story", "beta"),
            storedVersion: JSON.parse(memory.get("sonder.ui-next")).version,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "migrated": {
            "version": 2,
            "appearance": {"theme": "ash-brass"},
            "navigation": {"route": "#/library/stories"},
            "panes": {"side": "closed"},
            "drafts": {"story": {"alpha": "alpha draft"}},
        },
        "writesAfterTwoReads": 1,
        "isolated": {
            "alpha": "alpha draft",
            "beta": "beta draft",
            "otherType": None,
        },
        "afterClear": None,
        "storedVersion": 2,
    }


def test_local_storage_discards_only_bad_members_and_survives_write_failure(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createLocalState } = await import(
            `${base}/static/js/ui-next/storage.js?release=wp02.1`
          );
          const errors = [];
          const storage = {
            value: JSON.stringify({
              version: 2,
              appearance: "broken",
              navigation: { route: "#/settings/language" },
              panes: { inspector: "open" },
              drafts: { story: { alpha: "safe" }, character: 4 },
            }),
            getItem() { return this.value; },
            setItem() { throw new DOMException("quota", "QuotaExceededError"); },
            removeItem() {},
          };
          const state = createLocalState({
            storage,
            onError: error => errors.push(error.kind),
          });
          const loaded = state.snapshot();
          const persisted = state.setRecord("appearance", {
            theme: "midnight-ink",
          });
          let sensitive = null;
          try {
            state.setDraft("story", "alpha", "Bearer super-secret-token");
          } catch (error) {
            sensitive = error.kind;
          }
          return {
            loaded,
            persisted,
            inMemoryTheme: state.snapshot().appearance.theme,
            sensitive,
            errors,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "loaded": {
            "version": 2,
            "appearance": {},
            "navigation": {"route": "#/settings/language"},
            "panes": {"inspector": "open"},
            "drafts": {"story": {"alpha": "safe"}},
        },
        "persisted": False,
        "inMemoryTheme": "midnight-ink",
        "sensitive": "sensitive-material",
        "errors": ["invalid-member", "invalid-member", "storage-write"],
    }


def test_credential_submitter_allowlists_routes_and_always_clears_secrets(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { submitCredentialForm } = await import(
            `${base}/static/js/ui-next/credentials.js?release=wp02.1`
          );
          const calls = [];
          const apiClient = {
            request: async (method, path, options) => {
              calls.push({ method, path, body: { ...options.body } });
              return { data: { ok: true }, status: 200 };
            },
          };
          const form = document.createElement("form");
          const username = document.createElement("input");
          username.name = "username";
          username.value = "keeper";
          const password = document.createElement("input");
          password.name = "password";
          password.type = "password";
          password.value = "correct horse battery staple";
          form.append(username, password);
          const response = await submitCredentialForm({
            form,
            apiClient,
            method: "POST",
            endpoint: "/api/auth/login",
          });
          password.value = "must-clear-on-refusal";
          let refusal = null;
          try {
            await submitCredentialForm({
              form,
              apiClient,
              method: "POST",
              endpoint: "/api/chats?token=bad",
            });
          } catch (error) {
            refusal = error.kind;
          }
          return {
            calls,
            response,
            passwordAfterSuccess: calls.length ? password.value : "not-called",
            refusal,
            passwordAfterRefusal: password.value,
            url: location.href,
            storageContainsSecret: Object.values(localStorage).some(value => (
              String(value).includes("correct horse")
              || String(value).includes("must-clear")
            )),
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "calls": [
            {
                "method": "POST",
                "path": "/api/auth/login",
                "body": {
                    "username": "keeper",
                    "password": "correct horse battery staple",
                },
            }
        ],
        "response": {"data": {"ok": True}, "status": 200},
        "passwordAfterSuccess": "",
        "refusal": "credential-route",
        "passwordAfterRefusal": "",
        "url": f"{ui_base_url}/static/ui-next-lab.html",
        "storageContainsSecret": False,
    }
