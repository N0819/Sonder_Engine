# Current theme, localization, and extension inventory

**Themes:** `ink`, `lcars`, `stone`, `tavern`  
**CSS custom properties:** 86  
**UI catalog keys:** 1960  

## Extension routes

| Method | Route | Source |
|---|---|---|
| GET | `/api/extensions` | `web/app.py:1759` |
| POST | `/api/extensions/install` | `web/app.py:1781` |
| GET | `/api/extensions/ui.css` | `web/app.py:1959` |
| GET | `/api/extensions/ui.js` | `web/app.py:1950` |
| GET | `/api/extensions/updates` | `web/app.py:1802` |
| DELETE | `/api/extensions/{eid}` | `web/app.py:1823` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `web/app.py:2014` |
| POST | `/api/extensions/{eid}/disable` | `web/app.py:1831` |
| DELETE | `/api/extensions/{eid}/document` | `web/app.py:1927` |
| GET | `/api/extensions/{eid}/document` | `web/app.py:1895` |
| PUT | `/api/extensions/{eid}/document` | `web/app.py:1907` |
| DELETE | `/api/extensions/{eid}/documents` | `web/app.py:1937` |
| GET | `/api/extensions/{eid}/documents` | `web/app.py:1874` |
| GET | `/api/extensions/{eid}/documents/verify` | `web/app.py:1885` |
| POST | `/api/extensions/{eid}/enable` | `web/app.py:1773` |
| GET | `/api/extensions/{eid}/state` | `web/app.py:1836` |
| GET | `/api/extensions/{eid}/ui.css` | `web/app.py:1981` |
| GET | `/api/extensions/{eid}/ui.js` | `web/app.py:1969` |
| POST | `/api/extensions/{eid}/update` | `web/app.py:1813` |
