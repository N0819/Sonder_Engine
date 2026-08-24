export const MODULE_RELEASE = "alpha98-ui14-8c5f0c3f2d06";

export const STORY_TOOL_IDS = Object.freeze([
  "cast",
  "world",
  "style",
  "dialogue",
  "attire",
  "backdrops",
  "ambience",
  "conditions",
  "frames",
  "multiplayer",
]);

// UI_CATALOG_START: current-story tool names and short orientation copy.
const DEFINITIONS = Object.freeze({
  cast: Object.freeze({ group: "World and cast", label: "Cast", detail: "People in this story and where they are now." }),
  world: Object.freeze({ group: "World and cast", label: "World", detail: "Current places, entities, and established world state." }),
  style: Object.freeze({ group: "Presentation", label: "Style", detail: "How this story is written and interpreted." }),
  dialogue: Object.freeze({ group: "Story setup", label: "Dialogue", detail: "Conversation, background voices, and living-world limits." }),
  attire: Object.freeze({ group: "World and cast", label: "Attire", detail: "The story's current clothing state." }),
  backdrops: Object.freeze({ group: "Presentation", label: "Backdrops", detail: "Scene imagery behind the reading surface." }),
  ambience: Object.freeze({ group: "Presentation", label: "Ambience", detail: "Room sound, volume, pins, and chime." }),
  conditions: Object.freeze({ group: "World and cast", label: "Conditions", detail: "Player and cast condition without covering the story." }),
  frames: Object.freeze({ group: "Story setup", label: "Frames", detail: "Story eras and participant stationing." }),
  multiplayer: Object.freeze({ group: "Story setup", label: "Multiplayer", detail: "Participants and guarded guest invitations." }),
});
// UI_CATALOG_END

export const STORY_TOOLS = Object.freeze(STORY_TOOL_IDS.map((id, index) => Object.freeze({
  id,
  index: index + 1,
  ...DEFINITIONS[id],
})));

export function resolveStoryTool(value) {
  const id = String(value || "").toLowerCase();
  return STORY_TOOLS.find(tool => tool.id === id) || STORY_TOOLS[0];
}

