export const MODULE_RELEASE = "alpha98-ui13-a39372e1d8d1";

export const LAYOUT_STATES = Object.freeze(["compact", "medium", "wide", "expansive"]);

export const LAYOUT_CONTRACT = Object.freeze({
  compactMaxWidth: 719,
  shortLandscapeMaxHeight: 430,
  shortLandscapeMaxWidth: 899,
  mediumMaxWidth: 1099,
  wideMaxWidth: 1439,
  minimumWorkspaceWidth: 680,
  pinnedContextAllowance: 64,
});

function finiteSize(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : 0;
}

export function layoutStateFor(width, height) {
  const safeWidth = finiteSize(width);
  const safeHeight = finiteSize(height);
  if (safeWidth <= LAYOUT_CONTRACT.compactMaxWidth
      || (safeHeight <= LAYOUT_CONTRACT.shortLandscapeMaxHeight
        && safeWidth <= LAYOUT_CONTRACT.shortLandscapeMaxWidth)) {
    return "compact";
  }
  if (safeWidth <= LAYOUT_CONTRACT.mediumMaxWidth) return "medium";
  if (safeWidth <= LAYOUT_CONTRACT.wideMaxWidth) return "wide";
  return "expansive";
}

export function canPinContext(options = {}) {
  const viewportWidth = finiteSize(options.viewportWidth);
  if (layoutStateFor(viewportWidth, finiteSize(options.viewportHeight) || 900) !== "expansive") {
    return false;
  }
  const remaining = viewportWidth
    - finiteSize(options.railWidth)
    - finiteSize(options.drawerWidth)
    - finiteSize(options.allowance ?? LAYOUT_CONTRACT.pinnedContextAllowance);
  return remaining >= finiteSize(
    options.minimumWorkspaceWidth ?? LAYOUT_CONTRACT.minimumWorkspaceWidth,
  );
}

export function contextMode(options = {}) {
  if (!options.requestedOpen) return "closed";
  if (options.requestedPinned && canPinContext(options)) return "pinned";
  return "overlay";
}
