// The module entry named by `capabilities.ui.module`.
//
// The host imports this file, then calls `register` with a facade bound to
// this extension's id. That is why `register` may be async and may await: the
// facade attributes every call to `overlay-demo` regardless of what else is
// loading at the same moment, which the classic script path's ambient
// `_begin`/`_end` pair cannot do across an await.

import { createFrameView } from "./frame-view.js";

export function register(sonder) {
  sonder.registerView(createFrameView(sonder));

  sonder.registerTopBarButton({
    id: "overlay-demo-launch",
    icon: "🛰",
    title: "Story frame",
    onClick: () => sonder.openView("overlay-frame")
  });
}
