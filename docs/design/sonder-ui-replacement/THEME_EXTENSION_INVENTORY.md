# Current theme, localization, and extension inventory

**Themes:** `ink`, `lcars`, `stone`, `tavern`  
**CSS custom properties:** 86  
**UI catalog keys:** 1960  

## Extension routes

| Method | Route | Source |
|---|---|---|
| GET | `/api/extensions` | `web/app.py:1773` |
| POST | `/api/extensions/install` | `web/app.py:1795` |
| GET | `/api/extensions/ui.css` | `web/app.py:1973` |
| GET | `/api/extensions/ui.js` | `web/app.py:1964` |
| GET | `/api/extensions/updates` | `web/app.py:1816` |
| DELETE | `/api/extensions/{eid}` | `web/app.py:1837` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `web/app.py:2028` |
| POST | `/api/extensions/{eid}/disable` | `web/app.py:1845` |
| DELETE | `/api/extensions/{eid}/document` | `web/app.py:1941` |
| GET | `/api/extensions/{eid}/document` | `web/app.py:1909` |
| PUT | `/api/extensions/{eid}/document` | `web/app.py:1921` |
| DELETE | `/api/extensions/{eid}/documents` | `web/app.py:1951` |
| GET | `/api/extensions/{eid}/documents` | `web/app.py:1888` |
| GET | `/api/extensions/{eid}/documents/verify` | `web/app.py:1899` |
| POST | `/api/extensions/{eid}/enable` | `web/app.py:1787` |
| GET | `/api/extensions/{eid}/state` | `web/app.py:1850` |
| GET | `/api/extensions/{eid}/ui.css` | `web/app.py:1995` |
| GET | `/api/extensions/{eid}/ui.js` | `web/app.py:1983` |
| POST | `/api/extensions/{eid}/update` | `web/app.py:1827` |
