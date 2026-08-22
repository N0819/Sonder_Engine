# Current theme, localization, and extension inventory

**Themes:** `ash-brass`, `carbon-signal`, `ink`, `lcars`, `midnight-ink`, `parchment-night`, `stone`, `tavern`  
**CSS custom properties:** 155
**UI catalog keys:** 2035

## Extension routes

| Method | Route | Source |
|---|---|---|
| GET | `/api/extensions` | `web/app.py:1860` |
| POST | `/api/extensions/install` | `web/app.py:1882` |
| GET | `/api/extensions/ui.css` | `web/app.py:2060` |
| GET | `/api/extensions/ui.js` | `web/app.py:2051` |
| GET | `/api/extensions/updates` | `web/app.py:1903` |
| DELETE | `/api/extensions/{eid}` | `web/app.py:1924` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `web/app.py:2115` |
| POST | `/api/extensions/{eid}/disable` | `web/app.py:1932` |
| DELETE | `/api/extensions/{eid}/document` | `web/app.py:2028` |
| GET | `/api/extensions/{eid}/document` | `web/app.py:1996` |
| PUT | `/api/extensions/{eid}/document` | `web/app.py:2008` |
| DELETE | `/api/extensions/{eid}/documents` | `web/app.py:2038` |
| GET | `/api/extensions/{eid}/documents` | `web/app.py:1975` |
| GET | `/api/extensions/{eid}/documents/verify` | `web/app.py:1986` |
| POST | `/api/extensions/{eid}/enable` | `web/app.py:1874` |
| GET | `/api/extensions/{eid}/state` | `web/app.py:1937` |
| GET | `/api/extensions/{eid}/ui.css` | `web/app.py:2082` |
| GET | `/api/extensions/{eid}/ui.js` | `web/app.py:2070` |
| POST | `/api/extensions/{eid}/update` | `web/app.py:1914` |
