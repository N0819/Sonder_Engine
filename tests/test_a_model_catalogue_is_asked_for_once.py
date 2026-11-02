"""A provider's model catalogue is asked for once, however many pickers want it.

Opening ⚙ API builds one model combobox per role row, and each one primes its
catalogue (`load(+cp, { open: false })` -> `fetchModels`). `fetchModels`
cached a catalogue only once a request RESOLVED, so every row started its own
request before the first came back -- about 17 identical upstream requests for
336-652-model catalogues, with no server cache behind `list_models` (frontend
audit 2026-11-01, frontend_settings_world E2). The in-flight promise is shared
now; a failure is still answered with an empty list and is not cached, so the
next open asks again.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

COMPONENTS = (Path(__file__).resolve().parents[1] / "static" / "js" / "components.js"
              ).read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

_HARNESS = r"""
const fs = require("fs");
const [, , subject, failFirst] = process.argv;
const S = { models: {}, imageModels: {} };
const asked = [];
let failures = failFirst === "1" ? 1 : 0;
const api = async (method, url) => {
  asked.push(url);
  await new Promise(resolve => setTimeout(resolve, 20));
  if (failures > 0) { failures -= 1; throw new Error("HTTP 502"); }
  return { models: [url.endsWith("image_models") ? "img-1" : "chat-1"] };
};
eval(fs.readFileSync(subject, "utf8"));
(async () => {
  const first = await Promise.all(Array.from({ length: 17 }, () => fetchModels(4)));
  const images = await Promise.all([fetchImageModels(4), fetchImageModels(4)]);
  const again = await fetchModels(4);
  process.stdout.write(JSON.stringify({ asked, first, images, again }));
})();
"""


def _run(fail_first: bool) -> dict:
    start = COMPONENTS.index("// ---- Model picker ----")
    block = COMPONENTS[start:COMPONENTS.index("function modelCombobox(", start)]
    with tempfile.TemporaryDirectory(prefix="models-") as tmp:
        harness, subject = Path(tmp) / "harness.js", Path(tmp) / "subject.js"
        harness.write_text(_HARNESS, encoding="utf-8")
        subject.write_text(block, encoding="utf-8")
        run = subprocess.run(["node", str(harness), str(subject), "1" if fail_first else "0"],
                             capture_output=True, text=True, check=True, timeout=60)
    return json.loads(run.stdout)


def test_seventeen_pickers_share_one_request():
    got = _run(fail_first=False)
    assert got["asked"] == ["/api/providers/4/models", "/api/providers/4/image_models"]
    assert got["first"] == [["chat-1"]] * 17
    assert got["images"] == [["img-1"], ["img-1"]]
    assert got["again"] == ["chat-1"]          # answered from the cache


def test_a_failed_catalogue_is_not_remembered():
    got = _run(fail_first=True)
    assert got["first"] == [[]] * 17           # one failure, shared, answered empty
    assert got["asked"].count("/api/providers/4/models") == 2
    assert got["again"] == ["chat-1"]          # asked again, and this time it came
