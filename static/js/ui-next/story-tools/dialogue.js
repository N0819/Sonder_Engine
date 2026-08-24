export const MODULE_RELEASE = "alpha98-ui12-7eaf6b3481a3";

import { element, errorState, fieldLabel, replaceLocalized, stateMessage, toolScope } from "./shared.js?release=alpha98-ui12-7eaf6b3481a3";
import { mountDocumentEditor } from "./document-editor.js?release=alpha98-ui12-7eaf6b3481a3";
import { mountCharterSection } from "./charters.js?release=alpha98-ui12-7eaf6b3481a3";

// UI_CATALOG_START: Dialogue tool copy.
const COPY = Object.freeze({
  loading: "Loading dialogue and living-world limits…",
  pacing: "Dialogue pacing",
  autonomy: "NPC autonomy",
  offscreen: "Off-screen life",
  background: "Background life",
  world: "Living-world mechanisms",
});
// UI_CATALOG_END

const BOUNDS = Object.freeze({
  min_lines: [0, null], max_lines: [0, null], variance: [0, 1], autonomy: [0, 100],
  initial_parallel_reactors: [1, 12], promote_after_addressed: [0, 99], max_offscreen_actors: [0, 12],
});

export function validateDialogueDocument(value) {
  const dialogue = value?.dialogue_config || {};
  for (const [key, [minimum, maximum]] of Object.entries(BOUNDS)) {
    const number = Number(dialogue[key]);
    if (!Number.isFinite(number) || number < minimum || (maximum !== null && number > maximum)) {
      return `${key} must be ${minimum}${maximum === null ? " or more" : `–${maximum}`}.`;
    }
  }
  if (Number(dialogue.max_lines) < Number(dialogue.min_lines)) return "max_lines must not be below min_lines.";
  const background = value?.background_config || {};
  if (!Number.isFinite(Number(background.max_managed)) || Number(background.max_managed) < 1 || Number(background.max_managed) > 8) return "max_managed must be 1–8.";
  if (!Number.isFinite(Number(background.max_reactors)) || Number(background.max_reactors) < 1 || Number(background.max_reactors) > 3) return "max_reactors must be 1–3.";
  return "";
}

function clone(value) {
  return globalThis.structuredClone ? structuredClone(value) : JSON.parse(JSON.stringify(value));
}

export function mountDialogueTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "dialogue");
  let child = null;
  const load = async () => {
    const { chatId, owner } = scope.current();
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const results = await Promise.allSettled([
        scope.run("GET", "dialogue", `/api/chats/${chatId}/dialogue_config`),
        scope.run("GET", "background", `/api/chats/${chatId}/background_config`),
        scope.run("GET", "living-world", `/api/chats/${chatId}/living_world`),
        scope.run("GET", "charters", `/api/chats/${chatId}/charters`),
        scope.run("GET", "lorebooks", `/api/chats/${chatId}/lorebooks`),
      ]);
      const [dialogueResult, backgroundResult, livingWorldResult, charterResult, lorebookResult] = results;
      const coreFailure = [dialogueResult, backgroundResult, livingWorldResult]
        .find(result => result.status === "rejected");
      if (coreFailure) throw coreFailure.reason;
      const dialogue = dialogueResult.value;
      const background = backgroundResult.value;
      const livingWorld = livingWorldResult.value;
      if (!scope.isLive() || !dialogue || !background || !livingWorld) return;
      child = mountDocumentEditor({
        services, target, document: documentRef, toolId: "dialogue", owner,
        serverValue: { dialogue_config: dialogue, background_config: background, living_world: livingWorld },
        validate: validateDialogueDocument,
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
          const numeric = (label, section, key, min, max = null, step = "1") => {
            const control = documentRef.createElement("input");
            control.type = "number";
            control.min = String(min);
            if (max !== null) control.max = String(max);
            control.step = step;
            control.value = value[section]?.[key] ?? "";
            control.addEventListener("input", () => {
              const number = Number(control.value);
              const invalid = !Number.isFinite(number) || number < min || (max !== null && number > max);
              control.setCustomValidity(invalid ? `${label} is outside its supported range.` : "");
              set(section, key, number);
            });
            return fieldLabel(documentRef, label, control);
          };
          const choice = (label, section, key, values) => {
            const control = documentRef.createElement("select");
            for (const item of values) {
              const raw = typeof item === "string" ? item : item.value;
              const option = element(documentRef, "option", "", raw);
              option.value = raw;
              option.selected = raw === value[section]?.[key];
              control.append(option);
            }
            control.addEventListener("change", () => set(section, key, control.value));
            return fieldLabel(documentRef, label, control);
          };
          const boolean = (label, section, key) => {
            const control = documentRef.createElement("input");
            control.type = "checkbox";
            control.checked = Boolean(value[section]?.[key]);
            control.addEventListener("change", () => set(section, key, control.checked));
            return fieldLabel(documentRef, label, control);
          };
          form.append(
            element(documentRef, "h4", "ui-heading ui-heading--5", COPY.pacing),
            choice("Style", "dialogue_config", "style", ["terse", "natural", "chatty"]),
            numeric("Minimum lines", "dialogue_config", "min_lines", 0),
            numeric("Maximum lines", "dialogue_config", "max_lines", 0),
            numeric("Variance", "dialogue_config", "variance", 0, 1, "0.1"),
            element(documentRef, "h4", "ui-heading ui-heading--5", COPY.autonomy),
            numeric(COPY.autonomy, "dialogue_config", "autonomy", 0, 100),
            boolean("NPC initiative", "dialogue_config", "allow_npc_initiative"),
            boolean("NPC-to-NPC dialogue", "dialogue_config", "allow_npc_to_npc_dialogue"),
            boolean("Stop on player address", "dialogue_config", "stop_on_player_address"),
            boolean("Stop on question to player", "dialogue_config", "stop_on_question_to_player"),
            boolean("Silence ends exchange", "dialogue_config", "silence_ends_exchange"),
            numeric("Opening reactors", "dialogue_config", "initial_parallel_reactors", 1, 12),
            boolean("Isolate opening reactors", "dialogue_config", "parallel_isolated_reactors"),
            numeric("Turns before promotion", "dialogue_config", "promote_after_addressed", 0, 99),
            numeric("Maximum off-screen actors", "dialogue_config", "max_offscreen_actors", 0, 12),
            choice(COPY.offscreen, "dialogue_config", "offscreen_life", value.dialogue_config?.offscreen_life_levels || []),
            element(documentRef, "h4", "ui-heading ui-heading--5", COPY.background),
            choice("Scene life", "background_config", "scene_life", ["off", "ambient", "full"]),
            numeric("Maximum managed extras", "background_config", "max_managed", 1, 8),
            numeric("Maximum background reactors", "background_config", "max_reactors", 1, 3),
            element(documentRef, "p", "ui-muted", COPY.world),
          );
          return form;
        },
        async onSave(value) {
          const error = validateDialogueDocument(value);
          if (error) throw new Error(error);
          await scope.run("PUT", "dialogue-save", `/api/chats/${chatId}/dialogue_config`, value.dialogue_config || {});
          await scope.run("PUT", "background-save", `/api/chats/${chatId}/background_config`, value.background_config || {});
          await scope.run("PUT", "living-world-save", `/api/chats/${chatId}/living_world`, {
            living_world: value.living_world?.living_world || value.living_world || {},
          });
        },
      });
      target.append(mountCharterSection({
        services, scope, chatId, document: documentRef,
        data: charterResult.status === "fulfilled" ? charterResult.value : {},
        unavailable: charterResult.status === "rejected",
        lorebooks: lorebookResult.status === "fulfilled" ? lorebookResult.value?.lorebooks || [] : [],
        generationUnavailable: lorebookResult.status === "rejected",
      }));
    } catch (error) {
      if (!scope.isLive() || error?.kind === "stale" || error?.kind === "aborted") return;
      const problem = errorState(error);
      replaceLocalized(services, target, stateMessage(documentRef, problem.state, problem.message, load));
    }
  };
  void load();
  return Object.freeze({ teardown() { child?.teardown(); scope.teardown(); } });
}
