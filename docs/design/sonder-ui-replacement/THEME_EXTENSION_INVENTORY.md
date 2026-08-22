# Current theme, localization, and extension inventory

**Themes:** `ash-brass`, `carbon-signal`, `ink`, `lcars`, `midnight-ink`, `parchment-night`, `stone`, `tavern`  
**CSS custom properties:** 156

**UI catalog keys:** 2293

## Extension routes

| Method | Route | Source |
|---|---|---|
| GET | `/api/extensions` | `web/app.py:1862` |
| POST | `/api/extensions/install` | `web/app.py:1884` |
| GET | `/api/extensions/ui.css` | `web/app.py:2062` |
| GET | `/api/extensions/ui.js` | `web/app.py:2053` |
| GET | `/api/extensions/updates` | `web/app.py:1905` |
| DELETE | `/api/extensions/{eid}` | `web/app.py:1926` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `web/app.py:2117` |
| POST | `/api/extensions/{eid}/disable` | `web/app.py:1934` |
| DELETE | `/api/extensions/{eid}/document` | `web/app.py:2030` |
| GET | `/api/extensions/{eid}/document` | `web/app.py:1998` |
| PUT | `/api/extensions/{eid}/document` | `web/app.py:2010` |
| DELETE | `/api/extensions/{eid}/documents` | `web/app.py:2040` |
| GET | `/api/extensions/{eid}/documents` | `web/app.py:1977` |
| GET | `/api/extensions/{eid}/documents/verify` | `web/app.py:1988` |
| POST | `/api/extensions/{eid}/enable` | `web/app.py:1876` |
| GET | `/api/extensions/{eid}/state` | `web/app.py:1939` |
| GET | `/api/extensions/{eid}/ui.css` | `web/app.py:2084` |
| GET | `/api/extensions/{eid}/ui.js` | `web/app.py:2072` |
| POST | `/api/extensions/{eid}/update` | `web/app.py:1916` |
