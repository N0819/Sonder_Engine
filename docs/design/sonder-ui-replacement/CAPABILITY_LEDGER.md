# Current capability ledger

Evidence map for the completed replacement; WP14 is the release authority.

| ID | Capability | Current authority / evidence | Owner | Mobile | Disposition |
|---|---|---|---|---|---|
| `CAP-PLAY-OPEN` | Open and switch stories | static/js/ui-next/play-runtime.js; /api/chats/{cid} | WP-04 | required | replace |
| `CAP-PLAY-TRANSCRIPT` | Read transcript and player turns | static/js/ui-next/play-view.js | WP-04 | required | adapt |
| `CAP-PLAY-STREAM` | Submit, stream, stop, retry, and recover turns | static/js/ui-next/play-runtime.js; pipeline routes | WP-04 | required | adapt |
| `CAP-PLAY-DRAFT` | Keep composer drafts isolated per story | composer input and browser state | WP-04 | required | rebuild |
| `CAP-PLAY-SCROLLBACK` | Load long transcript scrollback | static/js/ui-next/play-runtime.js; Play browser tests | WP-04 | required | adapt |
| `CAP-PLAY-REROLL` | Reroll and select narration variants | static/js/ui-next/play-runtime.js; narration variant routes | WP-04 | required | adapt |
| `CAP-PLAY-FRAMES` | Inspect and select story frames | frame routes and current dialogs | WP-05 | required | adapt |
| `CAP-PLAY-CONDITION` | View player and NPC condition/vitals | static/js/ui-next/story-tools/conditions.js; vitals routes; UNBUILT §1.66 | WP-05 | required | rebuild |
| `CAP-PLAY-WORLD` | Inspect world and positions | world/position routes and dialogs | WP-05 | required | replace |
| `CAP-PLAY-CAST` | Manage current story cast | character association routes and dialogs | WP-05 | required | replace |
| `CAP-PLAY-STYLE` | Edit style guide and dialogue configuration | style/dialogue routes | WP-05 | required | replace |
| `CAP-PLAY-ATTIRE` | Inspect and author attire | attire route and authoring dialog | WP-05 | required | replace |
| `CAP-PLAY-BACKDROP` | Commission, select, and display backdrops | static/js/ui-next/story-tools/backdrops.js | WP-05 | required | adapt |
| `CAP-PLAY-AMBIENCE` | Search, pin, play, mute, and stop ambience | static/js/ui-next/story-tools/ambience.js | WP-05 | required | adapt |
| `CAP-PLAY-WEATHER` | Render and configure weather effects | static/js/ui-next/play-view.js; UNBUILT §2.11 | WP-05 | required | adapt |
| `CAP-LIB-STORIES` | List, search, create, rename, archive, import, and export stories | static/js/ui-next/library-runtime.js; chat routes | WP-06 | required | rebuild |
| `CAP-LIB-CHARACTERS` | List, import, export, edit, and reuse characters | static/js/ui-next/library-authoring-runtime.js | WP-06 | required | rebuild |
| `CAP-LIB-PERSONAS` | List, import, export, edit, and reuse personas | static/js/ui-next/library-authoring-runtime.js | WP-06 | required | rebuild |
| `CAP-LIB-LORE` | Browse, edit, import, export, and reuse lorebooks | static/js/ui-next/library-runtime.js | WP-06 | required | rebuild |
| `CAP-LIB-SCOPE` | Filter reusable assets by story association | association routes | WP-06 | required | rebuild |
| `CAP-LIB-EDITORS` | Preserve every editor field, validation, and draft | static/js/ui-next/library-authoring-runtime.js; library-editors/ | WP-07 | required | replace |
| `CAP-SET-EXPERIENCE` | Configure theme, reading, language, sound, motion, and accessibility | static/js/ui-next/settings-view.js; static/css/ui/themes/ | WP-08 | required | replace |
| `CAP-SET-AI` | Configure providers, models, roles, credentials, and generation defaults | static/js/ui-next/settings-view.js; provider routes | WP-08 | required | replace |
| `CAP-SET-CONTENT` | Configure content/data handling and imports/exports | static/js/ui-next/settings-view.js | WP-08 | required | replace |
| `CAP-SET-ADDONS` | Install, configure, enable, disable, update, and retire extensions | static/js/ui-next/extensions.js; extension routes | WP-08 | required | replace |
| `CAP-SET-MAINT` | Run updates, backups, repairs, logs, and maintenance | static/js/ui-next/settings-view.js; maintenance routes; UNBUILT §1.58 | WP-08 | required | replace |
| `CAP-SET-ADVANCED` | Edit prompts, parameters, diagnostics, and raw story data | static/js/ui-next/settings-view.js | WP-08 | required | replace |
| `CAP-NEW-DESCRIBE` | Create a generated story from a description | newChatWizard and chat creation routes | WP-09 | required | adapt |
| `CAP-NEW-LIBRARY` | Create a story from reusable Library assets | current creation and association routes | WP-09 | required | replace |
| `CAP-NEW-BLANK` | Create a blank story without a provider | chat creation route | WP-09 | required | adapt |
| `CAP-AUTH-SETUP` | Claim a new host safely | static/login.html; auth setup route | WP-10 | required | adapt |
| `CAP-AUTH-LOGIN` | Sign in, lock out abusive retries, and sign out | login.html; auth routes | WP-10 | required | adapt |
| `CAP-AUTH-SESSION` | Recover predictably from session expiry | API/session guards | WP-10 | required | adapt |
| `CAP-GUEST-JOIN` | Redeem a guest join code | static/guest.html; guest routes | WP-11 | required | adapt |
| `CAP-GUEST-PLAY` | Read and submit guest turns with session limits | guest.html; guest state/turn routes | WP-11 | required | adapt |
| `CAP-THEME-CURATED` | Use curated semantic themes without layout changes | static/css/ui/themes/; static/js/ui/appearance.js | WP-12 | required | replace |
| `CAP-THEME-LEGACY` | Retain usable Legacy theme mappings | static/js/ui-next/settings-view.js | WP-12 | required | adapt |
| `CAP-A11Y` | Use keyboard, screen reader, zoom, contrast, motion, and target preferences | HTML/CSS/browser behavior | WP-01 | required | replace |
| `CAP-I18N` | Render UI copy through language packs without translating user data | static/js/i18n.js; language_packs; UNBUILT §1.48 | WP-02 | required | replace |
| `CAP-EXT-V1` | Run supported extension v1 UI and lifecycle | static/js/ui-next/extensions-v1.js; /api/extensions | WP-12 | required | preserve |
| `CAP-EXT-V2` | Register versioned routes, slots, tasks, permissions, and teardown | static/js/ui-next/extensions.js; static/js/ui-next/extension-host.js; browser_tests/test_ui_wp12.py | WP-12 | required | rebuild |
| `CAP-LIVING-WORLD` | Configure built living-world floors without overstating ceilings | static/js/ui-next/settings-view.js; LIVING_WORLD_BUILT; UNBUILT §6.8 | WP-08 | required | replace |
| `CAP-ENGINE-NOTES` | Inspect per-turn engine notes and warnings | pipeline drawer; UNBUILT §1.11 | WP-04 | required | adapt |
| `CAP-TASKS` | Show persistent async tasks, progress, cancellation, and recovery | static/js/ui-next/tasks.js and route-specific surfaces | WP-02 | required | rebuild |
| `CAP-NOTICES` | Show contextual errors and persistent extension notices | static/js/ui-next/notices.js; static/js/ui-next/extensions.js | WP-02 | required | rebuild |
| `CAP-ARCHIVE` | Archive, restore, branch, and checkpoint without semantic drift | server routes and persistence | WP-07 | required | preserve |
| `CAP-IMPORT-EXPORT` | Round-trip all supported authored records | route-specific import/export | WP-07 | required | preserve |
| `CAP-DEFAULT-CUTOVER` | Replace the root entry and delete classic host code | static/ui-next.html and web/app.py root route | WP-13 | required | remove-at-cutover |
| `CAP-RESPONSIVE` | Keep all capabilities through desktop, tablet, phone, landscape, and zoom | static/css/ui/; browser tests | WP-14 | required | rebuild |
