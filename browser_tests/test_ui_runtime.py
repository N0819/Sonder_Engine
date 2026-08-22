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
