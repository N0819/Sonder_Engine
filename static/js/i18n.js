"use strict";

// Standalone localization for the login and guest pages, which intentionally
// do not load the host SPA.
//
// NOT loaded by index.html: that page gets the same behaviour from
// utils.js + app.js, and running both meant a second catalog fetch, a second
// permanent observer, and a race over which one localized a node first.
//
// The RULES are not here and must never be copied back in -- they are
// i18n-core.js, loaded by this page and by the SPA alike. Two hand-kept
// copies drifted twice before B25 (review 2026-09-07) removed the second
// copy; see that file's header for both cases. All this file owns is where
// the catalog comes from on a page with no bootstrap.
(async function loadStandaloneUILanguage() {
  let state;
  try {
    const response = await fetch("/api/ui", { cache: "no-store" });
    if (!response.ok) return;
    state = await response.json();
  } catch (_error) {
    return;
  }
  const messages = state.messages || {};
  document.documentElement.lang = state.language || "en";
  document.documentElement.dir = state.direction || "ltr";

  const rules = i18nCompileTemplates(messages);
  const translate = source => i18nTranslate(messages, rules, source);
  const localize = root => i18nLocalize(root, translate);

  localize(document.body);
  i18nObserve(localize, translate);
})();
