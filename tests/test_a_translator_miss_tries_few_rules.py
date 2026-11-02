"""A string that is not a catalog key costs the translator a handful of rules, not all of them.

Every text node and chrome attribute the page adds reaches `i18nTranslate`
(i18n-core.js), and most of them -- names, prose, numbers -- are misses. A miss
tried every one of the 446 template rules: measured 0.11 ms a miss, in English
as much as in Japanese, which the memory browser pays about 45 times a card
for up to 1,000 cards -- seconds of main thread per render in ja (frontend
audit 2026-11-01, frontend_core E1). A rule can match only a string that
begins with its first literal and ends with its last, so the candidates are
looked up by those and tried in the rules' own order.

The other half: el() translates a string and the mutation observer then hands
the RESULT back in. A catalog value that is not also a key is already a
translation, and matching it against the English templates again garbled one
ja value outright ("set_vistas には名前と方角（n, ne, …）" came back as
"s, ne, e, nw）を持つ…" twice over). Such a value is returned as it is.

The specification is the full linear scan, copied below from i18n-core.js as
it stood before the index; the indexed lookup must answer exactly what it
answers, on every pack and a corpus.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "static" / "js" / "i18n-core.js"
PACKS = sorted((ROOT / "language_packs").glob("*/ui.json"))

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

_HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const [, , core, packsJson] = process.argv;
const ctx = vm.createContext({ Node: { ELEMENT_NODE: 1, TEXT_NODE: 3 }, console });
vm.runInContext(fs.readFileSync(core, "utf8"), ctx, { filename: "i18n-core.js" });
const LINE_BREAK = vm.runInContext("I18N_LINE_BREAK", ctx);   // a const: not on the global
// The full scan, as the specification of `i18nLookup`: the exact key, then
// every rule in its order. (The value rule and the whitespace retry sit
// above the lookup in `i18nTranslate` and are pinned on their own: the vista
// below, and tests/test_a_line_broken_message_is_still_translated.py.)
function scan(catalog, rules, source) {
  if (catalog[source] !== undefined) return { text: catalog[source], same: catalog[source] === source };
  const broken = LINE_BREAK.test(source);
  for (const rule of rules || []) {
    const match = ctx.i18nMatchTemplate(rule, source, broken);
    if (!match) continue;
    const named = new Map(rule.names.map((name, i) => [name, match[i]]));
    let index = 0;
    const text = rule.value.replace(/\$\{([^}]+)\}/g, (_, name) => {
      const captured = (named.has(name) ? named.get(name) : match[index]) || "";
      index++;
      const inner = catalog[captured.trim()];
      return inner === undefined ? captured : inner;
    });
    return { text, same: rule.value === rule.key };
  }
  return null;
}
let attempts = 0;
const realMatch = ctx.i18nMatchTemplate;
const result = {};
for (const path of JSON.parse(packsJson)) {
  const lang = path.split("/").slice(-2)[0];
  const catalog = JSON.parse(fs.readFileSync(path, "utf8"));
  const rules = ctx.i18nCompileTemplates(catalog);
  // A corpus of what the page really hands it: keys, values, every template
  // filled with ordinary words, names, prose, numbers and fragments.
  const corpus = [];
  const fills = ["Hinami", "3", "the harbour", "Close", "Mirelle Sulmirath", "12 of 40", ""];
  for (const [key, value] of Object.entries(catalog)) {
    corpus.push(key, value);
    if (!key.includes("${")) continue;
    const literals = key.split(/\$\{[^}]+\}/g);
    for (const fill of fills) corpus.push(literals.join(fill));
  }
  const misses = ["Hinami", "Mirelle Sulmirath", "The Doctor", "Tavern", "42", "turn 12",
    "She remembers the harbour lantern swinging in the rain, and the smell of tar.",
    "灯台の下で彼女は待っていた。", "Room ambience: off", "x of y in z", "e12", "kitchen"];
  corpus.push(...misses);
  let mismatches = [];
  for (const source of corpus) {
    const want = JSON.stringify(scan(catalog, rules, source));
    const got = JSON.stringify(ctx.i18nLookup(catalog, rules, source));
    if (got !== want && mismatches.length < 5) mismatches.push({ source, want, got });
  }
  // Cost: rule matches attempted per miss.
  ctx.i18nMatchTemplate = (...args) => { attempts++; return realMatch(...args); };
  attempts = 0;
  for (const source of misses) ctx.i18nTranslate(catalog, rules, source);
  const perMiss = attempts / misses.length;
  ctx.i18nMatchTemplate = realMatch;
  const vista = Object.values(catalog).find(v => v.startsWith("set_vistas には"));
  result[lang] = { checked: corpus.length, rules: rules.length, mismatches, perMiss,
                   vista: vista ? ctx.i18nTranslate(catalog, rules, vista) === vista : null };
}
process.stdout.write(JSON.stringify(result));
"""


@pytest.fixture(scope="module")
def measured() -> dict:
    with tempfile.TemporaryDirectory(prefix="i18n-index-") as tmp:
        harness = Path(tmp) / "harness.js"
        harness.write_text(_HARNESS, encoding="utf-8")
        run = subprocess.run(["node", str(harness), str(CORE),
                              json.dumps([str(path) for path in PACKS])],
                             capture_output=True, text=True, check=True, timeout=120)
    return json.loads(run.stdout)


def test_the_indexed_translator_answers_what_the_full_scan_answers(measured):
    for lang, got in measured.items():
        assert got["checked"] > 2000, (lang, got["checked"])
        assert got["mismatches"] == [], (lang, got["mismatches"])


def test_a_miss_tries_a_handful_of_rules(measured):
    for lang, got in measured.items():
        assert got["rules"] > 400, lang                  # what the scan used to try
        assert got["perMiss"] <= 20, (lang, got["perMiss"])


def test_a_translation_is_not_translated_again(measured):
    assert measured["ja"]["vista"] is True
