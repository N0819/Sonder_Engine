# 20. Content and Terminology

## Voice

Sonder speaks like a calm, capable assistant. Copy should be concise, direct, and specific.

Use:

- sentence case;
- active voice;
- concrete verbs;
- plain descriptions of consequence;
- short headings;
- helpful error recovery.

Avoid:

- corporate language;
- marketing language inside the application;
- unnecessary technical jargon;
- playful exclamation marks;
- vague confirmation labels;
- anthropomorphizing the engine when it obscures responsibility;
- overly formal or legalistic phrasing in ordinary flows.

## Naming rules

Preserve established Sonder names when they are clear. Rename when a term is confusing, internal, or inconsistent.

Ordinary UI prefers:

- Play;
- Library;
- Settings;
- Story Tools;
- AI Connections;
- Appearance;
- Current Story;
- Background work;
- Technical detail;
- Add-ons;
- Maintenance;
- Advanced.

Advanced may expose internal terms with explanation.

## Action labels

Use verb + object when ambiguity exists:

- Create Story;
- Save Character;
- Remove from Story;
- Test Connection;
- Install Extension;
- Delete Lorebook;
- Export Story.

Use short verbs when context is unambiguous:

- Send;
- Stop;
- Edit;
- Reroll;
- Close;
- Back.

Avoid:

- OK;
- Confirm;
- Submit;
- Proceed;
- Execute;
- Apply Changes when a more specific action exists.

## Descriptions

Help text should answer one of these questions:

- What does this affect?
- When should I use it?
- Is it reversible?
- Does it change existing stories or only future output?
- Does it cost time or model usage?

Do not explain obvious mechanics such as "Click this button to save."

## Errors

An error message should contain:

1. what failed;
2. likely cause when known;
3. what the user can do next;
4. whether their work was preserved.

Example:

> Could not connect to the provider. The server did not accept this key. Your entry is still here; check the key and try again.

Avoid raw HTTP status or stack text in ordinary UI. Technical detail may be expandable.

## Empty states

Use plain orientation and a next step.

Good:

> No characters in this story yet. Add one from your Library or create a new character.

Poor:

> No data found.

## Progress and background work

Use task names:

- Generating character;
- Importing lorebook;
- Rebuilding search index;
- Saving story;
- Checking for updates.

Do not use Working without context when the operation lasts more than a moment.

## Content preferences

Adult-content and safety-related controls should be plain, neutral, and nonjudgmental. Avoid playful toggles or loud badges in the primary Play header.

## Localization

- Do not concatenate translated sentence fragments.
- Allow labels to expand by at least 30 percent.
- Preserve user-authored names and model prose from interface translation.
- Avoid English-only abbreviations in primary navigation.
- Keep index codes separate from translated labels.
- Review mobile layouts with long translated labels.
