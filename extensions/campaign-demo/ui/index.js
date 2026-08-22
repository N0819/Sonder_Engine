// The module entry named by `capabilities.ui.module`.
//
// Everything it renders comes from ONE route, and that route answers from
// `api.player_view` rather than `api.story_view`. That is the whole lesson of
// this panel: a campaign's rules read canonical truth, and a campaign's UI
// does not, because a panel fed canonical truth shows the player which room
// the key is in before anyone has told them.

import { createCampaignView } from "./campaign-view.js";

export function register(sonder) {
  sonder.registerDestination(createCampaignView(sonder));
}
