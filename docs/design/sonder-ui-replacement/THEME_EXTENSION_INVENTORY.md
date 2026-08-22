# Current theme, localization, and extension inventory

**Themes:** `ink`, `lcars`, `stone`, `tavern`  
**CSS custom properties:** 86  
**UI catalog keys:** 1960  

## Extension routes

| Method | Route | Source |
|---|---|---|
| GET | `/api/extensions` | `web/app.py:1810` |
| POST | `/api/extensions/install` | `web/app.py:1832` |
| GET | `/api/extensions/ui.css` | `web/app.py:2010` |
| GET | `/api/extensions/ui.js` | `web/app.py:2001` |
| GET | `/api/extensions/updates` | `web/app.py:1853` |
| DELETE | `/api/extensions/{eid}` | `web/app.py:1874` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `web/app.py:2065` |
| POST | `/api/extensions/{eid}/disable` | `web/app.py:1882` |
| DELETE | `/api/extensions/{eid}/document` | `web/app.py:1978` |
| GET | `/api/extensions/{eid}/document` | `web/app.py:1946` |
| PUT | `/api/extensions/{eid}/document` | `web/app.py:1958` |
| DELETE | `/api/extensions/{eid}/documents` | `web/app.py:1988` |
| GET | `/api/extensions/{eid}/documents` | `web/app.py:1925` |
| GET | `/api/extensions/{eid}/documents/verify` | `web/app.py:1936` |
| POST | `/api/extensions/{eid}/enable` | `web/app.py:1824` |
| GET | `/api/extensions/{eid}/state` | `web/app.py:1887` |
| GET | `/api/extensions/{eid}/ui.css` | `web/app.py:2032` |
| GET | `/api/extensions/{eid}/ui.js` | `web/app.py:2020` |
| POST | `/api/extensions/{eid}/update` | `web/app.py:1864` |
