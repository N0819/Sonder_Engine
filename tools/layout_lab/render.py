"""Write the layout lab's browse page from its JSON results.

    LAYOUT_LAB_OUT=<results dir> python tools/layout_lab/render.py <page.html>
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

OUT = Path(os.environ.get("LAYOUT_LAB_OUT", "/tmp/layout_lab"))
TEMPLATE = Path(__file__).with_name("page.html")


def main(dest):
    data = []
    for name in ("shrine", "inn", "lighthouse"):
        path = OUT / f"{name}.json"
        if path.exists():
            data.append(json.loads(path.read_text()))
    html = TEMPLATE.read_text().replace(
        "__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    Path(dest).write_text(html)
    print("wrote", dest, len(html), "bytes")


if __name__ == "__main__":
    main(sys.argv[1])
