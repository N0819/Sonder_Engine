export const MODULE_RELEASE = "alpha98-ui5-98f796584158";

import { mountCastTool } from "./story-tools/cast.js?release=alpha98-ui5-98f796584158";
import { mountConditionsTool } from "./story-tools/conditions.js?release=alpha98-ui5-98f796584158";
import { mountFramesTool } from "./story-tools/frames.js?release=alpha98-ui5-98f796584158";
import { mountMultiplayerTool } from "./story-tools/multiplayer.js?release=alpha98-ui5-98f796584158";
import { mountWorldTool } from "./story-tools/world.js?release=alpha98-ui5-98f796584158";
import { mountStyleTool } from "./story-tools/style.js?release=alpha98-ui5-98f796584158";
import { mountDialogueTool } from "./story-tools/dialogue.js?release=alpha98-ui5-98f796584158";
import { mountAttireTool } from "./story-tools/attire.js?release=alpha98-ui5-98f796584158";
import { mountBackdropsTool } from "./story-tools/backdrops.js?release=alpha98-ui5-98f796584158";
import { mountAmbienceTool } from "./story-tools/ambience.js?release=alpha98-ui5-98f796584158";

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
