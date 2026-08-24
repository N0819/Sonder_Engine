export const MODULE_RELEASE = "alpha98-ui8-eb87a8415bda";

import { mountCastTool } from "./story-tools/cast.js?release=alpha98-ui8-eb87a8415bda";
import { mountConditionsTool } from "./story-tools/conditions.js?release=alpha98-ui8-eb87a8415bda";
import { mountFramesTool } from "./story-tools/frames.js?release=alpha98-ui8-eb87a8415bda";
import { mountMultiplayerTool } from "./story-tools/multiplayer.js?release=alpha98-ui8-eb87a8415bda";
import { mountWorldTool } from "./story-tools/world.js?release=alpha98-ui8-eb87a8415bda";
import { mountStyleTool } from "./story-tools/style.js?release=alpha98-ui8-eb87a8415bda";
import { mountDialogueTool } from "./story-tools/dialogue.js?release=alpha98-ui8-eb87a8415bda";
import { mountAttireTool } from "./story-tools/attire.js?release=alpha98-ui8-eb87a8415bda";
import { mountBackdropsTool } from "./story-tools/backdrops.js?release=alpha98-ui8-eb87a8415bda";
import { mountAmbienceTool } from "./story-tools/ambience.js?release=alpha98-ui8-eb87a8415bda";

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
