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

      root.append(el("div", {
        class: `${CLS}-card`,
        style: "background:var(--card-bg);border:1px solid var(--card-border);"
          + "border-radius:var(--control-radius,8px);padding:12px;margin:8px"
      },
        el("div", {
          class: `${CLS}-head`,
          style: "display:flex;align-items:baseline;gap:8px;margin-bottom:8px"
        },
          el("b", {}, "Scene cohesion"),
          el("span", { style: "flex:1" }),
          el("span", { style: `font-variant-numeric:tabular-nums;color:${tone}` },
            value(score))
        ),
        // A bar rather than a chart: one number, and its distance from full.
        el("div", {
          class: `${CLS}-meter`,
          role: "img",
          "aria-label": "Scene cohesion meter",
          style: "height:8px;border-radius:999px;overflow:hidden;background:var(--bg3)"
        },
          el("div", {
            class: `${CLS}-fill`,
            style: `width:${score}%;height:100%;background:${tone}`
          })
        ),
        el("div", {
          class: `${CLS}-note`,
          style: "color:var(--muted);font-size:12px;margin-top:8px"
        }, "How well the last beat held together with the one before it.")
      ));
    }
  });

  // The pipeline drawer renders every step as raw JSON unless somebody claims
  // it. This extension added the step, so it knows what a pulse looks like.
  Sonder.registerStepRenderer(`ext:${EXT}:pulse`, (content, root) => {
    const data = content && typeof content === "object" ? content : {};
    const delta = Number(data.delta || 0);
    const sign = delta > 0 ? "+" : "";
    const evidence = Array.isArray(data.evidence)
      ? data.evidence
      : (data.evidence ? [data.evidence] : []);

    const box = el("div", { class: `${CLS}-pulse`, style: "line-height:1.5" },
      el("div", {},
        "Cohesion ",
        value(`${sign}${delta}`),
        typeof data.cohesion === "number" ? txt(" → ") : null,
        typeof data.cohesion === "number" ? value(data.cohesion) : null
      )
    );

    if (evidence.length) {
      const list = el("ul", {
        class: `${CLS}-evidence`,
        translate: "no",
        style: "margin:6px 0 0 16px;padding:0"
      });
      // Evidence is quoted from the beat, so it is story text: `txt()` only.
      for (const line of evidence) list.append(el("li", {}, txt(String(line))));
      box.append(el("div", { style: "color:var(--muted);margin-top:6px" }, "Evidence"), list);
    }

    root.append(box);
  });

  // A turn just landed, so whatever the panel is showing is one beat stale.
  Sonder.on("turn:done", () => Sonder.refresh());
})();
