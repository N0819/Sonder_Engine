export const MODULE_RELEASE = "wp05.1";

import { mountCastTool } from "./story-tools/cast.js?release=wp05.1";
import { mountConditionsTool } from "./story-tools/conditions.js?release=wp05.1";
import { mountFramesTool } from "./story-tools/frames.js?release=wp05.1";
import { mountMultiplayerTool } from "./story-tools/multiplayer.js?release=wp05.1";
import { mountWorldTool } from "./story-tools/world.js?release=wp05.1";
import { mountStyleTool } from "./story-tools/style.js?release=wp05.1";
import { mountDialogueTool } from "./story-tools/dialogue.js?release=wp05.1";
import { mountAttireTool } from "./story-tools/attire.js?release=wp05.1";
import { mountBackdropsTool } from "./story-tools/backdrops.js?release=wp05.1";
import { mountAmbienceTool } from "./story-tools/ambience.js?release=wp05.1";

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
