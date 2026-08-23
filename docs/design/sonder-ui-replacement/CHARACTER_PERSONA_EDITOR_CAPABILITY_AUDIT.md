# Character and Persona Editor Capability Audit

**Audit date:** 2026-08-23  
**Scope:** Reusable Characters, reusable Personas, and story-specific Character
cards  
**Authority:** Current schemas, routes, persistence contracts, maintained UI
guidance, and browser-visible behavior

This audit records what the shared authoring workspace must retain. A legacy
surface may identify a missing capability, but does not define the accepted
composition.

| Capability | Character | Persona | Story card | Current authority | Required workspace result |
|---|---|---|---|---|---|
| Lossless complete document | Supported | Supported | Supported | `/api/library/authoring/{kind}/{id}` and story-card route | Every known and unknown field remains editable through sections, Additional fields, or Advanced and round-trips unchanged. |
| Stable identity | Supported | Supported | Inherited/read-only | `identity.uid` normalization | Show read-only; never regenerate during edit. |
| Name, aliases, pronouns | Supported | Supported | Name inherited; remaining card fields supported | Person editor and schemas | Provide plain controls in Basics and preserve normalization. |
| Appearance and embodiment | Supported | Supported | Supported | Character/Persona schemas; appearance preview routes | Provide a dedicated Appearance section, including structured outfit, senses, extra parts, scent, and abilities. |
| Public/private history | Supported | Supported | Supported | `knowledge` document fields | Provide a History section; preserve structured private history. |
| Psychology and drives | Supported | Not applicable | Supported | Character schema and psychology preview | Provide Character Inner life; keep preview reversible until Save. |
| Voice and social behavior | Supported | Persona narration only | Supported | Character `social.voice`; Persona `narration` | Expose in Inner life or Story presence without flattening fields. |
| Initial mood/stress/hedonics | Supported | Not applicable | Supported | Character `initial_state` | Expose in Inner life; story-card save must not overwrite live runtime state. |
| Simulation controls | Supported | Not applicable | Supported where document contains them | Character `simulation` | Provide a Character Simulation section, including explicit off-screen opt-in. |
| Opening message and greetings | Supported | Not applicable | Supported | `opening`, greeting routes | Provide Opening with first message, stored greetings, generate, recover, retry, and discard preview. |
| Draft recovery | Supported | Supported | Supported | `library-authoring` owner-scoped local envelope | Retain on navigation/reload; distinguish local draft from server save. |
| Revision conflict | Supported | Supported | Story route is accepted-write owned | authoring runtime and API revision tokens | Keep draft on rejection and present actionable conflict state. |
| Advanced/raw access | Supported | Supported | Supported | Complete JSON editor | Keep behind Advanced disclosure/section; invalid JSON applies nothing. |
| Create from blank template | Supported | Supported | Not applicable | `/api/{kind}/new-document`, POST create | Use the same workspace and route family. |
| AI generation from brief | Supported | Supported | Not applicable | generate-preview routes | Apply only to current draft as reversible preview. |
| Appearance fill | Supported | Supported | Supported | fill-appearance routes | Retain current-draft preview and retry behavior. |
| Psychology fill | Supported | Not applicable | Supported | fill-psychology route | Retain current-draft preview and retry behavior. |
| Greeting generation/recovery | Supported | Not applicable | Supported | greeting routes | Retain current-draft preview and retry behavior. |
| Import | Supported | Supported | Not applicable | `/api/characters/import`, `/api/personas/import` | Use the same outer workspace; preserve native import and optional reinterpretation. |
| Export | Supported | Supported | Not separately exported | current export routes | Keep in selected-item actions and make it reachable before and after editing. |
| Duplicate | Supported | Supported | Not applicable | current duplicate routes | Keep in selected-item actions and route to the new selected copy. |
| Story associations | Supported | Supported | Story-owned by definition | Library projection/mutation routes | Keep concise in contextual detail; do not dominate the editor. |
| Story-specific card override | Supported | Not applicable | Supported | `/api/chats/{story}/characters/{id}/card` | Use the shared framework with Story context and preserve live state boundaries. |
| Quick Start | Supported | Participates as selected player | Not applicable | `/api/characters/{id}/start` | Retain Persona, greeting, Lore, already-known, language, and lived-location choices. |
| Lived location | Supported through Quick Start | Participates | Not applicable | shared lived-location adapter | Preserve public resident/private history disclosure and save-before-start order. |
| Validation and focus | Partial | Partial | Partial | required name and JSON checks | Move to the affected section, focus the first invalid control, and retain the full draft. |
| Desktop focused presentation | Missing | Missing | Missing | UI-FU-01 | Replace Library inner workspace during authoring. |
| Compact full-screen presentation | Partial inspector sheet | Partial inspector sheet | Partial inspector sheet | UI-FU-01 | Use one full-screen destination stage with reachable Back and Save. |
| Return-state restoration | Partial | Partial | Partial | Library route/scroll envelope | Prove category, scope, query, sort, visibility, selection, and scroll restoration. |

## Audit conclusion

The server and browser runtime already provide the required persistence and
workflow capabilities. The implementation gap is the shared presentation and
navigation contract, plus browser proof for validation, compact staging, and
return-state restoration. No new server data model is required.

