export const MODULE_RELEASE = "wp05.1";

import { mountCastTool } from "./story-tools/cast.js?release=wp05.1";
import { mountConditionsTool } from "./story-tools/conditions.js?release=wp05.1";
import { mountFramesTool } from "./story-tools/frames.js?release=wp05.1";
import { mountMultiplayerTool } from "./story-tools/multiplayer.js?release=wp05.1";

const MOUNTS = Object.freeze({
  cast: mountCastTool,
  conditions: mountConditionsTool,
  frames: mountFramesTool,
  multiplayer: mountMultiplayerTool,
});

export function mountStoryTool(toolId, options) {
  return MOUNTS[toolId]?.(options) || null;
}
