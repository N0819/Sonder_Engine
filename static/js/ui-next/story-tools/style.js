export const MODULE_RELEASE = "alpha98-ui15-5b0f039aae29";

import { element, errorState, fieldLabel, frameQuery, replaceLocalized, stateMessage, toolScope } from "./shared.js?release=alpha98-ui15-5b0f039aae29";
import { mountDocumentEditor } from "./document-editor.js?release=alpha98-ui15-5b0f039aae29";

// UI_CATALOG_START: Style tool copy and field labels.
const COPY = Object.freeze({
  loading: "Loading story style…",
  genre: "Genre",
  tone: "Tone",
  weather: "Weather severity",
  director: "Director notes",
  mapping: "Mapping notes",
  avoid: "Avoid",
  language: "Story language",
  authority: "Player authority",
  survival: "Track bodily condition",
  showNpcs: "Show cast condition beside the story",
});
// UI_CATALOG_END

function clone(value) {
  return globalThis.structuredClone ? structuredClone(value) : JSON.parse(JSON.stringify(value));
}

export function mountStyleTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "style");
  let child = null;
  const load = async () => {
    const { chatId, frameId, owner } = scope.current();
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const [guide, language, survival, authority] = await Promise.all([
        scope.run("GET", "guide", `/api/chats/${chatId}/style_guide`),
        scope.run("GET", "language", `/api/chats/${chatId}/language`),
        scope.run("GET", "survival", `/api/chats/${chatId}/survival`),
        scope.run("GET", "authority", `/api/chats/${chatId}/player_authority`),
      ]);
      if (!scope.isLive() || !guide || !language || !survival || !authority) return;
      const documentValue = {
        style_guide: guide.style_guide || {},
        language: { ...language, selected: language.stored || language.language || "en" },
        survival,
        player_authority: authority,
      };
      child = mountDocumentEditor({
        services, target, document: documentRef, toolId: "style", owner,
        serverValue: documentValue,
        summary(value, update) {
          const form = element(documentRef, "section", "ui-tool-form ui-tool-card");
          const set = (section, key, next) => {
            update(current => {
              const draft = clone(current);
              draft[section] ||= {};
              draft[section][key] = next;
              return draft;
            });
          };
          const input = (label, key, multiline = false) => {
            const control = documentRef.createElement(multiline ? "textarea" : "input");
            control.value = value.style_guide?.[key] || "";
            if (multiline) control.rows = 3;
            control.addEventListener("input", () => set("style_guide", key, control.value));
            return fieldLabel(documentRef, label, control);
          };
          const weather = documentRef.createElement("select");
          for (const choice of ["calm", "seasonal", "harsh", "catastrophic"]) {
            const option = element(documentRef, "option", "", choice);
            option.value = choice;
            option.selected = choice === (value.style_guide?.weather_severity || "seasonal");
            weather.append(option);
          }
          weather.addEventListener("change", () => set("style_guide", "weather_severity", weather.value));
          const language = documentRef.createElement("select");
          const packs = services.store.getSnapshot().settings?.data?.language_packs || [];
          const stored = value.language?.selected || value.language?.stored || value.language?.language || "en";
          const choices = packs.filter(pack => pack.story);
          if (!choices.some(pack => pack.id === stored)) choices.unshift({ id: stored, name: `${stored} (pack not installed)` });
          for (const pack of choices) {
            const option = element(documentRef, "option", "", pack.native_name || pack.name || pack.id);
            option.value = pack.id;
            option.selected = pack.id === stored;
            language.append(option);
          }
          language.addEventListener("change", () => set("language", "selected", language.value));
          const authority = documentRef.createElement("select");
          for (const mode of value.player_authority?.modes || []) {
            const option = element(documentRef, "option", "", mode.label || String(mode.value || "").replaceAll("_", " "));
            option.value = mode.value;
            option.selected = mode.value === value.player_authority?.mode;
            authority.append(option);
          }
          authority.addEventListener("change", () => set("player_authority", "mode", authority.value));
          const check = (label, key) => {
            const control = documentRef.createElement("input");
            control.type = "checkbox";
            control.checked = Boolean(value.survival?.[key]);
            control.addEventListener("change", () => set("survival", key, control.checked));
            return fieldLabel(documentRef, label, control);
          };
          form.append(
            input(COPY.genre, "genre"), input(COPY.tone, "tone"),
            fieldLabel(documentRef, COPY.weather, weather),
            input(COPY.director, "director_notes", true),
            input(COPY.mapping, "mapping_notes", true), input(COPY.avoid, "avoid", true),
            fieldLabel(documentRef, COPY.language, language),
            fieldLabel(documentRef, COPY.authority, authority),
            check(COPY.survival, "enabled"), check(COPY.showNpcs, "show_npcs"),
          );
          return form;
        },
        async onSave(value) {
          const turnIdx = services.store.getSnapshot().story.data?.turns?.at(-1)?.idx ?? null;
          await scope.run("PUT", "guide-save", `/api/chats/${chatId}/style_guide`, { style_guide: value.style_guide || {} });
          await scope.run("PUT", "survival-save", `/api/chats/${chatId}/survival${frameQuery(frameId)}`, value.survival || {});
          await scope.run("PUT", "authority-save", `/api/chats/${chatId}/player_authority`, {
            mode: value.player_authority?.mode,
            turn_idx: turnIdx,
          });
          await scope.run("PUT", "language-save", `/api/chats/${chatId}/language`, {
            language: value.language?.selected || value.language?.stored || value.language?.language,
          });
        },
      });
    } catch (error) {
      if (!scope.isLive() || error?.kind === "stale" || error?.kind === "aborted") return;
      const problem = errorState(error);
      replaceLocalized(services, target, stateMessage(documentRef, problem.state, problem.message, load));
    }
  };
  void load();
  return Object.freeze({ teardown() { child?.teardown(); scope.teardown(); } });
}
