export const MODULE_RELEASE = "alpha98-ui6-ff8a9b712a2d";

import { mountCastTool } from "./story-tools/cast.js?release=alpha98-ui6-ff8a9b712a2d";
import { mountConditionsTool } from "./story-tools/conditions.js?release=alpha98-ui6-ff8a9b712a2d";
import { mountFramesTool } from "./story-tools/frames.js?release=alpha98-ui6-ff8a9b712a2d";
import { mountMultiplayerTool } from "./story-tools/multiplayer.js?release=alpha98-ui6-ff8a9b712a2d";
import { mountWorldTool } from "./story-tools/world.js?release=alpha98-ui6-ff8a9b712a2d";
import { mountStyleTool } from "./story-tools/style.js?release=alpha98-ui6-ff8a9b712a2d";
import { mountDialogueTool } from "./story-tools/dialogue.js?release=alpha98-ui6-ff8a9b712a2d";
import { mountAttireTool } from "./story-tools/attire.js?release=alpha98-ui6-ff8a9b712a2d";
import { mountBackdropsTool } from "./story-tools/backdrops.js?release=alpha98-ui6-ff8a9b712a2d";
import { mountAmbienceTool } from "./story-tools/ambience.js?release=alpha98-ui6-ff8a9b712a2d";

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
