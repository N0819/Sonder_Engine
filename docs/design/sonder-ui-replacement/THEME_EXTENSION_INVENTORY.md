# Current theme, localization, and extension inventory

**Themes:** `ash-brass`, `carbon-signal`, `midnight-ink`, `parchment-night`
**CSS custom properties:** 70

**UI catalog keys:** 779

## Extension routes

| Method | Route | Source |
|---|---|---|
| GET | `/api/extensions` | `web/app.py:1857` |
| POST | `/api/extensions/install` | `web/app.py:1879` |
| GET | `/api/extensions/ui.css` | `web/app.py:2057` |
| GET | `/api/extensions/ui.js` | `web/app.py:2048` |
| GET | `/api/extensions/updates` | `web/app.py:1900` |
| DELETE | `/api/extensions/{eid}` | `web/app.py:1921` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `web/app.py:2112` |
| POST | `/api/extensions/{eid}/disable` | `web/app.py:1929` |
| DELETE | `/api/extensions/{eid}/document` | `web/app.py:2025` |
| GET | `/api/extensions/{eid}/document` | `web/app.py:1993` |
| PUT | `/api/extensions/{eid}/document` | `web/app.py:2005` |
| DELETE | `/api/extensions/{eid}/documents` | `web/app.py:2035` |
| GET | `/api/extensions/{eid}/documents` | `web/app.py:1972` |
| GET | `/api/extensions/{eid}/documents/verify` | `web/app.py:1983` |
| POST | `/api/extensions/{eid}/enable` | `web/app.py:1871` |
| GET | `/api/extensions/{eid}/state` | `web/app.py:1934` |
| GET | `/api/extensions/{eid}/ui.css` | `web/app.py:2079` |
| GET | `/api/extensions/{eid}/ui.js` | `web/app.py:2067` |
| POST | `/api/extensions/{eid}/update` | `web/app.py:1911` |
