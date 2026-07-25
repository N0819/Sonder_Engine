"""Render run_log.jsonl into a readable transcript."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in
        open(os.path.join(HERE, "run_log.jsonl"), encoding="utf-8") if l.strip()]

out = ["# Tavern — scene-manager test transcript", "",
       "Model: `zai-org/glm-latest` for every role. Two full party characters "
       "(Bran Holt, Ysolde Marr); the entire tavern populace invented on the "
       "fly by the Director. `background_config.scene_life = \"full\"`.", ""]

for r in rows:
    out.append("## Turn %s  _(%ss)_" % (r["idx"], r.get("dur")))
    out.append("")
    if r.get("error"):
        out.append("**ERROR:** `%s`" % r["error"])
        out.append("")
    if r.get("input"):
        out.append("> **Player:** %s" % r["input"])
        out.append("")
    out.append(r.get("prose", ""))
    out.append("")
    sel = r.get("selected") or []
    acts = r.get("reactions") or []
    out.append("**Scene manager** — managed %d: %s" %
               (len(sel), ", ".join(sel) if sel else "_none_"))
    out.append("")
    if acts:
        for a in acts:
            bits = []
            if a.get("quote"):
                bits.append('"%s"' % a["quote"]
                            + (" → %s" % a["target"] if a.get("target") else ""))
            if a.get("action"):
                bits.append("_%s_" % a["action"])
            out.append("- **%s** — %s" % (a["name"], "  ".join(bits)))
    else:
        out.append("- _(no one acted)_")
    out.append("")

out.append("## Final presence profiles")
out.append("")
last = rows[-1].get("presences") or {} if rows else {}
for name, rec in last.items():
    b = rec.get("blurb") or {}
    out.append("### %s" % name)
    if b:
        for k in ("look", "manner", "trait", "tell"):
            if b.get(k):
                out.append("- **%s:** %s" % (k, b[k]))
    else:
        out.append("- _(no blurb)_")
    tail = rec.get("recent") or []
    if tail:
        out.append("")
        out.append("Recent conduct:")
        for t in tail:
            out.append("- t%s — %s" % (t.get("turn"), t.get("text")))
    out.append("")

path = os.path.join(HERE, "transcript.md")
open(path, "w", encoding="utf-8").write("\n".join(out))
print("wrote", path, "-", len(rows), "turns")
