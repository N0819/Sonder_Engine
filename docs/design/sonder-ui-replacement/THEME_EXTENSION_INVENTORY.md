# Current theme, localization, and extension inventory

**Themes:** `ash-brass`, `carbon-signal`, `ink`, `lcars`, `midnight-ink`, `parchment-night`, `stone`, `tavern`  
**CSS custom properties:** 156

**UI catalog keys:** 2414

## Extension routes

| Method | Route | Source |
|---|---|---|
| GET | `/api/extensions` | `web/app.py:1868` |
| POST | `/api/extensions/install` | `web/app.py:1890` |
| GET | `/api/extensions/ui.css` | `web/app.py:2068` |
| GET | `/api/extensions/ui.js` | `web/app.py:2059` |
| GET | `/api/extensions/updates` | `web/app.py:1911` |
| DELETE | `/api/extensions/{eid}` | `web/app.py:1932` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `web/app.py:2123` |
| POST | `/api/extensions/{eid}/disable` | `web/app.py:1940` |
| DELETE | `/api/extensions/{eid}/document` | `web/app.py:2036` |
| GET | `/api/extensions/{eid}/document` | `web/app.py:2004` |
| PUT | `/api/extensions/{eid}/document` | `web/app.py:2016` |
| DELETE | `/api/extensions/{eid}/documents` | `web/app.py:2046` |
| GET | `/api/extensions/{eid}/documents` | `web/app.py:1983` |
| GET | `/api/extensions/{eid}/documents/verify` | `web/app.py:1994` |
| POST | `/api/extensions/{eid}/enable` | `web/app.py:1882` |
| GET | `/api/extensions/{eid}/state` | `web/app.py:1945` |
| GET | `/api/extensions/{eid}/ui.css` | `web/app.py:2090` |
| GET | `/api/extensions/{eid}/ui.js` | `web/app.py:2078` |
| POST | `/api/extensions/{eid}/update` | `web/app.py:1922` |
