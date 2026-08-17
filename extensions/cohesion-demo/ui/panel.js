// Cohesion demo -- the reference extension UI.
//
// Written the way a third party would write one: it talks to `Sonder` and to
// the two DOM helpers the host publishes (`el`, `txt`), owns a class prefix of
// its own, and assumes nothing about the host beyond the documented surface.
(() => {
  // The bundle wrapper already guards on `window.Sonder`, but the code inside
  // it does not -- and the whole bundle is one script, so a ReferenceError
  // here would take every extension after it down too.
  if (!window.Sonder) return;

  const EXT = "cohesion-demo";
  const CLS = "ext-cohesion-demo";

  // Story- and model-derived numbers are DATA. `el()` runs plain string
  // children through the UI translator before they reach the DOM, so every
  // value goes in through `txt()` inside a `translate="no"` box -- the same
  // two-part guard the transcript uses.
  const value = (v) => el("span", { class: `${CLS}-value`, translate: "no" }, txt(v));

  Sonder.registerSidebarTab({
    id: "cohesion",
    label: "Cohesion",
    render: async (root) => {
      const { chatId } = Sonder.state();
      if (!chatId) {
        root.append(typeof emptyState === "function"
          ? emptyState("Open a story to see its cohesion.")
          : el("div", { class: "empty-state" }, "Open a story to see its cohesion."));
        return;
      }

      const state = await Sonder.extState(EXT);
      if (!state || typeof state.cohesion !== "number") {
        root.append(typeof emptyState === "function"
          ? emptyState("No reading yet — cohesion is measured after the first turn.")
          : el("div", { class: "empty-state" },
              "No reading yet — cohesion is measured after the first turn."));
        return;
      }

      const score = Math.max(0, Math.min(100, Number(state.cohesion)));
      const tone = score >= 66 ? "var(--ok)" : score >= 33 ? "var(--warn)" : "var(--err)";

      // Layout and colour live in panel.css; only the two values that depend
      // on the reading -- the bar's width and its tone -- are set inline,
      // because they are data.
      root.append(el("div", { class: `${CLS}-card` },
        el("div", { class: `${CLS}-head` },
          el("b", {}, "Scene cohesion"),
          el("span", { style: "flex:1" }),
          el("span", { class: `${CLS}-score`, style: `color:${tone}` }, value(score))
        ),
        // A bar rather than a chart: one number, and its distance from full.
        el("div", {
          class: `${CLS}-meter`,
          role: "img",
          "aria-label": "Scene cohesion meter"
        },
          el("div", {
            class: `${CLS}-fill`,
            style: `width:${score}%;background:${tone}`
          })
        ),
        el("div", { class: `${CLS}-note` },
          "How well the last beat held together with the one before it.")
      ));
    }
  });

  // The pipeline drawer renders every step as raw JSON unless somebody claims
  // it. This extension added the step, so it knows what a pulse looks like.
  Sonder.registerStepRenderer(`ext:${EXT}:pulse`, (content, root) => {
    const data = content && typeof content === "object" ? content : {};
    // `cohesion_delta` is what the stage actually returns. Reading `delta`
    // here rendered every pulse as +0 -- silently, because the drawer had
    // something to show. A renderer and its stage are two halves of one
    // contract and nothing type-checks across them; name the key exactly.
    const delta = Number(data.cohesion_delta || 0);
    const sign = delta > 0 ? "+" : "";
    const evidence = Array.isArray(data.evidence)
      ? data.evidence
      : (data.evidence ? [data.evidence] : []);

    // The step records the delta and its grounds; the running score lives in
    // story state, not in the step, so it is not shown here.
    const box = el("div", { class: `${CLS}-pulse` },
      el("div", {}, "Cohesion ", value(`${sign}${delta}`)));

    if (evidence.length) {
      const list = el("ul", { class: `${CLS}-evidence`, translate: "no" });
      // Evidence is quoted from the beat, so it is story text: `txt()` only.
      for (const line of evidence) list.append(el("li", {}, txt(String(line))));
      box.append(el("div", { class: `${CLS}-evidence-label` }, "Evidence"), list);
    }

    root.append(box);
  });

  // A turn just landed, so whatever the panel is showing is one beat stale.
  Sonder.on("turn:done", () => Sonder.refresh());
})();
