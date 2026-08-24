export const MODULE_RELEASE = "alpha98-ui15-5b0f039aae29";

import { mountCastTool } from "./story-tools/cast.js?release=alpha98-ui15-5b0f039aae29";
import { mountConditionsTool } from "./story-tools/conditions.js?release=alpha98-ui15-5b0f039aae29";
import { mountFramesTool } from "./story-tools/frames.js?release=alpha98-ui15-5b0f039aae29";
import { mountMultiplayerTool } from "./story-tools/multiplayer.js?release=alpha98-ui15-5b0f039aae29";
import { mountWorldTool } from "./story-tools/world.js?release=alpha98-ui15-5b0f039aae29";
import { mountStyleTool } from "./story-tools/style.js?release=alpha98-ui15-5b0f039aae29";
import { mountDialogueTool } from "./story-tools/dialogue.js?release=alpha98-ui15-5b0f039aae29";
import { mountAttireTool } from "./story-tools/attire.js?release=alpha98-ui15-5b0f039aae29";
import { mountBackdropsTool } from "./story-tools/backdrops.js?release=alpha98-ui15-5b0f039aae29";
import { mountAmbienceTool } from "./story-tools/ambience.js?release=alpha98-ui15-5b0f039aae29";

const MOUNTS = Object.freeze({
  cast: mountCastTool,
  conditions: mountConditionsTool,
  frames: mountFramesTool,
  multiplayer: mountMultiplayerTool,
  world: mountWorldTool,
  style: mountStyleTool,
  dialogue: mountDialogueTool,
  attire: mountAttireTool,
  backdrops: mountBackdropsTool,
  ambience: mountAmbienceTool,
});

export function mountStoryTool(toolId, options) {
  return MOUNTS[toolId]?.(options) || null;
}
