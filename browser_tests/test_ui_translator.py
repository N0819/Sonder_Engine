"""The UI translator on what it is actually handed (issue #23).

`el()` hands every string child to `t()` before the node exists, and the
mutation observer hands it every text node the page adds, so the translator
sees whatever the page holds -- not only interface labels. Issue #23 was two
defects meeting in the pipeline drawer's step editor, whose ✎ builds a
textarea around a step's stored JSON:

* The VALUE was translated. The walk in i18n-core.js has always skipped a
  textarea's text (`I18N_SKIP_TEXT`), but `el()` ran first, so the skip held
  only where a caller wrapped the value in `txt()` -- and 20 textareas did
  not. Under a translated catalog a value that was a catalog key opened
  translated, and saving wrote the translation back.
* The template rules were regexes, /^L0(.+?)L1…(.+?)Lk$/, whose lazy groups
  backtrack. A line that keeps offering a rule's literals before failing
  costs the cube of its length, and Firefox abandoned about 30,000 characters
  of one-line step JSON with "too much recursion".

Chromium survives the depth Firefox does not, so the cost test below uses the
cubic shape rather than the recursion error itself. The error was reproduced
in Firefox on 2026-10-06 and is gone there with this change.
"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import Page


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "js"
PACKS = sorted((ROOT / "language_packs").glob("*/ui.json"))


def _harness(page: Page, catalog: dict) -> None:
    """`t()` and `el()` as the SPA loads them: the rules first, as their own
    tag (`"use strict"` is a whole-script directive), then the slice of
    utils.js holding `S` and `t`, then components.js's `txt` and `el`."""
    core = (JS / "i18n-core.js").read_text(encoding="utf-8")
    utils = (JS / "utils.js").read_text(encoding="utf-8")
    utils = utils[utils.index("const S = {"):utils.index("function watchUILanguage(")]
    components = (JS / "components.js").read_text(encoding="utf-8")
    components = components[components.index("function txt("):
                            components.index("// ---- Modal ----")]
    page.set_content("<!doctype html><body></body>")
    page.add_script_tag(content=core)
    page.add_script_tag(content=utils + "\n" + components)
    page.evaluate("(c) => { S.uiCatalog = c; S.uiTemplateRules = null; }", catalog)


def test_a_value_is_never_translated_on_its_way_into_an_editor(page: Page) -> None:
    _harness(page, {"Close": "閉じる", "${n} of ${m} done": "${n}／${m}件完了"})
    got = page.evaluate("""() => ({
        value: el("textarea", {}, "Close").value,
        templated: el("textarea", {}, "3 of 5 done").value,
        placeholder: el("textarea", {placeholder: "Close"}).placeholder,
        optedOut: el("div", {translate: "no"}, "Close").textContent,
        label: el("button", {}, "Close").textContent,
        counter: el("span", {}, "3 of 5 done").textContent,
    })""")
    assert got == {
        # What an editor saves is what it was given.
        "value": "Close",
        "templated": "3 of 5 done",
        # An editor's chrome is still chrome.
        "placeholder": "閉じる",
        # The walk's opt-out now holds in el() too.
        "optedOut": "Close",
        "label": "閉じる",
        "counter": "3／5件完了",
    }


def test_a_long_line_costs_one_pass(page: Page) -> None:
    """The shape that makes the regex cubic: one line offering every literal
    of a three-placeholder rule thousands of times, then failing. Measured in
    V8 on 2026-10-06, the old rule took 13 ms on 2,000 characters and 102 ms on
    4,000, so these 30,000 cost it tens of seconds."""
    _harness(page, {"${a} of ${b} in ${c}": "${a}/${b}/${c}"})
    got = page.evaluate("""() => {
        const line = "x of y in ".repeat(3000);
        const started = performance.now();
        const failing = t(line + "\\nz");
        const matching = t(line + "q");
        return {
            ms: performance.now() - started,
            failing: failing === line + "\\nz",
            matching: matching.startsWith("x/y/x of y in ") && matching.endsWith("in q"),
        };
    }""")
    assert got["failing"] and got["matching"], got
    assert got["ms"] < 1000, got


# The rules this replaced, verbatim from i18n-core.js before issue #23 and
# renamed, kept as the specification the one-pass match must reproduce: which
# rule answers first, and what each of its placeholders captured.
REGEX_RULES = r"""
function regexCompileTemplates(messages) {
  return Object.entries(messages || {})
    .filter(([key]) => key.includes("${"))
    .map(([key, value]) => {
      const literals = key.split(/\$\{[^}]+\}/g);
      const parts = literals
        .map(part => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      return {
        regex: new RegExp(`^${parts.join("(.+?)")}$`),
        value,
        weight: literals.join("").trim().length,
      };
    })
    .filter(rule => rule.weight >= I18N_MIN_ANCHOR_CHARS)
    .sort((a, b) => b.weight - a.weight);
}
"""

LS, PS = chr(0x2028), chr(0x2029)

# Shapes no pack holds yet: adjacent placeholders, a literal repeated or
# overlapping itself, a line break inside a literal (the regex fallback), an
# unclosed placeholder, and rules too vague to keep.
SYNTHETIC = {
    "${a}${b} pair": "P${a}|${b}",
    "${a}-${b}-${c} dashes": "D${c}${b}${a}",
    "aa${a}aa${b}aa": "A${a}/${b}",
    "Done.\n${n} files": "完了\n${n}件",
    "${a}\n${b} and more": "${b}+${a}",
    "${a} of ${b} in ${c}": "${a}/${b}/${c}",
    "x${a}": "short",
    "Cost ${": "cost",
    "${a}${b}${c}abc": "T${c}${b}${a}",
    "abc${a}${b}${c}": "U${a}${b}${c}",
    "${a} (${b})": "${a}[${b}]",
    "of ${a} of ${b} of": "O${a}O${b}",
    "Close": "閉じる",
    "Writing the scene": "場面を書いている",
}

# What a placeholder may be filled with: plain words, other keys' literal
# text, every line break a regex's `.` refuses, and nothing at all.
FILLS = ["1", "12", "Hinami", "a b", "3 of 5", "x\ny", "\n", "${n}", " ", "of",
         "Close", "Writing the scene", "(", ")", ".", "…", "日本語", "a" + LS + "b",
         "c" + PS, "\r", "  padded  ", "-", "aa", "abc", ""]

COMPARE = r"""(a) => {
  let seed = 20261006;
  const rng = () => {
    seed = seed + 0x6D2B79F5 | 0;
    let x = Math.imul(seed ^ seed >>> 15, 1 | seed);
    x = x + Math.imul(x ^ x >>> 7, 61 | x) ^ x;
    return ((x ^ x >>> 14) >>> 0) / 4294967296;
  };
  const pick = list => list[Math.floor(rng() * list.length)];
  const catalogs = [...a.packs, a.synthetic, Object.assign({}, a.packs[0], a.synthetic)];
  const corpus = [];
  for (const cat of catalogs) {
    for (const [key, value] of Object.entries(cat)) {
      corpus.push(key, value);
      if (!key.includes("${")) continue;
      const lits = key.split(/\$\{[^}]+\}/g);
      for (const fill of a.fills) corpus.push(lits.join(fill));
      for (let r = 0; r < 8; r++) {
        corpus.push(lits.map((l, i) => (i ? pick(a.fills.concat(lits)) : "") + l).join(""));
      }
      const once = lits.join("x");
      corpus.push(once.slice(1), once.slice(0, -1), once + once, " " + once, once + " ");
    }
  }
  const alphabet = [...new Set(catalogs.flatMap(c => Object.keys(c)
    .filter(k => k.includes("${")).flatMap(k => k.split(/\$\{[^}]+\}/g))))].filter(Boolean);
  for (let r = 0; r < 20000; r++) {
    let s = "";
    const n = 1 + Math.floor(rng() * 7);
    for (let i = 0; i < n; i++) s += rng() < 0.55 ? pick(alphabet) : pick(a.fills);
    corpus.push(s);
  }
  const first = (rules, source, match) => {
    for (let i = 0; i < rules.length; i++) {
      const captures = match(rules[i], source);
      if (captures) return [i, captures];
    }
    return null;
  };
  let checked = 0, matched = 0;
  const mismatches = [];
  for (const cat of catalogs) {
    const regexRules = regexCompileTemplates(cat), rules = i18nCompileTemplates(cat);
    if (JSON.stringify(regexRules.map(r => r.value)) !== JSON.stringify(rules.map(r => r.value))) {
      mismatches.push({order: "the rules are not in the regex rules' order"});
    }
    for (const s of corpus) {
      const want = first(regexRules, s, (rule, source) => {
        const m = source.match(rule.regex);
        return m ? m.slice(1) : null;
      });
      const broken = I18N_LINE_BREAK.test(s);
      const got = first(rules, s, (rule, source) => i18nMatchTemplate(rule, source, broken));
      checked++;
      if (want) matched++;
      if (JSON.stringify(want) !== JSON.stringify(got) && mismatches.length < 10) {
        mismatches.push({s, want, got});
      }
    }
  }
  return {checked, matched, mismatches};
}"""


def test_the_one_pass_match_is_the_regex_it_replaced(page: Page) -> None:
    """Every pack's catalog, the shapes above, and a generated corpus: the
    one-pass match must answer exactly what the regex answered, including
    every refusal."""
    packs = [json.loads(path.read_text(encoding="utf-8")) for path in PACKS]
    _harness(page, {})
    page.add_script_tag(content=REGEX_RULES)
    got = page.evaluate(COMPARE, {"packs": packs, "synthetic": SYNTHETIC, "fills": FILLS})
    assert got["mismatches"] == [], got["mismatches"]
    # The corpus reaches the matching path, not only the refusals.
    assert got["matched"] > 10000, got
