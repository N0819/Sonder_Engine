export const MODULE_RELEASE = "alpha98-ui6-57d168ae23cf";

import { mountCastTool } from "./story-tools/cast.js?release=alpha98-ui6-57d168ae23cf";
import { mountConditionsTool } from "./story-tools/conditions.js?release=alpha98-ui6-57d168ae23cf";
import { mountFramesTool } from "./story-tools/frames.js?release=alpha98-ui6-57d168ae23cf";
import { mountMultiplayerTool } from "./story-tools/multiplayer.js?release=alpha98-ui6-57d168ae23cf";
import { mountWorldTool } from "./story-tools/world.js?release=alpha98-ui6-57d168ae23cf";
import { mountStyleTool } from "./story-tools/style.js?release=alpha98-ui6-57d168ae23cf";
import { mountDialogueTool } from "./story-tools/dialogue.js?release=alpha98-ui6-57d168ae23cf";
import { mountAttireTool } from "./story-tools/attire.js?release=alpha98-ui6-57d168ae23cf";
import { mountBackdropsTool } from "./story-tools/backdrops.js?release=alpha98-ui6-57d168ae23cf";
import { mountAmbienceTool } from "./story-tools/ambience.js?release=alpha98-ui6-57d168ae23cf";

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
