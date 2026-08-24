export const MODULE_RELEASE = "alpha98-ui14-8c5f0c3f2d06";

function localImageSource(value) {
  const source = String(value || "");
  return source.startsWith("/static/") || source.startsWith("/api/") ? source : "";
}

export function createMediaThumb(documentRef, item = {}) {
  const media = documentRef.createElement("span");
  media.className = "ui-media-row__media";
  media.setAttribute("aria-hidden", "true");
  const source = localImageSource(item.image_url || item.image || item.thumbnail);
  if (source) {
    const image = documentRef.createElement("img");
    image.src = source;
    image.alt = "";
    image.loading = "lazy";
    media.append(image);
  } else {
    const fallback = documentRef.createElement("span");
    fallback.className = "ui-media-row__fallback";
    fallback.dataset.mediaFallback = "true";
    fallback.textContent = String(item.name || item.kind || "?").trim().slice(0, 1).toLocaleUpperCase() || "?";
    media.append(fallback);
  }
  return media;
}
