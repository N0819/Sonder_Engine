# Current theme, localization, and extension inventory

**Themes:** `ash-brass`, `carbon-signal`, `ink`, `lcars`, `midnight-ink`, `parchment-night`, `stone`, `tavern`  
**CSS custom properties:** 153  
**UI catalog keys:** 1963  

## Extension routes

| Method | Route | Source |
|---|---|---|
| GET | `/api/extensions` | `web/app.py:1818` |
| POST | `/api/extensions/install` | `web/app.py:1840` |
| GET | `/api/extensions/ui.css` | `web/app.py:2018` |
| GET | `/api/extensions/ui.js` | `web/app.py:2009` |
| GET | `/api/extensions/updates` | `web/app.py:1861` |
| DELETE | `/api/extensions/{eid}` | `web/app.py:1882` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `web/app.py:2073` |
| POST | `/api/extensions/{eid}/disable` | `web/app.py:1890` |
| DELETE | `/api/extensions/{eid}/document` | `web/app.py:1986` |
| GET | `/api/extensions/{eid}/document` | `web/app.py:1954` |
| PUT | `/api/extensions/{eid}/document` | `web/app.py:1966` |
| DELETE | `/api/extensions/{eid}/documents` | `web/app.py:1996` |
| GET | `/api/extensions/{eid}/documents` | `web/app.py:1933` |
| GET | `/api/extensions/{eid}/documents/verify` | `web/app.py:1944` |
| POST | `/api/extensions/{eid}/enable` | `web/app.py:1832` |
| GET | `/api/extensions/{eid}/state` | `web/app.py:1895` |
| GET | `/api/extensions/{eid}/ui.css` | `web/app.py:2040` |
| GET | `/api/extensions/{eid}/ui.js` | `web/app.py:2028` |
| POST | `/api/extensions/{eid}/update` | `web/app.py:1872` |
