export const MODULE_RELEASE = "alpha98-ui4-842dd802b09f";

import { mountCastTool } from "./story-tools/cast.js?release=alpha98-ui4-842dd802b09f";
import { mountConditionsTool } from "./story-tools/conditions.js?release=alpha98-ui4-842dd802b09f";
import { mountFramesTool } from "./story-tools/frames.js?release=alpha98-ui4-842dd802b09f";
import { mountMultiplayerTool } from "./story-tools/multiplayer.js?release=alpha98-ui4-842dd802b09f";
import { mountWorldTool } from "./story-tools/world.js?release=alpha98-ui4-842dd802b09f";
import { mountStyleTool } from "./story-tools/style.js?release=alpha98-ui4-842dd802b09f";
import { mountDialogueTool } from "./story-tools/dialogue.js?release=alpha98-ui4-842dd802b09f";
import { mountAttireTool } from "./story-tools/attire.js?release=alpha98-ui4-842dd802b09f";
import { mountBackdropsTool } from "./story-tools/backdrops.js?release=alpha98-ui4-842dd802b09f";
import { mountAmbienceTool } from "./story-tools/ambience.js?release=alpha98-ui4-842dd802b09f";

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
