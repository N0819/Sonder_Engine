export const MODULE_RELEASE = "alpha98-ui11-0acc47fb0573";

function node(documentRef, tag, className = "", text = "") {
  const result = documentRef.createElement(tag);
  if (className) result.className = className;
  if (text) result.textContent = text;
  return result;
}

function perceiverViews(content) {
  const views = content && content.views;
  if (!views || typeof views !== "object" || Array.isArray(views)) return null;
  return Object.keys(views).length ? views : null;
}

function loopMindIds(content) {
  const rounds = content && content.rounds;
  if (!Array.isArray(rounds) || !rounds.length) return [];
  const ids = [];
  for (const round of rounds) {
    if (!round || typeof round !== "object") continue;
    const id = round.speaker_id ?? round.reactor_id ?? round.character_id;
    if (id !== null && id !== undefined && !ids.includes(String(id))) ids.push(String(id));
  }
  return ids;
}

function specialistIds(content) {
  const record = content && content.orchestration;
  const table = record && typeof record === "object" && record.specialists;
  if (!table || typeof table !== "object") return [];
  return Object.keys(table).filter(name => table[name] && table[name].run);
}

export function stepLenses(content) {
  if (!content || typeof content !== "object" || Array.isArray(content)) return null;
  const specialists = specialistIds(content);
  if (specialists.length) return { kind: "specialist", label: "Written by", ids: ["prose"].concat(specialists) };
  if (perceiverViews(content)) return { kind: "perceiver", label: "Seen by", ids: Object.keys(content.views) };
  const minds = loopMindIds(content);
  if (minds.length) return { kind: "mind", label: "Decided by", ids: minds };
  const keys = Object.keys(content).filter(key => key !== "_engine_notes");
  return keys.length ? { kind: "key", label: "Show", ids: keys } : null;
}

function perceiverLabel(id, names) {
  const name = names[id];
  if (id === "player") return name ? `${name} (player)` : "player";
  return name ? `${name} (${id})` : `#${id}`;
}

function facetBadge(value) {
  if (value === null || value === undefined || value === "") return "∅";
  if (Array.isArray(value)) return String(value.length);
  if (typeof value === "object") return String(Object.keys(value).length);
  return "";
}

function lensLabel(lenses, id, content, names) {
  if (lenses.kind === "specialist") {
    if (id === "prose") return "prose author";
    const state = content.orchestration?.specialists?.[id];
    if (state?.ran === false) return `${id} ·failed`;
    const filled = state?.channels_filled || [];
    return filled.length ? `${id} ·${filled.length}` : id;
  }
  if (lenses.kind === "key") {
    const badge = facetBadge(content[id]);
    return badge ? `${id} ·${badge}` : id;
  }
  return perceiverLabel(id, names);
}

function specialistSlice(content, id) {
  if (id === "prose") {
    const own = {};
    const delegated = new Set();
    for (const state of Object.values(content.orchestration?.specialists || {})) {
      for (const channel of state?.channels || []) delegated.add(channel);
    }
    for (const [key, value] of Object.entries(content)) {
      if (key === "orchestration" || key === "_engine_notes") continue;
      if (key !== "state_diff") { own[key] = value; continue; }
      own[key] = Object.fromEntries(Object.entries(value || {}).filter(([channel]) => !delegated.has(channel)));
    }
    return `The beat's account, and the state changes no specialist owns.\n\n${JSON.stringify(own, null, 2)}`;
  }
  const state = content.orchestration?.specialists?.[id];
  if (!state) return "(this specialist has no record on this step)";
  const out = [];
  if (state.ran === false) out.push("DID NOT RUN — the beat kept the author's channels (fail-open).", state.error || "", "");
  const scope = state.scope || [];
  out.push(`granted (${scope.length} of ${(state.channels || []).length}): ${scope.join(", ") || "nothing"}`);
  if (state.channels_filled?.length) out.push(`filled: ${state.channels_filled.join(", ")}`);
  const repair = content.reconciliation?.specialist_repairs?.[id];
  if (repair) out.push("", `— asked again to repair ${(repair.scope || []).join(", ")} — ${repair.ok ? "answered" : "FAILED"} —`);
  const diff = content.state_diff || {};
  const empty = value => value === null || value === undefined || (Array.isArray(value) ? !value.length : typeof value === "object" ? !Object.keys(value).length : value === "");
  const written = scope.filter(channel => !empty(diff[channel]));
  const silent = scope.filter(channel => empty(diff[channel]));
  if (written.length) {
    out.push("", "— its channels in the merged diff —", "");
    for (const channel of written) out.push(`${channel}: ${JSON.stringify(diff[channel], null, 2)}`);
  }
  if (silent.length) out.push("", `granted and left empty: ${silent.join(", ")}`);
  const ungranted = (state.channels || []).filter(channel => !scope.includes(channel));
  if (ungranted.length) out.push("", `gated out this beat: ${ungranted.join(", ")}`);
  return out.filter(value => value !== undefined).join("\n");
}

function perceiverSlice(content, id, names) {
  const view = content.views?.[id];
  const out = [perceiverLabel(id, names), "", view === null || view === undefined || view === ""
    ? "(no view — nothing registered, or this mind was not asked)" : String(view)];
  const observations = content.observations?.[id];
  if (Array.isArray(observations) && observations.length) {
    out.push("", `— observations (${observations.length}) —`, "");
    for (const observation of observations) out.push(`[${observation.channel || "?"}] ${observation.observed?.text || ""}${observation.directed_at_self ? "  ← at them" : ""}`);
  }
  return out.join("\n");
}

function mindSlice(content, id, names) {
  const out = [perceiverLabel(id, names), ""];
  const rounds = (content.rounds || []).filter(round => String(round && (round.speaker_id ?? round.reactor_id ?? round.character_id)) === id);
  if (!rounds.length) out.push("(no round — this mind did not act in the loop)");
  for (const round of rounds) out.push(`— round ${round.round} —`, JSON.stringify(round, null, 2), "");
  const results = content.character_results || content.reaction_results || {};
  if (Object.prototype.hasOwnProperty.call(results, id)) out.push("— stored result —", JSON.stringify(results[id], null, 2));
  return out.join("\n");
}

function keySlice(content, key) {
  const value = content[key];
  if (typeof value === "string") return value || "(empty)";
  if (value === null || value === undefined) return "(null)";
  return JSON.stringify(value, null, 2);
}

function lensSlice(lenses, content, id, names) {
  if (lenses.kind === "specialist") return specialistSlice(content, id);
  if (lenses.kind === "perceiver") return perceiverSlice(content, id, names);
  if (lenses.kind === "mind") return mindSlice(content, id, names);
  return keySlice(content, id);
}

function engineNotes(documentRef, content) {
  const box = node(documentRef, "div", "ui-play__engine-notes");
  const notes = content?._engine_notes;
  if (!notes) return box;
  if (notes.parallel_with?.length) box.append(node(documentRef, "p", "ui-muted", `⇉ ran concurrently with ${notes.parallel_with.join(", ")}`));
  for (const call of notes.llm_calls || []) {
    const served = call.served && call.served !== call.requested ? `${call.requested} → ${call.served}` : (call.served || call.requested || "?");
    box.append(node(documentRef, "p", "ui-muted", `⏱ ${call.role || "?"} · ${served} · in ${call.in || 0} · out ${call.out || 0} · ${(Number(call.duration) || 0).toFixed(2)}s`));
  }
  for (const warning of notes.warnings || []) box.append(node(documentRef, "p", "ui-play__engine-warning", `⚠ ${warning}`));
  return box;
}

function parseVariant(variant) {
  try { return JSON.parse(variant?.content); } catch (_) { return null; }
}

export function renderPipelineInspector(documentRef, payload) {
  const root = node(documentRef, "div", "ui-play__pipeline");
  const perceivers = payload?.perceivers || {};
  for (const step of payload?.steps || []) {
    const card = node(documentRef, "section", "ui-play__pipeline-step");
    card.append(node(documentRef, "h3", "", step.label || step.key || "Step"));
    const variants = step.variants || [];
    let index = variants.findIndex(variant => variant.active);
    if (index < 0) index = Math.max(0, variants.length - 1);
    let lens = null;
    const controls = node(documentRef, "div", "ui-play__pipeline-controls");
    const notesHost = node(documentRef, "div");
    const facets = node(documentRef, "div", "ui-play__pipeline-facets");
    const output = node(documentRef, "pre", "ui-play__technical");
    const reasoning = node(documentRef, "details", "ui-play__reasoning");
    const reasoningText = node(documentRef, "pre", "ui-play__technical");
    reasoning.append(node(documentRef, "summary", "", "Expand reasoning"), reasoningText);
    const paint = () => {
      controls.replaceChildren(); notesHost.replaceChildren(); facets.replaceChildren();
      const variant = variants[index];
      if (!variant) { output.textContent = "(no active variant)"; return; }
      reasoningText.textContent = String(variant.reasoning || "").trim();
      reasoning.hidden = !reasoningText.textContent;
      reasoning.open = false;
      const content = parseVariant(variant);
      notesHost.append(engineNotes(documentRef, content));
      const lenses = stepLenses(content);
      if (!lenses) { output.textContent = content === null ? variant.content : JSON.stringify(content, null, 2); return; }
      if (lens === null || (lens !== "" && !lenses.ids.includes(lens))) lens = lenses.kind === "key" ? "" : lenses.ids[0];
      const choices = [["", "{ } JSON"], ...lenses.ids.map(id => [id, lensLabel(lenses, id, content, perceivers)])];
      facets.append(node(documentRef, "span", "ui-muted", lenses.label));
      for (const [id, label] of choices) {
        const control = node(documentRef, "button", `ui-button ui-button--quiet${lens === id ? " is-active" : ""}`, label);
        control.type = "button";
        control.title = id ? label : "The whole step as stored";
        control.addEventListener("click", () => { lens = id; paint(); });
        facets.append(control);
      }
      output.textContent = lens === "" ? JSON.stringify(content, null, 2) : lensSlice(lenses, content, lens, perceivers);
      if (variants.length > 1) {
        const previous = node(documentRef, "button", "ui-button ui-button--quiet", "Previous version");
        const next = node(documentRef, "button", "ui-button ui-button--quiet", "Next version");
        previous.type = next.type = "button";
        previous.addEventListener("click", () => { index = (index - 1 + variants.length) % variants.length; paint(); });
        next.addEventListener("click", () => { index = (index + 1) % variants.length; paint(); });
        controls.append(previous, node(documentRef, "span", "ui-muted", `${index + 1} of ${variants.length}`), next);
      }
    };
    card.append(notesHost, facets, output, reasoning, controls);
    root.append(card);
    paint();
  }
  return root;
}
